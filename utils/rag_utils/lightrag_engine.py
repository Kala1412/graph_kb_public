import asyncio
import json
import os
from typing import Any

from utils.rag_utils.chunk_cleaner import ChunkCleaner
from utils.rag_utils.chunking import split_markdown_to_chunks
from utils.rag_utils.entity_dedup import EntityDeduplicator
from utils.rag_utils.entity_normalizer import EntityNormalizer
from utils.rag_utils.graph_store import GraphStore
from utils.rag_utils.kg_extractor import KGExtractor
from utils.rag_utils.rerank_client import rerank_documents
from utils.rag_utils.vector_store import MilvusVectorStore


WORKING_DIR_BASE = "./saves/lightrag_data"
os.makedirs(WORKING_DIR_BASE, exist_ok=True)


class LightRAGEngine:
    def __init__(self):
        self._initialized = False
        self._initialized_kb_ids: set[int] = set()
        self.vector_store = MilvusVectorStore()
        self.graph_store = GraphStore()
        self.kg_extractor = KGExtractor()
        self.chunk_cleaner = ChunkCleaner()
        self.entity_normalizer = EntityNormalizer()
        self.entity_dedup = EntityDeduplicator()

    async def initialize(self):
        if self._initialized:
            return
        print("⏳ Initializing manual LightRAG engine...")
        try:
            self.vector_store.ensure_collection(1)
            print("✅ Milvus connection verified")
        except Exception as exc:
            print(f"⚠️ Milvus connection check failed: {exc}")
        try:
            self.graph_store.ensure_fulltext_index(1)
            print("✅ Neo4j connection verified")
        except Exception as exc:
            print(f"⚠️ Neo4j connection check failed: {exc}")
        self._initialized = True
        print("✅ Manual LightRAG engine initialized")

    # 首次使用知识库时初始化独立的 Milvus collection 和 Neo4j 全文索引。
    async def _ensure_kb(self, kb_id: int) -> None:
        if kb_id in self._initialized_kb_ids:
            return
        await asyncio.to_thread(self.vector_store.ensure_collection, kb_id)
        await asyncio.to_thread(self.graph_store.ensure_fulltext_index, kb_id)
        self._initialized_kb_ids.add(kb_id)

    async def insert_document(
        self, markdown_text: str, file_id: str, kb_id: int, force_reindex: bool = False
    ):
        await self._ensure_kb(kb_id)
        doc_id = f"kb_{kb_id}_file_{file_id}"

        # 始终先清理同 doc_id 历史索引，保证幂等（重试/重复触发都不会重复入库）
        if force_reindex:
            print(f"🔁 Force reindex enabled, cleanup existing index for {doc_id}")
        await self.delete_document(file_id=file_id, kb_id=kb_id)

        chunks = split_markdown_to_chunks(markdown_text)
        chunks = self.chunk_cleaner.clean(chunks)
        if not chunks:
            return {"status": "success", "file_id": file_id, "kb_id": kb_id, "chunks": 0}

        chunk_rows: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_id = chunk.metadata.get("chunk_id")
            source_chunk_ids = chunk.metadata.get("source_chunk_ids") or [chunk_id]
            metadata = {
                "kb_id": kb_id,
                "file_id": int(file_id),
                "doc_id": doc_id,
                "source": f"file_{file_id}",
                "headers": {k: v for k, v in chunk.metadata.items() if k.startswith("Header")},
                "chunk_id": chunk_id,
                "source_chunk_ids": source_chunk_ids,
            }
            chunk_rows.append(
                {
                    "chunk_id": chunk_id,
                    "file_id": int(file_id),
                    "doc_id": doc_id,
                    "content": chunk.page_content,
                    "metadata": metadata,
                }
            )

        try:
            await asyncio.to_thread(self.vector_store.upsert_chunks, kb_id, chunk_rows)

            # 4.定义并发锁，限制最多同时跑3个任务
            sem = asyncio.Semaphore(3)

            async def process_chunk(row: dict[str, Any]):
                async with sem:
                    raw_entities = await self.kg_extractor.extract_entities(row["content"])
                    normalized_entities = []
                    for entity in raw_entities:
                        normalized = self.entity_normalizer.normalize_entity(
                            entity_name=entity.get("entity_name") or "",
                            entity_type=entity.get("entity_type"),
                            context=row["content"],
                        )
                        normalized_entities.append(
                            {
                                "entity_name": entity.get("entity_name")
                                or normalized["canonical_name"],
                                "canonical_name": normalized["canonical_name"],
                                "entity_type": entity.get("entity_type")
                                or normalized.get("entity_type")
                                or "Other",
                                "description": entity.get("description", ""),
                                "aliases": normalized.get("aliases", []),
                            }
                        )

                    deduped = self.entity_dedup.deduplicate(normalized_entities)
                    if deduped:
                        for entity in deduped:
                            entity["entity_id"] = entity["canonical_name"]
                            entity["entity_name"] = entity["canonical_name"]
                            entity["source_chunk_id"] = row["chunk_id"]
                            entity["file_id"] = int(file_id)
                            entity["doc_id"] = doc_id
                        await asyncio.to_thread(
                            self.graph_store.upsert_entities, kb_id, deduped
                        )

                    # 5.2 抽取关系 -> 将关系的首尾节点替换为“规范化”后的实体名
                    relations = await self.kg_extractor.extract_relations(
                        row["content"], raw_entities
                    )
                    if relations:
                        alias_map = {}
                        type_map = {}
                        for entity in deduped:
                            canonical = entity["canonical_name"]
                            for alias in entity.get("aliases", []):
                                alias_map[alias] = canonical
                            type_map[canonical] = entity.get("entity_type", "Other")
                        for rel in relations:
                            head_raw = rel["head"]
                            tail_raw = rel["tail"]
                            head_norm = alias_map.get(head_raw) or self.entity_normalizer.normalize_entity(head_raw)["canonical_name"]
                            tail_norm = alias_map.get(tail_raw) or self.entity_normalizer.normalize_entity(tail_raw)["canonical_name"]
                            rel["head_id"] = head_norm
                            rel["tail_id"] = tail_norm
                            rel["head_name"] = head_norm
                            rel["tail_name"] = tail_norm
                            rel["head_type"] = type_map.get(head_norm, "Other")
                            rel["tail_type"] = type_map.get(tail_norm, "Other")
                            rel["head_raw"] = head_raw
                            rel["tail_raw"] = tail_raw
                            rel["source_chunk_id"] = row["chunk_id"]
                            rel["file_id"] = int(file_id)
                            rel["doc_id"] = doc_id
                        await asyncio.to_thread(
                            self.graph_store.upsert_relations, kb_id, relations
                        )

            await asyncio.gather(*(process_chunk(row) for row in chunk_rows))
        except Exception:
            print(f"⚠️ Indexing failed, rollback indexed data for {doc_id}")
            await self.delete_document(file_id=file_id, kb_id=kb_id)
            raise

        return {"status": "success", "file_id": file_id, "kb_id": kb_id, "chunks": len(chunk_rows)}

    async def delete_document(self, file_id: str, kb_id: int):
        doc_id = f"kb_{kb_id}_file_{file_id}"
        await asyncio.to_thread(self.vector_store.delete_by_doc_id, kb_id, doc_id)
        await asyncio.to_thread(self.graph_store.delete_by_doc_id, kb_id, doc_id)
        return True

    async def delete_knowledge_base(self, kb_id: int):
        await asyncio.to_thread(self.vector_store.drop_collection, kb_id)
        await asyncio.to_thread(self.graph_store.delete_kb, kb_id)
        working_dir = os.path.join(WORKING_DIR_BASE, f"kb_{kb_id}")
        if os.path.exists(working_dir):
            import shutil

            shutil.rmtree(working_dir)
        if kb_id in self._initialized_kb_ids:
            self._initialized_kb_ids.remove(kb_id)
        return True

    def _build_context(
        self,
        chunks: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> str:
        return (
            "Knowledge Graph Data (Entity)\n"
            "```json\n"
            f"{json.dumps(entities, ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "Knowledge Graph Data (Relationship)\n"
            "```json\n"
            f"{json.dumps(relationships, ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "Document Chunks\n"
            "```json\n"
            f"{json.dumps(chunks, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )

    def _apply_rerank(self, query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not chunks:
            return []
        documents = [chunk.get("content", "") for chunk in chunks]
        results = rerank_documents(query, documents)
        if not results:
            return chunks
        min_score = float(os.getenv("MIN_RERANK_SCORE", "0.0"))
        scored = []
        for item in results:
            idx = item.get("index")
            score = item.get("relevance_score", 0.0)
            if idx is None or idx >= len(chunks):
                continue
            if score < min_score:
                continue
            entry = dict(chunks[idx])
            entry["rerank_score"] = score
            scored.append(entry)
        return scored or chunks

    def _dedup_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 实体去重：避免同一实体在多次召回/扩展后重复出现
        seen: dict[str, dict[str, Any]] = {}
        unnamed: list[dict[str, Any]] = []
        for entity in entities or []:
            key = entity.get("entity_id") or entity.get("entity_name")
            if not key:
                unnamed.append(entity)
                continue
            if key not in seen:
                seen[key] = entity
        return list(seen.values()) + unnamed

    def _dedup_relationships(self, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 关系去重：防止子图扩展后关系爆炸、上下文冗余
        seen = set()
        out: list[dict[str, Any]] = []
        for rel in relationships or []:
            key = (
                rel.get("head"),
                rel.get("relation"),
                rel.get("tail"),
                rel.get("source_chunk_id"),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(rel)
        return out

    def _collect_graph_chunk_ids(
        self, entities: list[dict[str, Any]], relationships: list[dict[str, Any]]
    ) -> list[str]:
        # 从图结果反查关联文本块ID：把“图证据”映射回“文本证据”
        chunk_ids: list[str] = []
        for entity in entities or []:
            chunk_ids.extend(entity.get("source_chunk_ids", []))
        for rel in relationships or []:
            chunk_id = rel.get("source_chunk_id")
            if chunk_id:
                chunk_ids.append(chunk_id)
        return list(dict.fromkeys(cid for cid in chunk_ids if cid))

    def _merge_chunks(
        self, primary: list[dict[str, Any]], secondary: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # 按优先级合并两批chunk并按chunk_id去重
        merged: dict[str, dict[str, Any]] = {}
        ordered: list[dict[str, Any]] = []
        for chunk in (primary or []) + (secondary or []):
            cid = chunk.get("chunk_id")
            if cid and cid in merged:
                continue
            if cid:
                merged[cid] = chunk
            ordered.append(chunk)
        return ordered

    async def query(
        self,
        question: str,
        kb_id: int,
        mode: str = "hybrid",
        top_k: int = 5,
        only_context: bool = False,
        enable_rerank: bool | None = None,
    ):
        await self._ensure_kb(kb_id)

        mode = (mode or "hybrid").lower()
        final_k = max(1, int(top_k))
        # 将“初始候选池大小”与“最终返回条数”拆开，避免小 top_k 过早截断真正相关结果。
        # naive 纯向量模式没有图谱补强，单独给更大的候选池，便于 rerank 从更宽的范围里挑出真正相关块。
        if mode == "naive":
            vector_candidate_k = max(final_k * 6, 30)
        else:
            vector_candidate_k = max(final_k * 3, 15)
        graph_entity_candidate_k = max(final_k * 3, 12)
        graph_chunk_candidate_k = max(final_k * 4, 20)

        if enable_rerank is None:
            default_rerank = os.getenv("RERANK_BY_DEFAULT", "true").lower() == "true"
            enable_rerank = default_rerank and mode in {"hybrid"}

        chunks: list[dict[str, Any]] = []
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []

        if mode in {"naive", "local", "hybrid"}:
            chunks = await asyncio.to_thread(
                self.vector_store.search, kb_id, question, vector_candidate_k
            )

        if mode in {"local", "hybrid"}:
            chunk_ids = [chunk.get("chunk_id") for chunk in chunks if chunk.get("chunk_id")]
            entities = await asyncio.to_thread(self.graph_store.get_entities_by_chunk_ids, kb_id, chunk_ids)
            relationships = await asyncio.to_thread(
                self.graph_store.get_relations_by_chunk_ids, kb_id, chunk_ids
            )
            entities = self._dedup_entities(entities)
            relationships = self._dedup_relationships(relationships)

        # local 模式补充一跳局部子图，并把相关图块优先并入检索候选
        if mode == "local":
            """
                取当前实体 entity_id
                expand_subgraph(..., hop=1, limit=200)
                与已有实体/关系合并后再去重
                用 _collect_graph_chunk_ids 拿图相关 chunk id
                fetch_chunks_by_ids(..., max(top_k*3, top_k)) 拉更多候选
                chunks = _merge_chunks(graph_chunks, chunks)（图块优先）
                效果：local 不再只依赖最初向量命中块，会补充一跳图邻域文本证据。
            """
            local_entity_ids = [e.get("entity_id") for e in entities if e.get("entity_id")]
            expanded_local = await asyncio.to_thread(
                self.graph_store.expand_subgraph, kb_id, local_entity_ids, 1, 200
            )
            entities = self._dedup_entities((entities or []) + (expanded_local.get("entities") or []))
            relationships = self._dedup_relationships(
                (relationships or []) + (expanded_local.get("relationships") or [])
            )

            graph_chunk_ids = self._collect_graph_chunk_ids(entities, relationships)
            graph_chunks = await asyncio.to_thread(
                self.vector_store.fetch_chunks_by_ids,
                kb_id,
                graph_chunk_ids,
                graph_chunk_candidate_k,
            )
            # local 优先保留图结构相关块，再补齐向量召回块
            chunks = self._merge_chunks(graph_chunks, chunks)

        # global模式仅仅用全文索引在Neo4j中找实体。不查Milvus，所以chunks可能很少或为空
        if mode == "global":
            entities = await asyncio.to_thread(
                self.graph_store.search_entities_fulltext,
                kb_id,
                question,
                graph_entity_candidate_k,
            )
            entity_ids = [e.get("entity_id") for e in entities if e.get("entity_id")]
            expanded = await asyncio.to_thread(
                self.graph_store.expand_subgraph, kb_id, entity_ids, 2, 200
            )
            if expanded.get("entities"):
                entities = expanded["entities"]
            relationships = expanded.get("relationships", [])


        if mode == "hybrid":
            global_entities = await asyncio.to_thread(
                self.graph_store.search_entities_fulltext,
                kb_id,
                question,
                graph_entity_candidate_k,
            )

            global_entity_ids = [e.get("entity_id") for e in global_entities if e.get("entity_id")]
            expanded = await asyncio.to_thread(
                self.graph_store.expand_subgraph, kb_id, global_entity_ids, 2, 200
            )
            entities = self._dedup_entities((entities or []) + (expanded.get("entities") or []))
            relationships = self._dedup_relationships(
                (relationships or []) + (expanded.get("relationships") or [])
            )

            graph_chunk_ids = self._collect_graph_chunk_ids(entities, relationships)

            graph_chunks = await asyncio.to_thread(
                self.vector_store.fetch_chunks_by_ids,
                kb_id,
                graph_chunk_ids,
                graph_chunk_candidate_k,
            )

            # hybrid 保持向量召回优先，再追加图扩展块
            chunks = self._merge_chunks(chunks, graph_chunks)

        if enable_rerank:
            chunks = self._apply_rerank(question, chunks)
        # 统一严格裁剪到 top_k，保证 @k 语义一致
        chunks = chunks[:final_k]

        context = self._build_context(chunks, entities, relationships)

        result = {
            "status": "success",
            "mode": mode,
            "chunks": chunks,
            "entities": entities,
            "relationships": relationships,
            "context": context if only_context else context,
        }
        return result


lightrag_engine = LightRAGEngine()
