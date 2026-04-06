"""Global configuration loaded from the local .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    APP_NAME: str = "求职智能管家"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096

    MAX_DAILY_DELIVERY: int = Field(default=20, ge=1, le=50, description="单日最大投递量")
    MIN_DELAY_SECONDS: int = Field(default=2, ge=1, le=10, description="最小投递延迟")
    MAX_DELAY_SECONDS: int = Field(default=4, ge=1, le=10, description="最大投递延迟")
    DELIVERY_START_HOUR: int = Field(default=9, ge=0, le=23, description="投递开始时段")
    DELIVERY_END_HOUR: int = Field(default=18, ge=0, le=23, description="投递结束时段")
    MATCH_THRESHOLD: int = Field(default=70, ge=0, le=100, description="最低匹配分阈值")

    ENCRYPTION_KEY: str = Field(default="", description="本地加密密钥")
    COOKIE_EXPIRE_DAYS: int = Field(default=7, ge=1, description="Cookie 过期天数")

    PLATFORM: str = Field(default="boss", description="当前招聘平台")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "job_agent.db"
RESUME_DIR = DATA_DIR / "resumes"
BACKUP_DIR = DATA_DIR / "backups"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

for directory in (DATA_DIR, LOG_DIR, RESUME_DIR, BACKUP_DIR, SCREENSHOT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return the shared settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Reload settings from disk."""
    get_settings.cache_clear()
    return get_settings()


def update_env_file(updates: dict[str, str]) -> None:
    """Update or append keys in the project .env file."""
    env_path = BASE_DIR / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line if line.endswith("\n") else line + "\n")

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    env_path.write_text("".join(new_lines), encoding="utf-8")
