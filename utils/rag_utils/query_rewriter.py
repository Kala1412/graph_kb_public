import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Sequence

from langchain_core.messages import BaseMessage, HumanMessage

from utils.llm_client import llm_client


_REFERENTIAL_PATTERN = re.compile(
    r"(这个|这个药|这药|该药|它|它们|其|这些|那些|那种|上述|前面提到|上面说的|那个|that|this|it|they)",
    re.IGNORECASE,
)


@dataclass
class RewriteResult:
    need_rewrite: bool
    original_query: str
    rewritten_query: str
    rewrite_applied: bool
    reason: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "need_rewrite": self.need_rewrite,
            "original_query": self.original_query,
            "rewritten_query": self.rewritten_query,
            "rewrite_applied": self.rewrite_applied,
            "rewrite_reason": self.reason,
            "rewrite_confidence": self.confidence,
        }


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except Exception:
        return default
    if result < 0:
        return 0.0
    if result > 1:
        return 1.0
    return result


def _extract_json_block(text: str) -> str:
    content = (text or "").strip()
    if not content:
        return ""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return content


def _normalize_role(raw_role: str) -> str:
    role = (raw_role or "").lower()
    if role in {"human", "user"}:
        return "user"
    if role in {"ai", "assistant"}:
        return "assistant"
    if role == "system":
        return "system"
    return "unknown"


def _trim_text(text: str, max_len: int = 1000) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len]


def build_history_window(
    messages: Sequence[BaseMessage],
    summary: str | None,
    rounds: int = 3,
) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    rounds = max(1, int(rounds))

    if summary and summary.strip():
        history.append({"role": "summary", "content": _trim_text(summary.strip(), max_len=1200)})

    if not messages:
        return history

    history_messages = list(messages[:-1])
    if not history_messages:
        return history

    max_messages = rounds * 2
    tail = history_messages[-max_messages:]
    for msg in tail:
        role = _normalize_role(getattr(msg, "type", "unknown"))
        content = _trim_text(str(getattr(msg, "content", "") or ""))
        if not content:
            continue
        history.append({"role": role, "content": content})
    return history


def quick_should_rewrite(
    query: str,
    history: list[dict[str, str]],
) -> tuple[bool, str]:
    query = (query or "").strip()
    if not query:
        return False, "empty_query"

    if _env_bool("QUERY_REWRITE_FORCE_LLM", False):
        return True, "force_llm"

    if not history:
        return False, "no_history"

    max_query_len = _safe_int(os.getenv("QUERY_REWRITE_MAX_QUERY_LEN"), 128)
    if len(query) > max_query_len:
        return False, "query_too_long"

    if _REFERENTIAL_PATTERN.search(query):
        return True, "contains_reference"

    short_threshold = 12
    if len(query) <= short_threshold:
        return True, "short_query"

    return False, "query_complete"


async def rewrite_with_llm(
    query: str,
    history: list[dict[str, str]],
    timeout_ms: int = 3000,
) -> dict[str, Any]:
    history_text = "\n".join(
        f"- [{item.get('role', 'unknown')}] {item.get('content', '')}" for item in history
    ).strip()
    prompt = f"""
你是检索查询改写器。目标：仅在必要时把“当前用户问题”改写为可独立检索的查询。

规则：
1. 若当前问题不依赖历史上下文，need_rewrite=false，并保持 rewritten_query 与原问题一致。
2. 若当前问题存在代词/省略并依赖历史，need_rewrite=true，rewritten_query 要补全主体但不得新增事实。
3. rewritten_query 必须简洁、可直接用于知识库检索。
4. 只输出 JSON，不要输出解释性文本。

输出 JSON schema:
{{
  "need_rewrite": true/false,
  "rewritten_query": "string",
  "reason": "string",
  "confidence": 0~1
}}

历史信息:
{history_text or "(empty)"}

当前用户问题:
{query}
""".strip()

    model = llm_client.get_rewrite_model()
    model_info = llm_client.get_rewrite_model_info()
    print(
        "[RewriteLLM] using model="
        f"{model_info.get('model_id') or '(inherit chat_model)'}, "
        f"base_url={model_info.get('base_url') or '(inherit chat_model)'}, "
        f"request_timeout_ms={model_info.get('request_timeout_ms')}"
    )

    response = await asyncio.wait_for(
        model.ainvoke([HumanMessage(content=prompt)]),
        timeout=max(0.1, timeout_ms / 1000),
    )
    raw = _extract_json_block(str(response.content or ""))
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")

    need_rewrite = bool(data.get("need_rewrite", False))
    rewritten_query = str(data.get("rewritten_query", "") or "").strip()
    reason = str(data.get("reason", "") or "").strip() or "llm_decision"
    confidence = _safe_float(data.get("confidence", 0.0), 0.0)

    if not rewritten_query:
        rewritten_query = query
        need_rewrite = False
        reason = "empty_rewritten_query"
        confidence = 0.0

    return {
        "need_rewrite": need_rewrite,
        "rewritten_query": rewritten_query,
        "reason": reason,
        "confidence": confidence,
    }


async def rewrite_query(
    messages: Sequence[BaseMessage],
    summary: str,
    query: str,
    rounds: int = 3,
) -> RewriteResult:
    original_query = (query or "").strip()
    if not original_query:
        return RewriteResult(
            need_rewrite=False,
            original_query="",
            rewritten_query="",
            rewrite_applied=False,
            reason="empty_query",
            confidence=0.0,
        )

    if not _env_bool("QUERY_REWRITE_ENABLED", True):
        return RewriteResult(
            need_rewrite=False,
            original_query=original_query,
            rewritten_query=original_query,
            rewrite_applied=False,
            reason="rewrite_disabled",
            confidence=0.0,
        )

    history = build_history_window(messages=messages, summary=summary, rounds=rounds)
    should_rewrite, quick_reason = quick_should_rewrite(original_query, history)

    if not should_rewrite:
        return RewriteResult(
            need_rewrite=False,
            original_query=original_query,
            rewritten_query=original_query,
            rewrite_applied=False,
            reason=quick_reason,
            confidence=0.0,
        )

    timeout_ms = _safe_int(os.getenv("QUERY_REWRITE_TIMEOUT_MS"), 8000)
    try:
        result = await rewrite_with_llm(
            query=original_query,
            history=history,
            timeout_ms=timeout_ms,
        )
    except Exception as exc:
        return RewriteResult(
            need_rewrite=False,
            original_query=original_query,
            rewritten_query=original_query,
            rewrite_applied=False,
            reason=f"llm_failed:{type(exc).__name__}",
            confidence=0.0,
        )

    rewritten_query = str(result.get("rewritten_query", original_query) or "").strip() or original_query
    need_rewrite = bool(result.get("need_rewrite", False))
    confidence = _safe_float(result.get("confidence", 0.0), 0.0)
    reason = str(result.get("reason", "") or "").strip() or "llm_decision"
    rewrite_applied = need_rewrite and rewritten_query != original_query

    if need_rewrite and not rewrite_applied:
        reason = "rewrite_same_as_original"

    return RewriteResult(
        need_rewrite=need_rewrite,
        original_query=original_query,
        rewritten_query=rewritten_query,
        rewrite_applied=rewrite_applied,
        reason=reason,
        confidence=confidence,
    )
