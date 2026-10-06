"""FastAPI dependencies — current user 주입. AUTH-SPEC §6.1."""
import uuid

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from eolgae.auth.security import decode_access_token
from eolgae.db import get_db
from eolgae.models.user import User


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    token = _extract_bearer(authorization)
    if token is None:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None
    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    try:
        user_id = uuid.UUID(user_id_str)
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "missing_token", "message": "authorization header required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "access token expired"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "invalid token"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "invalid token payload"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = uuid.UUID(user_id_str)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "invalid user id"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_not_found", "message": "user not found or inactive"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
