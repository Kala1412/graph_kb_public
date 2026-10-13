import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas_likes_dto
from database import get_db
from utils.audit_logger import log_audit_event
from utils.auth_midware import get_current_user, is_admin
from utils.medical_profile_utils import (
    normalize_record_source,
    normalize_record_type,
    upsert_medical_profile_record,
)


medical_profiles = APIRouter(
    prefix="/medical-profiles",
    tags=["Medical Profiles"],
)


def _clean_content(content: str | None) -> str:
    cleaned = str(content or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="病症状况内容不能为空")
    return cleaned


def _effective_target_user_id(
    requested_user_id: int | None,
    current_user: models.User,
) -> int:
    # 普通用户仅操作自己的档案；管理员可指定其他 user_id。
    if is_admin(current_user):
        return requested_user_id or current_user.id
    return current_user.id


async def _get_record_or_404(
    record_id: int,
    db: AsyncSession,
    current_user: models.User,
) -> models.UserMedicalProfileRecord:
    record = await db.get(models.UserMedicalProfileRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="病症状况记录不存在")
    if not is_admin(current_user) and record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该病症状况记录")
    return record


@medical_profiles.get("/", response_model=schemas_likes_dto.MedicalProfileRecordListResponse)
async def list_medical_profile_records(
    user_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 按更新时间倒序返回，前端使用首条记录展示最近摘要。
    target_user_id = _effective_target_user_id(user_id, current_user)

    base_stmt = select(models.UserMedicalProfileRecord).where(
        models.UserMedicalProfileRecord.user_id == target_user_id
    )
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    stmt = (
        base_stmt
        .order_by(
            models.UserMedicalProfileRecord.updated_at.desc(),
            models.UserMedicalProfileRecord.id.desc(),
        )
        .offset(skip)
        .limit(limit)
    )

    total = (await db.execute(total_stmt)).scalar() or 0
    items = (await db.execute(stmt)).scalars().all()
    return {"items": items, "total": total}


@medical_profiles.get("/{record_id}", response_model=schemas_likes_dto.MedicalProfileRecordResponse)
async def get_medical_profile_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await _get_record_or_404(record_id, db, current_user)


@medical_profiles.post("/", response_model=schemas_likes_dto.MedicalProfileRecordResponse)
async def create_medical_profile_record(
    payload: schemas_likes_dto.MedicalProfileRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    target_user_id = _effective_target_user_id(payload.user_id, current_user)
    content = _clean_content(payload.content)

    try:
        record, _ = await upsert_medical_profile_record(
            db=db,
            user_id=target_user_id,
            record_type=normalize_record_type(payload.record_type.value),
            content=content,
            source=normalize_record_source(payload.source.value),
        )
        # upsert 内部可能返回“已有记录被更新来源”的情况，
        # 所以这里统一 commit 后 refresh，拿到最终可返回给前端的对象。
        await db.commit()
        await db.refresh(record)

        await log_audit_event(
            action="medical_profile.create",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(record.id),
            resource_name=record.content[:80],
            status="success",
            detail={"user_id": target_user_id, "record_type": record.record_type, "source": record.source},
            request=request,
        )
        return record
    except HTTPException as exc:
        await log_audit_event(
            action="medical_profile.create",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=None,
            resource_name=None,
            status="failed",
            detail={"user_id": target_user_id, "error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="medical_profile.create",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=None,
            resource_name=None,
            status="failed",
            detail={"user_id": target_user_id, "error": str(exc)},
            request=request,
        )
        raise


@medical_profiles.put("/{record_id}", response_model=schemas_likes_dto.MedicalProfileRecordResponse)
async def update_medical_profile_record(
    record_id: int,
    payload: schemas_likes_dto.MedicalProfileRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    try:
        record = await _get_record_or_404(record_id, db, current_user)
        # 对 update 接口做“部分更新”兼容：
        # 前端没传的字段，默认沿用旧值；传了再进入归一化/清洗流程。
        next_record_type = normalize_record_type(
            payload.record_type.value if payload.record_type is not None else record.record_type
        )
        next_content = _clean_content(payload.content if payload.content is not None else record.content)
        next_source = normalize_record_source(payload.source.value if payload.source is not None else record.source)

        # 更新前按用户、分类、内容查重，避免产生重复档案。
        duplicate_stmt = select(models.UserMedicalProfileRecord).where(
            models.UserMedicalProfileRecord.user_id == record.user_id,
            models.UserMedicalProfileRecord.record_type == next_record_type,
            models.UserMedicalProfileRecord.content == next_content,
            models.UserMedicalProfileRecord.id != record.id,
        )
        duplicate_records = (await db.execute(duplicate_stmt)).scalars().all()

        if duplicate_records:
            # 发生重复时保留最近更新记录，更新来源并合并其余重复项。
            duplicate_records = sorted(
                duplicate_records,
                key=lambda item: (
                    getattr(item, "updated_at", None) or getattr(item, "created_at", None) or datetime.datetime.min,
                    getattr(item, "id", 0),
                ),
                reverse=True,
            )
            primary_duplicate = duplicate_records[0]
            primary_duplicate.source = next_source
            primary_duplicate.updated_at = datetime.datetime.utcnow()
            for extra_duplicate in duplicate_records[1:]:
                await db.delete(extra_duplicate)
            await db.delete(record)
            await db.commit()
            await db.refresh(primary_duplicate)
            result = primary_duplicate
        else:
            record.record_type = next_record_type
            record.content = next_content
            record.source = next_source
            record.updated_at = datetime.datetime.utcnow()
            await db.commit()
            await db.refresh(record)
            result = record

        await log_audit_event(
            action="medical_profile.update",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(result.id),
            resource_name=result.content[:80],
            status="success",
            detail={"user_id": result.user_id, "record_type": result.record_type, "source": result.source},
            request=request,
        )
        return result
    except HTTPException as exc:
        await log_audit_event(
            action="medical_profile.update",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(record_id),
            resource_name=None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="medical_profile.update",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(record_id),
            resource_name=None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


@medical_profiles.delete("/{record_id}")
async def delete_medical_profile_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    try:
        # 删除前先取到记录本体，除了权限校验之外，
        # 还要提前拿到一份 resource_name，用于删除后写审计日志。
        record = await _get_record_or_404(record_id, db, current_user)
        resource_name = record.content[:80]
        await db.delete(record)
        await db.commit()

        await log_audit_event(
            action="medical_profile.delete",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(record_id),
            resource_name=resource_name,
            status="success",
            detail={"user_id": record.user_id},
            request=request,
        )
        return {"message": "删除成功"}
    except HTTPException as exc:
        await log_audit_event(
            action="medical_profile.delete",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(record_id),
            resource_name=None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="medical_profile.delete",
            actor=current_user,
            resource_type="medical_profile",
            resource_id=str(record_id),
            resource_name=None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise
