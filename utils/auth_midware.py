from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import models
from database import AsyncSessionLocal
from utils import security


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"}
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, security.SECRET_KEY, security.ALGORITHM)
        if payload.get("type") != "access":
            raise credentials_exception

        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = ((await db.execute(select(models.User).where(models.User.username == username)))
            .scalar_one_or_none()
            )
    if user is None:
        raise credentials_exception
    if getattr(user, "status", "active") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )
    return user

def is_admin(user: models.User) -> bool:
    return getattr(user, "role", None) == "admin"

async def require_kb_access(kb_id: int, db: AsyncSession, current_user: models.User):
    kb = await db.get(models.KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    if not is_admin(current_user) and kb.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该知识库")
    return kb

async def require_file_access(file_id: int, db: AsyncSession, current_user: models.User):
    file_record = await db.get(models.KnowledgeFile, file_id)
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # 通过文件关联的知识库检查权限
    await require_kb_access(file_record.kb_id, db, current_user)

    return file_record

async def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
