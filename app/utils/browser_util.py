"""浏览器工具类

Playwright 浏览器会话管理, Cookie 加密存储/加载, 页面操作封装。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.core.logger import get_logger
from app.utils.security_util import clear_cookie, load_cookie, save_cookie

logger = get_logger(__name__)


class BrowserManager:
    """浏览器会话管理器 (单例)"""

    _instance: Optional[BrowserManager] = None
    _pw = None
    _browser = None
    _context = None
    _page = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def launch(self, headless: bool = False) -> None:
        """启动浏览器"""
        if self._browser:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        cookies = load_cookie()
        if cookies:
            try:
                await self._context.add_cookies(cookies)
                logger.info("已加载本地 Cookie")
            except Exception as e:
                logger.warning("Cookie 加载失败: %s", e)

        self._page = await self._context.new_page()
        logger.info("浏览器已启动")

    async def get_page(self):
        """获取当前页面 (自动启动浏览器)"""
        if not self._page:
            await self.launch()
        return self._page

    async def navigate(self, url: str, timeout: int = 30000) -> None:
        """导航到指定 URL"""
        page = await self.get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        logger.info("已导航到: %s", url)

    async def save_current_cookies(self) -> None:
        """保存当前浏览器 Cookie"""
        if self._context:
            cookies = await self._context.cookies()
            save_cookie(cookies)
            logger.info("Cookie 已保存 (%d 条)", len(cookies))

    async def screenshot(self, save_path: str) -> str:
        """页面截图"""
        page = await self.get_page()
        await page.screenshot(path=save_path, full_page=False)
        logger.info("截图已保存: %s", save_path)
        return save_path

    async def close(self) -> None:
        """关闭浏览器并保存 Cookie"""
        try:
            await self.save_current_cookies()
        except Exception:
            pass
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        self._context = None
        self._page = None
        logger.info("浏览器已关闭")

    @property
    def is_running(self) -> bool:
        return self._browser is not None


def get_browser_manager() -> BrowserManager:
    """获取浏览器管理器单例"""
    return BrowserManager()
