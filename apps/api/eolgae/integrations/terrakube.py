"""Read-only Terrakube JSON:API adapter with explicit user/workspace scope."""
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException

from eolgae.config import settings


def identifiers(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


def authorized(user_id) -> bool:
    return settings.terrakube_enabled and str(user_id) in identifiers(settings.terrakube_user_ids)


def require_access(user_id, workspace_id: str | None = None) -> None:
    if not authorized(user_id):
        raise HTTPException(403, "Terrakube 조회 권한이 없습니다.")
    if workspace_id is not None and workspace_id not in identifiers(settings.terrakube_workspace_ids):
        raise HTTPException(403, "허용되지 않은 Terrakube Workspace입니다.")


def _url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise HTTPException(503, "Terrakube URL 설정을 확인하세요.")
    return value.rstrip("/")


def configured() -> bool:
    return bool(settings.terrakube_enabled and settings.terrakube_api_url
                and settings.terrakube_organization_id and settings.terrakube_token_file
                and settings.terrakube_workspace_ids)


def _organization() -> str:
    try:
        return str(UUID(settings.terrakube_organization_id))
    except ValueError:
        raise HTTPException(503, "Terrakube Organization 설정을 확인하세요.") from None


def headers() -> dict[str, str]:
    if not configured():
        raise HTTPException(503, "Terrakube 연결 설정이 필요합니다.")
    try:
        token = Path(settings.terrakube_token_file).read_text().strip()
    except OSError:
        raise HTTPException(503, "Terrakube token 파일을 읽을 수 없습니다.") from None
    if not token or "\n" in token or "\r" in token:
        raise HTTPException(503, "Terrakube token 설정을 확인하세요.")
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.api+json"}


def request(path: str, params: dict | None = None) -> dict:
    base = _url(settings.terrakube_api_url)
    auth_headers = headers()
    try:
        # Never forward tokens to redirects or caller-supplied remote URLs.
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.get(base + path, params=params, headers=auth_headers)
        if response.status_code in {401, 403}:
            raise HTTPException(502, "Terrakube 인증 또는 원격 조회 권한을 확인하세요.")
        if response.status_code == 404:
            raise HTTPException(404, "Terrakube 리소스를 찾을 수 없습니다.")
        if not 200 <= response.status_code < 300:
            raise HTTPException(502, "Terrakube 조회에 실패했습니다.")
        body = response.json()
        if not isinstance(body, dict) or "data" not in body:
            raise ValueError("Invalid JSON:API document")
        return body
    except httpx.TimeoutException:
        raise HTTPException(504, "Terrakube 응답 시간이 초과되었습니다.") from None
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Terrakube 연결 또는 응답 형식을 확인하세요.") from None


def workspace_path(workspace_id: str) -> str:
    try:
        workspace = str(UUID(workspace_id))
    except ValueError:
        raise HTTPException(422, "Workspace ID must be a UUID") from None
    return f"/organization/{_organization()}/workspace/{workspace}"


def workspace_link(workspace_id: str) -> str | None:
    if not settings.terrakube_ui_url:
        return None
    return f"{_url(settings.terrakube_ui_url)}/organizations/{_organization()}/workspaces/{workspace_id}"


def get_workspace(workspace_id: str) -> dict:
    data = request(workspace_path(workspace_id))["data"]
    if not isinstance(data, dict) or str(data.get("id")) != workspace_id:
        raise HTTPException(502, "Terrakube Workspace 응답이 일치하지 않습니다.")
    attrs = data.get("attributes") or {}
    return {"id": workspace_id, "name": attrs.get("name", workspace_id),
            "branch": attrs.get("branch"), "folder": attrs.get("folder"),
            "terraform_version": attrs.get("terraformVersion"),
            "url": workspace_link(workspace_id)}


def get_jobs(workspace_id: str) -> dict:
    # Terrakube 2.33.x relationship collections reject page parameters.
    body = request(workspace_path(workspace_id) + "/job")
    data = body["data"]
    if not isinstance(data, list):
        raise HTTPException(502, "Terrakube Run 목록 형식이 올바르지 않습니다.")
    items = []
    for item in data:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            raise HTTPException(502, "Terrakube Run 응답 형식이 올바르지 않습니다.")
        attrs = item.get("attributes") or {}
        link = workspace_link(workspace_id)
        # No raw logs, variables, state or arbitrary upstream attributes.
        items.append({"id": str(item["id"]), "status": attrs.get("status", "unknown"),
                      "created_at": attrs.get("createdDate"),
                      "commit": attrs.get("commitId"),
                      "url": f"{link}/runs/{item['id']}" if link else None})
    items.sort(key=lambda item: int(item["id"]), reverse=True)
    return {"items": items[:20], "has_more": len(items) > 20 or bool((body.get("links") or {}).get("next"))}
