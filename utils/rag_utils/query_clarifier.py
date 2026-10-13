import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Sequence

from langchain_core.messages import BaseMessage, HumanMessage

from utils.llm_client import llm_client
from utils.rag_utils.query_rewriter import build_history_window

# 这些模式用于快速识别“指代/省略”的问句。
_REFERENTIAL_PATTERN = re.compile(
    r"(这个|这个药|这药|该药|它|它们|其|这些|那些|那种|上述|前面提到|上面说的|那个|that|this|it|they)",
    re.IGNORECASE,
)
_AMBIGUOUS_PATTERN = re.compile(
    r"(怎么办|怎么吃|怎么用|怎么治疗|有用吗|能吃吗|可以吗|怎么处理|咋办)",
    re.IGNORECASE,
)


@dataclass
class ClarifyResult:
    need_clarification: bool
    clarification_question: str
    reason: str
    confidence: float
    normalized_query: str
    pending_query: str


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


def _default_clarification_question(query: str) -> str:
    """当规则判定不清晰时，给出一个稳定、可复用的澄清问题模板。"""
    q = (query or "").strip()
    if "药" in q or _REFERENTIAL_PATTERN.search(q):
        return "为了更准确回答，请补充具体药名、用途或你最关心的点。"
    return "为了更准确回答，请补充更具体的信息（如对象、症状、时间或背景）。"


def _looks_like_short_answer(query: str) -> bool:
    """用于识别用户在回答上一轮澄清问题，而不是在发起全新问题。"""
    q = (query or "").strip()
    if not q:
        return False
    if len(q) > _safe_int(os.getenv("QUERY_CLARIFY_SHORT_ANSWER_MAX_LEN"), 32):
        return False
    # 带这些词通常是一个新的问题，不当作“澄清回答”合并。
    if re.search(r"(怎么|如何|是否|能不能|可以吗|\?|？)", q, re.IGNORECASE):
        return False
    return True


def quick_should_clarify(
    query: str,
    history: list[dict[str, str]],
    pending_query: str,
) -> dict[str, Any]:
    """
    低成本规则快判：
    1) 能快速确定需要澄清 -> 直接澄清
    2) 能快速确定不需要澄清 -> 直接放行
    3) 边界场景 -> 交给 LLM 判断
    """
    query = (query or "").strip()
    pending_query = (pending_query or "").strip()

    if not query:
        return {
            "need_clarification": True,
            "should_invoke_llm": False,
            "reason": "empty_query",
            "normalized_query": query,
        }

    # 如果上一轮是澄清，且本轮像短回答，则将短回答合并回待检索问题。
    if pending_query and _looks_like_short_answer(query):
        return {
            "need_clarification": False,
            "should_invoke_llm": False,
            "reason": "clarification_answer_merged",
            "normalized_query": f"{pending_query}。补充信息：{query}",
        }

    if _env_bool("QUERY_CLARIFY_FORCE_LLM", False):
        return {
            "need_clarification": False,
            "should_invoke_llm": True,
            "reason": "force_llm",
            "normalized_query": query,
        }

    # 超短问题通常缺乏可检索主体，直接进入澄清。
    if len(query) <= 2:
        return {
            "need_clarification": True,
            "should_invoke_llm": False,
            "reason": "query_too_short",
            "normalized_query": query,
        }

    # 无历史且出现强指代时，规则可直接判定需要澄清。
    if _REFERENTIAL_PATTERN.search(query) and not history:
        return {
            "need_clarification": True,
            "should_invoke_llm": False,
            "reason": "reference_without_history",
            "normalized_query": query,
        }

    # 有历史时出现“这个药/它”等指代，优先交给 rewrite 去补全检索主体。
    # 这样可显著减少“明明已有上下文却还追问”的过度澄清。
    if _REFERENTIAL_PATTERN.search(query) and history:
        return {
            "need_clarification": False,
            "should_invoke_llm": False,
            "reason": "reference_with_history_defer_to_rewrite",
            "normalized_query": query,
        }

    # 这类短泛化问句高概率缺信息，交给 LLM 做细判，避免误伤。
    if len(query) <= 12 and (_REFERENTIAL_PATTERN.search(query) or _AMBIGUOUS_PATTERN.search(query)):
        return {
            "need_clarification": False,
            "should_invoke_llm": True,
            "reason": "possible_ambiguous_query",
            "normalized_query": query,
        }

    return {
        "need_clarification": False,
        "should_invoke_llm": False,
        "reason": "query_clear",
        "normalized_query": query,
    }


