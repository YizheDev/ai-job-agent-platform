"""SQLite 数据模型

定义所有数据表结构，提供数据库连接与初始化功能。
严格遵循技术设计文档的表结构定义。
支持 user_name 字段实现多用户数据隔离。
"""

from __future__ import annotations

import sqlite3

from app.core.config import DB_PATH
from app.core.logger import get_logger

logger = get_logger(__name__)

CREATE_TABLES_SQL = """
-- 简历表
CREATE TABLE IF NOT EXISTS resume (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name       TEXT    DEFAULT '',
    file_name       TEXT    NOT NULL,
    file_path       TEXT    NOT NULL,
    file_type       TEXT    NOT NULL CHECK(file_type IN ('pdf', 'docx')),
    file_size       INTEGER DEFAULT 0,
    struct_data     TEXT    DEFAULT '{}',
    is_original     INTEGER DEFAULT 1,
    parent_id       INTEGER DEFAULT NULL,
    version_label   TEXT    DEFAULT '',
    is_default      INTEGER DEFAULT 0,
    is_encrypted    INTEGER DEFAULT 0,
    create_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    update_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (parent_id) REFERENCES resume(id) ON DELETE SET NULL
);

-- 投递记录表
CREATE TABLE IF NOT EXISTS delivery_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name       TEXT    DEFAULT '',
    company         TEXT    NOT NULL,
    position        TEXT    NOT NULL,
    position_url    TEXT    NOT NULL,
    platform        TEXT    DEFAULT 'boss',
    resume_id       INTEGER,
    match_score     INTEGER DEFAULT 0,
    match_feedback  TEXT    DEFAULT '[]',
    cover_letter    TEXT    DEFAULT '',
    status          TEXT    DEFAULT 'pending'
        CHECK(status IN ('pending','confirmed','delivering','success','failed','cancelled','error')),
    error_code      TEXT    DEFAULT '',
    error_msg       TEXT    DEFAULT '',
    screenshot_path TEXT    DEFAULT '',
    create_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    update_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (resume_id) REFERENCES resume(id) ON DELETE SET NULL
);

-- 系统配置表
CREATE TABLE IF NOT EXISTS sys_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name       TEXT    DEFAULT '',
    config_key      TEXT    NOT NULL,
    config_value    TEXT    NOT NULL DEFAULT '',
    description     TEXT    DEFAULT '',
    create_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    update_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(user_name, config_key)
);

-- 异常日志表
CREATE TABLE IF NOT EXISTS exception_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    error_code      TEXT    NOT NULL,
    error_msg       TEXT    NOT NULL,
    error_detail    TEXT    DEFAULT '',
    module          TEXT    DEFAULT '',
    screenshot_path TEXT    DEFAULT '',
    resolved        INTEGER DEFAULT 0,
    create_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- JD匹配记录表
CREATE TABLE IF NOT EXISTS jd_match_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name       TEXT    DEFAULT '',
    resume_id       INTEGER,
    jd_text         TEXT    NOT NULL,
    jd_struct       TEXT    DEFAULT '{}',
    match_score     INTEGER DEFAULT 0,
    match_items     TEXT    DEFAULT '[]',
    missing_items   TEXT    DEFAULT '[]',
    weak_items      TEXT    DEFAULT '[]',
    create_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (resume_id) REFERENCES resume(id) ON DELETE SET NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（启用WAL模式和外键约束）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_add_user_name(conn: sqlite3.Connection) -> None:
    """为现有数据库添加 user_name 列以支持多用户数据隔离。

    仅在旧表缺少 user_name 列时执行, 新建库跳过。
    """
    cursor = conn.execute("PRAGMA table_info(resume)")
    columns = [row[1] for row in cursor.fetchall()]

    if "user_name" in columns:
        return

    logger.info("数据库迁移: 添加 user_name 列...")

    for table in ("resume", "delivery_record", "jd_match_record"):
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN user_name TEXT DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sys_config_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name       TEXT    DEFAULT '',
            config_key      TEXT    NOT NULL,
            config_value    TEXT    NOT NULL DEFAULT '',
            description     TEXT    DEFAULT '',
            create_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            update_time     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE(user_name, config_key)
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO sys_config_new
            (user_name, config_key, config_value, description, create_time, update_time)
        SELECT '', config_key, config_value, description, create_time, update_time
        FROM sys_config
    """)
    conn.execute("DROP TABLE sys_config")
    conn.execute("ALTER TABLE sys_config_new RENAME TO sys_config")

    conn.commit()
    logger.info("数据库迁移完成: user_name 列已添加")


def init_database() -> None:
    """初始化数据库（创建所有表，幂等操作）"""
    try:
        conn = get_connection()
        conn.executescript(CREATE_TABLES_SQL)
        _migrate_add_user_name(conn)
        conn.commit()
        conn.close()
        logger.info("数据库初始化成功: %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("数据库初始化失败: %s", e)
        raise
