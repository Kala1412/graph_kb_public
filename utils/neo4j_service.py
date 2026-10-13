import os
from neo4j import GraphDatabase
import logging

logger = logging.getLogger(__name__)

class Neo4jService:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_subgraph(self, kb_id: int = None, limit: int = 100):
        """
        获取特定知识库的子图
        LightRAG 在 Neo4j 中通常会给节点加上对应的标签或属性
        workspace = f"kb_{kb_id}"
        """


        with self.driver.session() as session:
            if kb_id is not None:
                workspace_label = f"kb_{kb_id}"
                query = f"""
                MATCH (n:`{workspace_label}`)-[r]->(m:`{workspace_label}`)
                RETURN 
                    {{id: id(n), name: n.entity_id, type: n.entity_type,properties: properties(n)}} as source,
                    {{id: id(r), type: type(r), source: id(n), target: id(m), properties: properties(r)}} as edge,
                    {{id: id(m), name: m.entity_id, type: m.entity_type,properties: properties(m)}} as target
                LIMIT $limit
                """
            else:
                # 查全部节点（不限定 workspace 标签）
                query = """
                            MATCH (n)-[r]->(m)
                            RETURN 
                                {id: id(n), name: n.entity_id, type: n.entity_type, properties: properties(n)} as source,
                                {id: id(r), type: type(r), source: id(n), target: id(m), properties: properties(r)} as edge,
                                {id: id(m), name: m.entity_id, type: m.entity_type, properties: properties(m)} as target
                            LIMIT $limit
                            """

            result = session.run(query,limit = limit)

            nodes = {}
            edges = []

            for record in result:
                s = record["source"]
                t = record["target"]
                e = record["edge"]

                nodes[s["id"]] = {
                    "id": str(s["id"]),
                    "name": s["name"] or "Unknown",
                    "label": s["type"],
                    "properties": s["properties"]
                }
                nodes[t["id"]] = {
                    "id": str(t["id"]),
                    "name": t["name"] or "Unknown",
                    "label": t["type"],
                    "properties": t["properties"]
                }
                edges.append({
                    "id": str(e["id"]),
                    "source": str(e["source"]),
                    "target": str(e["target"]),
                    "type": e["type"],
                    "properties": e["properties"]
                })

            return {
                "nodes": list(nodes.values()),
                "edges": edges
            }


neo4j_service = Neo4jService()