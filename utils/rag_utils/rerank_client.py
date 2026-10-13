import json
import os
import urllib.request
from typing import Any


def rerank_documents(query: str, documents: list[str]) -> list[dict[str, Any]]:
    """
    Call rerank API (SiliconFlow-compatible) and return list of
    {index: int, relevance_score: float}.
    """
    if not query or not documents:
        return []

    base_url = os.getenv("RERANK_BASE_URL")
    model = os.getenv("RERANK_MODEL")
    api_key = os.getenv("RERANK_API_KEY") or os.getenv("LLM_API_KEY")

    if not base_url or not model:
        return []

    payload = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(base_url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
    except Exception:
        return []

    results = parsed.get("results") or parsed.get("data") or []
    cleaned = []
    for item in results:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        score = item.get("relevance_score") or item.get("score")
        if idx is None:
            continue
        cleaned.append({"index": int(idx), "relevance_score": float(score or 0.0)})
    """
    API 返回的结果通常长这样：
    [{"index": 2, "relevance_score": 0.98}, {"index": 0, "relevance_score": 0.65}, ...]
    注意，这里的 index 是这个文档在原始传入列表中的位置。大模型认为你传进来的第 3 个文档（index=2）最符合问题，给出了 0.98 的超高分。
    """
    return cleaned
