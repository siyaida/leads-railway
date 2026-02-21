import logging
import secrets
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger(__name__)

KEY_MAP = {
    "serper": "SERPER_API_KEY",
    "apollo": "APOLLO_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _get_db_setting(key: str) -> Optional[str]:
    """Read a single setting from the app_settings table."""
    try:
        from app.core.database import SessionLocal
        from app.models.app_setting import AppSetting

        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            return row.value if row else None
        finally:
            db.close()
    except Exception as e:
        # Table may not exist yet during first startup
        logger.debug(f"Could not read DB setting {key}: {e}")
        return None


def _set_db_setting(key: str, value: str) -> None:
    """Write a single setting to the app_settings table (upsert)."""
    try:
        from app.core.database import SessionLocal
        from app.models.app_setting import AppSetting

        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            if row:
                row.value = value
            else:
                db.add(AppSetting(key=key, value=value))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Could not save DB setting {key}: {e}")


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./siyada_leads.db"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    SERPER_API_KEY: str = ""
    APOLLO_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def get_api_key(self, service: str) -> str:
        """Get API key: first check database, then fall back to env/settings."""
        env_attr = KEY_MAP.get(service, "")
        if not env_attr:
            return ""
        db_val = _get_db_setting(env_attr)
        if db_val:
            return db_val
        return getattr(self, env_attr, "")

    def set_api_key(self, service: str, value: str) -> None:
        """Persist an API key to the database."""
        env_attr = KEY_MAP.get(service)
        if env_attr:
            _set_db_setting(env_attr, value.strip())

    def get_model(self) -> str:
        """Get the configured OpenAI model: check database first, then fall back to env/settings."""
        db_val = _get_db_setting("OPENAI_MODEL")
        if db_val:
            return db_val
        return self.OPENAI_MODEL

    def set_model(self, model: str) -> None:
        """Persist the OpenAI model choice to the database."""
        _set_db_setting("OPENAI_MODEL", model.strip())

    def get_all_api_keys_masked(self) -> dict:
        """Return masked versions of all API keys for the settings UI."""
        result = {}
        for service in ("serper", "apollo", "openai"):
            key = self.get_api_key(service)
            if key and len(key) > 6:
                masked = key[:3] + "..." + key[-3:]
            elif key:
                masked = "***"
            else:
                masked = ""
            result[service] = {
                "configured": bool(key),
                "masked_key": masked,
            }
        return result


settings = Settings()
