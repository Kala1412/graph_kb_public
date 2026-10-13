import asyncio
import json

import uuid
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, UploadFile
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessageChunk, AIMessage
from typing import Any, Literal
from starlette.datastructures import UploadFile as StarletteUploadFile

from sqlalchemy.ext.asyncio import AsyncSession

from agents.simple_chatbot.rag_agent import medical_agent
from database import get_db, AsyncSessionLocal
from models import ChatSession, ChatMessage, User, MedicalProfileRecordSource
from sqlalchemy import select, update
from schemas_likes_dto import SessionResponse, MessageResponse
from utils.auth_midware import get_current_user, is_admin, require_kb_access
from utils.llm_client import llm_client
from utils.audit_logger import log_audit_event
from utils.medical_profile_utils import (
    parse_extracted_medical_profile_records,
    upsert_medical_profile_record,
)
from utils.rag_utils.chat_image_understanding import (
    build_attachment_display_url,
    process_chat_images,
)

agent_router = APIRouter(
    prefix="/agent",
    tags=["Agent Chat API"],
)

class AgentChatRequest(BaseModel):
    query: str
    kb_id: int | None = None
    thread_id: str = "default_user"
    top_k: int = 5
    mode: Literal["local", "global", "hybrid", "naive"] = "hybrid"
    enable_rerank: bool | None = None

class AgentChatResponse(BaseModel):
    answer: str
    intent: str
    context_preview: str | None = None
    rewrite_applied: bool | None = None
    original_query: str | None = None
    rewritten_query: str | None = None
    rewrite_reason: str | None = None
    rewrite_confidence: float | None = None
    clarification_needed: bool | None = None
    clarification_question: str | None = None
    clarification_reason: str | None = None
    clarification_confidence: float | None = None
    pending_query: str | None = None

class UpdateSessionRequest(BaseModel):
    title: str


def _parse_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"null", "none"}:
        return None
    try:
        return int(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"无效整数参数: {value}") from exc


def _parse_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"", "null", "none"}:
        return None
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise HTTPException(status_code=422, detail=f"无效布尔参数: {value}")


def _is_upload_file_obj(value: Any) -> bool:
    """
    兼容识别 FastAPI/Starlette 的 UploadFile 对象。
    说明：request.form() 返回对象在不同版本组合下可能不是 fastapi.UploadFile 的直接实例，
    若只用 isinstance(value, fastapi.UploadFile) 会把真实文件误过滤掉，导致 has_images=false。
    """
    if isinstance(value, (UploadFile, StarletteUploadFile)):
        return True
    # 兜底走鸭子类型：具备 filename 与异步 read 能力即可视为上传文件对象。
    return hasattr(value, "filename") and hasattr(value, "read")


async def _parse_stream_chat_request(http_request: Request) -> tuple[AgentChatRequest, list[UploadFile]]:
    """
    双协议解析入口：
    - 兼容旧版 application/json（历史前端不改即可继续工作）
    - 新增 multipart/form-data（支持图片文件上传）
    """
    content_type = (http_request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form = await http_request.form()
        query = str(form.get("query") or "")
        thread_id = str(form.get("thread_id") or "default_user").strip() or "default_user"
        kb_id = _parse_optional_int(form.get("kb_id"))
        top_k = _parse_optional_int(form.get("top_k")) or 5
        mode = str(form.get("mode") or "hybrid").strip() or "hybrid"
        enable_rerank = _parse_optional_bool(form.get("enable_rerank"))
        # 兼容 multipart 数组字段 images 和 images[]。
        image_items = list(form.getlist("images")) + list(form.getlist("images[]"))
        image_files = [item for item in image_items if _is_upload_file_obj(item)]

        try:
            parsed = AgentChatRequest(
                query=query,
                kb_id=kb_id,
                thread_id=thread_id,
                top_k=top_k,
                mode=mode,
                enable_rerank=enable_rerank,
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"请求参数校验失败: {exc}") from exc

        return parsed, image_files

    try:
        payload = await http_request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="请求体必须是 JSON 或 multipart/form-data") from exc

    try:
        parsed = AgentChatRequest(**payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"请求参数校验失败: {exc}") from exc

    return parsed, []


