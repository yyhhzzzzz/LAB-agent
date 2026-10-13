import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)
_EPHEMERAL_AUTH_SECRET = secrets.token_urlsafe(32)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("{} must be an integer".format(name)) from exc


def _storage_path_env() -> Path:
    configured_path = (
        os.getenv("DOCUMENT_STORAGE_PATH", "data/uploads").strip() or "data/uploads"
    )
    path = Path(configured_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: str
    openai_api_base: str
    chat_model_name: str
    document_context_max_chars: int
    document_storage_path: Path
    document_upload_max_bytes: int
    auth_token_secret: str
    auth_token_expire_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            database_path = PROJECT_ROOT / "data" / "lab_device_assistant.sqlite3"
            database_url = "sqlite+aiosqlite:///{}".format(database_path.as_posix())
        else:
            parsed_database_url = make_url(database_url)
            if parsed_database_url.get_backend_name() == "sqlite":
                parsed_database_url = parsed_database_url.set(drivername="sqlite+aiosqlite")
            elif parsed_database_url.get_backend_name() == "postgresql":
                parsed_database_url = parsed_database_url.set(drivername="postgresql+asyncpg")
            else:
                raise ValueError("DATABASE_URL must use SQLite or PostgreSQL")
            if (
                parsed_database_url.get_backend_name() == "sqlite"
                and parsed_database_url.database not in {None, "", ":memory:"}
                and not Path(parsed_database_url.database).is_absolute()
            ):
                database_path = PROJECT_ROOT / parsed_database_url.database
                parsed_database_url = parsed_database_url.set(database=str(database_path.resolve()))
            database_url = parsed_database_url.render_as_string(hide_password=False)

        settings = cls(
            database_url=database_url,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_api_base=os.getenv("OPENAI_API_BASE", "").strip(),
            chat_model_name=os.getenv("CHAT_MODEL_NAME", "gpt-4o-mini").strip(),
            document_context_max_chars=_int_env("DOCUMENT_CONTEXT_MAX_CHARS", 60000),
            document_storage_path=_storage_path_env(),
            document_upload_max_bytes=_int_env("DOCUMENT_UPLOAD_MAX_BYTES", 26214400),
            auth_token_secret=os.getenv("SECRET_KEY", "").strip() or _EPHEMERAL_AUTH_SECRET,
            auth_token_expire_minutes=_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 1440),
        )
        if settings.document_context_max_chars < 1:
            raise ValueError("DOCUMENT_CONTEXT_MAX_CHARS must be greater than zero")
        if settings.document_upload_max_bytes < 1:
            raise ValueError("DOCUMENT_UPLOAD_MAX_BYTES must be greater than zero")
        if settings.auth_token_expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero")
        if not settings.chat_model_name:
            raise ValueError("CHAT_MODEL_NAME must not be empty")
        return settings
