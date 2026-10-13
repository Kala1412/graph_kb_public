import difflib
from typing import Any


class EntityDeduplicator:
    def __init__(self, similarity_threshold: float = 0.9):
        # 设定模糊匹配的相似度阈值，默认0.9（即 90% 相似就认为是同一个东西）
        self.similarity_threshold = similarity_threshold

    def _similar(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a, b).ratio()

    def deduplicate(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not entities:
            return []
        """
            阶段1：基于(类型, 标准名)的精确合并(ExactMerge)
            
            作用： 这是绝对精确的合并。把完全一样的实体融合成一个超级节点。
            举例： LLM 从一段话里抽出了两个字典：
                1. {"entity_name": "糖病", "canonical_name": "糖尿病", "description": ""}
                2. {"entity_name": "T2DM", "canonical_name": "糖尿病", "description": "一种代谢疾病"}
            通过这一步合并，最终只会保留一个字典：
                {"canonical_name": "糖尿病", "aliases": {"糖病", "T2DM", "糖尿病"}, "description": "一种代谢疾病"}
            工程亮点：重点关注对description的处理。它不仅是去重，还在做信息互补，这在知识图谱中叫**“属性对齐与融合”**
        """
        # 核心数据结构：用一个字典来做分组 (Group By)
        # 键Key是一个元组：(实体类型, 标准名)，比如("Disease", "糖尿病")
        groups: dict[tuple[str, str], dict[str, Any]] = {}

        for entity in entities:
            entity_type = entity.get("entity_type") or "Other"
            canonical = entity.get("canonical_name") or entity.get("entity_name")
            key = (entity_type, canonical)
            if key not in groups:
                groups[key] = {
                    "canonical_name": canonical,
                    "entity_type": entity_type,
                    "description": entity.get("description", ""),
                    "aliases": set(entity.get("aliases", []) + [entity.get("entity_name", canonical)]),
                }
            else:
                group = groups[key]
                group["aliases"].update(entity.get("aliases", []))
                # 2. 融合描述：如果旧档案里没写描述，但这次抽取的包含了描述，就补填进去
                if not group["description"] and entity.get("description"):
                    group["description"] = entity.get("description")

        deduped = list(groups.values())

        """
        阶段2：同类型下的模糊合并(Fuzzy Merge)
        """
        merged: list[dict[str, Any]] = []
        for entity in deduped:
            merged_into = None

            for existing in merged:
                # 仅在相同实体类型内进行近似合并。
                if existing["entity_type"] != entity["entity_type"]:
                    continue
                # 限制条件 2：计算两个标准名的字符串相似度，如果 >= 0.9 (默认值)
                if self._similar(existing["canonical_name"], entity["canonical_name"]) >= self.similarity_threshold:
                    merged_into = existing
                    break
            if merged_into:
                merged_into["aliases"].update(entity.get("aliases", []))
                if not merged_into.get("description") and entity.get("description"):
                    merged_into["description"] = entity.get("description")
            else:
                merged.append(entity)

        for entity in merged:
            # 别名转为有序列表，保证 JSON 和 Neo4j 存储结果稳定。
            entity["aliases"] = sorted(set(entity.get("aliases", [])))

        return merged
