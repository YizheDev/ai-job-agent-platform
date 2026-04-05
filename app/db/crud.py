"""数据库 CRUD 操作

提供所有数据表的增删改查，支持事务和异常处理。
所有业务表操作通过 user_name 参数实现多用户数据隔离。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

from app.core.exceptions import DatabaseError
from app.core.logger import get_logger
from app.db.models import get_connection

logger = get_logger(__name__)


@contextmanager
def _get_db():
    """数据库连接上下文管理器（自动提交/回滚/关闭）"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("数据库操作失败: %s", e)
        raise DatabaseError(details=str(e))
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """sqlite3.Row 转 dict"""
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    """sqlite3.Row 列表转 dict 列表"""
    return [dict(r) for r in rows]


# ================================================================
# 简历 CRUD
# ================================================================
class ResumeCRUD:
    """简历表操作"""

    @staticmethod
    def create(
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int = 0,
        struct_data: str = "{}",
        is_original: bool = True,
        parent_id: int | None = None,
        version_label: str = "",
        user_name: str = "",
    ) -> int:
        """创建简历记录，返回新记录ID"""
        with _get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO resume
                   (user_name, file_name, file_path, file_type, file_size,
                    struct_data, is_original, parent_id, version_label)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_name, file_name, file_path, file_type, file_size,
                 struct_data, 1 if is_original else 0, parent_id, version_label),
            )
            resume_id = cursor.lastrowid
            logger.info("创建简历记录: id=%d, name=%s, user=%s", resume_id, file_name, user_name)
            return resume_id

    @staticmethod
    def get_by_id(resume_id: int) -> dict | None:
        """根据ID查询简历"""
        with _get_db() as conn:
            row = conn.execute("SELECT * FROM resume WHERE id = ?", (resume_id,)).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def get_all(original_only: bool = False, user_name: str = "") -> list[dict]:
        """查询当前用户的所有简历"""
        with _get_db() as conn:
            sql = "SELECT * FROM resume WHERE user_name = ?"
            params: list = [user_name]
            if original_only:
                sql += " AND is_original = 1"
            sql += " ORDER BY create_time DESC"
            rows = conn.execute(sql, params).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def get_versions(parent_id: int) -> list[dict]:
        """获取指定简历的所有优化版本"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM resume WHERE parent_id = ? ORDER BY create_time DESC",
                (parent_id,),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def count_versions(parent_id: int) -> int:
        """统计优化版本数量"""
        with _get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM resume WHERE parent_id = ?", (parent_id,)
            ).fetchone()
            return row["cnt"] if row else 0

    @staticmethod
    def update(resume_id: int, **kwargs) -> bool:
        """更新简历字段"""
        if not kwargs:
            return False
        allowed = {"file_name", "file_path", "struct_data", "is_default",
                    "version_label", "is_encrypted", "update_time"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        fields["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [resume_id]
        with _get_db() as conn:
            conn.execute(f"UPDATE resume SET {set_clause} WHERE id = ?", values)
            logger.info("更新简历记录: id=%d, fields=%s", resume_id, list(fields.keys()))
            return True

    @staticmethod
    def set_default(resume_id: int, user_name: str = "") -> bool:
        """设置默认简历（仅重置当前用户的默认标记）"""
        with _get_db() as conn:
            conn.execute(
                "UPDATE resume SET is_default = 0 WHERE user_name = ?", (user_name,)
            )
            conn.execute(
                "UPDATE resume SET is_default = 1 WHERE id = ? AND user_name = ?",
                (resume_id, user_name),
            )
            logger.info("设置默认简历: id=%d, user=%s", resume_id, user_name)
            return True

    @staticmethod
    def delete(resume_id: int) -> bool:
        """删除简历 (同时删除关联的优化版本)"""
        with _get_db() as conn:
            row = conn.execute("SELECT id FROM resume WHERE id = ?", (resume_id,)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM resume WHERE parent_id = ?", (resume_id,))
            conn.execute("DELETE FROM resume WHERE id = ?", (resume_id,))
            logger.info("删除简历记录: id=%d", resume_id)
            return True


# ================================================================
# 投递记录 CRUD
# ================================================================
class DeliveryRecordCRUD:
    """投递记录表操作"""

    @staticmethod
    def create(
        company: str,
        position: str,
        position_url: str,
        platform: str = "boss",
        resume_id: int | None = None,
        match_score: int = 0,
        match_feedback: str = "[]",
        cover_letter: str = "",
        status: str = "pending",
        user_name: str = "",
    ) -> int:
        """创建投递记录"""
        with _get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO delivery_record
                   (user_name, company, position, position_url, platform, resume_id,
                    match_score, match_feedback, cover_letter, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_name, company, position, position_url, platform, resume_id,
                 match_score, match_feedback, cover_letter, status),
            )
            record_id = cursor.lastrowid
            logger.info("创建投递记录: id=%d, company=%s, user=%s", record_id, company, user_name)
            return record_id

    @staticmethod
    def get_by_id(record_id: int) -> dict | None:
        """根据ID查询投递记录"""
        with _get_db() as conn:
            row = conn.execute("SELECT * FROM delivery_record WHERE id = ?", (record_id,)).fetchone()
            return _row_to_dict(row)

    @staticmethod
    def get_all(
        status: str | None = None,
        days: int | None = None,
        limit: int = 100,
        offset: int = 0,
        user_name: str = "",
    ) -> list[dict]:
        """查询当前用户的投递记录"""
        conditions = ["user_name = ?"]
        params: list = [user_name]
        if status:
            conditions.append("status = ?")
            params.append(status)
        if days:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            conditions.append("create_time >= ?")
            params.append(since)
        where = "WHERE " + " AND ".join(conditions)
        params.extend([limit, offset])
        with _get_db() as conn:
            rows = conn.execute(
                f"SELECT * FROM delivery_record {where} ORDER BY create_time DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def get_recent(count: int = 5, user_name: str = "") -> list[dict]:
        """获取当前用户最近N条投递记录"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM delivery_record WHERE user_name = ? ORDER BY create_time DESC LIMIT ?",
                (user_name, count),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def get_today_count(user_name: str = "") -> int:
        """获取当前用户今日投递数量"""
        today = datetime.now().strftime("%Y-%m-%d")
        with _get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM delivery_record "
                "WHERE user_name = ? AND date(create_time) = ? "
                "AND status IN ('success', 'delivering', 'confirmed')",
                (user_name, today),
            ).fetchone()
            return row["cnt"] if row else 0

    @staticmethod
    def get_total_count(user_name: str = "") -> int:
        """获取当前用户累计投递总数"""
        with _get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM delivery_record WHERE user_name = ?",
                (user_name,),
            ).fetchone()
            return row["cnt"] if row else 0

    @staticmethod
    def get_avg_score(days: int = 7, user_name: str = "") -> float:
        """获取当前用户近N日平均匹配分"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with _get_db() as conn:
            row = conn.execute(
                "SELECT AVG(match_score) as avg_score FROM delivery_record "
                "WHERE user_name = ? AND create_time >= ? AND match_score > 0",
                (user_name, since),
            ).fetchone()
            return round(row["avg_score"], 1) if row and row["avg_score"] else 0.0

    @staticmethod
    def get_daily_stats(days: int = 7, user_name: str = "") -> list[dict]:
        """获取当前用户近N日每日投递量统计"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with _get_db() as conn:
            rows = conn.execute(
                """SELECT date(create_time) as date, COUNT(*) as count
                   FROM delivery_record
                   WHERE user_name = ? AND date(create_time) >= ?
                   GROUP BY date(create_time) ORDER BY date""",
                (user_name, since),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def get_score_distribution(user_name: str = "") -> dict:
        """获取当前用户匹配分数分布"""
        with _get_db() as conn:
            high = conn.execute(
                "SELECT COUNT(*) as cnt FROM delivery_record WHERE user_name = ? AND match_score >= 85",
                (user_name,),
            ).fetchone()
            mid = conn.execute(
                "SELECT COUNT(*) as cnt FROM delivery_record "
                "WHERE user_name = ? AND match_score >= 60 AND match_score < 85",
                (user_name,),
            ).fetchone()
            low = conn.execute(
                "SELECT COUNT(*) as cnt FROM delivery_record "
                "WHERE user_name = ? AND match_score < 60 AND match_score > 0",
                (user_name,),
            ).fetchone()
            return {
                "high": high["cnt"] if high else 0,
                "medium": mid["cnt"] if mid else 0,
                "low": low["cnt"] if low else 0,
            }

    @staticmethod
    def update_status(record_id: int, status: str, error_code: str = "", error_msg: str = "") -> bool:
        """更新投递状态"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _get_db() as conn:
            conn.execute(
                "UPDATE delivery_record SET status = ?, error_code = ?, error_msg = ?, update_time = ? WHERE id = ?",
                (status, error_code, error_msg, now, record_id),
            )
            logger.info("更新投递状态: id=%d, status=%s", record_id, status)
            return True

    @staticmethod
    def delete(record_id: int) -> bool:
        """删除投递记录"""
        with _get_db() as conn:
            conn.execute("DELETE FROM delivery_record WHERE id = ?", (record_id,))
            logger.info("删除投递记录: id=%d", record_id)
            return True


# ================================================================
# 系统配置 CRUD
# ================================================================
class SysConfigCRUD:
    """系统配置表操作（按 user_name 隔离）"""

    @staticmethod
    def get(key: str, user_name: str = "") -> str | None:
        """获取配置值"""
        with _get_db() as conn:
            row = conn.execute(
                "SELECT config_value FROM sys_config WHERE config_key = ? AND user_name = ?",
                (key, user_name),
            ).fetchone()
            return row["config_value"] if row else None

    @staticmethod
    def set(key: str, value: str, description: str = "", user_name: str = "") -> None:
        """设置配置值（存在则更新，不存在则创建）"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM sys_config WHERE config_key = ? AND user_name = ?",
                (key, user_name),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE sys_config SET config_value = ?, update_time = ? "
                    "WHERE config_key = ? AND user_name = ?",
                    (value, now, key, user_name),
                )
            else:
                conn.execute(
                    "INSERT INTO sys_config (user_name, config_key, config_value, description) "
                    "VALUES (?, ?, ?, ?)",
                    (user_name, key, value, description),
                )
            logger.debug("配置更新: [%s] %s = %s", user_name, key, value[:50] if len(value) > 50 else value)

    @staticmethod
    def get_all(user_name: str = "") -> dict[str, str]:
        """获取当前用户所有配置"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT config_key, config_value FROM sys_config WHERE user_name = ?",
                (user_name,),
            ).fetchall()
            return {r["config_key"]: r["config_value"] for r in rows}

    @staticmethod
    def delete(key: str, user_name: str = "") -> bool:
        """删除配置"""
        with _get_db() as conn:
            conn.execute(
                "DELETE FROM sys_config WHERE config_key = ? AND user_name = ?",
                (key, user_name),
            )
            return True


# ================================================================
# 异常日志 CRUD (系统全局, 不按用户隔离)
# ================================================================
class ExceptionLogCRUD:
    """异常日志表操作"""

    @staticmethod
    def create(
        error_code: str,
        error_msg: str,
        error_detail: str = "",
        module: str = "",
        screenshot_path: str = "",
    ) -> int:
        """记录异常日志"""
        with _get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO exception_log
                   (error_code, error_msg, error_detail, module, screenshot_path)
                   VALUES (?, ?, ?, ?, ?)""",
                (error_code, error_msg, error_detail, module, screenshot_path),
            )
            log_id = cursor.lastrowid
            logger.warning("异常日志记录: [%s] %s (module=%s)", error_code, error_msg, module)
            return log_id

    @staticmethod
    def get_all(limit: int = 100) -> list[dict]:
        """获取所有异常日志"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM exception_log ORDER BY create_time DESC LIMIT ?", (limit,)
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def get_recent(count: int = 10) -> list[dict]:
        """获取最近N条异常日志"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM exception_log ORDER BY create_time DESC LIMIT ?", (count,)
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def mark_resolved(log_id: int) -> bool:
        """标记异常已解决"""
        with _get_db() as conn:
            conn.execute("UPDATE exception_log SET resolved = 1 WHERE id = ?", (log_id,))
            return True

    @staticmethod
    def delete(log_id: int) -> bool:
        """删除异常日志"""
        with _get_db() as conn:
            conn.execute("DELETE FROM exception_log WHERE id = ?", (log_id,))
            return True

    @staticmethod
    def cleanup_old(days: int = 30) -> int:
        """清理N天前的异常日志"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with _get_db() as conn:
            cursor = conn.execute("DELETE FROM exception_log WHERE create_time < ?", (cutoff,))
            count = cursor.rowcount
            logger.info("清理过期异常日志: %d条 (超过%d天)", count, days)
            return count


# ================================================================
# JD匹配记录 CRUD
# ================================================================
class JDMatchRecordCRUD:
    """JD匹配记录表操作"""

    @staticmethod
    def create(
        resume_id: int,
        jd_text: str,
        jd_struct: str = "{}",
        match_score: int = 0,
        match_items: str = "[]",
        missing_items: str = "[]",
        weak_items: str = "[]",
        user_name: str = "",
    ) -> int:
        """创建匹配记录"""
        with _get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO jd_match_record
                   (user_name, resume_id, jd_text, jd_struct, match_score,
                    match_items, missing_items, weak_items)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_name, resume_id, jd_text, jd_struct, match_score,
                 match_items, missing_items, weak_items),
            )
            return cursor.lastrowid

    @staticmethod
    def get_by_resume(resume_id: int, user_name: str = "") -> list[dict]:
        """获取指定简历的匹配记录"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM jd_match_record WHERE resume_id = ? AND user_name = ? "
                "ORDER BY create_time DESC",
                (resume_id, user_name),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def get_all(limit: int = 50, user_name: str = "") -> list[dict]:
        """获取当前用户所有匹配记录"""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM jd_match_record WHERE user_name = ? "
                "ORDER BY create_time DESC LIMIT ?",
                (user_name, limit),
            ).fetchall()
            return _rows_to_list(rows)

    @staticmethod
    def delete(record_id: int) -> bool:
        """删除匹配记录"""
        with _get_db() as conn:
            conn.execute("DELETE FROM jd_match_record WHERE id = ?", (record_id,))
            return True
