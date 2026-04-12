"""全局配置模块

从 .env 文件读取配置，管理所有风控参数、大模型配置、平台配置。
支持通过 reload_settings() 实现热更新。
"""

from __future__ import annotations

import os
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置类（所有配置从 .env 读取，禁止硬编码）"""

    # --- 项目基础 ---
    APP_NAME: str = "AI求职智能管家"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --- 大模型配置 ---
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096

    # --- 风控参数（严格遵循PRD默认值） ---
    MAX_DAILY_DELIVERY: int = Field(default=20, ge=1, le=50, description="单日最大投递量")
    MIN_DELAY_SECONDS: int = Field(default=2, ge=1, le=10, description="最小投递延时(秒)")
    MAX_DELAY_SECONDS: int = Field(default=4, ge=1, le=10, description="最大投递延时(秒)")
    DELIVERY_START_HOUR: int = Field(default=9, ge=0, le=23, description="投递开始时段")
    DELIVERY_END_HOUR: int = Field(default=18, ge=1, le=24, description="投递结束时段")
    MATCH_THRESHOLD: int = Field(default=70, ge=0, le=100, description="最低匹配分数阈值")

    # --- 安全配置 ---
    ENCRYPTION_KEY: str = Field(default="", description="AES加密密钥(base64)")
    COOKIE_EXPIRE_DAYS: int = Field(default=7, ge=1, description="Cookie过期天数")

    # --- 平台配置 ---
    PLATFORM: str = Field(default="boss", description="当前招聘平台(boss)")
    SERVER_PORT: int = Field(default=7860, ge=1024, le=65535, description="服务端口")

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:
        if self.DELIVERY_START_HOUR >= self.DELIVERY_END_HOUR:
            object.__setattr__(self, "DELIVERY_START_HOUR", 9)
            object.__setattr__(self, "DELIVERY_END_HOUR", 18)
        if self.MIN_DELAY_SECONDS > self.MAX_DELAY_SECONDS:
            object.__setattr__(self, "MIN_DELAY_SECONDS", self.MAX_DELAY_SECONDS)


# ===== 路径配置（基于项目根目录推导，不从 .env 读取） =====
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "job_agent.db"
RESUME_DIR = DATA_DIR / "resumes"
BACKUP_DIR = DATA_DIR / "backups"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

# 确保必要目录存在
for _dir in (DATA_DIR, LOG_DIR, RESUME_DIR, BACKUP_DIR, SCREENSHOT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


_settings_lock = threading.Lock()


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()


def reload_settings() -> Settings:
    """热更新配置（重新读取 .env）

    如果 .env 中有无效值导致 ValidationError，缓存保持为空，
    下次 get_settings() 会重新尝试加载。
    """
    with _settings_lock:
        get_settings.cache_clear()
        return get_settings()


_env_lock = threading.Lock()


def update_env_file(updates: dict[str, str]) -> None:
    """将键值对写入 .env 文件，已有的 key 就地更新，没有的追加

    使用临时文件 + os.replace 实现原子写入，防止断电/崩溃导致 .env 损坏。
    """
    env_path = BASE_DIR / ".env"
    with _env_lock:
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

        content = "".join(new_lines)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(env_path.parent), suffix=".tmp", prefix=".env_",
        )
        closed = False
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            closed = True
            os.replace(tmp_path, str(env_path))
        except Exception:
            if not closed:
                os.close(fd)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
