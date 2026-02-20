import json
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


API_KEYS_FILE = Path(__file__).resolve().parent.parent.parent / "api_keys.json"


def _load_api_keys() -> dict:
    """Load API keys from the persistent JSON file."""
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_api_keys(keys: dict) -> None:
    """Save API keys to the persistent JSON file."""
    existing = _load_api_keys()
    existing.update(keys)
    with open(API_KEYS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


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
        """Get API key: first check api_keys.json, then fall back to env/settings."""
        stored = _load_api_keys()
        key_map = {
            "serper": "SERPER_API_KEY",
            "apollo": "APOLLO_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_attr = key_map.get(service, "")
        stored_val = stored.get(env_attr, "")
        if stored_val:
            return stored_val
        return getattr(self, env_attr, "")

    def set_api_key(self, service: str, value: str) -> None:
        """Persist an API key to api_keys.json."""
        key_map = {
            "serper": "SERPER_API_KEY",
            "apollo": "APOLLO_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        env_attr = key_map.get(service)
        if env_attr:
            _save_api_keys({env_attr: value.strip()})

    def get_model(self) -> str:
        """Get the configured OpenAI model: check api_keys.json first, then fall back to env/settings."""
        stored = _load_api_keys()
        stored_model = stored.get("OPENAI_MODEL", "")
        if stored_model:
            return stored_model
        return self.OPENAI_MODEL

    def set_model(self, model: str) -> None:
        """Persist the OpenAI model choice to api_keys.json."""
        _save_api_keys({"OPENAI_MODEL": model.strip()})

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
