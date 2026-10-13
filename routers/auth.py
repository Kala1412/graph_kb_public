import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import select
from starlette import status
from pydantic import BaseModel

from utils.security import verify_password, create_access_token, create_refresh_token, SECRET_KEY, ALGORITHM
import models
from database import AsyncSessionLocal

auth = APIRouter(prefix="/auth", tags=["auth"])

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

class RefreshRequest(BaseModel):
    refresh_token: str

@auth.post("/login")
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db:AsyncSessionLocal = Depends(get_db)
):
    user = ((await db.execute(select(models.User).where(models.User.username == form_data.username)))
            .scalar_one_or_none()
            )
    if user is None or not verify_password(form_data.password,user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if getattr(user, "status", "active") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    token_data = {"sub": user.username, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": user.role,
        "token_type":"bearer"
    }

@auth.post("/refresh")
async def refresh_token(
        req: RefreshRequest,
        db: AsyncSessionLocal = Depends(get_db)
):
    """
    用 Refresh Token 换取新的 Access Token + 新的 Refresh Token（旋转刷新）
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token 无效或已过期，请重新登录",
    )
    try:
        payload = jwt.decode(req.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
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
            detail="账号已被禁用",
        )

    token_data = {"sub": user.username, "role": user.role}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "role": user.role,
        "token_type":"bearer"
    }























