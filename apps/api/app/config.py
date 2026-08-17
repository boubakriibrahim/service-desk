from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PLACEHOLDER_SECRET = "change-this-in-production"
APP_ENVIRONMENTS = ("development", "test", "production")


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = PLACEHOLDER_SECRET
    web_origin: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://service_desk:service_desk@db:5432/service_desk"
    file_storage_path: str = "/data/uploads"
    demo_documents_path: str = "/demo/documents"
    cookie_secure: bool | None = None
    enable_demo_reset: bool | None = None
    seed_demo_data: bool | None = None

    ai_mode: str = "demo"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_provider_kind: str = "cloud"
    ai_max_sensitivity: str = "internal"
    ai_timeout_seconds: int = 60

    laya_mode: str = "demo"
    laya_base_url: str = "http://laya:8010"
    laya_model: str = "convaiinnovations/laya"
    laya_timeout_seconds: int = 45
    laya_required: bool = False

    embedding_mode: str = "demo"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return str(value).strip().lower()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.web_origin.split(",") if o.strip()]

    @property
    def effective_cookie_secure(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def effective_enable_demo_reset(self) -> bool:
        return not self.is_production if self.enable_demo_reset is None else self.enable_demo_reset

    @property
    def effective_seed_demo_data(self) -> bool:
        return not self.is_production if self.seed_demo_data is None else self.seed_demo_data


def validate_runtime_settings(settings: Settings) -> None:
    # An unknown value (a typo such as "prod") would otherwise run with the development defaults.
    if settings.app_env not in APP_ENVIRONMENTS:
        raise RuntimeError(f"APP_ENV must be one of {', '.join(APP_ENVIRONMENTS)}, not {settings.app_env!r}")
    # CORS allows credentials, so a wildcard would accept signed-in requests from any website.
    if "*" in settings.cors_origins:
        raise RuntimeError("WEB_ORIGIN cannot be '*'; list the web app's origins")
    if not settings.is_production:
        return
    if settings.secret_key == PLACEHOLDER_SECRET or len(settings.secret_key) < 32:
        raise RuntimeError("SECRET_KEY must be set to a unique value of at least 32 characters when APP_ENV=production")
    insecure = [origin for origin in settings.cors_origins if not origin.startswith("https://")]
    if insecure:
        raise RuntimeError(f"WEB_ORIGIN must list only https:// origins when APP_ENV=production, not {', '.join(insecure)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
