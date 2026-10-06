"""LLM provider abstraction (Anthropic / OpenAI / OpenAI-compatible).

env 의 API 키에 따라 provider 자동 선택. Anthropic 우선.
OpenAI-compatible endpoint (vLLM / Ollama 등) 는 OPENAI_BASE_URL 지정 시 사용.

complete_json() — 단일 호출 (전체 응답 받고 반환)
complete_json_stream() — generator, chunk 별로 yield
"""
from collections.abc import Iterator
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from eolgae.config import settings

# 기본 모델 — env 로 override 가능
ANTHROPIC_MODEL = "claude-sonnet-4-6"
OPENAI_MODEL_DEFAULT = "gpt-4o-2024-08-06"


class LLMProvider:
    """Provider-agnostic LLM 호출자."""

    def __init__(self) -> None:
        if settings.anthropic_api_key:
            self.provider = "anthropic"
            self.client: Any = Anthropic(api_key=settings.anthropic_api_key)
            self.model = ANTHROPIC_MODEL
            self.use_json_mode = False
        elif settings.openai_api_key or settings.openai_base_url:
            self.provider = "openai"
            kwargs: dict[str, Any] = {
                "api_key": settings.openai_api_key or "dummy",
            }
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
                self.use_json_mode = False
            else:
                self.use_json_mode = True
            self.client = OpenAI(**kwargs)
            self.model = settings.openai_model or OPENAI_MODEL_DEFAULT
        else:
            raise RuntimeError(
                "LLM provider 미설정 — ANTHROPIC_API_KEY / OPENAI_API_KEY / "
                "OPENAI_BASE_URL 중 하나 필요"
            )

    # ---------- non-streaming ----------

    def complete_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> str:
        """JSON 응답을 텍스트로 반환 (caller 가 parse)."""
        if self.provider == "anthropic":
            return self._anthropic_complete(system, user, max_tokens)
        return self._openai_complete(system, user, max_tokens)

    @staticmethod
    def _cached_system(system: str) -> list[dict[str, Any]]:
        """system 프롬프트를 ephemeral 프롬프트 캐시 대상으로 표시.

        같은 system 으로 5분(TTL) 내 재요청 시 입력 토큰을 캐시에서 재사용 →
        비용/지연 절감. 단 캐시 가능 최소 prefix(Sonnet ~1024토큰) 미만이면
        Anthropic 이 캐시를 건너뛴다(무해 — 에러 없이 일반 처리). 프롬프트가
        커질수록 자동으로 캐시가 발동한다.
        """
        return [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _anthropic_complete(
        self, system: str, user: str, max_tokens: int
    ) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self._cached_system(system),
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if hasattr(block, "text"):
                return block.text  # type: ignore[no-any-return]
        return ""

    def _openai_complete(
        self, system: str, user: str, max_tokens: int
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    # ---------- streaming ----------

    def complete_json_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """JSON 응답을 chunk 별로 yield (caller 가 누적 후 parse)."""
        if self.provider == "anthropic":
            yield from self._anthropic_stream(system, user, max_tokens)
        else:
            yield from self._openai_stream(system, user, max_tokens)

    def _anthropic_stream(
        self, system: str, user: str, max_tokens: int
    ) -> Iterator[str]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=self._cached_system(system),
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _openai_stream(
        self, system: str, user: str, max_tokens: int
    ) -> Iterator[str]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
        }
        if self.use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content


_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Singleton LLM provider — process 당 1회 init."""
    global _provider
    if _provider is None:
        _provider = LLMProvider()
    return _provider
