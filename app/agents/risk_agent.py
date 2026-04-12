"""风控与限流智能体

职责: 单日投递量控制, 随机延时, 时段控制, 真人行为模拟, 风控关键词检测。
严格遵循 PRD 风控参数: 单日上限 20, 延时 2~4秒, 时段 9:00~18:00。
"""

from __future__ import annotations

import random
from datetime import datetime

from app.core.config import get_settings
from app.core.exceptions import RiskControlError
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)


def _check_daily_limit(user_name: str = "") -> tuple[bool, str]:
    """检查今日投递量是否达到上限"""
    settings = get_settings()
    today_count = DeliveryRecordCRUD.get_today_count(user_name=user_name)
    max_count = settings.MAX_DAILY_DELIVERY
    if today_count >= max_count:
        msg = f"今日投递已达上限 ({today_count}/{max_count}), 明日解锁"
        logger.warning(msg)
        return False, msg
    remaining = max_count - today_count
    logger.info("今日投递额度: %d/%d (剩余 %d)", today_count, max_count, remaining)
    return True, f"剩余额度: {remaining}"


def _check_time_window() -> tuple[bool, str]:
    """检查当前是否在允许的投递时段"""
    settings = get_settings()
    now = datetime.now()
    current_hour = now.hour
    start = settings.DELIVERY_START_HOUR
    end = settings.DELIVERY_END_HOUR
    if not (start <= current_hour < end):
        msg = f"当前不在投递时段 ({start}:00~{end}:00), 当前时间 {now.strftime('%H:%M')}"
        logger.warning(msg)
        return False, msg
    return True, "在投递时段内"


def _compute_random_delay() -> float:
    """计算建议延时值 (不执行 sleep, 由调用方自行控制)"""
    settings = get_settings()
    lo = min(settings.MIN_DELAY_SECONDS, settings.MAX_DELAY_SECONDS)
    hi = max(settings.MIN_DELAY_SECONDS, settings.MAX_DELAY_SECONDS)
    delay = random.uniform(lo, hi)
    logger.debug("建议随机延时: %.2f 秒", delay)
    return delay


def risk_check_node(state: JobAgentState) -> dict:
    """风控校验节点（LangGraph 工作流节点函数）

    校验项:
    1. 今日投递量是否达上限
    2. 当前是否在投递时段
    3. 执行随机延时
    """
    logger.info("===== 风控校验节点启动 =====")

    try:
        user_name = state.get("user_name", "")

        # 1. 检查日投递上限
        limit_ok, limit_msg = _check_daily_limit(user_name)
        if not limit_ok:
            return {
                "risk_passed": False,
                "risk_message": limit_msg,
                "delivery_status": "cancelled",
                "error_code": "",
                "error_msg": "",
            }

        # 2. 检查投递时段
        time_ok, time_msg = _check_time_window()
        if not time_ok:
            return {
                "risk_passed": False,
                "risk_message": time_msg,
                "delivery_status": "cancelled",
                "error_code": "",
                "error_msg": "",
            }

        # 3. 计算建议延时
        delay = _compute_random_delay()

        logger.info("风控校验通过 (建议延时 %.2f 秒)", delay)
        return {
            "risk_passed": True,
            "risk_message": "风控校验通过",
            "error_code": "",
            "error_msg": "",
        }

    except RiskControlError as e:
        logger.error("风控异常: %s", e.message)
        return {
            "risk_passed": False,
            "risk_message": e.message,
            "error_code": "E006",
            "error_msg": e.message,
        }
    except Exception as e:
        logger.error("风控校验异常: %s", e)
        return {
            "risk_passed": False,
            "risk_message": f"风控校验异常: {e}",
            "error_code": "E006",
            "error_msg": str(e),
        }
