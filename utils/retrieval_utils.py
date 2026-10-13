import json
import re
from typing import Any


def _parse_json_block(raw_block: str) -> list[dict[str, Any]]:
    if not raw_block:
        return []

    raw_block = raw_block.strip().replace('\r', '')

    # 1) 尝试整体 JSON（数组 / 对象）
    try:
        parsed = json.loads(raw_block)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    # 2) 逐行 JSONL
    rows = []
    for line in raw_block.split('\n'):
        line = line.strip().rstrip(',')
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def _extract_section_json(marker: str, text: str) -> list[dict[str, Any]]:
    pattern = rf"{marker}.*?```(?:json|jsonl)\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    raw_block = match.group(1).strip()
    return _parse_json_block(raw_block)


def parse_lightrag_context(raw_text: str) -> dict[str, list[dict[str, Any]]]:
    if not raw_text:
        return {"chunks": [], "entities": [], "relations": []}
    """
    解析步骤（将前面取出来的context）
    1. 使用正则找三段：
        `Knowledge Graph Data (Entity)`  
        `Knowledge Graph Data (Relationship)`  
        `Document Chunks`

    2. 每段中提取 ```json / ```jsonl 的内容

    3. 调用 `_parse_json_block()` 解析 JSON 
    """
    return {
        "entities": _extract_section_json(r"Knowledge Graph Data \(Entity\)", raw_text),
        "relations": _extract_section_json(r"Knowledge Graph Data \(Relationship\)", raw_text),
        "chunks": _extract_section_json(r"Document Chunks", raw_text),
    }
