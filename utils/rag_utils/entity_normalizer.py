import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from utils.llm_client import llm_client


class EntityNormalizer:
    def __init__(self):
        self.synonyms = self._load_synonyms()
        self.enable_llm = os.getenv("ENTITY_NORMALIZE_ENABLE_LLM", "false").lower() == "true"
        self.common_suffixes = [
            "病",
            "症",
            "综合征",
            "片",
            "胶囊",
            "注射液",
            "口服液",
        ]

    def _load_synonyms(self) -> dict[str, str]:
        path = Path("docs/synonyms.json")
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        mapping: dict[str, str] = {}
        if isinstance(raw, dict):
            for canonical, aliases in raw.items():
                if not isinstance(aliases, list):
                    continue
                for alias in aliases:
                    if isinstance(alias, str) and alias.strip():
                        mapping[alias.strip()] = canonical
        return mapping

    def _normalize_text(self, name: str) -> str:
        if not name:
            return ""
        # 1.NFKC 编码标准化：解决全角/半角、特殊符号问题
        text = unicodedata.normalize("NFKC", name)
        text = re.sub(r"\s+", "", text)
        return text.strip()
    # 剥离医疗后缀以提高同义词匹配覆盖率。
    def _strip_suffix(self, name: str) -> str:
        for suffix in self.common_suffixes:
            if name.endswith(suffix) and len(name) > len(suffix) + 1:
                return name[: -len(suffix)]
        return name

    def normalize_entity(
        self,
        entity_name: str,
        entity_type: str | None = None,
        context: str | None = None,
        candidates: list[str] | None = None,
    ) -> dict[str, Any]:
        original = entity_name or ""
        normalized = self._normalize_text(original)
        normalized = self._strip_suffix(normalized)

        # 尝试拿处理后的词去查字典，查不到再尝试拿原词查，实在没有就用处理后的词
        canonical = self.synonyms.get(normalized) or self.synonyms.get(original) or normalized

        # 3. 第三步：大模型层面的智能对齐（兜底机制）
        if self.enable_llm and candidates:
            canonical = self._llm_choose_canonical(original, canonical, candidates, context, entity_type)

        aliases = {original, normalized}
        if canonical:
            aliases.add(canonical)

        aliases = [a for a in aliases if a]

        return {
            "original_name": original,
            "canonical_name": canonical or original,
            "aliases": aliases,
            "entity_type": entity_type,
        }
    def _llm_choose_canonical(
        self,
        name: str,
        canonical: str,
        candidates: list[str],
        context: str | None,
        entity_type: str | None,
    ) -> str:
        prompt = f"""你是一个医学实体规范化助手。
请判断“{name}”是否等同于候选实体之一，并输出最合适的规范名称。

候选列表：{", ".join(candidates)}
当前规范化结果：{canonical}
实体类型：{entity_type or "未知"}
上下文：{context or "无"}

只输出一个名称，不要解释。
"""
        try:
            response = llm_client.chat_model.invoke([HumanMessage(content=prompt)])
            text = response.content.strip()
            if text:
                return text
        except Exception:
            pass
        return canonical
