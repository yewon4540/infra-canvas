"""Operator-owned profiles bind credentials to endpoints, users and namespaces."""
import base64
import json
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from eolgae.config import settings

NAMESPACE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


@dataclass(frozen=True)
class Access:
    endpoint: str
    token: str
    tls: ssl.SSLContext
    namespace: str
    namespaces: list[str]


def profile_for(target) -> dict:
    if target.kind != "kubernetes_cluster" or getattr(target, "archived_at", None):
        raise HTTPException(409, "조회 가능한 Kubernetes Target을 선택하세요.")
    try:
        profiles = json.loads(Path(settings.kubernetes_read_profiles_file).read_text())
        name = (target.secret_ref or {}).get("name")
        matches = [p for p in profiles if p["name"] == name
                   and str(target.owner_id) in p["user_ids"]
                   and target.endpoint == p["endpoint"]]
        if len(matches) != 1:
            raise HTTPException(403, "관리자의 Kubernetes 조회 profile 허용 범위를 확인하세요.")
        profile = matches[0]
        url = urlsplit(profile["endpoint"])
        if (url.scheme != "https" or not url.netloc or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError()
        scopes = profile["namespaces"]
        if not isinstance(scopes, list) or not scopes or any(
            not isinstance(n, str) or (n != "*" and not NAMESPACE.fullmatch(n)) for n in scopes
        ):
            raise ValueError()
        return profile
    except HTTPException:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise HTTPException(503, "Kubernetes 조회 profile 파일 설정이 필요합니다.") from None


def scope_for(target) -> dict:
    p = profile_for(target)
    default = (target.config or {}).get("default_namespace") or "default"
    if "*" not in p["namespaces"] and default not in p["namespaces"]:
        default = p["namespaces"][0]
    return {"namespaces": p["namespaces"], "default_namespace": default}


def access_for(target, namespace: str | None) -> Access:
    p = profile_for(target)
    namespace = namespace if namespace is not None else scope_for(target)["default_namespace"]
    if namespace != "*" and not NAMESPACE.fullmatch(namespace):
        raise HTTPException(422, "올바른 namespace를 입력하세요.")
    if "*" not in p["namespaces"] and namespace not in p["namespaces"]:
        raise HTTPException(403, "허용되지 않은 namespace입니다.")
    try:
        token = Path(p["token_file"]).read_text().strip()
        ca = Path(p["ca_file"]).read_text().strip()
        if not token or any(c.isspace() for c in token):
            raise ValueError()
        if "-----BEGIN CERTIFICATE-----" not in ca:
            ca = base64.b64decode(ca, validate=True).decode()
        tls = ssl.create_default_context(cadata=ca)
    except (OSError, ValueError, KeyError, ssl.SSLError, UnicodeError):
        raise HTTPException(503, "Kubernetes token 또는 CA 파일을 확인하세요.") from None
    return Access(p["endpoint"].rstrip("/"), token, tls, namespace, p["namespaces"])
