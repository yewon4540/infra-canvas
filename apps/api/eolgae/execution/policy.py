"""Fail closed before queueing or running a direct infrastructure operation."""
from fastapi import HTTPException

from eolgae.config import settings


def require_direct_execution(canvas) -> None:
    if not settings.direct_execution_enabled:
        raise HTTPException(409, "이 설치에서는 직접 실행이 비활성화되어 있습니다.")
    if canvas is None:
        raise HTTPException(404, "Canvas not found")
    if getattr(canvas, "execution_backend", "eolgae_direct") != "eolgae_direct":
        raise HTTPException(409, "이 대상의 실행은 외부 backend에서 관리합니다.")
