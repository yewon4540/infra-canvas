"""Authentication endpoints — signup / login / logout / refresh / me + OAuth.

AUTH-SPEC.md §2-7 따름. 자체 ID/PW + OAuth 하이브리드 (ADR 017).
"""
from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.auth.oauth_providers import OAuthError, get_provider
from eolgae.auth.security import (
    create_access_token,
    create_oauth_state,
    decode_oauth_state,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from eolgae.config import settings
from eolgae.db import get_db
from eolgae.models.oauth_account import OAuthAccount
from eolgae.models.refresh_token import RefreshToken
from eolgae.models.user import User
from eolgae.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh"
REFRESH_COOKIE_PATH = "/auth/refresh"
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30d, AUTH-SPEC §4.2


# ===== Helper =====


def _err(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=http_status, detail={"code": code, "message": message}
    )


def _set_refresh_cookie(response: Response, refresh_plain: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_plain,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, httponly=True
    )


def _issue_tokens(
    *,
    db: Session,
    user: User,
    request: Request,
    response: Response,
    replace: RefreshToken | None = None,
) -> TokenResponse:
    """Access 발급 + refresh 발급/회전 + cookie 세팅."""
    refresh_plain, refresh_hash, refresh_expires = generate_refresh_token()
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_expires,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        ip_address=request.client.host if request.client else None,
    )
    db.add(refresh_row)
    db.flush()  # id 확보

    if replace is not None:
        replace.revoked_at = datetime.now(tz=timezone.utc)
        replace.replaced_by_id = refresh_row.id

    db.commit()
    db.refresh(user)

    access, expires_in = create_access_token(
        user_id=user.id, username=user.username, email=user.email
    )
    _set_refresh_cookie(response, refresh_plain)
    return TokenResponse(
        user=UserResponse.model_validate(user),
        access_token=access,
        token_type="bearer",
        expires_in=expires_in,
    )


def _revoke_chain(db: Session, root_user_id) -> None:
    """user 의 모든 활성 refresh token revoke (reuse detection 등)."""
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == root_user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(tz=timezone.utc))
    )
    db.commit()


# ===== 자체 가입 / 로그인 =====


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    # username 충돌
    existing_username = db.scalar(select(User).where(User.username == payload.username))
    if existing_username is not None:
        raise _err(status.HTTP_409_CONFLICT, "username_taken", "username already taken")
    # email 충돌 (값 있을 때만)
    if payload.email:
        existing_email = db.scalar(select(User).where(User.email == payload.email))
        if existing_email is not None:
            raise _err(status.HTTP_409_CONFLICT, "email_taken", "email already in use")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
    )
    db.add(user)
    db.flush()  # id 확보 (refresh_token 발급 위함)
    user.last_login_at = datetime.now(tz=timezone.utc)
    return _issue_tokens(db=db, user=user, request=request, response=response)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(
        select(User).where(
            or_(User.username == payload.identifier, User.email == payload.identifier)
        )
    )
    if user is None or not user.is_active or user.password_hash is None:
        raise _err(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "invalid username or password",
        )
    if not verify_password(payload.password, user.password_hash):
        raise _err(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "invalid username or password",
        )
    user.last_login_at = datetime.now(tz=timezone.utc)
    return _issue_tokens(db=db, user=user, request=request, response=response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    db: Session = Depends(get_db),
) -> Response:
    if refresh:
        token_hash = hash_refresh_token(refresh)
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(tz=timezone.utc)
            db.commit()
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    refresh: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if not refresh:
        raise _err(status.HTTP_401_UNAUTHORIZED, "missing_refresh", "refresh token required")
    token_hash = hash_refresh_token(refresh)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None:
        raise _err(status.HTTP_401_UNAUTHORIZED, "invalid_refresh", "invalid refresh token")
    # Reuse detection: 이미 revoked 된 token 의 재사용 → chain 전체 무효화
    if row.revoked_at is not None:
        _revoke_chain(db, row.user_id)
        _clear_refresh_cookie(response)
        raise _err(
            status.HTTP_401_UNAUTHORIZED,
            "refresh_reuse_detected",
            "refresh token chain revoked",
        )
    if row.expires_at <= datetime.now(tz=timezone.utc):
        raise _err(status.HTTP_401_UNAUTHORIZED, "refresh_expired", "refresh token expired")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise _err(status.HTTP_401_UNAUTHORIZED, "user_not_found", "user not found or inactive")
    return _issue_tokens(db=db, user=user, request=request, response=response, replace=row)


# ===== 본인 정보 =====


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.email is not None and payload.email != user.email:
        existing = db.scalar(
            select(User).where(User.email == payload.email, User.id != user.id)
        )
        if existing is not None:
            raise _err(status.HTTP_409_CONFLICT, "email_taken", "email already in use")
        user.email = payload.email
    if payload.display_name is not None:
        user.display_name = payload.display_name
    db.commit()
    db.refresh(user)
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if user.password_hash is None or not verify_password(
        payload.current_password, user.password_hash
    ):
        raise _err(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "current password incorrect",
        )
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    _revoke_chain(db, user.id)
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


