import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import AuditLog
from schemas_likes_dto import AuditLogListResponse, AuditLogResponse
from utils.auth_midware import require_admin


audit = APIRouter(prefix="/audit", tags=["审计日志"])


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


def _parse_date(value: str | None, is_end: bool = False) -> datetime.datetime | None:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.datetime.fromisoformat(value)
        date_obj = datetime.date.fromisoformat(value)
        if is_end:
            return datetime.datetime.combine(date_obj, datetime.time.max)
        return datetime.datetime.combine(date_obj, datetime.time.min)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式不正确，需为 YYYY-MM-DD 或 ISO 格式")


@audit.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    action: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    if page < 1:
        page = 1
    page_size = max(1, min(page_size, 200))

    start_dt = _parse_date(date_from, is_end=False)
    end_dt = _parse_date(date_to, is_end=True)

    stmt = select(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.actor_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if status:
        stmt = stmt.where(AuditLog.status == status)
    if start_dt:
        stmt = stmt.where(AuditLog.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(AuditLog.created_at <= end_dt)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                AuditLog.resource_name.ilike(like),
                AuditLog.actor_username.ilike(like),
            )
        )

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar() or 0

    data_stmt = (
        stmt.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(data_stmt)
    logs = result.scalars().all()

    items: list[AuditLogResponse] = []
    for log in logs:
        detail_data = None
        if log.detail:
            try:
                detail_data = json.loads(log.detail)
            except Exception:
                detail_data = {"raw": log.detail}
        items.append(
            AuditLogResponse(
                id=log.id,
                actor_id=log.actor_id,
                actor_username=log.actor_username,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                resource_name=log.resource_name,
                status=log.status,
                detail=detail_data,
                ip=log.ip,
                user_agent=log.user_agent,
                created_at=log.created_at,
            )
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