def _compose_user_message_content(query: str, has_images: bool) -> str:
    text = str(query or "").strip()
    if text:
        return text
    if has_images:
        return "【用户上传了图片】"
    return ""


def _with_attachment_display_urls(attachments: list | None) -> list:
    result: list[dict[str, Any]] = []
    for item in attachments or []:
        if not isinstance(item, dict):
            continue
        data = dict(item)
        object_name = str(data.get("minio_object") or "")
        fallback_url = data.get("minio_url")
        data["display_url"] = build_attachment_display_url(object_name, fallback_url=fallback_url)
        result.append(data)
    return result


def _build_stream_metadata_payload(
    *,
    intent: str,
    context: str,
    references: list,
    graph_path: list,
    kb_id: int | None,
    rewrite_applied: bool,
    original_query: str,
    rewritten_query: str,
    rewrite_reason: str,
    rewrite_confidence: float,
    clarification_needed: bool,
    clarification_question: str,
    clarification_reason: str,
    clarification_confidence: float,
    pending_query: str,
    has_images: bool = False,
    image_count: int = 0,
    effective_query: str = "",
    image_summary: str = "",
    image_understanding_status: str = "skipped_no_images",
    image_understanding_reason: str = "no_images",
    user_attachments: list | None = None,
) -> dict:
    context_preview = context[:100] + "..." if context else "No context"
    return {
        "type": "metadata",
        "intent": intent,
        "context_preview": context_preview,
        "references": references,
        "graph_path": graph_path,
        "kb_id": kb_id,
        "rewrite_applied": rewrite_applied,
        "original_query": original_query,
        "rewritten_query": rewritten_query,
        "rewrite_reason": rewrite_reason,
        "rewrite_confidence": rewrite_confidence,
        "clarification_needed": clarification_needed,
        "clarification_question": clarification_question,
        "clarification_reason": clarification_reason,
        "clarification_confidence": clarification_confidence,
        "pending_query": pending_query,
        # 图片参与检索的状态随 metadata 返回，便于展示和排障。
        "has_images": has_images,
        "image_count": image_count,
        "effective_query": effective_query,
        "image_summary": image_summary,
        "image_understanding_status": image_understanding_status,
        "image_understanding_reason": image_understanding_reason,
        "user_attachments": user_attachments or [],
    }


async def _log_intent_classification_audit(
    *,
    actor: User | None,
    http_request: Request | None,
    chat_request: AgentChatRequest,
    endpoint: Literal["chat", "chat_stream"],
    intent: str,
    status: Literal["success", "failed"],
    rewrite_applied: bool = False,
    rewritten_query: str | None = None,
    clarification_needed: bool = False,
    clarification_question: str | None = None,
    error: str | None = None,
) -> None:
    """
    在路由层记录“意图分类”审计日志。
    说明：这里能拿到 current_user 与 HTTP request(IP/UA)，而 graph 节点层不具备这些完整审计上下文。
    """
    # detail 字段用于管理端筛选与排障，尽量保持固定结构，便于后续检索和统计。
    detail = {
        "query": chat_request.query,
        "intent": intent,
        "kb_id": chat_request.kb_id,
        "thread_id": chat_request.thread_id,
        "endpoint": endpoint,
        "mode": chat_request.mode,
        "top_k": chat_request.top_k,
        "rewrite_applied": rewrite_applied,
        "rewritten_query": rewritten_query or chat_request.query,
        "clarification_needed": clarification_needed,
        "clarification_question": clarification_question or "",
    }
    if error:
        detail["error"] = error

    await log_audit_event(
        action="agent.intent.classify",
        actor=actor,
        resource_type="agent_chat",
        resource_id=str(chat_request.thread_id),
        resource_name=(chat_request.query or "")[:50] or None,
        status=status,
        detail=detail,
        request=http_request,
    )
