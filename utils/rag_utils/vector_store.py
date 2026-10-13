import json
import math
import os
import time
from typing import Any, Iterable

from langchain_openai import OpenAIEmbeddings
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)


class MilvusVectorStore:
    def __init__(self):
        self._connected = False
        self.alias = "default"
        self.uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        self.token = os.getenv("MILVUS_TOKEN", "")
        self.db_name = os.getenv("MILVUS_DB_NAME")
        self.embedding_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self.embedding_batch_size = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "50")))
        self.embedding_provider_max_batch = max(
            1, int(os.getenv("EMBEDDING_PROVIDER_MAX_BATCH", "64"))
        )
        self.embedding_retry_max = max(0, int(os.getenv("EMBEDDING_RETRY_MAX", "3")))
        self.embedding_retry_backoff_sec = max(
            0.0, float(os.getenv("EMBEDDING_RETRY_BACKOFF_SEC", "0.8"))
        )

        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            model=self.embedding_model,
        )

    def _connect(self) -> None:
        if self._connected:
            return
        connect_kwargs = {
            "alias": self.alias,
            "uri": self.uri,
            "token": self.token,
        }
        if self.db_name:
            connect_kwargs["db_name"] = self.db_name
        connections.connect(**connect_kwargs)
        self._connected = True

    def _collection_name(self, kb_id: int) -> str:
        return f"kb_{kb_id}_chunks"

    # 创建Milvus集合（如果不存在）。集合名格式：kb_{kb_id}_chunks
    def ensure_collection(self, kb_id: int) -> Collection:
        self._connect()
        name = self._collection_name(kb_id)
        if utility.has_collection(name, using=self.alias):
            collection = Collection(name, using=self.alias)
            if not collection.indexes:
                collection.create_index(
                    field_name="embedding",
                    index_params={
                        "index_type": "HNSW",
                        "metric_type": "IP",
                        "params": {"M": 16, "efConstruction": 200},
                    },
                )
            collection.load()
            return collection
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="file_id", dtype=DataType.INT64),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
        ]
        schema = CollectionSchema(fields, description="Knowledge chunks")
        collection = Collection(name=name, schema=schema, using=self.alias)
        collection.create_index(
            field_name="embedding",
            index_params={
                "index_type": "HNSW",
                "metric_type": "IP",
                "params": {"M": 16, "efConstruction": 200}, # 参数M代表图中每个节点的边数，efConstruction代表建树时的搜索范围
            },
        )
        collection.load()
        return collection

    def _l2_normalize(self, vector: Iterable[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [float(v) / norm for v in vector]

    def _iter_batches(self, items: list[Any], batch_size: int):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def _is_batch_limit_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return (
            "input batch size" in msg
            or "maximum allowed batch size" in msg
            or "max batch size" in msg
            or "20042" in msg
        )

    def _embed_once_with_retry(self, texts: list[str]) -> list[list[float]]:
        attempts = 0
        while True:
            try:
                vectors = self.embeddings.embed_documents(texts)
                if vectors is None:
                    raise RuntimeError("Embedding response is None")
                if not isinstance(vectors, list):
                    raise RuntimeError(
                        f"Embedding response type invalid: {type(vectors).__name__}"
                    )
                if len(vectors) != len(texts):
                    raise RuntimeError(
                        f"Embedding response length mismatch: expected={len(texts)} got={len(vectors)}"
                    )
                for idx, vec in enumerate(vectors):
                    if vec is None:
                        raise RuntimeError(f"Embedding vector is None at index={idx}")
                    if not isinstance(vec, (list, tuple)):
                        raise RuntimeError(
                            f"Embedding vector type invalid at index={idx}: {type(vec).__name__}"
                        )
                    if not vec:
                        raise RuntimeError(f"Embedding vector empty at index={idx}")
                return vectors
            except Exception as exc:
                # 触发批大小限制时，交给上层自适应降批逻辑处理
                if self._is_batch_limit_error(exc):
                    raise
                if attempts >= self.embedding_retry_max:
                    raise
                sleep_s = self.embedding_retry_backoff_sec * (2**attempts)
                time.sleep(sleep_s)
                attempts += 1

    def _embed_batch_adaptive(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        queue: list[list[str]] = [texts]
        vectors: list[list[float]] = []

        while queue:
            current = queue.pop(0)
            try:
                vectors.extend(self._embed_once_with_retry(current))
                continue
            except Exception as exc:
                if self._is_batch_limit_error(exc) and len(current) > 1:
                    next_size = max(1, len(current) // 2)
                    print(
                        f"⚠️ Embedding batch limit hit (size={len(current)}), "
                        f"auto-shrink to {next_size}"
                    )
                    queue.insert(0, current[next_size:])
                    queue.insert(0, current[:next_size])
                    continue
                raise
        return vectors

    # 调用embedding模型 → L2归一化（向量归一化后使用 IP 相似度）
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._embed_batch_adaptive(texts)  # 批量请求并自适应降批
        return [self._l2_normalize(vec) for vec in vectors]  # 强制L2归一化

    # 写入向量数据。字段：chunk_id / file_id / doc_id / content / metadata / embedding
    def upsert_chunks(self, kb_id: int, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        collection = self.ensure_collection(kb_id)

        # 固定小于等于 provider 限制，避免直接触发 413
        batch_size = min(self.embedding_batch_size, self.embedding_provider_max_batch)
        total_batches = math.ceil(len(chunks) / batch_size)

        for idx, batch_chunks in enumerate(self._iter_batches(chunks, batch_size), start=1):
            print(
                f"[embedding] kb={kb_id} batch={idx}/{total_batches} size={len(batch_chunks)}"
            )

            chunk_ids = [chunk["chunk_id"] for chunk in batch_chunks]
            file_ids = [int(chunk.get("file_id", 0)) for chunk in batch_chunks]
            doc_ids = [chunk.get("doc_id", "") for chunk in batch_chunks]
            contents = [chunk.get("content", "") for chunk in batch_chunks]
            metadata_raw = [
                json.dumps(chunk.get("metadata", {}), ensure_ascii=False) for chunk in batch_chunks
            ]

            embeddings = self.embed_texts(contents)

            data = [chunk_ids, file_ids, doc_ids, contents, metadata_raw, embeddings]
            collection.insert(data)

        collection.flush()

    def search(self, kb_id: int, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        作用：基于内容的纯向量检索（Dense Retrieval）。
        举例：用户问“如何治疗二型糖尿病？”，库里有一句话“二甲双胍是2型糖尿病首选药”。
        哪怕这两句话没有重叠的关键字，因为它们的高维空间语义距离很近，Milvus也能把它搜出来
        """
        if not query:
            return []
        collection = self.ensure_collection(kb_id)
        query_embedding = self._l2_normalize(self.embeddings.embed_query(query))
        if not query_embedding:
            return []

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},# ef: 检索时的探索深度
            limit=top_k,
            output_fields=["chunk_id", "file_id", "doc_id", "content", "metadata"],
        )

        hits = []
        for hit in results[0]:
            metadata_raw = hit.entity.get("metadata") or "{}"
            try:
                metadata = json.loads(metadata_raw)
            except Exception:
                metadata = {}
            hits.append(
                {
                    "chunk_id": hit.entity.get("chunk_id"),
                    "file_id": hit.entity.get("file_id"),
                    "doc_id": hit.entity.get("doc_id"),
                    "content": hit.entity.get("content"),
                    "metadata": metadata,
                    "similarity_score": float(hit.score),
                }
            )
        return hits

    def fetch_chunks_by_ids(
        self, kb_id: int, chunk_ids: list[str], limit: int = 20
    ) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        collection = self.ensure_collection(kb_id)
        safe_ids = list({cid for cid in chunk_ids if cid})
        if not safe_ids:
            return []
        expr = f"chunk_id in {json.dumps(safe_ids)}"
        rows = collection.query(
            expr=expr,
            output_fields=["chunk_id", "file_id", "doc_id", "content", "metadata"],
            limit=limit,
        )
        results = []
        for row in rows:
            metadata_raw = row.get("metadata") or "{}"
            try:
                metadata = json.loads(metadata_raw)
            except Exception:
                metadata = {}
            results.append(
                {
                    "chunk_id": row.get("chunk_id"),
                    "file_id": row.get("file_id"),
                    "doc_id": row.get("doc_id"),
                    "content": row.get("content"),
                    "metadata": metadata,
                    "similarity_score": None,
                }
            )
        return results

    def delete_by_doc_id(self, kb_id: int, doc_id: str) -> None:
        if not doc_id:
            return
        collection = self.ensure_collection(kb_id)
        expr = f"doc_id == {json.dumps(doc_id)}"
        collection.delete(expr)
        collection.flush()

    def drop_collection(self, kb_id: int) -> None:
        name = self._collection_name(kb_id)
        self._connect()
        if utility.has_collection(name, using=self.alias):
            utility.drop_collection(name, using=self.alias)
