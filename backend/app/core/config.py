from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    # Environment variables win, then backend/.env, then the project-root .env.
    # Resolve from this file so launching from either working directory is stable.
    model_config = SettingsConfigDict(env_file=(PROJECT_ROOT / '.env', BACKEND_ROOT / '.env'),
                                      extra='ignore', hide_input_in_errors=True)

    supabase_url: str
    supabase_publishable_key: SecretStr
    supabase_secret_key: SecretStr = SecretStr('')
    gemini_api_key: SecretStr = SecretStr('')

    @field_validator('supabase_url')
    @classmethod
    def secure_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.path not in ('', '/') or url.query or url.fragment):
            raise ValueError('SUPABASE_URL must be an HTTPS origin')
        return value.rstrip('/')

    @field_validator('supabase_publishable_key')
    @classmethod
    def public_key(cls, value: SecretStr) -> SecretStr:
        # Modern publishable keys only: prevent accidentally using a bypass-RLS key.
        if not value.get_secret_value().startswith('sb_publishable_'):
            raise ValueError('Use a modern Supabase publishable key')
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
