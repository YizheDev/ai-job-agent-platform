"""全局配置模块

从 .env 文件读取配置，管理所有风控参数、大模型配置、平台配置。
支持通过 reload_settings() 实现热更新。
"""

from __future__ import annotations

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
    DELIVERY_END_HOUR: int = Field(default=18, ge=0, le=23, description="投递结束时段")
    MATCH_THRESHOLD: int = Field(default=70, ge=0, le=100, description="最低匹配分数阈值")

    # --- 安全配置 ---
    ENCRYPTION_KEY: str = Field(default="", description="AES加密密钥(base64)")
    COOKIE_EXPIRE_DAYS: int = Field(default=7, ge=1, description="Cookie过期天数")

    # --- 平台配置 ---
    PLATFORM: str = Field(default="boss", description="当前招聘平台(boss)")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


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


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()


def reload_settings() -> Settings:
    """热更新配置（重新读取 .env）"""
    get_settings.cache_clear()
    return get_settings()
