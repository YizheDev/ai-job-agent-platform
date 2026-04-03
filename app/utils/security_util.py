"""安全工具类

AES 加密/解密 (基于 Fernet), Cookie 管理, 数据脱敏, 一键清理。
所有敏感数据 (简历/Cookie/API 密钥) 加密本地存储, 不上传云端。
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from app.core.config import DATA_DIR, RESUME_DIR, SCREENSHOT_DIR, get_settings
from app.core.exceptions import EncryptionError
from app.core.logger import get_logger

logger = get_logger(__name__)

_COOKIE_FILE = DATA_DIR / ".cookies.enc"
_KEY_FILE = DATA_DIR / ".keyfile"


def generate_encryption_key() -> str:
    """生成 Fernet 加密密钥 (base64 编码)"""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def _get_fernet():
    """获取 Fernet 实例"""
    from cryptography.fernet import Fernet

    settings = get_settings()
    key = settings.ENCRYPTION_KEY
    if not key:
        if _KEY_FILE.exists():
            key = _KEY_FILE.read_text(encoding="utf-8").strip()
        else:
            key = generate_encryption_key()
            _KEY_FILE.write_text(key, encoding="utf-8")
            logger.info("自动生成加密密钥并保存")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise EncryptionError(details=f"加密密钥格式错误: {e}")


def encrypt_data(data: str) -> str:
    """加密字符串数据"""
    try:
        f = _get_fernet()
        return f.encrypt(data.encode("utf-8")).decode("utf-8")
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(details=f"加密失败: {e}")


def decrypt_data(encrypted: str) -> str:
    """解密字符串数据"""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(details=f"解密失败: {e}")


def save_cookie(cookie_data: dict) -> None:
    """加密保存 Cookie"""
    raw = json.dumps(cookie_data, ensure_ascii=False)
    encrypted = encrypt_data(raw)
    _COOKIE_FILE.write_text(encrypted, encoding="utf-8")
    logger.info("Cookie 已加密保存")


def load_cookie() -> dict | None:
    """加载解密 Cookie"""
    if not _COOKIE_FILE.exists():
        return None
    try:
        encrypted = _COOKIE_FILE.read_text(encoding="utf-8")
        raw = decrypt_data(encrypted)
        return json.loads(raw)
    except Exception as e:
        logger.warning("Cookie 加载失败: %s", e)
        return None


def clear_cookie() -> None:
    """清除 Cookie"""
    if _COOKIE_FILE.exists():
        _COOKIE_FILE.unlink()
        logger.info("Cookie 已清除")


def mask_sensitive(text: str, keep_start: int = 3, keep_end: int = 4) -> str:
    """数据脱敏 (保留前 N 位和后 N 位, 中间用 * 替代)"""
    if len(text) <= keep_start + keep_end:
        return text
    return text[:keep_start] + "*" * (len(text) - keep_start - keep_end) + text[-keep_end:]


def wipe_all_data() -> bool:
    """一键清除所有本地数据 (不可恢复)"""
    try:
        for target_dir in (RESUME_DIR, SCREENSHOT_DIR):
            if target_dir.exists():
                shutil.rmtree(str(target_dir))
                target_dir.mkdir(parents=True, exist_ok=True)

        db_path = DATA_DIR / "job_agent.db"
        if db_path.exists():
            db_path.unlink()

        clear_cookie()

        if _KEY_FILE.exists():
            _KEY_FILE.unlink()

        logger.warning("所有本地数据已清除")
        return True
    except Exception as e:
        logger.error("数据清除失败: %s", e)
        return False
