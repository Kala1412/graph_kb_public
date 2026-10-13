import io
import os
import re
import time
from datetime import timedelta

from fastapi import Depends, HTTPException, APIRouter, UploadFile, File, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas_likes_dto
from database import AsyncSessionLocal
from utils import security
from utils.auth_midware import require_admin, get_current_user
from utils.minio_client import minio_handler
from utils.audit_logger import log_audit_event

users = APIRouter(prefix="/users", tags=["用户相关接口"])

ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_AVATAR_SIZE = 5 * 1024 * 1024


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

# 用于确保文件名在MinIO中是安全的（没有特殊字符）并具有扩展名
def _normalize_minio_filename(name: str, fallback_ext: str = ".jpg") -> str:
    raw_name = os.path.basename(name or "avatar")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    if "." not in safe_name:
        safe_name = f"{safe_name}{fallback_ext}"
    return safe_name

# 用于构建访问MinIO对象的完整HTTP(S)URL
def _build_minio_file_url(object_name: str) -> str:
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9010")
    secure = os.getenv("MINIO_SECURE", "False").lower() == "true"
    scheme = "https" if secure else "http"
    return f"{scheme}://{endpoint}/{minio_handler.bucket_name}/{object_name}"

# 提取url名称，maker(minio_handler.bucket_name)之后的url链接部分
def _extract_object_name_from_url(url: str | None) -> str | None:
    if not url:
        return None
    marker = f"/{minio_handler.bucket_name}/"
    idx = url.find(marker)
    if idx < 0:
        return None
    return url[idx + len(marker):]

# 生成一个临时的预签名URL，有效期为7天。使得头像可以通过HTTPS临时访问，即使存储桶不是公开的
def _resolve_avatar_display_url(raw_avatar_url: str | None) -> str | None:
    if not raw_avatar_url:
        return None
    object_name = _extract_object_name_from_url(raw_avatar_url)
    if not object_name:
        return raw_avatar_url
    try:
        return minio_handler.client.presigned_get_object(
            minio_handler.bucket_name,
            object_name,
            expires=timedelta(days=7)
        )
    except Exception:
        return raw_avatar_url

# 将传入User对象(把用户头像avatar_url转成可访问的预签名链接)返回
def _user_me_payload(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "avatar_url": _resolve_avatar_display_url(user.avatar_url),
        "status": getattr(user, "status", "active"),
    }

