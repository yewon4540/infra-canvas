"""Application settings (env-driven)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    valkey_url: str = "redis://localhost:6379/0"
    jwt_secret: str

    direct_execution_enabled: bool = False
    terrakube_enabled: bool = False
    terrakube_api_url: str = ""
    terrakube_ui_url: str = ""
    terrakube_token_file: str = ""
    terrakube_organization_id: str = ""
    # Comma separated IDs; empty lists deny access.
    terrakube_workspace_ids: str = ""
    terrakube_user_ids: str = ""
    terrakube_plan_enabled: bool = False
    terrakube_plan_template_id: str = ""
    terrakube_plan_user_ids: str = ""

    # Operator-owned Kubernetes read profiles; no user-supplied credential destinations.
    kubernetes_read_profiles_file: str = ""
    resource_ai_enabled: bool = False

    # LLM provider — 우선순위: Anthropic > OpenAI / OpenAI-compatible
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # OpenAI-compatible endpoint (vLLM / Ollama / OpenRouter 등) 사용 시 지정
    # 비어있으면 공식 OpenAI 사용
    openai_base_url: str = ""
    openai_model: str = ""  # 비어있으면 기본 모델 (gpt-4o-2024-08-06)

    # OAuth providers — 비어있으면 해당 provider 엔드포인트 503
    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    # OAuth callback redirect whitelist (스킴 미포함 host 또는 host:port)
    allowed_redirect_hosts: list[str] = ["localhost", "127.0.0.1"]
    # OAuth callback 자체 URL (provider 등록한 URI). 환경별 override
    oauth_callback_base_url: str = "http://localhost/auth/oauth"

    # 쿠키 보안 — dev 환경에선 False 로 override (Secure 미강제)
    cookie_secure: bool = True

    # Cross-account AWS onboarding
    eolgae_aws_account_id: str = ""
    cfn_template_url: str = ""

    # Deployment artifact storage
    artifact_store_backend: str = "local"
    artifact_local_root: str = "/var/lib/eolgae/artifacts"
    artifact_retention_policy: str = "keep"
    artifact_s3_bucket: str = ""
    artifact_s3_prefix: str = "artifacts"
    artifact_s3_region: str = "ap-northeast-2"
    artifact_s3_endpoint_url: str = ""
    artifact_s3_access_key_id: str = ""
    artifact_s3_secret_access_key: str = ""
    artifact_s3_session_token: str = ""
    artifact_s3_force_path_style: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore[call-arg]
