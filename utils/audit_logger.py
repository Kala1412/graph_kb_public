import json
from typing import Any

from fastapi import Request

from database import AsyncSessionLocal
from models import AuditLog, User


async def log_audit_event(
    action: str,
    actor: User | None,
    resource_type: str,
    resource_id: str | None,
    resource_name: str | None,
    status: str,
    detail: dict | None,
    request: Request | None = None,
):
    try:
        actor_id = getattr(actor, "id", None) if actor else None
        actor_username = getattr(actor, "username", None) if actor else None

        ip = None
        user_agent = None
        if request is not None:
            ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        detail_json = json.dumps(detail, ensure_ascii=False) if detail else None

        async with AsyncSessionLocal() as db:
            log = AuditLog(
                actor_id=actor_id,
                actor_username=actor_username,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                resource_name=resource_name,
                status=status,
                detail=detail_json,
                ip=ip,
                user_agent=user_agent,
            )
            db.add(log)
            await db.commit()
    except Exception:
        return