# ===== OAuth =====


def _build_redirect_uri(provider: str) -> str:
    return f"{settings.oauth_callback_base_url.rstrip('/')}/{provider}/callback"


def _validate_redirect(redirect: str) -> str:
    """callback 후 FE 로 보낼 redirect 경로. 외부 호스트 차단."""
    if not redirect or redirect.startswith("/"):
        return redirect or "/"
    # 절대 URL 인 경우 host whitelist 검증
    from urllib.parse import urlparse

    parsed = urlparse(redirect)
    if not parsed.hostname:
        return "/"
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    if host not in settings.allowed_redirect_hosts and parsed.hostname not in settings.allowed_redirect_hosts:
        return "/"
    return redirect


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, redirect: str = "/") -> RedirectResponse:
    p = get_provider(provider)
    if p is None:
        raise _err(status.HTTP_404_NOT_FOUND, "unknown_provider", f"unknown provider: {provider}")
    if not p.configured:
        raise _err(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "provider_not_configured",
            f"{provider} OAuth not configured",
        )
    redirect_uri = _build_redirect_uri(provider)
    state = create_oauth_state(redirect=_validate_redirect(redirect))
    return RedirectResponse(p.build_authorize_url(redirect_uri=redirect_uri, state=state))


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        raise _err(status.HTTP_400_BAD_REQUEST, "provider_error", f"{provider} error: {error}")
    if not code or not state:
        raise _err(status.HTTP_400_BAD_REQUEST, "missing_params", "code and state required")
    p = get_provider(provider)
    if p is None or not p.configured:
        raise _err(status.HTTP_503_SERVICE_UNAVAILABLE, "provider_not_configured", "")

    # state 검증
    try:
        state_payload = decode_oauth_state(state)
    except jwt.PyJWTError as e:
        raise _err(status.HTTP_400_BAD_REQUEST, "invalid_state", "invalid or expired state") from e
    redirect_to = _validate_redirect(state_payload.get("redirect", "/"))

    try:
        access_token = await p.exchange_code(code=code, redirect_uri=_build_redirect_uri(provider))
        info = await p.fetch_user(access_token=access_token)
    except OAuthError as e:
        raise _err(status.HTTP_502_BAD_GATEWAY, "provider_error", str(e)) from e

    # 기존 oauth_accounts 조회
    existing_oauth = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == info.provider,
            OAuthAccount.provider_user_id == info.provider_user_id,
        )
    )
    if existing_oauth is not None:
        user = db.get(User, existing_oauth.user_id)
        if user is None or not user.is_active:
            raise _err(status.HTTP_401_UNAUTHORIZED, "user_inactive", "user inactive")
        user.last_login_at = datetime.now(tz=timezone.utc)
    else:
        # 신규 user 생성 — username 충돌 시 hint 변형
        username = _resolve_username(db, base=info.username_hint, provider=info.provider)
        user = User(
            username=username,
            email=info.email,
            password_hash=None,  # OAuth-only
            display_name=info.display_name or username,
            last_login_at=datetime.now(tz=timezone.utc),
        )
        db.add(user)
        db.flush()
        db.add(
            OAuthAccount(
                user_id=user.id,
                provider=info.provider,
                provider_user_id=info.provider_user_id,
                email_at_provider=info.email,
            )
        )

    # 세션 발급 — refresh cookie 세팅 후 FE 로 redirect
    tokens = _issue_tokens(db=db, user=user, request=request, response=response)

    # access token 은 redirect URL 의 fragment 로 전달 (history/log 노출 회피)
    sep = "&" if "?" in redirect_to else "?"
    target = f"{redirect_to}{sep}access_token={tokens.access_token}&expires_in={tokens.expires_in}"
    redirect = RedirectResponse(url=target, status_code=302)
    # _set_refresh_cookie 는 response 에 세팅됨 — RedirectResponse 에도 복사
    if response.headers.get("set-cookie"):
        redirect.headers["set-cookie"] = response.headers["set-cookie"]
    return redirect


def _resolve_username(db: Session, *, base: str, provider: str) -> str:
    """provider username 충돌 시 prefix + suffix 로 회피. AUTH-SPEC §7.5."""
    candidates = [
        base,
        f"{provider[:2]}_{base}",
    ]
    for c in candidates:
        c_clean = "".join(ch for ch in c if ch.isalnum() or ch in "_-")[:64] or f"{provider}_user"
        if db.scalar(select(User).where(User.username == c_clean)) is None:
            return c_clean
    # 마지막 fallback — provider prefix + suffix 숫자
    base_clean = "".join(ch for ch in base if ch.isalnum() or ch in "_-")[:50] or "user"
    for n in range(2, 1000):
        cand = f"{provider[:2]}_{base_clean}_{n}"[:64]
        if db.scalar(select(User).where(User.username == cand)) is None:
            return cand
    raise _err(status.HTTP_500_INTERNAL_SERVER_ERROR, "username_exhausted", "could not resolve username")
