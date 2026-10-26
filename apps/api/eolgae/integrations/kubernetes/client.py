"""Bounded GET-only list client. No redirects, raw errors, watch or write APIs."""
import time
import httpx

KINDS = {
    "Namespace": ("/api/v1", "namespaces"),
    "Deployment": ("/apis/apps/v1", "deployments"),
    "ReplicaSet": ("/apis/apps/v1", "replicasets"),
    "Pod": ("/api/v1", "pods"),
    "Service": ("/api/v1", "services"),
    "Ingress": ("/apis/networking.k8s.io/v1", "ingresses"),
}
ERRORS = {401: "인증 실패", 403: "조회 권한 부족", 404: "API 또는 namespace 없음",
          410: "목록 만료: 새로고침 필요", 429: "요청 제한"}
MAX_PAGES = 5
MAX_BYTES = 8 * 1024 * 1024


class ReadError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message


class Reader:
    def __init__(self, access, transport=None):
        self.access = access
        self.client = httpx.Client(verify=access.tls, timeout=5, follow_redirects=False,
                                   trust_env=False, transport=transport,
                                   headers={"Authorization": f"Bearer {access.token}"})
        self.deadline = time.monotonic() + 20

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def get(self, path, params=None):
        if time.monotonic() >= self.deadline:
            raise ReadError("timeout", "조회 시간 초과")
        try:
            with self.client.stream("GET", self.access.endpoint + path, params=params) as response:
                if response.status_code != 200:
                    raise ReadError(str(response.status_code), ERRORS.get(response.status_code, "Kubernetes 조회 실패"))
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES or time.monotonic() > self.deadline:
                        raise ReadError("limit", "응답 크기 또는 조회 시간 제한")
                    chunks.append(chunk)
                import json
                body = json.loads(b"".join(chunks))
                if not isinstance(body, dict):
                    raise ValueError()
                return body
        except httpx.TimeoutException:
            raise ReadError("timeout", "조회 시간 초과") from None
        except httpx.HTTPError:
            raise ReadError("connection", "연결 또는 TLS 검증 실패") from None
        except (ValueError, TypeError):
            raise ReadError("invalid_response", "Kubernetes 응답 형식 오류") from None

    def collect(self, kind):
        base, plural = ("/api/v1", "events") if kind == "Event" else KINDS[kind]
        ns = self.access.namespace
        if kind == "Namespace" and ns != "*":
            item = self.get(f"{base}/namespaces/{ns}")
            return [item], True
        path = f"{base}/{plural}" if ns == "*" else f"{base}/namespaces/{ns}/{plural}"
        items, cursor = [], ""
        for _ in range(MAX_PAGES):
            body = self.get(path, {"limit": 200, **({"continue": cursor} if cursor else {})})
            page = body.get("items")
            if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
                raise ReadError("invalid_response", "Kubernetes 목록 형식 오류")
            items.extend(page)
            cursor = (body.get("metadata") or {}).get("continue", "")
            if not cursor:
                return items, True
        return items, False
