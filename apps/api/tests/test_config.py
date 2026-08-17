import pytest
from app.config import Settings, validate_runtime_settings

STRONG = "x" * 40
HTTPS_ORIGIN = "https://desk.example.com"
SETTING_ENV_VARS = ("APP_ENV", "SECRET_KEY", "WEB_ORIGIN", "COOKIE_SECURE", "ENABLE_DEMO_RESET", "SEED_DEMO_DATA")


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for name in SETTING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def make(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_cors_origins_parses_comma_list():
    s = make(web_origin=" http://a.test , ,http://b.test,")
    assert s.cors_origins == ["http://a.test", "http://b.test"]
    assert make().cors_origins == ["http://localhost:3000"]


def test_production_rejects_placeholder_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_runtime_settings(make(app_env="production"))


def test_production_rejects_short_secret():
    with pytest.raises(RuntimeError):
        validate_runtime_settings(make(app_env="production", secret_key="short"))


def test_production_accepts_strong_secret():
    validate_runtime_settings(make(app_env="production", secret_key=STRONG, web_origin=HTTPS_ORIGIN))


def test_development_allows_placeholder_secret():
    validate_runtime_settings(make(app_env="development"))
    validate_runtime_settings(make(app_env="test"))


def test_app_env_is_normalized():
    s = make(app_env=" Production ")
    assert s.app_env == "production" and s.is_production


def test_unknown_app_env_is_rejected():
    with pytest.raises(RuntimeError, match="APP_ENV"):
        validate_runtime_settings(make(app_env="prod", secret_key=STRONG, web_origin=HTTPS_ORIGIN))


def test_wildcard_origin_is_rejected():
    with pytest.raises(RuntimeError, match="WEB_ORIGIN"):
        validate_runtime_settings(make(web_origin="*"))


def test_production_requires_https_origins():
    with pytest.raises(RuntimeError, match="http://localhost:3000"):
        validate_runtime_settings(make(app_env="production", secret_key=STRONG))
    validate_runtime_settings(make(app_env="production", secret_key=STRONG, web_origin=f"{HTTPS_ORIGIN},https://admin.example.com"))


def test_cookie_secure_defaults_and_override():
    assert make().effective_cookie_secure is False
    assert make(app_env="production").effective_cookie_secure is True
    assert make(app_env="production", cookie_secure=False).effective_cookie_secure is False
    assert make(cookie_secure=True).effective_cookie_secure is True


def test_demo_reset_defaults_and_override():
    assert make().effective_enable_demo_reset is True
    assert make(app_env="production").effective_enable_demo_reset is False
    assert make(app_env="production", enable_demo_reset=True).effective_enable_demo_reset is True
    assert make(enable_demo_reset=False).effective_enable_demo_reset is False


def test_demo_seed_defaults_and_override():
    assert make().effective_seed_demo_data is True
    assert make(app_env="production").effective_seed_demo_data is False
    assert make(app_env="production", seed_demo_data=True).effective_seed_demo_data is True
