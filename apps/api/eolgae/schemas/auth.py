"""Pydantic schemas for /auth router. AUTH-SPEC.md §3 따름."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 비밀번호 최소 길이 — signup / change 공통 단일 소스.
# (FE 는 별도 런타임이라 값을 공유 못 함 — apps/web/src/lib/constants.ts 에서 동일 값 유지)
MIN_PASSWORD_LENGTH = 4


def _blank_to_none(v: object) -> object:
    """빈 문자열/공백 email 을 None 으로 — 미입력 시 패턴 검증에 걸리지 않게."""
    if isinstance(v, str) and not v.strip():
        return None
    return v


class UserResponse(BaseModel):
    """본인 정보 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    display_name: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)
    # email-validator 의존성 회피 — 가벼운 형식 검증만. 정식 검증은 Later.
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str | None = Field(default=None, max_length=100)

    _email_blank = field_validator("email", mode="before")(_blank_to_none)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    """로그인/회원가입/refresh 공통 응답. Refresh 는 cookie 로만."""

    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    _email_blank = field_validator("email", mode="before")(_blank_to_none)
