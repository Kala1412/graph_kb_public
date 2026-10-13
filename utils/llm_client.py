import os
import sys

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(override=True)


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


class LLMClient:
    def __init__(self):
        self.chat_model = ChatOpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            model=os.getenv("LLM_MODEL_ID"),
            temperature=0.3
        )
        self._rewrite_model_info = {
            "enabled": False,
            "model_id": os.getenv("LLM_MODEL_ID") or "",
            "base_url": os.getenv("LLM_BASE_URL") or "",
            "request_timeout_ms": None,
            "max_retries": None,
        }
        self.rewrite_model = self._init_rewrite_model()
        self._vision_model_info = {
            "enabled": False,
            "model_id": "",
            "base_url": "",
            "request_timeout_ms": None,
            "max_retries": None,
        }
        self.vision_model = self._init_vision_model()

    def _init_rewrite_model(self):
        enabled = _env_bool("QUERY_REWRITE_LLM_ENABLED", False)
        if not enabled:
            return None

        api_key = os.getenv("QUERY_REWRITE_LLM_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = os.getenv("QUERY_REWRITE_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
        model_id = os.getenv("QUERY_REWRITE_LLM_MODEL_ID") or os.getenv("LLM_MODEL_ID")
        temperature = _env_float("QUERY_REWRITE_LLM_TEMPERATURE", 0.0)
        request_timeout_ms = max(1000, _env_int("QUERY_REWRITE_LLM_REQUEST_TIMEOUT_MS", 12000))
        max_retries = max(0, _env_int("QUERY_REWRITE_LLM_MAX_RETRIES", 1))
        max_tokens = _env_int("QUERY_REWRITE_LLM_MAX_TOKENS", 0)

        if not api_key or not base_url or not model_id:
            print("[LLM] rewrite model config incomplete, fallback to chat_model")
            return None

        kwargs = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model_id,
            "temperature": temperature,
            "request_timeout": max(1.0, request_timeout_ms / 1000),
            "max_retries": max_retries,
        }
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens

        try:
            model = ChatOpenAI(**kwargs)
            self._rewrite_model_info = {
                "enabled": True,
                "model_id": model_id,
                "base_url": base_url,
                "request_timeout_ms": request_timeout_ms,
                "max_retries": max_retries,
            }
            print(
                f"[LLM] rewrite model enabled: model={model_id}, "
                f"timeout_ms={request_timeout_ms}, retries={max_retries}"
            )
            return model
        except Exception as exc:
            print(f"[LLM] rewrite model init failed, fallback to chat_model: {exc}")
            return None

    def get_rewrite_model(self):
        return self.rewrite_model or self.chat_model

    def get_rewrite_model_info(self) -> dict:
        return dict(self._rewrite_model_info)

    def _init_vision_model(self):
        """
        独立初始化视觉模型，和主 chat/rewrite 模型解耦。
        这样图片理解超时/故障不会影响主问答链路的稳定性。
        """
        enabled = _env_bool("CHAT_IMAGE_VISION_ENABLED", False)
        if not enabled:
            return None

        api_key = os.getenv("CHAT_IMAGE_VISION_LLM_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = os.getenv("CHAT_IMAGE_VISION_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
        model_id = os.getenv("CHAT_IMAGE_VISION_LLM_MODEL_ID") or os.getenv("LLM_MODEL_ID")
        temperature = _env_float("CHAT_IMAGE_VISION_LLM_TEMPERATURE", 0.0)
        request_timeout_ms = max(1000, _env_int("CHAT_IMAGE_VISION_TIMEOUT_MS", 12000))
        max_retries = max(0, _env_int("CHAT_IMAGE_VISION_MAX_RETRIES", 1))
        max_tokens = _env_int("CHAT_IMAGE_VISION_LLM_MAX_TOKENS", 0)

        if not api_key or not base_url or not model_id:
            print("[LLM] vision model config incomplete, disable vision path")
            return None

        kwargs = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model_id,
            "temperature": temperature,
            "request_timeout": max(1.0, request_timeout_ms / 1000),
            "max_retries": max_retries,
        }
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens

        try:
            model = ChatOpenAI(**kwargs)
            self._vision_model_info = {
                "enabled": True,
                "model_id": model_id,
                "base_url": base_url,
                "request_timeout_ms": request_timeout_ms,
                "max_retries": max_retries,
            }
            print(
                f"[LLM] vision model enabled: model={model_id}, "
                f"timeout_ms={request_timeout_ms}, retries={max_retries}"
            )
            return model
        except Exception as exc:
            print(f"[LLM] vision model init failed, disable vision path: {exc}")
            return None

    def get_vision_model(self):
        return self.vision_model

    def get_vision_model_info(self) -> dict:
        return dict(self._vision_model_info)

    def generate_answer(self, query: str, context: list[str]) -> str:
        """
        RAG 的灵魂：拼装 Prompt
        """
        context_str = "\n\n".join(context)

        system_prompt = """你是一个专业的医疗知识助手。请基于以下提供的【参考资料】来回答用户的【问题】。
如果参考资料里没有提到的内容，请直接说"资料中未提及"，不要编造。
请用专业、简洁的中文回答。

【参考资料】：
{context}
""".format(context=context_str)

        user_prompt = f"【问题】：{query}"

        print("--- Sending Prompt into LLM ---")
        try:
            print(system_prompt)
        except UnicodeEncodeError:
            safe_prompt = system_prompt.encode(
                sys.stdout.encoding or "utf-8", errors="backslashreplace"
            ).decode(sys.stdout.encoding or "utf-8", errors="ignore")
            print(safe_prompt)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = self.chat_model.invoke(messages)
        return response.content

    async def generate_title(self, query: str) -> str:
        """
        仅基于用户提问生成简短标题（4-15个字）
        """
        prompt = f"""
        请将用户的以下提问总结为一个简短的标题（Title）。
        要求：
        1. 这里的场景是医疗知识库问答。
        2. 只要输出标题文本，不要包含引号、"标题："等前缀。
        3. 长度控制在 4 到 15 个汉字之间。
        4. 如果提问是无意义字符或单纯的问候（如"你好"），请生成"新对话"。

        用户提问：{query[:300]}
        """
        try:
            response = await self.chat_model.ainvoke([HumanMessage(content=prompt)])
            title = response.content.strip().replace('"', '').replace('“', '').replace('”', '').replace('《', '').replace('》', '')

            # 限制生成标题长度。
            if len(title) > 15:
                title = title[:15]

            return title
        except Exception as e:
            print(f"⚠️ 标题生成失败: {e}")
            return query[:15] + "..."

llm_client = LLMClient()
