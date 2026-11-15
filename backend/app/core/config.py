from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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
    gemini_embedding_model: str = 'gemini-embedding-001'
    gemini_embedding_dimensions: int = Field(768, ge=768, le=768)
    gemini_generation_model: str = 'gemini-3.5-flash-lite'
    rag_chunk_words: int = Field(550, ge=100, le=800)
    rag_overlap_words: int = Field(80, ge=0, le=100)
    rag_chunk_max_bytes: int = Field(1800, ge=256, le=1800)
    rag_max_chunks: int = Field(128, ge=1, le=256)
    rag_max_text_chars: int = Field(200000, ge=1000, le=500000)
    rag_max_pdf_pages: int = Field(200, ge=1, le=1000)
    rag_extraction_timeout: int = Field(15, ge=1, le=30)
    rag_index_timeout: int = Field(180, ge=30, le=300)
    rag_similarity_threshold: float = Field(0.35, ge=-1, le=1)
    rag_default_top_k: int = Field(5, ge=1, le=10)
    rag_max_context_chars: int = Field(12000, ge=2000, le=20000)

    @field_validator('gemini_embedding_model', 'gemini_generation_model')
    @classmethod
    def model_identifier(cls, value: str) -> str:
        import re
        if not re.fullmatch(r'[a-zA-Z0-9._-]{1,100}', value):
            raise ValueError('Use an unqualified Gemini model identifier')
        return value

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