@users.post("/", response_model=schemas_likes_dto.UserResponse)
async def create_user(
        user: schemas_likes_dto.UserCreate,
        db:AsyncSession= Depends(get_db)
):
    res = await db.execute(select(models.User).where(models.User.username == user.username))
    user_in_db = res.scalar_one_or_none()
    if user_in_db:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )

    new_user = models.User(
        username=user.username,
        email=user.email,
        role=user.role,
        password=security.get_password_hash(user.password),
        status=getattr(user, "status", "active")
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@users.get("/me", response_model=schemas_likes_dto.UserMeResponse)
async def get_my_profile(
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    db_user = await db.get(models.User, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_me_payload(db_user)


@users.put("/me/profile", response_model=schemas_likes_dto.UserProfileUpdateResponse)
async def update_my_profile(
        profile: schemas_likes_dto.UserProfileUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        request: Request = None
):
    try:
        db_user = await db.get(models.User, current_user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        input_data = profile.model_dump(exclude_unset=True)
        next_username = input_data.get("username")
        next_email = input_data.get("email")

        if next_username is not None:
            next_username = next_username.strip()
            if not next_username:
                raise HTTPException(status_code=400, detail="用户名不能为空")

        changed_username = False
        if next_username and next_username != db_user.username:
            exists = (
                await db.execute(
                    select(models.User).where(
                        models.User.username == next_username,
                        models.User.id != db_user.id
                    )
                )
            ).scalar_one_or_none()
            if exists:
                raise HTTPException(status_code=400, detail="用户名已存在")
            db_user.username = next_username
            changed_username = True

        if next_email is not None:
            db_user.email = next_email.strip() or None

        await db.commit()
        await db.refresh(db_user)

        await log_audit_event(
            action="user.profile.update",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=db_user.username,
            status="success",
            detail={"updated_fields": list(input_data.keys())},
            request=request,
        )

        return {
            "user": _user_me_payload(db_user),
            "require_relogin": changed_username
        }
    except HTTPException as exc:
        await log_audit_event(
            action="user.profile.update",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="user.profile.update",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


@users.put("/me/password")
async def change_my_password(
        payload: schemas_likes_dto.PasswordChangeRequest,
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        request: Request = None
):
    try:
        db_user = await db.get(models.User, current_user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if not security.verify_password(payload.old_password, db_user.password):
            raise HTTPException(status_code=400, detail="旧密码错误")

        if len(payload.new_password) < 6:
            raise HTTPException(status_code=400, detail="新密码长度不能少于6位")

        db_user.password = security.get_password_hash(payload.new_password)
        await db.commit()

        await log_audit_event(
            action="user.password.change",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="success",
            detail={},
            request=request,
        )

        return {"message": "密码修改成功"}
    except HTTPException as exc:
        await log_audit_event(
            action="user.password.change",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="user.password.change",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


@users.post("/me/avatar", response_model=schemas_likes_dto.AvatarUploadResponse)
async def upload_my_avatar(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        request: Request = None
):
    try:
        db_user = await db.get(models.User, current_user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if file.content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="头像仅支持 JPG/PNG/WEBP/GIF")

        file_data = await file.read()
        if not file_data:
            raise HTTPException(status_code=400, detail="头像文件不能为空")
        if len(file_data) > MAX_AVATAR_SIZE:
            raise HTTPException(status_code=400, detail="头像大小不能超过 5MB")

        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        safe_name = _normalize_minio_filename(file.filename or "avatar", fallback_ext=ext)
        object_name = f"users/{db_user.id}/avatar/{int(time.time())}_{safe_name}"

        minio_handler.client.put_object(
            minio_handler.bucket_name,
            object_name,
            io.BytesIO(file_data),
            length=len(file_data),
            content_type=file.content_type
        )
        avatar_url = _build_minio_file_url(object_name)

        old_object = _extract_object_name_from_url(db_user.avatar_url)
        if old_object and old_object != object_name:
            try:
                minio_handler.client.remove_object(minio_handler.bucket_name, old_object)
            except Exception:
                pass

        db_user.avatar_url = avatar_url
        await db.commit()
        await db.refresh(db_user)

        await log_audit_event(
            action="user.avatar.upload",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="success",
            detail={"filename": file.filename},
            request=request,
        )

        return {"avatar_url": _resolve_avatar_display_url(db_user.avatar_url)}
    except HTTPException as exc:
        await log_audit_event(
            action="user.avatar.upload",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="user.avatar.upload",
            actor=current_user,
            resource_type="user",
            resource_id=str(current_user.id),
            resource_name=current_user.username,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise


@users.get("/", response_model=list[schemas_likes_dto.UserResponse])
async def read_all_users(
        skip: int = 0,
        limit: int = 100,
        user_name: str | None = None,
        db: AsyncSession = Depends(get_db),
        current_user: models.User = Depends(require_admin)
):

    print(f"当前访问者是: {current_user.username}")

    stmt = select(models.User)

    if user_name:
        stmt = stmt.where(models.User.username == user_name)
    stmt = stmt.offset(skip).limit(limit)

    res = await db.execute(stmt)
    users = res.scalars().all()
    return users

@users.put("/", response_model=schemas_likes_dto.UserResponse)
async def update_user(
        user:schemas_likes_dto.UserUpdate,
        db:AsyncSession = Depends(get_db),
        current_user: models.User = Depends(require_admin),
        request: Request = None
):
    try:
        db_user = (await db.execute(select(models.User).where(models.User.id == user.id))).scalar_one_or_none()
        if db_user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        update_data = user.model_dump(exclude_unset=True)
        previous_status = getattr(db_user, "status", "active")
        if "password" in update_data and update_data["password"] is not None:
            update_data["password"] = security.get_password_hash(update_data["password"])
        if "status" in update_data and update_data["status"] is not None:
            next_status = update_data["status"]
            if next_status not in ("active", "disabled"):
                raise HTTPException(status_code=400, detail="无效的用户状态")
            if db_user.id == current_user.id and next_status == "disabled":
                raise HTTPException(status_code=400, detail="不能禁用当前登录账号")

        for key, value in update_data.items():
            if key != "id" and hasattr(db_user, key):
                setattr(db_user, key, value)

        await db.commit()
        await db.refresh(db_user)

        updated_fields = [key for key in update_data.keys() if key not in {"id", "password"}]
        if "password" in update_data:
            updated_fields.append("password")

        status_changed = "status" in update_data and update_data.get("status") != previous_status
        action = "user.status.change" if status_changed else "user.update"
        detail = {"updated_fields": updated_fields}
        if status_changed:
            detail["previous_status"] = previous_status
            detail["current_status"] = update_data.get("status")

        await log_audit_event(
            action=action,
            actor=current_user,
            resource_type="user",
            resource_id=str(db_user.id),
            resource_name=db_user.username,
            status="success",
            detail=detail,
            request=request,
        )

        return db_user
    except HTTPException as exc:
        await log_audit_event(
            action="user.update",
            actor=current_user,
            resource_type="user",
            resource_id=str(user.id) if user and user.id else None,
            resource_name=None,
            status="failed",
            detail={"error": exc.detail},
            request=request,
        )
        raise
    except Exception as exc:
        await log_audit_event(
            action="user.update",
            actor=current_user,
            resource_type="user",
            resource_id=str(user.id) if user and user.id else None,
            resource_name=None,
            status="failed",
            detail={"error": str(exc)},
            request=request,
        )
        raise
