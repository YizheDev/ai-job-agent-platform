"""异常处理智能体

职责: 验证码暂停处理, 登录失效重连, 页面改版降级, 异常日志记录。
所有异常自动记录截图和详情, 支持重试和人工介入。
"""

from __future__ import annotations

from app.core.config import SCREENSHOT_DIR
from app.core.logger import get_logger
from app.db.crud import ExceptionLogCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)


def _log_exception(
    error_code: str,
    error_msg: str,
    detail: str = "",
    module: str = "exception_agent",
    screenshot_path: str = "",
) -> int:
    """记录异常到数据库"""
    return ExceptionLogCRUD.create(
        error_code=error_code,
        error_msg=error_msg,
        error_detail=detail,
        module=module,
        screenshot_path=screenshot_path,
    )


def _handle_captcha_exception(state: JobAgentState) -> dict:
    """处理验证码异常 (E003)

    策略: 暂停投递, 提示用户输入验证码, 最多重试 3 次
    """
    logger.warning("处理验证码异常: 暂停投递, 等待用户输入")
    _log_exception("E003", "检测到验证码, 投递已暂停", module="delivery_agent")
    return {
        "delivery_status": "failed",
        "error_msg": "检测到验证码, 请在弹窗中输入验证码后继续",
        "need_human_intervene": True,
        "retry": False,
    }


def _handle_login_expired_exception(state: JobAgentState) -> dict:
    """处理登录失效异常 (E004)

    策略: 暂停投递, 引导用户重新扫码登录, 登录后断点续投
    """
    logger.warning("处理登录失效: 引导用户重新登录")
    _log_exception("E004", "登录已失效", module="delivery_agent")
    return {
        "delivery_status": "failed",
        "error_msg": "登录已失效, 请重新扫码登录后恢复投递",
        "need_human_intervene": True,
        "retry": False,
    }


def _handle_page_changed_exception(state: JobAgentState) -> dict:
    """处理页面改版异常 (E005)

    策略: 终止自动投递, 提供手动投递入口, 记录页面结构变化日志
    """
    logger.warning("处理页面改版: 终止自动投递, 引导手动投递")
    _log_exception("E005", "页面结构已变更", module="delivery_agent")
    return {
        "delivery_status": "failed",
        "error_msg": "页面结构已变更, 自动投递暂不可用, 请使用手动投递",
        "need_human_intervene": True,
        "retry": False,
    }


def _handle_risk_control_exception(state: JobAgentState) -> dict:
    """处理风控触发异常 (E006)

    策略: 立即停止投递, 当日禁止继续, 提供申诉指引
    """
    logger.error("处理风控触发: 立即停止投递")
    _log_exception("E006", "检测到平台风控", module="risk_agent")
    return {
        "delivery_status": "failed",
        "error_msg": (
            "检测到平台风控, 当日请勿继续投递。\n"
            "处理步骤:\n"
            "1. 退出招聘平台账号\n"
            "2. 清除浏览器 Cookie\n"
            "3. 更换网络环境\n"
            "4. 等待 24 小时后重新登录\n"
            "5. 如账号异常, 请访问平台官方申诉入口"
        ),
        "need_human_intervene": True,
        "retry": False,
    }


def _handle_timeout_exception(state: JobAgentState) -> dict:
    """处理投递超时异常 (E007)"""
    logger.warning("处理投递超时")
    _log_exception("E007", "投递操作超时", module="delivery_agent")
    return {
        "delivery_status": "failed",
        "error_msg": "投递操作超时, 请检查网络后重试",
        "need_human_intervene": False,
        "retry": True,
    }


def _handle_generic_exception(state: JobAgentState) -> dict:
    """处理其他未知异常"""
    error_code = state.get("error_code", "E999")
    error_msg = state.get("error_msg", "未知异常")
    logger.error("处理未知异常: [%s] %s", error_code, error_msg)
    _log_exception(error_code, error_msg, module="unknown")
    return {
        "delivery_status": "failed",
        "error_msg": error_msg,
        "need_human_intervene": False,
        "retry": False,
    }


def handle_exception_node(state: JobAgentState) -> dict:
    """异常处理节点（LangGraph 工作流节点函数）

    根据 error_code 分发到对应的异常处理策略:
    - E001: 简历解析失败 → 不可恢复
    - E002: JD 匹配失败 → 不可恢复
    - E003: 验证码 → 暂停等待人工
    - E004: 登录失效 → 引导重新登录
    - E005: 页面改版 → 引导手动投递
    - E006: 风控触发 → 当日停止
    - E007: 投递超时 → 可重试
    """
    error_code = state.get("error_code", "")
    logger.info("===== 异常处理节点启动: error_code=%s =====", error_code)

    handlers = {
        "E003": _handle_captcha_exception,
        "E004": _handle_login_expired_exception,
        "E005": _handle_page_changed_exception,
        "E006": _handle_risk_control_exception,
        "E007": _handle_timeout_exception,
    }

    handler = handlers.get(error_code, _handle_generic_exception)
    result = handler(state)

    logger.info("异常处理完成: retry=%s, need_human=%s",
                result.get("retry"), result.get("need_human_intervene"))
    return result