async def update_session_title_task(thread_id: str, query: str):
    """后台任务：调用 LLM 生成标题并更新数据库"""
    print(f"🔄 [Background] 正在为会话 {thread_id} 生成标题...")

    new_title = await llm_client.generate_title(query)
    # 更新数据库 (注意：后台任务需要独立的 DB Session)
    async with AsyncSessionLocal() as db:
        try:
            stmt = (
                update(ChatSession)
                .where(ChatSession.id == thread_id)
                .values(title=new_title)
            )
            await db.execute(stmt)
            await db.commit()
            print(f"✅ [Background] 标题已更新为: {new_title}")
        except Exception as e:
            print(f"❌ [Background] 更新失败: {e}")



# 抽取结构化医疗事实，逐条写入 user_medical_profile_records。
async def extract_and_update_long_term_memory_task(user_id: int, query: str):
    """后台任务：抽取结构化病症状况事实并逐条写入明细表"""
    print("🔄 [Background] 正在分析用户发言以提取长期记忆...")
    extract_prompt = f"""
        分析用户输入: "{query}"
        任务：判断是否包含用户的长期医疗属性，如过敏史、疾病、症状、既往史、特殊体质、长期用药等。
        如果包含，请只返回 JSON 数组，不要输出任何额外说明。
        JSON 数组中的每一项格式为:
        {{"record_type": "allergy|disease|symptom|history|constitution|medication|other", "content": "精炼后的事实"}}
        例如:
        [{{"record_type":"allergy","content":"对头孢过敏"}},{{"record_type":"disease","content":"患有糖尿病"}}]
        如果不包含，返回 "NONE"。
        """
    try:
        response = await llm_client.chat_model.ainvoke([HumanMessage(content=extract_prompt)])
        extracted_facts = response.content.strip()
        # 解析模型 JSON 输出，过滤无效项并按分类、内容去重。
        parsed_records = parse_extracted_medical_profile_records(extracted_facts)

        if not parsed_records:
            print("📋 [LTM Extraction] 没有提取到该用户有价值的医疗事实")
            return

        print(f"🧬 [Background] 成功提取用户长期事实: {parsed_records}")

        async with AsyncSessionLocal() as db:
            # 逐条 upsert 相同事实，更新来源和时间，保留其他已有记录。
            for item in parsed_records:
                await upsert_medical_profile_record(
                    db=db,
                    user_id=user_id,
                    record_type=item["record_type"],
                    content=item["content"],
                    source=MedicalProfileRecordSource.CHAT_IMPORT,
                )
            await db.commit()
    except Exception as e:
        print(f"❌ [Background] 提取长期记忆失败: {e}")


@agent_router.post("/chat", response_model=AgentChatResponse)
async def chat_agent(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    http_request: Request = None,
):
    """
    智能体对话接口 (LangGraph驱动)
    - 自动判断意图 (闲聊 vs 检索)
    - 自动维护对话历史 (Memory)
    """
    print(f"\n🚀 [API] 收到请求: thread_id={request.thread_id}, query={request.query}")

    try:
        if request.kb_id:
            await require_kb_access(request.kb_id, db, current_user)
        final_state = await medical_agent.invoke_messages(
            messages=[HumanMessage(content=request.query)],
            thread_id=request.thread_id,
            kb_id=request.kb_id,
            top_k=request.top_k,
            mode=request.mode,
            enable_rerank=request.enable_rerank
        )

        last_message = final_state["messages"][-1]
        context = final_state.get("context", "")
        context_preview = context[:100] + "..." if context else "No context"
        intent = final_state.get("intent", "unknown")
        rewrite_applied = bool(final_state.get("rewrite_applied", False))
        original_query = str(final_state.get("original_query") or request.query)
        rewritten_query = str(final_state.get("retrieval_query") or request.query)
        rewrite_reason = str(final_state.get("rewrite_reason") or "")
        rewrite_confidence = float(final_state.get("rewrite_confidence") or 0.0)
        clarification_needed = bool(final_state.get("clarification_needed", False))
        clarification_question = str(final_state.get("clarification_question") or "")
        clarification_reason = str(final_state.get("clarification_reason") or "")
        clarification_confidence = float(final_state.get("clarification_confidence") or 0.0)
        pending_query = str(final_state.get("pending_query") or "")

        # 成功路径：记录本次请求的最终意图分类结果，便于管理端审计检索。
        await _log_intent_classification_audit(
            actor=current_user,
            http_request=http_request,
            chat_request=request,
            endpoint="chat",
            intent=intent,
            status="success",
            rewrite_applied=rewrite_applied,
            rewritten_query=rewritten_query,
            clarification_needed=clarification_needed,
            clarification_question=clarification_question,
        )

        return AgentChatResponse(
            answer=last_message.content,
            intent=intent,
            context_preview=context_preview,
            rewrite_applied=rewrite_applied,
            original_query=original_query,
            rewritten_query=rewritten_query,
            rewrite_reason=rewrite_reason,
            rewrite_confidence=rewrite_confidence,
            clarification_needed=clarification_needed,
            clarification_question=clarification_question,
            clarification_reason=clarification_reason,
            clarification_confidence=clarification_confidence,
            pending_query=pending_query,
        )
    except Exception as e:
        print(f"❌ [API] 处理请求时发生错误: {e}")
        # 失败兜底：即使主流程异常，也记录一次 failed 审计日志方便回溯。
        await _log_intent_classification_audit(
            actor=current_user,
            http_request=http_request,
            chat_request=request,
            endpoint="chat",
            intent="unknown",
            status="failed",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="内部服务器错误")