async def clarify_with_llm(
    query: str,
    history: list[dict[str, str]],
    timeout_ms: int,
) -> dict[str, Any]:
    history_text = "\n".join(
        f"- [{item.get('role', 'unknown')}] {item.get('content', '')}" for item in history
    ).strip()
    prompt = f"""
你是“检索前澄清判断器”。
目标：判断当前问题是否信息不足，若不足请给出简洁反问以收集缺失信息。

规则：
1. 仅当问题确实缺关键检索信息时，need_clarification=true。
2. 若信息已足够，need_clarification=false，clarification_question 置空字符串。
3. 不要编造事实，不要替用户补不存在的信息。
4. 若历史中已明确了主体（如具体药名/病名），应优先判定为无需澄清。
5. 只输出 JSON，不要输出解释文字。

输出 JSON schema:
{{
  "need_clarification": true/false,
  "clarification_question": "string",
  "normalized_query": "string",
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
        "[ClarifyLLM] using model="
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

    need_clarification = bool(data.get("need_clarification", False))
    clarification_question = str(data.get("clarification_question", "") or "").strip()
    normalized_query = str(data.get("normalized_query", "") or "").strip() or query
    reason = str(data.get("reason", "") or "").strip() or "llm_decision"
    confidence = _safe_float(data.get("confidence", 0.0), 0.0)

    if need_clarification and not clarification_question:
        clarification_question = _default_clarification_question(query)
        reason = "empty_clarification_question"
        confidence = 0.0

    return {
        "need_clarification": need_clarification,
        "clarification_question": clarification_question,
        "normalized_query": normalized_query,
        "reason": reason,
        "confidence": confidence,
    }


async def clarify_query(
    messages: Sequence[BaseMessage],
    summary: str,
    query: str,
    pending_query: str = "",
    rounds: int = 3,
) -> ClarifyResult:
    query = (query or "").strip()
    pending_query = (pending_query or "").strip()

    if not query:
        return ClarifyResult(
            need_clarification=True,
            clarification_question=_default_clarification_question(query),
            reason="empty_query",
            confidence=1.0,
            normalized_query=query,
            pending_query=query,
        )

    if not _env_bool("QUERY_CLARIFY_ENABLED", True):
        return ClarifyResult(
            need_clarification=False,
            clarification_question="",
            reason="clarify_disabled",
            confidence=0.0,
            normalized_query=query,
            pending_query="",
        )

    history = build_history_window(messages=messages, summary=summary, rounds=rounds)
    quick = quick_should_clarify(query=query, history=history, pending_query=pending_query)

    if quick["need_clarification"]:
        return ClarifyResult(
            need_clarification=True,
            clarification_question=_default_clarification_question(query),
            reason=str(quick.get("reason") or "quick_need_clarification"),
            confidence=0.8,
            normalized_query=str(quick.get("normalized_query") or query),
            pending_query=query,
        )

    if not quick["should_invoke_llm"]:
        return ClarifyResult(
            need_clarification=False,
            clarification_question="",
            reason=str(quick.get("reason") or "quick_no_clarification"),
            confidence=0.0,
            normalized_query=str(quick.get("normalized_query") or query),
            pending_query="",
        )

    timeout_ms = _safe_int(os.getenv("QUERY_CLARIFY_TIMEOUT_MS"), 8000)
    try:
        llm_result = await clarify_with_llm(
            query=query,
            history=history,
            timeout_ms=timeout_ms,
        )
    except Exception as exc:
        return ClarifyResult(
            need_clarification=False,
            clarification_question="",
            reason=f"llm_failed:{type(exc).__name__}",
            confidence=0.0,
            normalized_query=query,
            pending_query="",
        )

    need_clarification = bool(llm_result.get("need_clarification", False))
    clarification_question = str(llm_result.get("clarification_question", "") or "").strip()
    normalized_query = str(llm_result.get("normalized_query", "") or "").strip() or query
    reason = str(llm_result.get("reason", "") or "").strip() or "llm_decision"
    confidence = _safe_float(llm_result.get("confidence", 0.0), 0.0)

    if need_clarification and not clarification_question:
        clarification_question = _default_clarification_question(query)
        reason = "empty_clarification_question"
        confidence = 0.0

    return ClarifyResult(
        need_clarification=need_clarification,
        clarification_question=clarification_question,
        reason=reason,
        confidence=confidence,
        normalized_query=normalized_query,
        pending_query=query if need_clarification else "",
    )
