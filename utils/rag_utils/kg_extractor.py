import json
import os
import re
from typing import Any

from langchain_core.messages import HumanMessage

from utils.llm_client import llm_client
from utils.rag_utils.prompt_registry import prompt_registry


def _parse_json_block(text: str) -> list[dict[str, Any]]:
    """
        解析文本中的JSON块。提取代码块中的结构化数据
    :param text:
    :return:
    """
    if not text:
        return []

    text = text.strip().replace("\r", "")
    code_block = re.search(r"```(?:json|jsonl)?\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if code_block:
        text = code_block.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    rows = []
    for line in text.split("\n"):
        line = line.strip().rstrip(",")
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def _sanitize_relation(value: str, allowed_relations: set[str]) -> str:
    """
    保证图谱的 Schema（架构）不崩坏，限制关系类型必须是TREATS,HAS_SYMPTOM等定义的类型
    """
    if not value:
        return "RELATED_TO"
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", value.strip().upper())
    # 未知关系类型归一为 RELATED_TO。
    if not normalized:
        return "RELATED_TO"
    if normalized not in allowed_relations:
        return "RELATED_TO"
    return normalized


class KGExtractor:
    def __init__(self):
        entity_types_raw = os.getenv("ENTITY_TYPES")
        try:
            parsed = json.loads(entity_types_raw) if entity_types_raw else []
        except Exception:
            parsed = []
        self.entity_types = [item for item in parsed if isinstance(item, str)]
        self.entity_type_set = set(self.entity_types)

        self.allowed_relations = {
            "TREATS",
            "HAS_SYMPTOM",
            "HAS_SIDE_EFFECT",
            "HAS_INGREDIENT",
            "INDICATED_FOR",
            "CONTRAINDICATED_FOR",
            "INTERACTS_WITH",
            "REQUIRES_TEST",
            "HAS_DOSAGE",
            "RELATED_TO",
            "PART_OF",
            "CAUSES",
        }
        self.enable_multi_round = (
            os.getenv("EXTRACTION_MULTI_ROUND", "true").lower() == "true"
        )

    async def extract_entities(self, chunk_text: str) -> list[dict[str, Any]]:
        if not chunk_text:
            return []
        type_list = ", ".join(self.entity_types) if self.entity_types else "Disease, Symptom, Drug, Other"

        prompt = prompt_registry.render(
            "entity_extract",
            text=chunk_text,
            entity_types=type_list,
        )
        response = await llm_client.chat_model.ainvoke([HumanMessage(content=prompt)])
        raw_output = response.content

        items = _parse_json_block(raw_output)

        # 4. 多轮修正 (Refinement)
        """
        第二阶段是‘反馈修正’（Refinement）。将第一次输出的JSON再喂给LLM，
        让它以‘JSON 修复专家’的角色去检查错误、补充遗漏，这极大地提升了图谱数据入库的准确率
        """
        if self.enable_multi_round:
            refine_prompt = prompt_registry.render(
                "entity_refine",
                text=chunk_text,
                raw_output=raw_output,
                entity_types=type_list,
            )
            refine_resp = await llm_client.chat_model.ainvoke([HumanMessage(content=refine_prompt)])
            refined = _parse_json_block(refine_resp.content)
            if refined:
                items = refined

        results = []
        for item in items:
            name = (item.get("entity_name") or item.get("name") or "").strip()
            if not name:
                continue
            etype = (item.get("entity_type") or item.get("type") or "Other").strip()
            if self.entity_type_set and etype not in self.entity_type_set:
                etype = "Other"
            results.append(
                {
                    "entity_name": name,
                    "entity_type": etype,
                    "description": (item.get("description") or "").strip(),
                }
            )
        return results

    async def extract_relations(
        self, chunk_text: str, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not chunk_text:
            return []
        entity_names = [e["entity_name"] for e in entities if e.get("entity_name")]
        entity_hint = "、".join(entity_names[:20]) if entity_names else "无"

        prompt = prompt_registry.render(
            "relation_extract",
            text=chunk_text,
            entities=entity_hint,
        )

        response = await llm_client.chat_model.ainvoke([HumanMessage(content=prompt)])
        raw_output = response.content
        items = _parse_json_block(raw_output)

        if self.enable_multi_round:
            refine_prompt = prompt_registry.render(
                "relation_refine",
                text=chunk_text,
                entities=entity_hint,
                raw_output=raw_output,
            )
            refine_resp = await llm_client.chat_model.ainvoke([HumanMessage(content=refine_prompt)])
            refined = _parse_json_block(refine_resp.content)
            if refined:
                items = refined

        results = []
        for item in items:
            head = (item.get("head") or item.get("source") or "").strip()
            tail = (item.get("tail") or item.get("target") or "").strip()
            if not head or not tail:
                continue
            relation = _sanitize_relation(item.get("relation") or item.get("type") or "", self.allowed_relations)
            evidence = (item.get("evidence") or item.get("text") or "").strip()
            results.append(
                {
                    "head": head,
                    "tail": tail,
                    "relation": relation,
                    "evidence": evidence,
                }
            )
        return results
