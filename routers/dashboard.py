from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from models import User, KnowledgeBase, KnowledgeFile, FileStatus, ChatSession, ChatMessage
import datetime
import asyncio
import os
import time

from pymilvus import connections
from langchain_core.messages import HumanMessage

from utils.minio_client import minio_handler
from utils.neo4j_service import neo4j_service
from utils.llm_client import llm_client
from utils.auth_midware import get_current_user, is_admin


dashboard = APIRouter(prefix="/dashboard", tags=["仪表盘相关接口"])


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


@dashboard.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取仪表盘统计数据（admin=全站，user=本人）"""
    # 统一通过身份分流统计口径：管理员看全站，普通用户只看本人，避免前端维护多套接口。
    admin_mode = is_admin(current_user)

    if admin_mode:
        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    else:
        # 普通用户口径下，用户数固定为当前账号本身。
        total_users = 1

    kb_count_stmt = select(func.count(KnowledgeBase.id))
    if not admin_mode:
        # 普通用户过滤条件：仅统计 owner_id=当前用户 的知识库。
        kb_count_stmt = kb_count_stmt.where(KnowledgeBase.owner_id == current_user.id)
    total_kb = (await db.execute(kb_count_stmt)).scalar() or 0

    file_count_stmt = (
        select(func.count(KnowledgeFile.id))
        .select_from(KnowledgeFile)
        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeFile.kb_id)
    )
    if not admin_mode:
        # 普通用户过滤条件：通过 KnowledgeBase.owner_id 限定文件归属。
        file_count_stmt = file_count_stmt.where(KnowledgeBase.owner_id == current_user.id)
    total_files = (await db.execute(file_count_stmt)).scalar() or 0

    file_storage_stmt = (
        select(func.sum(KnowledgeFile.file_size))
        .select_from(KnowledgeFile)
        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeFile.kb_id)
    )
    if not admin_mode:
        # 普通用户过滤条件：仅累计本人知识库下文件大小。
        file_storage_stmt = file_storage_stmt.where(KnowledgeBase.owner_id == current_user.id)
    total_storage = (await db.execute(file_storage_stmt)).scalar() or 0

    indexed_files_stmt = (
        select(func.count(KnowledgeFile.id))
        .select_from(KnowledgeFile)
        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeFile.kb_id)
        .where(KnowledgeFile.status == FileStatus.INDEXED)
    )
    if not admin_mode:
        # 普通用户过滤条件：仅统计本人知识库中的可用文件（status=indexed）。
        indexed_files_stmt = indexed_files_stmt.where(KnowledgeBase.owner_id == current_user.id)
    indexed_files = (await db.execute(indexed_files_stmt)).scalar() or 0

    session_count_stmt = select(func.count(ChatSession.id))
    if not admin_mode:
        # 普通用户过滤条件：只统计 user_id=当前用户 的会话。
        session_count_stmt = session_count_stmt.where(ChatSession.user_id == current_user.id)
    total_sessions = (await db.execute(session_count_stmt)).scalar() or 0

    message_count_stmt = (
        select(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
    )
    if not admin_mode:
        # 普通用户过滤条件：通过会话归属限制消息统计范围。
        message_count_stmt = message_count_stmt.where(ChatSession.user_id == current_user.id)
    total_messages = (await db.execute(message_count_stmt)).scalar() or 0

    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    questions_7d_stmt = (
        select(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatMessage.created_at >= seven_days_ago, ChatMessage.role == "user")
    )
    # questions_7d 口径固定为“用户提问次数”，只统计 role=user 的消息。
    if not admin_mode:
        # 普通用户过滤条件：ChatSession.user_id = 当前用户。
        questions_7d_stmt = questions_7d_stmt.where(ChatSession.user_id == current_user.id)
    questions_7d = (await db.execute(questions_7d_stmt)).scalar() or 0

    kb_files_stmt = (
        select(KnowledgeBase.name, func.count(KnowledgeFile.id))
        .join(KnowledgeFile, KnowledgeBase.id == KnowledgeFile.kb_id)
        .group_by(KnowledgeBase.id, KnowledgeBase.name)
    )
    if not admin_mode:
        # 普通用户过滤条件：仅展示本人知识库的文件分布。
        kb_files_stmt = kb_files_stmt.where(KnowledgeBase.owner_id == current_user.id)
    kb_files_query = await db.execute(kb_files_stmt)
    kb_file_distribution = [{"name": row[0], "value": row[1]} for row in kb_files_query.all()]

    status_stmt = (
        select(KnowledgeFile.status, func.count(KnowledgeFile.id))
        .select_from(KnowledgeFile)
        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeFile.kb_id)
        .group_by(KnowledgeFile.status)
    )
    if not admin_mode:
        # 普通用户过滤条件：仅统计本人知识库中的文件状态。
        status_stmt = status_stmt.where(KnowledgeBase.owner_id == current_user.id)
    status_result = await db.execute(status_stmt)
    status_rows = status_result.all()

    status_map = {
        FileStatus.UPLOADED: "已上传",
        FileStatus.PARSING: "解析中",
        FileStatus.PARSED: "已解析",
        FileStatus.INDEXING: "索引中",
        FileStatus.INDEXED: "可用",
        FileStatus.ERROR_PARSING: "解析失败",
        FileStatus.ERROR_INDEXING: "索引失败",
    }
    status_distribution = []
    status_counts = {
        FileStatus.UPLOADED: 0,
        FileStatus.PARSING: 0,
        FileStatus.PARSED: 0,
        FileStatus.INDEXING: 0,
        FileStatus.INDEXED: 0,
        FileStatus.ERROR_PARSING: 0,
        FileStatus.ERROR_INDEXING: 0,
    }
    for status_code, count in status_rows:
        normalized_code = status_code or "unknown"
        status_distribution.append(
            {"name": status_map.get(normalized_code, normalized_code), "value": count}
        )
        status_counts[normalized_code] = count

    # 告警字段用于管理员快速判断待处理和失败风险；total_files=0 时错误率回退为 0，避免除零异常。
    parsing_count = status_counts.get(FileStatus.PARSING, 0)
    indexing_count = status_counts.get(FileStatus.INDEXING, 0)
    error_count = status_counts.get(FileStatus.ERROR_PARSING, 0) + status_counts.get(
        FileStatus.ERROR_INDEXING, 0
    )
    error_rate = round((error_count / total_files), 4) if total_files > 0 else 0

    fourteen_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)

    file_trend_stmt = (
        select(func.date(KnowledgeFile.created_at), func.count(KnowledgeFile.id))
        .select_from(KnowledgeFile)
        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeFile.kb_id)
        .where(KnowledgeFile.created_at >= fourteen_days_ago)
        .group_by(func.date(KnowledgeFile.created_at))
    )
    if not admin_mode:
        # 普通用户过滤条件：仅统计本人知识库文件趋势。
        file_trend_stmt = file_trend_stmt.where(KnowledgeBase.owner_id == current_user.id)
    file_trend_query = await db.execute(file_trend_stmt)
    file_counts = {str(row[0]): row[1] for row in file_trend_query.all()}

    # 通过 session 归属过滤消息趋势，确保普通用户只看到自己的对话数据。
    msg_trend_stmt = (
        select(func.date(ChatMessage.created_at), func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatMessage.created_at >= fourteen_days_ago)
        .group_by(func.date(ChatMessage.created_at))
    )
    if not admin_mode:
        # 普通用户过滤条件：ChatSession.user_id = 当前用户。
        msg_trend_stmt = msg_trend_stmt.where(ChatSession.user_id == current_user.id)
    msg_trend_query = await db.execute(msg_trend_stmt)
    msg_counts = {str(row[0]): row[1] for row in msg_trend_query.all()}

    trend_data = []
    for i in range(14):
        date_str = str((datetime.datetime.utcnow() - datetime.timedelta(days=13 - i)).date())
        trend_data.append(
            {
                "date": date_str,
                "files": file_counts.get(date_str, 0),
                "messages": msg_counts.get(date_str, 0),
            }
        )

    return {
        "cards": {
            "total_users": total_users,
            "total_kb": total_kb,
            "total_files": total_files,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "storage_mb": round(total_storage / (1024 * 1024), 2),
            "questions_7d": questions_7d,
            "indexed_files": indexed_files,
        },
        "kb_file_distribution": kb_file_distribution,
        "status_distribution": status_distribution,
        "status_counts": status_counts,
        "alerts": {
            "parsing_count": parsing_count,
            "indexing_count": indexing_count,
            "error_count": error_count,
            "error_rate": error_rate,
        },
        "activity_trend": trend_data,
    }


def _millis(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


async def _check_milvus():
    def _sync_check():
        alias = "health_check"
        milvus_uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        token = os.getenv("MILVUS_TOKEN", "")
        start = time.perf_counter()
        try:
            if token:
                connections.connect(alias=alias, uri=milvus_uri, token=token)
            else:
                connections.connect(alias=alias, uri=milvus_uri)
            return True, _millis(start), "connected"
        finally:
            try:
                connections.disconnect(alias)
            except Exception:
                pass

    try:
        ok, latency_ms, message = await run_in_threadpool(_sync_check)
        return {"status": "up", "latency_ms": latency_ms, "message": message}
    except Exception as exc:
        return {"status": "down", "latency_ms": None, "message": str(exc)}


async def _check_neo4j():
    def _sync_check():
        start = time.perf_counter()
        with neo4j_service.driver.session() as session:
            session.run("RETURN 1 AS ok").single()
        return True, _millis(start), "connected"

    try:
        ok, latency_ms, message = await run_in_threadpool(_sync_check)
        return {"status": "up", "latency_ms": latency_ms, "message": message}
    except Exception as exc:
        return {"status": "down", "latency_ms": None, "message": str(exc)}


async def _check_minio():
    def _sync_check():
        start = time.perf_counter()
        exists = minio_handler.client.bucket_exists(minio_handler.bucket_name)
        return True, _millis(start), "bucket exists" if exists else "bucket missing"

    try:
        ok, latency_ms, message = await run_in_threadpool(_sync_check)
        return {"status": "up", "latency_ms": latency_ms, "message": message}
    except Exception as exc:
        return {"status": "down", "latency_ms": None, "message": str(exc)}


async def _check_llm():
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL_ID")
    if not base_url or not model:
        return {
            "status": "unknown",
            "latency_ms": None,
            "message": "missing LLM_BASE_URL/LLM_MODEL_ID",
        }

    start = time.perf_counter()
    try:
        await asyncio.wait_for(
            llm_client.chat_model.ainvoke([HumanMessage(content="ping")]),
            timeout=6,
        )
        return {"status": "up", "latency_ms": _millis(start), "message": "responded"}
    except Exception as exc:
        return {"status": "down", "latency_ms": None, "message": str(exc)}


@dashboard.get("/health")
async def get_dashboard_health():
    """系统依赖健康检查（Milvus/Neo4j/MinIO/LLM）"""
    results = await asyncio.gather(
        _check_milvus(),
        _check_neo4j(),
        _check_minio(),
        _check_llm(),
        return_exceptions=False,
    )

    services = [
        {"key": "milvus", "name": "Milvus", **results[0]},
        {"key": "neo4j", "name": "Neo4j", **results[1]},
        {"key": "minio", "name": "MinIO", **results[2]},
        {"key": "llm", "name": "LLM", **results[3]},
    ]

    return {
        "checked_at": datetime.datetime.utcnow().isoformat(),
        "services": services,
    }

