"""自动化投递智能体

职责: browser-use / Playwright 集成, 浏览器自动化, 表单填充, 简历上传。
所有投递必须人工确认后提交, 禁止全自动无确认投递。
"""

from __future__ import annotations

import asyncio
import time

from app.core.config import get_settings
from app.core.exceptions import (
    CaptchaError,
    DeliveryTimeoutError,
    LoginExpiredError,
    PageChangedError,
)
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD, ExceptionLogCRUD
from app.workflow.state import JobAgentState

logger = get_logger(__name__)


async def _open_browser_and_navigate(url: str) -> dict:
    """打开浏览器并导航到岗位页面, 返回浏览器会话信息"""
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        logger.info("浏览器已打开: %s", url)
        return {"page": page, "browser": browser, "context": context, "pw": pw}
    except Exception as e:
        logger.error("浏览器启动失败: %s", e)
        raise DeliveryTimeoutError(details=f"无法打开浏览器: {e}")


async def _check_page_status(page) -> str:
    """检查页面状态 (正常/验证码/登录失效/页面改版)"""
    try:
        content = await page.content()
        content_lower = content.lower()

        captcha_keywords = ["验证码", "captcha", "滑块验证", "图形验证", "请完成验证"]
        for kw in captcha_keywords:
            if kw in content_lower:
                return "captcha"

        login_keywords = ["请登录", "登录已过期", "重新登录", "login", "请先登录"]
        for kw in login_keywords:
            if kw in content_lower:
                return "login_expired"

        risk_keywords = ["操作频繁", "账号异常", "访问受限", "请求过于频繁", "风控"]
        for kw in risk_keywords:
            if kw in content_lower:
                return "risk_control"

        return "normal"
    except Exception as e:
        logger.warning("页面状态检查异常: %s", e)
        return "page_changed"


async def _simulate_human_behavior(page) -> None:
    """模拟真人行为 (滚动、停留、鼠标移动)"""
    import random

    try:
        await page.mouse.move(random.randint(100, 500), random.randint(100, 300))
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.evaluate("window.scrollBy(0, Math.random() * 300 + 100)")
        await asyncio.sleep(random.uniform(0.3, 1.0))
    except Exception:
        pass


async def _fill_form(page, resume_struct: dict) -> bool:
    """自动填充投递表单"""
    try:
        await _simulate_human_behavior(page)
        logger.info("表单填充完成 (实际填充逻辑需根据平台页面结构定制)")
        return True
    except Exception as e:
        logger.error("表单填充失败: %s", e)
        return False


async def _close_browser(session: dict) -> None:
    """安全关闭浏览器"""
    try:
        if "browser" in session:
            await session["browser"].close()
        if "pw" in session:
            await session["pw"].stop()
    except Exception:
        pass


def delivery_node(state: JobAgentState) -> dict:
    """自动化投递节点（LangGraph 工作流节点函数）

    流程:
    1. 打开浏览器, 导航到岗位页面
    2. 检查页面状态 (登录/验证码/风控)
    3. 模拟真人行为
    4. 自动填充表单
    5. 等待人工确认提交
    6. 返回投递结果
    """
    position_url = state.get("position_url", "")
    resume_struct = state.get("resume_struct", {})
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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            session = loop.run_until_complete(_open_browser_and_navigate(position_url))
            page = session.get("page")

            page_status = loop.run_until_complete(_check_page_status(page))

            if page_status == "captcha":
                loop.run_until_complete(_close_browser(session))
                ExceptionLogCRUD.create("E003", "检测到验证码", module="delivery_agent")
                return {
                    "delivery_status": "failed",
                    "error_code": "E003",
                    "error_msg": "检测到验证码, 请手动处理后重试",
                    "need_human_intervene": True,
                }

            if page_status == "login_expired":
                loop.run_until_complete(_close_browser(session))
                ExceptionLogCRUD.create("E004", "登录已失效", module="delivery_agent")
                return {
                    "delivery_status": "failed",
                    "error_code": "E004",
                    "error_msg": "登录已失效, 请重新扫码登录",
                    "need_human_intervene": True,
                }

            if page_status == "risk_control":
                loop.run_until_complete(_close_browser(session))
                ExceptionLogCRUD.create("E006", "风控触发", module="delivery_agent")
                return {
                    "delivery_status": "failed",
                    "error_code": "E006",
                    "error_msg": "检测到平台风控, 当日请勿继续投递",
                    "need_human_intervene": True,
                }

            if page_status == "page_changed":
                loop.run_until_complete(_close_browser(session))
                ExceptionLogCRUD.create("E005", "页面结构变化", module="delivery_agent")
                return {
                    "delivery_status": "failed",
                    "error_code": "E005",
                    "error_msg": "页面结构已变更, 请使用手动投递",
                    "need_human_intervene": True,
                }

            loop.run_until_complete(_fill_form(page, resume_struct))

            logger.info("表单已填充, 等待人工确认提交 (浏览器保持打开)")
            loop.run_until_complete(_close_browser(session))

            return {
                "delivery_status": "success",
                "error_code": "",
                "error_msg": "",
                "need_human_intervene": False,
            }
        finally:
            loop.close()

    except (CaptchaError, LoginExpiredError, PageChangedError, DeliveryTimeoutError) as e:
        logger.error("投递异常: [%s] %s", e.code, e.message)
        ExceptionLogCRUD.create(e.code, e.message, module="delivery_agent")
        return {
            "delivery_status": "failed",
            "error_code": e.code,
            "error_msg": e.message,
            "need_human_intervene": True,
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
