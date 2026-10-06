"""OAuth provider 어댑터 — GitHub / Google. AUTH-SPEC §7.

provider 별로 authorize URL / token 교환 / user info 조회를 추상화.
"""
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from eolgae.config import settings


@dataclass
class OAuthUserInfo:
    """provider 의 user 정보를 정규화."""

    provider: str
    provider_user_id: str
    email: str | None
    display_name: str
    username_hint: str  # provider 측 login/username, 자체 username 충돌 시 prefix 용


class OAuthError(Exception):
    """provider 호출 실패."""


class _BaseProvider:
    name: str = ""
    authorize_url: str = ""
    token_url: str = ""
    user_info_url: str = ""
    scope: str = ""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def build_authorize_url(self, *, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": self.scope,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        raise NotImplementedError

    async def fetch_user(self, *, access_token: str) -> OAuthUserInfo:
        raise NotImplementedError


class _GitHubProvider(_BaseProvider):
    name = "github"
    authorize_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    user_info_url = "https://api.github.com/user"
    scope = "read:user user:email"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
        if resp.status_code != 200:
            raise OAuthError(f"github token exchange failed: {resp.status_code}")
        data: dict[str, Any] = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise OAuthError(f"github token missing: {data.get('error', 'unknown')}")
        return str(access_token)

    async def fetch_user(self, *, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=10.0) as client:
            user_resp = await client.get(
                self.user_info_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if user_resp.status_code != 200:
                raise OAuthError(f"github user fetch failed: {user_resp.status_code}")
            user_data: dict[str, Any] = user_resp.json()

            # GitHub 의 email 은 public 아닌 경우가 많아 별도 endpoint 조회
            email = user_data.get("email")
            if not email:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if emails_resp.status_code == 200:
                    for item in emails_resp.json():
                        if item.get("primary") and item.get("verified"):
                            email = item.get("email")
                            break

        return OAuthUserInfo(
            provider="github",
            provider_user_id=str(user_data["id"]),
            email=email,
            display_name=user_data.get("name") or user_data.get("login") or "",
            username_hint=user_data.get("login") or f"gh{user_data['id']}",
        )


class _GoogleProvider(_BaseProvider):
    name = "google"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    user_info_url = "https://openidconnect.googleapis.com/v1/userinfo"
    scope = "openid email profile"

    def build_authorize_url(self, *, redirect_uri: str, state: str) -> str:
        # Google 은 response_type / access_type / prompt 추가
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": self.scope,
            "response_type": "code",
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        if resp.status_code != 200:
            raise OAuthError(f"google token exchange failed: {resp.status_code}")
        data: dict[str, Any] = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise OAuthError(f"google token missing: {data.get('error', 'unknown')}")
        return str(access_token)

    async def fetch_user(self, *, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.user_info_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code != 200:
            raise OAuthError(f"google user fetch failed: {resp.status_code}")
        data: dict[str, Any] = resp.json()
        return OAuthUserInfo(
            provider="google",
            provider_user_id=str(data["sub"]),
            email=data.get("email"),
            display_name=data.get("name") or (data.get("email") or "").split("@")[0],
            # email local part 를 username hint 로
            username_hint=(data.get("email") or f"g{data['sub']}").split("@")[0],
        )


def get_provider(name: str) -> _BaseProvider | None:
    if name == "github":
        return _GitHubProvider(settings.github_client_id, settings.github_client_secret)
    if name == "google":
        return _GoogleProvider(settings.google_client_id, settings.google_client_secret)
    return None
