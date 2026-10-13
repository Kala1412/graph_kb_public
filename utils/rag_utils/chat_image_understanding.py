import asyncio
import base64
import io
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Sequence

from fastapi import UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from langchain_core.messages import HumanMessage

from utils.llm_client import llm_client
from utils.minio_client import minio_handler


def _env_bool(key: str, default: bool) -> bool:
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


def _normalize_filename(name: str, fallback_ext: str = ".jpg") -> str:
    raw_name = os.path.basename(name or "image")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    if "." not in safe_name:
        safe_name = f"{safe_name}{fallback_ext}"
    return safe_name


def _build_minio_file_url(object_name: str) -> str:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9010")
    secure = os.getenv("MINIO_SECURE", "False").lower() == "true"
    scheme = "https" if secure else "http"
    return f"{scheme}://{endpoint}/{minio_handler.bucket_name}/{object_name}"


def build_attachment_display_url(object_name: str, fallback_url: str | None = None) -> str | None:
    """
    为聊天图片返回可访问 URL。
    优先返回预签名地址（私有桶可访问），失败时退回原始 URL，避免消息渲染直接报错。
    """
    if not object_name:
        return fallback_url
    try:
        expires_seconds = max(60, _env_int("CHAT_IMAGE_PRESIGNED_EXPIRE_SECONDS", 7 * 24 * 3600))
        return minio_handler.client.presigned_get_object(
            minio_handler.bucket_name,
            object_name,
            expires=timedelta(seconds=expires_seconds),
        )
    except Exception:
        return fallback_url


def _get_allowed_mime_types() -> set[str]:
    raw = os.getenv("CHAT_IMAGE_ALLOWED_MIME", "image/jpeg,image/png,image/webp")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_upload_file_obj(value: Any) -> bool:
    """
    兼容识别 FastAPI / Starlette 的上传文件对象。
    说明：路由层可能透传 Starlette UploadFile；这里只要是“有文件名+可 read”的对象就接受，
    避免跨版本类型差异导致图片被误判为无效，从而 has_images=false。
    """
    if isinstance(value, (UploadFile, StarletteUploadFile)):
        return True
    return hasattr(value, "filename") and hasattr(value, "read")


@dataclass
class ChatImageProcessResult:
    has_images: bool
    image_count: int
    attachments: list[dict[str, Any]]
    effective_query: str
    image_summary: str
    understanding_status: str
    understanding_reason: str


async def _understand_images_with_llm(
    *,
    user_query: str,
    image_payloads: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """
    多模态直读：从图片提取“可检索文本信号”。
    这里只抽取图片里看得见的信息，不新增事实，输出给检索链路做 query 增强。
    """
    model = llm_client.get_vision_model()
    if model is None:
        return {
            "status": "failed",
            "reason": "vision_model_unavailable",
            "query": "",
            "summary": "",
            "confidence": 0.0,
        }

    image_parts = []
    for item in image_payloads:
        data = item["bytes"]
        content_type = item["content_type"]
        b64 = base64.b64encode(data).decode("ascii")
        data_url = f"data:{content_type};base64,{b64}"
        image_parts.append({"type": "image_url", "image_url": {"url": data_url}})

    prompt = (
        "你是医疗问答系统的图像信息提取器。请仅根据图片可见内容提取检索信号，不要编造。"
        "返回严格 JSON："
        '{"query":"用于知识库检索的一句话","summary":"图片关键信息摘要","confidence":0~1,"reason":"判断依据"}'
        "。如果图片信息不足，query 置空字符串。"
        f"\n用户原始文本（可能为空）：{user_query or '(empty)'}"
    )

    try:
        timeout_ms = max(1000, _env_int("CHAT_IMAGE_VISION_TIMEOUT_MS", 12000))
        model_info = llm_client.get_vision_model_info()
        print(
            "[ImageLLM] using model="
            f"{model_info.get('model_id') or '(none)'}, "
            f"base_url={model_info.get('base_url') or '(none)'}, "
            f"request_timeout_ms={model_info.get('request_timeout_ms')}"
        )
        response = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content=[{"type": "text", "text": prompt}, *image_parts])]),
            timeout=max(0.1, timeout_ms / 1000),
        )
        raw = _extract_json_block(str(response.content or ""))
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("vision result is not json object")

        return {
            "status": "success",
            "reason": str(data.get("reason") or "vision_success"),
            "query": str(data.get("query") or "").strip(),
            "summary": str(data.get("summary") or "").strip(),
            "confidence": _safe_float(data.get("confidence", 0.0), 0.0),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "reason": f"vision_failed:{type(exc).__name__}",
            "query": "",
            "summary": "",
            "confidence": 0.0,
        }


