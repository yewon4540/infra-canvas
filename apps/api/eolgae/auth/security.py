"""비밀번호 해싱 + JWT 발급/검증 + refresh token 유틸. AUTH-SPEC §4-5."""
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from eolgae.config import settings

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
JWT_ALGORITHM = "HS256"

# 비밀번호 해싱: argon2id 우선 (ADR 017), argon2-cffi 미설치 시 bcrypt fallback.
# passlib 1.7.4 가 bcrypt 4.x 와 호환되지 않아(버전 감지 버그) 라이브러리를 직접 호출.
# 저장 해시의 prefix 로 알고리즘을 식별하므로 백엔드 전환 후에도 기존 해시 verify 가능.
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import Argon2Error

    _argon2 = PasswordHasher()  # time_cost/memory_cost 는 라이브러리 기본값
except ImportError:  # argon2-cffi 미설치 — bcrypt 로 동작
    _argon2 = None


# ----- 비밀번호 -----


def _bcrypt_prehash(plain: str) -> bytes:
    """bcrypt 의 72바이트 입력 제한 회피 — sha256 으로 고정 길이화 후 base64."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain: str) -> str:
    if _argon2 is not None:
        return _argon2.hash(plain)
    return bcrypt.hashpw(_bcrypt_prehash(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        if hashed.startswith("$argon2"):
            if _argon2 is None:
                return False
            try:
                return _argon2.verify(hashed, plain)
            except Argon2Error:
                return False
        # bcrypt ($2a$ / $2b$ / $2y$)
        return bcrypt.checkpw(_bcrypt_prehash(plain), hashed.encode("utf-8"))
    except Exception:
        return False


# ----- Access token (JWT) -----


def create_access_token(*, user_id: uuid.UUID, username: str, email: str | None) -> tuple[str, int]:
    """(jwt, expires_in_seconds)."""
    now = datetime.now(tz=timezone.utc)
    exp = now + ACCESS_TOKEN_TTL
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, int(ACCESS_TOKEN_TTL.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """디코드 + 만료 검증. 실패 시 jwt.PyJWTError 계열 raise."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


# ----- Refresh token -----


def generate_refresh_token() -> tuple[str, str, datetime]:
    """(plain, sha256_hex, expires_at_utc)."""
    plain = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    expires_at = datetime.now(tz=timezone.utc) + REFRESH_TOKEN_TTL
    return plain, token_hash, expires_at


def hash_refresh_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


# ----- OAuth state -----


def create_oauth_state(*, redirect: str, ttl_seconds: int = 300) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "redirect": redirect,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_oauth_state(state: str) -> dict[str, Any]:
    return jwt.decode(state, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
