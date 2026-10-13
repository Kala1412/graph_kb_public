import os
import re
from typing import Any

from neo4j import GraphDatabase


def _sanitize_label(value: str, fallback: str = "Other") -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value.strip())
    return cleaned or fallback


class GraphStore:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self) -> None:
        self.driver.close()

    def _kb_label(self, kb_id: int) -> str:
        return f"kb_{kb_id}"

    def ensure_fulltext_index(self, kb_id: int) -> None:
        label = self._kb_label(kb_id)
        index_name = f"kb_{kb_id}_entity_fulltext"
        query = (
            f"CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS "
            f"FOR (n:`{label}`) ON EACH [n.entity_name, n.aliases]"
        )
        with self.driver.session() as session:
            session.run(query)

    def upsert_entities(self, kb_id: int, entities: list[dict[str, Any]]) -> None:
        if not entities:
            return
        label = self._kb_label(kb_id)

        grouped: dict[str, list[dict[str, Any]]] = {}
        for entity in entities:
            entity_type = _sanitize_label(entity.get("entity_type") or "Other")
            grouped.setdefault(entity_type, []).append(entity)

        with self.driver.session() as session:
            for entity_type, rows in grouped.items():
                cypher = f"""
                UNWIND $rows AS row
                MERGE (e:`{label}`:`{entity_type}` {{entity_id: row.entity_id}})
                SET e.entity_name = row.entity_name,
                    e.entity_type = row.entity_type,
                    e.description = coalesce(e.description, row.description),
                    e.updated_at = timestamp()
                SET e.aliases = CASE
                    WHEN e.aliases IS NULL THEN coalesce(row.aliases, [])
                    ELSE e.aliases + [a IN coalesce(row.aliases, []) WHERE NOT a IN e.aliases]
                END
                SET e.source_doc_ids = CASE
                    WHEN e.source_doc_ids IS NULL THEN [row.doc_id]
                    WHEN row.doc_id IN e.source_doc_ids THEN e.source_doc_ids
                    ELSE e.source_doc_ids + row.doc_id
                END
                SET e.source_chunk_ids = CASE
                    WHEN e.source_chunk_ids IS NULL THEN [row.source_chunk_id]
                    WHEN row.source_chunk_id IN e.source_chunk_ids THEN e.source_chunk_ids
                    ELSE e.source_chunk_ids + row.source_chunk_id
                END
                SET e.source_file_ids = CASE
                    WHEN e.source_file_ids IS NULL THEN [row.file_id]
                    WHEN row.file_id IN e.source_file_ids THEN e.source_file_ids
                    ELSE e.source_file_ids + row.file_id
                END
                """
                session.run(cypher, rows=rows)

    def upsert_relations(self, kb_id: int, relations: list[dict[str, Any]]) -> None:
        if not relations:
            return
        label = self._kb_label(kb_id)

        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for rel in relations:
            rel_type = _sanitize_label(rel.get("relation") or "RELATED_TO", fallback="RELATED_TO")
            head_type = _sanitize_label(rel.get("head_type") or "Other")
            tail_type = _sanitize_label(rel.get("tail_type") or "Other")
            grouped.setdefault((rel_type, head_type, tail_type), []).append(rel)

        with self.driver.session() as session:
            for (rel_type, head_type, tail_type), rows in grouped.items():
                cypher = f"""
                UNWIND $rows AS row
                MERGE (h:`{label}`:`{head_type}` {{entity_id: row.head_id}})
                SET h.entity_name = row.head_name,
                    h.entity_type = row.head_type,
                    h.updated_at = timestamp()
                SET h.source_doc_ids = CASE
                    WHEN h.source_doc_ids IS NULL THEN [row.doc_id]
                    WHEN row.doc_id IN h.source_doc_ids THEN h.source_doc_ids
                    ELSE h.source_doc_ids + row.doc_id
                END
                SET h.source_chunk_ids = CASE
                    WHEN h.source_chunk_ids IS NULL THEN [row.source_chunk_id]
                    WHEN row.source_chunk_id IN h.source_chunk_ids THEN h.source_chunk_ids
                    ELSE h.source_chunk_ids + row.source_chunk_id
                END
                SET h.source_file_ids = CASE
                    WHEN h.source_file_ids IS NULL THEN [row.file_id]
                    WHEN row.file_id IN h.source_file_ids THEN h.source_file_ids
                    ELSE h.source_file_ids + row.file_id
                END
                MERGE (t:`{label}`:`{tail_type}` {{entity_id: row.tail_id}})
                SET t.entity_name = row.tail_name,
                    t.entity_type = row.tail_type,
                    t.updated_at = timestamp()
                SET t.source_doc_ids = CASE
                    WHEN t.source_doc_ids IS NULL THEN [row.doc_id]
                    WHEN row.doc_id IN t.source_doc_ids THEN t.source_doc_ids
                    ELSE t.source_doc_ids + row.doc_id
                END
                SET t.source_chunk_ids = CASE
                    WHEN t.source_chunk_ids IS NULL THEN [row.source_chunk_id]
                    WHEN row.source_chunk_id IN t.source_chunk_ids THEN t.source_chunk_ids
                    ELSE t.source_chunk_ids + row.source_chunk_id
                END
                SET t.source_file_ids = CASE
                    WHEN t.source_file_ids IS NULL THEN [row.file_id]
                    WHEN row.file_id IN t.source_file_ids THEN t.source_file_ids
                    ELSE t.source_file_ids + row.file_id
                END
                MERGE (h)-[r:`{rel_type}`]->(t)
                SET r.evidence = row.evidence,
                    r.source_chunk_id = row.source_chunk_id,
                    r.file_id = row.file_id,
                    r.doc_id = row.doc_id,
                    r.updated_at = timestamp()
                """
                session.run(cypher, rows=rows)

    def delete_by_doc_id(self, kb_id: int, doc_id: str) -> None:
        if not doc_id:
            return
        label = self._kb_label(kb_id)
        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (n:`{label}`)-[r]-()
                WHERE r.doc_id = $doc_id
                DELETE r
                """,
                doc_id=doc_id,
            )
            session.run(
                f"""
                MATCH (n:`{label}`)
                WHERE $doc_id IN coalesce(n.source_doc_ids, [])
                SET n.source_doc_ids = [d IN coalesce(n.source_doc_ids, []) WHERE d <> $doc_id]
                WITH n
                OPTIONAL MATCH (n)-[r]-()
                WITH n, count(r) AS rc
                WHERE size(coalesce(n.source_doc_ids, [])) = 0 AND rc = 0
                DELETE n
                """,
                doc_id=doc_id,
            )

    def delete_kb(self, kb_id: int) -> None:
        label = self._kb_label(kb_id)
        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (n:`{label}`)
                DETACH DELETE n
                """
            )

    def get_entities_by_chunk_ids(self, kb_id: int, chunk_ids: list[str]) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        label = self._kb_label(kb_id)
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (n:`{label}`)
                WHERE any(cid IN coalesce(n.source_chunk_ids, []) WHERE cid IN $chunk_ids)
                RETURN n
                """,
                chunk_ids=chunk_ids,
            )
            return [self._node_to_dict(record["n"]) for record in result]

    def get_relations_by_chunk_ids(self, kb_id: int, chunk_ids: list[str]) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        label = self._kb_label(kb_id)
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (n:`{label}`)-[r]->(m:`{label}`)
                WHERE r.source_chunk_id IN $chunk_ids
                RETURN n, r, m
                """,
                chunk_ids=chunk_ids,
            )
            relations = []
            for record in result:
                relations.append(self._relation_to_dict(record["n"], record["r"], record["m"]))
            return relations

    def search_entities_fulltext(self, kb_id: int, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not query:
            return []
        index_name = f"kb_{kb_id}_entity_fulltext"
        safe_query = self._sanitize_fulltext_query(query)

        # 先尝试原始 query，失败再尝试清洗后的 query
        candidates = [query]
        if safe_query != query:
            candidates.append(safe_query)

        last_exc = None
        for q in candidates:
            try:
                with self.driver.session() as session:
                    result = session.run(
                        """
                        CALL db.index.fulltext.queryNodes($index_name, $text)
                        YIELD node, score
                        RETURN node, score
                        ORDER BY score DESC
                        LIMIT $limit
                        """,
                        index_name=index_name,
                        text=q,
                        limit=limit,
                    )
                    entities = []
                    for record in result:
                        item = self._node_to_dict(record["node"])
                        item["score"] = record["score"]
                        entities.append(item)
                    return entities
            except Exception as exc:
                last_exc = exc

        if last_exc:
            raise last_exc
        return []


    def expand_subgraph(self, kb_id: int, entity_ids: list[str], depth: int = 1, limit: int = 200) -> dict[str, list]:
        if not entity_ids:
            return {"entities": [], "relationships": []}
        label = self._kb_label(kb_id)
        depth = 1 if depth < 1 else 2 if depth > 2 else depth
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH path=(n:`{label}`)-[r*1..{depth}]-(m:`{label}`)
                WHERE n.entity_id IN $entity_ids
                UNWIND relationships(path) AS rel
                WITH DISTINCT rel
                MATCH (h)-[rel]->(t)
                RETURN h, rel, t
                LIMIT $limit
                """,
                entity_ids=entity_ids,
                limit=limit,
            )
            nodes_map = {}
            rels = []
            for record in result:
                head = record["h"]
                tail = record["t"]
                rel = record["rel"]
                nodes_map[head.id] = self._node_to_dict(head)
                nodes_map[tail.id] = self._node_to_dict(tail)
                rels.append(self._relation_to_dict(head, rel, tail))
            return {"entities": list(nodes_map.values()), "relationships": rels}

    def _node_to_dict(self, node) -> dict[str, Any]:
        props = dict(node)
        return {
            "entity_name": props.get("entity_name") or props.get("entity_id"),
            "entity_type": props.get("entity_type"),
            "entity_id": props.get("entity_id"),
            "description": props.get("description"),
            "aliases": props.get("aliases", []),
            "source_chunk_ids": props.get("source_chunk_ids", []),
            "source_file_ids": props.get("source_file_ids", []),
            "source_doc_ids": props.get("source_doc_ids", []),
            "properties": props,
        }

    def _relation_to_dict(self, head, rel, tail) -> dict[str, Any]:
        return {
            "head": dict(head).get("entity_id"),
            "tail": dict(tail).get("entity_id"),
            "relation": rel.type,
            "evidence": rel.get("evidence"),
            "source_chunk_id": rel.get("source_chunk_id"),
            "file_id": rel.get("file_id"),
            "doc_id": rel.get("doc_id"),
        }

    def _rel_only_to_dict(self, rel) -> dict[str, Any]:
        return {
            "relation": rel.type,
            "evidence": rel.get("evidence"),
            "source_chunk_id": rel.get("source_chunk_id"),
            "file_id": rel.get("file_id"),
            "doc_id": rel.get("doc_id"),
        }
    
    def _sanitize_fulltext_query(self, query: str) -> str:
        if not query:
            return ""
        safe = query

        # Lucene/Neo4j fulltext 常见特殊字符，统一替换为空格
        # 注意先处理双字符，再处理单字符
        for token in ["&&", "||"]:
            safe = safe.replace(token, " ")

        for ch in ["\\", "/", "+", "-", "!", "(", ")", "{", "}", "[", "]", "^", '"', "~", "*", "?", ":"]:
            safe = safe.replace(ch, " ")

        safe = re.sub(r"\s+", " ", safe).strip()
        return safe or query

