from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.db.models import User, UserStatus
from app.db.session import get_db


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginUser(BaseModel):
    id: str
    username: str
    display_name: str
    role: Literal["student", "teacher", "admin"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: LoginUser


_DUMMY_PASSWORD_HASH = "pbkdf2_sha256$600000$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def create_auth_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

    @router.post("/login", response_model=LoginResponse)
    async def login(
        request: LoginRequest,
        session: AsyncSession = Depends(get_db),
    ) -> LoginResponse:
        user = await session.scalar(select(User).where(User.username == request.username))
        password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
        password_matches = await run_in_threadpool(
            verify_password, request.password, password_hash
        )
        if user is None or not password_matches or user.status is not UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(
            subject=user.id,
            secret=settings.auth_token_secret,
            expires_in_minutes=settings.auth_token_expire_minutes,
        )
        return LoginResponse(
            access_token=token,
            user=LoginUser(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=user.role.value,
            ),
        )

    return router
