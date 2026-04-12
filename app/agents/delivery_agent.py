"""自动化投递智能体

职责: 通过 BossCrawler 发起岗位沟通/投递。
复用全局 BossCrawler 实例, 继承反调试绕过、Cookie 持久化、反检测等能力。
所有投递必须人工确认后提交, 禁止全自动无确认投递。
"""

from __future__ import annotations

from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD, ExceptionLogCRUD
from app.utils.boss_crawler import get_crawler
from app.workflow.state import JobAgentState

logger = get_logger(__name__)


def delivery_node(state: JobAgentState) -> dict:
    """自动化投递节点（LangGraph 工作流节点函数）

    通过全局 BossCrawler 发起沟通, 复用已有登录态和反调试设置。
    """
    position_url = state.get("position_url", "")
    company = state.get("company", "")
    position = state.get("position", "")
    logger.info("===== 自动化投递节点启动: %s - %s =====", company, position)

    if not position_url:
        return {
            "delivery_status": "failed",
            "error_code": "E007",
            "error_msg": "岗位链接为空",
        }

    try:
        c = get_crawler()

        if not c.is_running:
            ExceptionLogCRUD.create("E004", "浏览器未连接", module="delivery_agent")
            return {
                "delivery_status": "failed",
                "error_code": "E004",
                "error_msg": "浏览器未连接, 请先前往 BOSS 账号页面连接",
                "need_human_intervene": True,
            }

        if not c.is_logged_in:
            ExceptionLogCRUD.create("E004", "未登录 BOSS 直聘", module="delivery_agent")
            return {
                "delivery_status": "failed",
                "error_code": "E004",
                "error_msg": "未登录 BOSS 直聘, 请先登录",
                "need_human_intervene": True,
            }

        if c.is_applied(position_url):
            return {
                "delivery_status": "cancelled",
                "error_code": "",
                "error_msg": "该岗位已沟通过, 跳过",
                "need_human_intervene": False,
            }

        greeting = c.greeting
        result = c.start_chat(position_url, greeting=greeting)

        if "已发起" in result or "沟通" in result:
            logger.info("投递成功: %s - %s", company, position)
            return {
                "delivery_status": "success",
                "error_code": "",
                "error_msg": "",
                "need_human_intervene": False,
            }

        is_login_issue = "登录" in result or "未连接" in result
        if is_login_issue:
            ExceptionLogCRUD.create("E004", result, module="delivery_agent")
            return {
                "delivery_status": "failed",
                "error_code": "E004",
                "error_msg": result,
                "need_human_intervene": True,
            }

        ExceptionLogCRUD.create("E007", result, module="delivery_agent")
        return {
            "delivery_status": "failed",
            "error_code": "E007",
            "error_msg": result,
            "need_human_intervene": False,
        }

    except Exception as e:
        logger.error("投递未知异常: %s", e)
        ExceptionLogCRUD.create("E007", str(e), module="delivery_agent")
        return {
            "delivery_status": "failed",
            "error_code": "E007",
            "error_msg": f"投递异常: {e}",
            "need_human_intervene": False,
        }