def _build_effective_query(user_query: str, image_query: str) -> str:
    user_query = (user_query or "").strip()
    image_query = (image_query or "").strip()

    # 关键设计：保留用户原文语义，同时把图像信号拼接到“检索 query”里，
    # 不回写用户原始输入，以免前端聊天记录被机器改写。
    if user_query and image_query:
        return f"{user_query}\n\n【图像补充】{image_query}"
    if user_query:
        return user_query
    if image_query:
        return image_query
    return "请结合用户上传的图片，提取可用于医疗知识检索的关键信息。"


async def process_chat_images(
    *,
    query: str,
    image_files: Sequence[UploadFile],
    user_id: int,
    thread_id: str,
) -> ChatImageProcessResult:
    user_query = (query or "").strip()
    # 不强依赖 filename 非空：
    # 某些浏览器/Blob 场景下文件对象可能没有稳定文件名，但二进制与 content_type 依然有效。
    # 这里先接收，再在后续上传阶段使用默认文件名兜底。
    files = [f for f in (image_files or []) if _is_upload_file_obj(f)]
    print(f"[ChatImage] received={len(image_files or [])}, accepted={len(files)}")

    if not files:
        return ChatImageProcessResult(
            has_images=False,
            image_count=0,
            attachments=[],
            effective_query=user_query,
            image_summary="",
            understanding_status="skipped_no_images",
            understanding_reason="no_images",
        )

    if not _env_bool("CHAT_IMAGE_ENABLED", True):
        raise ValueError("当前服务未开启聊天图片上传功能")

    max_count = max(1, _env_int("CHAT_IMAGE_MAX_COUNT", 3))
    if len(files) > max_count:
        raise ValueError(f"最多上传 {max_count} 张图片")

    max_size_bytes = max(1, _env_int("CHAT_IMAGE_MAX_SIZE_MB", 5)) * 1024 * 1024
    allowed_types = _get_allowed_mime_types()

    image_payloads: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    now_ms = int(time.time() * 1000)

    for idx, file in enumerate(files):
        content_type = str(file.content_type or "").lower()
        if content_type not in allowed_types:
            raise ValueError(f"不支持的图片类型: {content_type or 'unknown'}")

        data = await file.read()
        if not data:
            raise ValueError(f"图片内容为空: {file.filename or 'unnamed'}")
        if len(data) > max_size_bytes:
            raise ValueError(f"单张图片不能超过 {max_size_bytes // (1024 * 1024)}MB")

        ext = ".jpg"
        if content_type == "image/png":
            ext = ".png"
        elif content_type == "image/webp":
            ext = ".webp"
        safe_name = _normalize_filename(file.filename or f"image_{idx + 1}", fallback_ext=ext)
        object_name = f"chat/{user_id}/{thread_id}/{now_ms}_{uuid.uuid4().hex}_{safe_name}"

        # 先上传 MinIO，再写入消息附件元数据，保证数据库里的附件总是“可追溯对象”。
        minio_handler.client.put_object(
            minio_handler.bucket_name,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        minio_url = _build_minio_file_url(object_name)
        display_url = build_attachment_display_url(object_name, fallback_url=minio_url)

        attachments.append(
            {
                "id": uuid.uuid4().hex,
                "filename": file.filename or safe_name,
                "content_type": content_type,
                "size": len(data),
                "minio_object": object_name,
                "minio_url": minio_url,
                "display_url": display_url,
            }
        )
        image_payloads.append({"bytes": data, "content_type": content_type})

    vision = await _understand_images_with_llm(user_query=user_query, image_payloads=image_payloads)
    effective_query = _build_effective_query(user_query=user_query, image_query=str(vision.get("query") or ""))

    return ChatImageProcessResult(
        has_images=True,
        image_count=len(attachments),
        attachments=attachments,
        effective_query=effective_query,
        image_summary=str(vision.get("summary") or ""),
        understanding_status=str(vision.get("status") or "failed"),
        understanding_reason=str(vision.get("reason") or "vision_unknown"),
    )