@agent_router.post("/chat/stream")
async def chat_agent_stream(
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        http_request: Request = None,
):
    """
    流式对话接口 (SSE)

    返回格式：
    event: start
    data: {"type": "start", "thread_id": "xxx"}

    event: token
    data: {"type": "token", "content": "你"}

    event: metadata
    data: {"type": "metadata", "intent": "search", "context_preview": "..."}

    event: done
    data: {"type": "done"}
    """
    chat_request, image_files = await _parse_stream_chat_request(http_request)
    request = chat_request
    if chat_request.kb_id:
        await require_kb_access(chat_request.kb_id, db, current_user)

    try:
        # 图片预处理阶段：把“原文 query”和“检索 query”拆开管理，防止前端显示文本被系统改写。
        print(f"[ChatImage] route parsed image_files={len(image_files)}")
        image_processing = await process_chat_images(
            query=chat_request.query,
            image_files=image_files,
            user_id=current_user.id,
            thread_id=chat_request.thread_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_message_content = _compose_user_message_content(
        query=chat_request.query,
        has_images=image_processing.has_images,
    )
    graph_query = str(image_processing.effective_query or user_message_content).strip()
    if not graph_query:
        raise HTTPException(status_code=422, detail="query 不能为空（至少输入文本或上传图片）")

    # 这里提前生成一份“可显示附件”，供 metadata 与历史接口统一展示。
    response_user_attachments = _with_attachment_display_urls(image_processing.attachments)

    # 查询该 thread_id 是否属于当前用户
    stmt = select(ChatSession).where(ChatSession.id == chat_request.thread_id)
    if not is_admin(current_user):
        stmt = stmt.where(ChatSession.user_id == current_user.id)
    session = (await db.execute(stmt)).scalar_one_or_none()

    if not session:
        print(f"🆕 发现新会话 ID: {request.thread_id}，正在创建...")

        temp_title = (user_message_content or graph_query)[:10]

        session = ChatSession(
            id=chat_request.thread_id,
            user_id=current_user.id,
            title=temp_title,
            kb_id=chat_request.kb_id
        )

        db.add(session)

        await db.commit()  # 先提交，确保 Session 存在，否则外键报错

        # 标题优先使用用户原文；仅图片场景下才回退到 effective_query，避免标题为空。
        background_tasks.add_task(update_session_title_task, request.thread_id, user_message_content or graph_query)

    # 附件单独保存，保留用户原文并支持结构化回放。
    user_msg = ChatMessage(
        session_id=request.thread_id,
        role="user",
        content=user_message_content,
        attachments_json=json.dumps(image_processing.attachments, ensure_ascii=False)
        if image_processing.attachments else None,
    )
    db.add(user_msg)
    await db.commit()

    # 异步抽取用户原文中的医疗事实，供后续对话加载长期画像。
    background_tasks.add_task(extract_and_update_long_term_memory_task, current_user.id, user_message_content)

    # 防重复：同一个流式请求只写一条意图分类审计日志（success 或 failed 二选一）。
    intent_audit_logged = False

    async def event_generator():
        """SSE 事件生成器"""
        nonlocal intent_audit_logged
        try:
            yield f"event: start\n"
            yield f"data: {json.dumps({'type': 'start', 'thread_id': request.thread_id}, ensure_ascii=False)}\n\n"

            accumulated_content = ""
            intent = None
            context = None
            stream_intent = None
            clarify_token_sent = False

            # 生成一个明确的消息ID，保证后续 RemoveMessage 绝对生效
            msg_id = str(uuid.uuid4())
            # 允许澄清节点透传 token，避免前端只收到 start 事件。
            allowed_stream_nodes = {"rag_generate", "pure_chat", "clarify_generate"}
            async for msg, metadata in medical_agent.stream_messages(
                    messages=[HumanMessage(content=graph_query,id=msg_id)],
                    thread_id=request.thread_id,
                    kb_id=request.kb_id,
                    top_k=request.top_k,
                    mode=request.mode,
                    enable_rerank=request.enable_rerank,
                    user_id=current_user.id
            ):
                node_name = None
                if isinstance(metadata, dict):
                    node_name = metadata.get("langgraph_node") or metadata.get("node")
                if node_name and node_name not in allowed_stream_nodes:
                    continue
                if node_name == "rag_generate":
                    stream_intent = "search"
                elif node_name == "pure_chat":
                    stream_intent = "chat"
                elif node_name == "clarify_generate":
                    stream_intent = "search"

                # 1) 常规流式节点：AIMessageChunk（逐 token）
                if isinstance(msg, AIMessageChunk):
                    # 内容可能是字符串或字典，需要安全提取
                    token_content = msg.content if isinstance(msg.content, str) else ""

                    if token_content:
                        accumulated_content += token_content

                        yield f"event: token\n"
                        yield f"data: {json.dumps({'type': 'token', 'content': token_content}, ensure_ascii=False)}\n\n"
                        print(f"📤 Token: {token_content}")
                # 2) 澄清节点可能直接产出完整 AIMessage（不是 chunk）
                elif node_name == "clarify_generate" and isinstance(msg, AIMessage):
                    token_content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
                    # 澄清问题通常只需发送一次，避免重复追加。
                    if token_content and not clarify_token_sent:
                        clarify_token_sent = True
                        accumulated_content += token_content
                        yield f"event: token\n"
                        yield f"data: {json.dumps({'type': 'token', 'content': token_content}, ensure_ascii=False)}\n\n"
                        print(f"[ClarifyToken] {token_content}")

            print(f"\n✅ 流式输出完成，总计 {len(accumulated_content)} 字符")

            # 获取最终状态（用于提取 intent / context / references）
            references = []
            graph_path = []
            context = ""
            final_values = {}
            rewrite_applied = False
            original_query = graph_query
            rewritten_query = graph_query
            rewrite_reason = ""
            rewrite_confidence = 0.0
            clarification_needed = False
            clarification_question = ""
            clarification_reason = ""
            clarification_confidence = 0.0
            pending_query = ""

            try:
                intent = stream_intent or ("search" if request.kb_id else "chat")

                graph = await medical_agent.get_graph()
                state_snapshot = await graph.aget_state({"configurable": {"thread_id": request.thread_id}})
                if state_snapshot and state_snapshot.values:
                    final_values = state_snapshot.values

                if final_values:
                    intent = final_values.get("intent") or intent
                    context = final_values.get("context", "") or ""
                    references = final_values.get("references") or []
                    graph_path = final_values.get("graph_path") or []
                    rewrite_applied = bool(final_values.get("rewrite_applied", False))
                    original_query = str(final_values.get("original_query") or graph_query)
                    rewritten_query = str(final_values.get("retrieval_query") or graph_query)
                    rewrite_reason = str(final_values.get("rewrite_reason") or "")
                    rewrite_confidence = float(final_values.get("rewrite_confidence") or 0.0)
                    clarification_needed = bool(final_values.get("clarification_needed", False))
                    clarification_question = str(final_values.get("clarification_question") or "")
                    clarification_reason = str(final_values.get("clarification_reason") or "")
                    clarification_confidence = float(final_values.get("clarification_confidence") or 0.0)
                    pending_query = str(final_values.get("pending_query") or "")

                if intent == "search" and request.kb_id and not clarification_needed and not references:
                    retrieval_state = await medical_agent._node_retrieve({
                        "messages": [HumanMessage(content=graph_query)],
                        "kb_id": request.kb_id,
                        "top_k": request.top_k,
                        "mode": request.mode,
                        "enable_rerank": request.enable_rerank,
                        "original_query": original_query,
                        "retrieval_query": rewritten_query,
                        "rewrite_applied": rewrite_applied,
                        "rewrite_reason": rewrite_reason,
                        "rewrite_confidence": rewrite_confidence,
                    })
                    context = retrieval_state.get("context", "") or context
                    references = retrieval_state.get("references") or references
                    graph_path = retrieval_state.get("graph_path") or graph_path
                    rewrite_applied = bool(retrieval_state.get("rewrite_applied", rewrite_applied))
                    original_query = str(retrieval_state.get("original_query") or original_query)
                    rewritten_query = str(retrieval_state.get("retrieval_query") or rewritten_query)
                    rewrite_reason = str(retrieval_state.get("rewrite_reason") or rewrite_reason)
                    rewrite_confidence = float(retrieval_state.get("rewrite_confidence") or rewrite_confidence)
            except Exception as e:
                print(f"⚠️ 获取最终状态失败: {e}")
                intent = stream_intent or ("search" if request.kb_id else "chat")
                context = ""
                references = []
                graph_path = []
                rewrite_applied = False
                original_query = graph_query
                rewritten_query = graph_query
                rewrite_reason = "metadata_fallback"
                rewrite_confidence = 0.0
                clarification_needed = False
                clarification_question = ""
                clarification_reason = "metadata_fallback"
                clarification_confidence = 0.0
                pending_query = ""

            # 兜底：若澄清模式未产出 token，则直接把澄清问题补发给前端。
            if clarification_needed and not accumulated_content and clarification_question:
                accumulated_content = clarification_question
                yield f"event: token\n"
                yield f"data: {json.dumps({'type': 'token', 'content': clarification_question}, ensure_ascii=False)}\n\n"
                print(f"[ClarifyFallbackToken] {clarification_question}")


            if accumulated_content:
                ai_msg = ChatMessage(
                    session_id=request.thread_id,
                    role="assistant",
                    content=accumulated_content,
                    references_json=json.dumps(references, ensure_ascii=False) if references else None,
                    graph_path_json=json.dumps(graph_path, ensure_ascii=False) if graph_path else None,
                )
                db.add(ai_msg)
                await db.commit()

            # 成功路径：在流式请求完成后记录最终意图分类，且只记录一次。
            if not intent_audit_logged:
                await _log_intent_classification_audit(
                    actor=current_user,
                    http_request=http_request,
                    chat_request=request,
                    endpoint="chat_stream",
                    intent=intent or "unknown",
                    status="success",
                    rewrite_applied=rewrite_applied,
                    rewritten_query=rewritten_query,
                    clarification_needed=clarification_needed,
                    clarification_question=clarification_question,
                )
                intent_audit_logged = True

            yield f"event: metadata\n"
            metadata_payload = _build_stream_metadata_payload(
                intent=intent,
                context=context,
                references=references,
                graph_path=graph_path,
                kb_id=request.kb_id,
                rewrite_applied=rewrite_applied,
                original_query=original_query,
                rewritten_query=rewritten_query,
                rewrite_reason=rewrite_reason,
                rewrite_confidence=rewrite_confidence,
                clarification_needed=clarification_needed,
                clarification_question=clarification_question,
                clarification_reason=clarification_reason,
                clarification_confidence=clarification_confidence,
                pending_query=pending_query,
                has_images=image_processing.has_images,
                image_count=image_processing.image_count,
                effective_query=graph_query,
                image_summary=image_processing.image_summary,
                image_understanding_status=image_processing.understanding_status,
                image_understanding_reason=image_processing.understanding_reason,
                user_attachments=response_user_attachments,
            )
            yield f"data: {json.dumps(metadata_payload, ensure_ascii=False)}\n\n"
            yield f"event: done\n"
            yield f"data: {json.dumps({'type': 'done', 'total_length': len(accumulated_content)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            print(f"❌ [Stream] 错误: {e}")
            import traceback
            traceback.print_exc()

            # 失败兜底：流式中途异常时写 failed 审计日志，且避免与成功日志重复写入。
            if not intent_audit_logged:
                await _log_intent_classification_audit(
                    actor=current_user,
                    http_request=http_request,
                    chat_request=request,
                    endpoint="chat_stream",
                    intent="unknown",
                    status="failed",
                    error=str(e),
                )
                intent_audit_logged = True

            await db.rollback()

            yield f"event: error\n"
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@agent_router.get("/sessions", response_model=list[SessionResponse])
async def get_sessions(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    获取侧边栏会话列表
    - 仅返回属于当前用户的会话
    - 按创建时间倒序排列（最新的在最上面）
    """
    stmt = select(ChatSession).order_by(ChatSession.created_at.desc())
    if not is_admin(current_user):
        stmt = stmt.where(ChatSession.user_id == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@agent_router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
        session_id: str,
        db: AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user)
):
    """
    加载历史聊天记录
    """
    # 1. 安全检查：必须确认该会话属于当前用户，防止越权访问
    if is_admin(current_user):
        session = await db.get(ChatSession, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        stmt_check = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        )
        session_result = await db.execute(stmt_check)
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="无权访问该会话")

    # 2. 查询消息：按时间正序排列（从早到晚，符合聊天界面阅读习惯）
    stmt_msg = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )

    result = await db.execute(stmt_msg)
    records = result.scalars().all()

    # 历史附件动态生成展示链接，避免持久化已过期的 MinIO 预签名 URL。
    payload: list[dict[str, Any]] = []
    for msg in records:
        payload.append(
            {
                "role": msg.role,
                "content": msg.content,
                "references": msg.references,
                "graph_path": msg.graph_path,
                "attachments": _with_attachment_display_urls(msg.attachments),
                "created_at": msg.created_at,
            }
        )

    return payload

@agent_router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """删除整个会话及其聊天记录"""
    session = None
    try:
        # 检查所有权
        if is_admin(current_user):
            session = await db.get(ChatSession, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                raise HTTPException(status_code=403, detail="无权删除该会话")

        # (因为 models.py 里配置了 cascade="all, delete-orphan"，消息会自动连带删除)
        await db.delete(session)
        await db.commit()

        await log_audit_event(
            action="session.delete",
            actor=current_user,
            resource_type="session",
            resource_id=str(session_id),
            resource_name=session.title if session else None,
            status="success",
            detail={"user_id": session.user_id, "kb_id": session.kb_id} if session else {},
            request=request,
        )

        return {"status": "success", "message": "会话已删除"}
    except HTTPException as exc:
        await log_audit_event(
            action="session.delete",
            actor=current_user,
            resource_type="session",
            resource_id=str(session_id),
            resource_name=session.title if session else None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="session.delete",
            actor=current_user,
            resource_type="session",
            resource_id=str(session_id),
            resource_name=session.title if session else None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


@agent_router.put("/sessions/{session_id}")
async def update_session(
        session_id: str,
        request: UpdateSessionRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        http_request: Request = None
):
    try:
        stmt = update(ChatSession).where(ChatSession.id == session_id).values(title=request.title)
        if not is_admin(current_user):
            stmt = stmt.where(ChatSession.user_id == current_user.id)

        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")

        await log_audit_event(
            action="session.rename",
            actor=current_user,
            resource_type="session",
            resource_id=str(session_id),
            resource_name=request.title,
            status="success",
            detail={"new_title": request.title},
            request=http_request,
        )

        return {"message": "Title updated"}
    except HTTPException as exc:
        await log_audit_event(
            action="session.rename",
            actor=current_user,
            resource_type="session",
            resource_id=str(session_id),
            resource_name=request.title if request else None,
            status="failed",
            detail={"error": exc.detail},
            request=http_request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="session.rename",
            actor=current_user,
            resource_type="session",
            resource_id=str(session_id),
            resource_name=request.title if request else None,
            status="failed",
            detail={"error": str(exc)},
            request=http_request,
        )
        raise
