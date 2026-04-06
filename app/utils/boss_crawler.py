"""BOSS 直聘自动化爬虫

支持两种连接模式 + 自动熔断降级:
  1. CDP 模式 (主方案): 连接用户本地 Chrome, 复用真实登录态, 绕过反爬
  2. Playwright 模式 (备用方案): 内置 Chromium + Cookie 持久化 + 反检测增强

熔断降级策略:
  - CDP 连续 N 次搜索失败 → 自动切换 Playwright 备用方案
  - 熔断后定时探测 CDP 可用性 → 恢复后自动切回

注意: Gradio 6 运行在 asyncio 事件循环中, Playwright Sync API
无法直接在 asyncio 循环内调用。所有 Playwright 操作通过
ThreadPoolExecutor(max_workers=1) 派发到同一后台线程执行。
"""

from __future__ import annotations

import os
import random
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.core.config import DATA_DIR, get_settings
from app.core.logger import get_logger
from app.utils.security_util import load_cookie, save_cookie

logger = get_logger(__name__)

_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

CITY_CODES = {
    "全国": "100010000",
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "南京": "101190100",
    "武汉": "101200100",
    "西安": "101110100",
    "苏州": "101190400",
    "天津": "101030100",
    "重庆": "101040100",
    "长沙": "101250100",
    "郑州": "101180100",
    "东莞": "101281600",
    "合肥": "101220100",
    "青岛": "101120200",
    "厦门": "101230200",
    "大连": "101070200",
    "济南": "101120100",
    "宁波": "101210400",
    "无锡": "101190200",
    "珠海": "101280700",
}

CITY_LIST = list(CITY_CODES.keys())

HR_ACTIVITY_OPTIONS = ["不限", "在线", "今日活跃", "3日内活跃", "本周活跃"]


# ------------------------------------------------------------------
# Chrome auto-discovery & auto-launch
# ------------------------------------------------------------------

CHROME_PROFILE_DIR = DATA_DIR / "chrome_cdp_profile"

def _find_chrome() -> Optional[str]:
    """自动查找系统中的 Chrome 可执行文件"""
    candidates = []

    for env_var in ("%ProgramFiles%", "%ProgramFiles(x86)%", "%LocalAppData%"):
        expanded = os.path.expandvars(env_var)
        if expanded != env_var:
            candidates.append(
                os.path.join(expanded, "Google", "Chrome", "Application", "chrome.exe")
            )

    candidates.append(
        os.path.join(
            os.environ.get("USERPROFILE", ""),
            "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe",
        )
    )

    for path in candidates:
        if os.path.isfile(path):
            return path

    which = shutil.which("chrome") or shutil.which("google-chrome")
    if which:
        return which

    try:
        import winreg
        for key_path in (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.isfile(val):
                        return val
            except OSError:
                continue
    except ImportError:
        pass

    return None


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """检测本地端口是否可连接"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def _launch_chrome_debug(port: int = 9222) -> Optional[subprocess.Popen]:
    """自动启动 Chrome 并开启调试端口, 返回进程对象"""
    chrome_path = _find_chrome()
    if not chrome_path:
        logger.warning("未在系统中找到 Chrome 浏览器")
        return None

    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-blink-features=AutomationControlled",
        "https://www.zhipin.com",
    ]

    logger.info("自动启动 Chrome: %s (port=%d)", chrome_path, port)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return proc
    except Exception as e:
        logger.error("Chrome 启动失败: %s", e)
        return None


# ------------------------------------------------------------------
# Connection mode & circuit breaker
# ------------------------------------------------------------------

class ConnectionMode:
    CDP = "cdp"
    PLAYWRIGHT = "playwright"


MODE_LABELS = {
    ConnectionMode.CDP: "CDP 模式 (真实浏览器)",
    ConnectionMode.PLAYWRIGHT: "Playwright 模式 (内置浏览器)",
}


class CrawlerError(Exception):
    """搜索/导航级别错误, 触发熔断器计数"""


class CircuitBreaker:
    """搜索熔断器 — 主方案连续失败后自动降级到备用方案

    CLOSED    → 正常工作, 使用主方案
    OPEN      → 主方案失效, 已降级到备用方案
    HALF_OPEN → 探测中, 尝试恢复主方案
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = self.CLOSED
        self.last_failure_time: float = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if (self.failure_count >= self.failure_threshold
                and self.state == self.CLOSED):
            self.state = self.OPEN
            logger.warning(
                "熔断器开启: 连续 %d 次失败, 触发降级", self.failure_count,
            )

    def record_success(self):
        if self.state == self.HALF_OPEN:
            logger.info("熔断器恢复: 主方案已恢复正常")
        self.failure_count = 0
        self.state = self.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == self.OPEN

    def should_try_recovery(self) -> bool:
        if self.state != self.OPEN:
            return False
        if time.time() - self.last_failure_time >= self.recovery_timeout:
            self.state = self.HALF_OPEN
            logger.info("熔断器半开: 尝试恢复主方案")
            return True
        return False

    def reset(self):
        self.failure_count = 0
        self.state = self.CLOSED
        self.last_failure_time = 0

    @property
    def status_text(self) -> str:
        if self.state == self.CLOSED:
            return "正常"
        if self.state == self.OPEN:
            remaining = self.recovery_timeout - (
                time.time() - self.last_failure_time
            )
            if remaining > 0:
                return f"已熔断 ({int(remaining)}s 后尝试恢复)"
            return "已熔断 (即将尝试恢复)"
        return "恢复探测中"


# ------------------------------------------------------------------
# BossCrawler
# ------------------------------------------------------------------

class BossCrawler:
    """BOSS 直聘自动化爬虫 (CDP 主方案 + Playwright 备用 + 熔断降级)"""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._logged_in = False
        self._applied_urls: set[str] = set()
        self._greeting: str = ""

        self._mode: str = ""
        self._is_cdp: bool = False
        self._cdp_port: int = 9222
        self._chrome_proc: Optional[subprocess.Popen] = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=300,
        )

    # ----------------------------------------------------------------
    # Properties
    # ----------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._browser is not None

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def mode_display(self) -> str:
        return MODE_LABELS.get(self._mode, "未连接")

    @property
    def circuit_state(self) -> str:
        return self._circuit_breaker.status_text

    @property
    def greeting(self) -> str:
        return self._greeting

    @greeting.setter
    def greeting(self, value: str):
        self._greeting = value or ""

    def is_applied(self, url: str) -> bool:
        return url in self._applied_urls

    def mark_applied(self, url: str):
        self._applied_urls.add(url)

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _delay(self, lo: float = 1.0, hi: float = 3.0):
        time.sleep(random.uniform(lo, hi))

    def _scroll(self):
        if self._page:
            for _ in range(random.randint(2, 4)):
                self._page.mouse.wheel(0, random.randint(200, 500))
                time.sleep(random.uniform(0.2, 0.6))

    def _text(self, selector: str) -> str:
        try:
            el = self._page.locator(selector).first
            if el.count() > 0:
                return el.inner_text(timeout=3000).strip()
        except Exception:
            pass
        return ""

    # ----------------------------------------------------------------
    # Page recovery (CDP tab may be closed externally)
    # ----------------------------------------------------------------

    def _ensure_page(self):
        """Verify self._page is usable; recover if tab was closed."""
        if self._page:
            try:
                _ = self._page.url
                return
            except Exception:
                logger.warning("当前页面已失效, 尝试恢复...")
                self._page = None

        if not self._context:
            return

        pages = self._context.pages
        for p in pages:
            try:
                page_url = p.url or ""
                if "zhipin.com" in page_url:
                    self._page = p
                    logger.info("恢复页面: 复用 zhipin.com 页面")
                    return
            except Exception:
                continue

        non_blank = [
            p for p in pages
            if (p.url or "") not in ("", "about:blank")
        ]
        if non_blank:
            self._page = non_blank[0]
            return

        if pages:
            self._page = pages[0]
        else:
            self._page = self._context.new_page()
            logger.info("恢复页面: 创建新页面")

    # ----------------------------------------------------------------
    # Thread dispatch
    # ----------------------------------------------------------------

    def _run(self, fn, *args, timeout: float = 30, **kwargs):
        future = _pw_executor.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout)

    # ----------------------------------------------------------------
    # Safe navigation — handles BOSS redirect interruptions & retries
    # ----------------------------------------------------------------

    def _safe_goto(self, url: str, wait_until: str = "domcontentloaded",
                   timeout: int = 20000, retries: int = 2) -> str:
        for attempt in range(retries + 1):
            try:
                self._ensure_page()
                self._page.goto(url, wait_until=wait_until, timeout=timeout)
                final_url = self._page.url or ""
                if final_url == "about:blank" and attempt < retries:
                    logger.warning(
                        "页面被重定向到 about:blank, 重试 (%d/%d)",
                        attempt + 1, retries + 1,
                    )
                    self._delay(2, 4)
                    continue
                return final_url
            except Exception as e:
                err = str(e)
                is_redirect = (
                    "interrupted" in err
                    or "ERR_ABORTED" in err
                    or "Navigation failed because page was closed" in err
                )
                if is_redirect:
                    logger.info("导航被重定向中断, 等待最终页面: %s", url)
                    try:
                        self._ensure_page()
                        self._page.wait_for_load_state(
                            "domcontentloaded", timeout=10000,
                        )
                    except Exception:
                        pass
                    self._delay(1, 2)
                    final_url = self._page.url or ""
                    if final_url == "about:blank" and attempt < retries:
                        logger.warning(
                            "重定向后页面为 about:blank, 重试 (%d/%d)",
                            attempt + 1, retries + 1,
                        )
                        self._delay(2, 4)
                        continue
                    return final_url
                is_retryable = (
                    "timeout" in err.lower()
                    or "net::" in err.lower()
                    or "about:blank" in err.lower()
                    or "page was closed" in err.lower()
                )
                if attempt < retries and is_retryable:
                    logger.warning(
                        "导航 %d/%d 失败: %s, 重试...",
                        attempt + 1, retries + 1, err[:120],
                    )
                    self._ensure_page()
                    self._delay(2, 4)
                else:
                    raise
        return self._page.url or ""

    # ================================================================
    # Browser lifecycle — CDP (主方案)
    # ================================================================

    def launch_cdp(self, port: int = 9222) -> str:
        """连接用户本地 Chrome (CDP 模式)"""
        if self._browser:
            return "浏览器已处于运行状态"
        self._cdp_port = port
        return self._run(self._launch_cdp_impl, port, timeout=20)

    def _launch_cdp_impl(self, port: int) -> str:
        try:
            from playwright.sync_api import sync_playwright

            if not _is_port_open(port):
                logger.info("调试端口 %d 未开放, 尝试自动启动 Chrome...", port)
                proc = _launch_chrome_debug(port)
                if proc is None:
                    self._cleanup_refs()
                    return (
                        "CDP 连接失败: 未找到 Chrome 浏览器。"
                        "请安装 Google Chrome 后重试, "
                        "或切换到 Playwright 模式。"
                    )
                self._chrome_proc = proc

                for i in range(15):
                    time.sleep(1)
                    if _is_port_open(port):
                        logger.info("Chrome 调试端口 %d 已就绪 (等待 %ds)", port, i + 1)
                        break
                else:
                    logger.error("等待 Chrome 调试端口超时")
                    self._kill_chrome()
                    self._cleanup_refs()
                    return "Chrome 启动超时, 请稍后重试或切换到 Playwright 模式"

            self._pw = sync_playwright().start()
            endpoint = f"http://127.0.0.1:{port}"

            try:
                self._browser = self._pw.chromium.connect_over_cdp(endpoint)
            except Exception as e:
                logger.error("CDP 连接失败 (port=%d): %s", port, e)
                self._kill_chrome()
                self._cleanup_refs()
                return "CDP 连接失败, 请稍后重试或切换到 Playwright 模式"

            contexts = self._browser.contexts
            self._context = contexts[0] if contexts else self._browser.new_context()

            self._context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "Object.defineProperty(navigator,'languages',"
                "{get:()=>['zh-CN','zh','en']});"
            )

            pages = self._context.pages
            self._page = None
            for p in pages:
                try:
                    if "zhipin.com" in (p.url or ""):
                        self._page = p
                        logger.info("CDP: 复用已有 zhipin.com 页面")
                        break
                except Exception:
                    continue
            if not self._page:
                non_blank = [
                    p for p in pages
                    if (p.url or "") not in ("", "about:blank")
                ]
                if non_blank:
                    self._page = non_blank[0]
                    logger.info("CDP: 使用已有页面 (%s)", self._page.url)
                elif pages:
                    self._page = pages[0]
                    logger.info("CDP: 使用默认页面")
                else:
                    self._page = self._context.new_page()
                    logger.info("CDP: 创建新页面")

            self._mode = ConnectionMode.CDP
            self._is_cdp = True
            self._circuit_breaker.reset()

            if self._verify_login():
                logger.info("CDP 连接成功, 用户已登录")
                return "CDP 连接成功, 已检测到 BOSS 直聘登录状态 ✓"

            logger.info("CDP 连接成功, 未检测到登录")
            return (
                "Chrome 已自动启动, 请在弹出的 Chrome 窗口中登录 "
                "BOSS 直聘, 登录完成后点击「检查登录状态」"
            )
        except Exception as e:
            logger.error("CDP 启动失败: %s", e)
            self._kill_chrome()
            self._cleanup_refs()
            return f"CDP 启动失败: {e}"

    # ================================================================
    # Browser lifecycle — Playwright (备用方案)
    # ================================================================

    def launch_playwright(self, headless: bool = True) -> str:
        """启动内置 Chromium (Playwright 模式)"""
        if self._browser:
            return "浏览器已处于运行状态"
        return self._run(self._launch_playwright_impl, headless, timeout=30)

    def _launch_playwright_impl(self, headless: bool) -> str:
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                ],
            )
            self._context = self._browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
            )

            self._context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "Object.defineProperty(navigator,'languages',"
                "{get:()=>['zh-CN','zh','en']});"
            )

            cookies = load_cookie("boss_zhipin")
            if cookies:
                try:
                    self._context.add_cookies(cookies)
                    logger.info("已加载 Cookie (%d 条)", len(cookies))
                except Exception:
                    logger.warning("Cookie 加载失败, 需重新登录")

            self._page = self._context.new_page()
            self._mode = ConnectionMode.PLAYWRIGHT
            self._is_cdp = False

            if cookies and self._verify_login():
                self._persist_cookies()
                logger.info("Playwright: Cookie 验证通过")
            else:
                logger.info("Playwright: 需扫码登录")

            return "浏览器启动成功 (Playwright 模式)"
        except Exception as e:
            logger.error("Playwright 启动失败: %s", e)
            self._cleanup_refs()
            return f"Playwright 启动失败: {e}"

    # ================================================================
    # Unified launch
    # ================================================================

    def launch(self, headless: bool = True,
               mode: str = ConnectionMode.CDP,
               port: int = 9222) -> str:
        """启动浏览器。CDP 失败时自动降级到 Playwright。"""
        if self._browser:
            return "浏览器已处于运行状态"

        if mode == ConnectionMode.CDP:
            result = self.launch_cdp(port)
            if "失败" not in result:
                return result
            logger.warning("CDP 失败, 自动降级到 Playwright")
            return self.launch_playwright(headless)

        return self.launch_playwright(headless)

    # ================================================================
    # Close — CDP-aware
    # ================================================================

    def close(self) -> str:
        if not self._browser:
            return "浏览器未运行"
        return self._run(self._close_impl, timeout=15)

    def _close_impl(self) -> str:
        try:
            if self._is_cdp:
                if self._page:
                    try:
                        self._page.close()
                    except Exception:
                        pass
                if self._browser:
                    try:
                        self._browser.close()
                    except Exception:
                        pass
                self._page = None
                self._context = None
                self._browser = None
                if self._pw:
                    try:
                        self._pw.stop()
                    except Exception:
                        pass
                    self._pw = None
                self._kill_chrome()
                self._logged_in = False
                self._mode = ""
                self._is_cdp = False
                return "CDP 连接已断开, Chrome 已关闭"

            if self._context:
                try:
                    cookies = self._context.cookies()
                    if cookies:
                        save_cookie(cookies, "boss_zhipin")
                except Exception:
                    pass
            self._cleanup_refs()
            return "浏览器已关闭"
        except Exception as e:
            self._cleanup_refs()
            return f"关闭异常: {e}"

    def _kill_chrome(self):
        """终止由本程序启动的 Chrome 进程"""
        if self._chrome_proc:
            try:
                self._chrome_proc.terminate()
                self._chrome_proc.wait(timeout=5)
                logger.info("已关闭 Chrome 进程")
            except Exception:
                try:
                    self._chrome_proc.kill()
                except Exception:
                    pass
            self._chrome_proc = None

    def _cleanup_refs(self):
        for attr in ("_page", "_context", "_browser"):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None
        self._kill_chrome()
        self._logged_in = False
        self._mode = ""
        self._is_cdp = False

    # ================================================================
    # Fallback activation & CDP recovery
    # ================================================================

    def _activate_fallback(self) -> str:
        """CDP 熔断后切换到 Playwright (在 executor 线程调用)"""
        logger.warning("正在激活 Playwright 备用方案...")

        if self._context:
            try:
                cookies = self._context.cookies()
                if cookies:
                    save_cookie(cookies, "boss_zhipin")
                    logger.info("已保存 %d 条 Cookie 用于备用方案", len(cookies))
            except Exception:
                pass

        self._close_impl()
        return self._launch_playwright_impl(headless=True)

    def _try_cdp_recovery(self) -> bool:
        """熔断器半开时尝试恢复 CDP (在 executor 线程调用)"""
        logger.info("尝试恢复 CDP (port=%d)...", self._cdp_port)

        if self._context:
            try:
                cookies = self._context.cookies()
                if cookies:
                    save_cookie(cookies, "boss_zhipin")
            except Exception:
                pass

        self._close_impl()

        result = self._launch_cdp_impl(self._cdp_port)
        if "失败" not in result and self._logged_in:
            self._circuit_breaker.record_success()
            logger.info("CDP 恢复成功")
            return True

        logger.info("CDP 恢复失败, 继续使用 Playwright")
        self._circuit_breaker.state = CircuitBreaker.OPEN
        self._circuit_breaker.last_failure_time = time.time()
        if self._browser:
            self._close_impl()
        self._launch_playwright_impl(headless=True)
        return False

    # ================================================================
    # Login
    # ================================================================

    def open_login_page(self) -> str:
        if not self._page:
            return "请先启动浏览器"
        return self._run(self._open_login_impl, timeout=30)

    def _open_login_impl(self) -> str:
        try:
            if self._is_cdp:
                self._safe_goto("https://www.zhipin.com/", timeout=15000)
                self._delay(1, 2)
                if self._is_logged_in_on_page():
                    self._logged_in = True
                    return "检测到已登录 BOSS 直聘"
                return (
                    "请在 Chrome 浏览器中登录 BOSS 直聘, "
                    "然后点击「检查登录状态」"
                )

            self._safe_goto("https://www.zhipin.com/", timeout=15000)
            self._delay(1, 2)

            if self._is_logged_in_on_page():
                self._persist_cookies()
                return "检测到已登录, Cookie 已保存"

            self._safe_goto(
                "https://www.zhipin.com/web/user/?ka=header-login",
                timeout=20000,
            )
            self._delay(2, 3)

            for sel in [
                ".boss-login-qrcode", ".qr-img", "canvas",
                ".login-scan-code", "[class*='qr']", ".sign-wrap",
            ]:
                try:
                    self._page.wait_for_selector(sel, timeout=3000)
                    break
                except Exception:
                    continue

            if self._is_logged_in_on_page():
                self._persist_cookies()
                return "检测到已登录, Cookie 已保存"

            return "请使用 BOSS 直聘 APP 扫描下方二维码登录"
        except Exception as e:
            return f"打开登录页失败: {e}"

    def _is_logged_in_on_page(self) -> bool:
        current_url = self._page.url or ""
        if any(kw in current_url for kw in (
            "login", "/web/user/", "passport", "captcha",
        )):
            return False
        user_el = self._page.locator(
            '.nav-figure, [class*="avatar"], '
            '.header-geek-info, [class*="user-name"], '
            '.user-nav, .nav-userinfo'
        )
        return user_el.count() > 0

    def capture_login_screenshot(self) -> Optional[bytes]:
        if not self._page:
            return None
        return self._run(self._capture_screenshot_impl, timeout=10)

    def _capture_screenshot_impl(self) -> Optional[bytes]:
        try:
            return self._page.screenshot(type="png")
        except Exception as e:
            logger.warning("截图失败: %s", e)
            return None

    def check_login(self) -> str:
        if not self._page:
            return "请先启动浏览器"
        return self._run(self._check_login_impl, timeout=20)

    def _check_login_impl(self) -> str:
        if self._verify_login():
            self._persist_cookies()
            return "登录成功, Cookie 已保存"
        return "未检测到登录, 请用 BOSS 直聘 APP 扫码"

    def _verify_login(self) -> bool:
        try:
            self._safe_goto(
                "https://www.zhipin.com/web/geek/job", timeout=15000,
            )
            self._delay(3, 5)

            current_url = self._page.url or ""
            if any(kw in current_url for kw in (
                "login", "/web/user/", "passport", "captcha",
            )):
                logger.info("登录检测: 重定向到 %s", current_url)
                return False

            try:
                body_text = self._page.inner_text("body", timeout=5000)
                if "登录/注册" in body_text or "APP扫码登录" in body_text:
                    logger.info("登录检测: 页面含登录文本")
                    return False
            except Exception:
                pass

            user_el = self._page.locator(
                '.nav-figure, [class*="avatar"], '
                '.header-geek-info, [class*="user-name"], '
                '.user-nav, .nav-userinfo'
            )
            if user_el.count() > 0:
                logger.info("登录检测: 发现用户信息元素")
                return True

            logger.info("登录检测: 未能确认登录状态")
            return False
        except Exception as e:
            logger.warning("登录检测异常: %s", e)
            return False

    def _persist_cookies(self):
        if self._context:
            try:
                cookies = self._context.cookies()
                save_cookie(cookies, "boss_zhipin")
                self._logged_in = True
                logger.info(
                    "Cookie 已持久化 (%d 条, %s)", len(cookies), self._mode,
                )
            except Exception as e:
                self._logged_in = True
                logger.warning("Cookie 持久化失败: %s", e)

    # ================================================================
    # User profile
    # ================================================================

    def get_user_profile(self) -> dict:
        if not self._page or not self._logged_in:
            return {}
        return self._run(self._profile_impl, timeout=25)

    def _profile_impl(self) -> dict:
        try:
            self._safe_goto(
                "https://www.zhipin.com/web/geek/resume", timeout=15000,
            )
            self._delay(1, 2)

            profile: dict = {}
            name = self._text(
                ".geek-name, .resume-name, [class*='geek-name']",
            )
            if name:
                profile["name"] = name

            for sel, key in [
                (
                    ".expect-position, .expect-job, "
                    "[class*='expect-position']",
                    "expect_position",
                ),
                (
                    ".geek-geek-status, [class*='geek-status']",
                    "job_status",
                ),
                (".geek-advantage, [class*='advantage']", "advantage"),
            ]:
                val = self._text(sel)
                if val:
                    profile[key] = val

            info_items = self._page.locator(
                ".resume-info-line li, .base-info li, "
                "[class*='resume-info'] li"
            )
            basics = []
            for i in range(min(info_items.count(), 8)):
                txt = info_items.nth(i).inner_text(timeout=2000).strip()
                if txt:
                    basics.append(txt)
            if basics:
                profile["basics"] = " | ".join(basics)

            logger.info("获取用户信息: %s", profile.get("name", "unknown"))
            return profile
        except Exception as e:
            logger.error("获取用户信息失败: %s", e)
            return {}

    # ================================================================
    # Job search — with circuit breaker failover
    # ================================================================

    def search_jobs(self, keyword: str, city: str = "全国",
                    page_num: int = 1) -> list[dict]:
        if not self._page:
            return []
        if not self._logged_in:
            logger.warning("搜索失败: 未登录")
            return []

        if (self._mode == ConnectionMode.PLAYWRIGHT
                and self._cdp_port
                and self._circuit_breaker.should_try_recovery()):
            try:
                self._run(self._try_cdp_recovery, timeout=30)
            except Exception:
                logger.warning("CDP 恢复尝试异常")

        try:
            jobs = self._run(
                self._search_impl, keyword, city, page_num, timeout=60,
            )
            if jobs and self._is_cdp:
                self._circuit_breaker.record_success()
            return jobs
        except CrawlerError as e:
            logger.error("搜索错误 (%s): %s", self._mode, e)
            if self._is_cdp:
                self._circuit_breaker.record_failure()
                if self._circuit_breaker.is_open:
                    logger.warning("CDP 熔断, 切换 Playwright 备用方案")
                    try:
                        self._run(self._activate_fallback, timeout=30)
                    except Exception:
                        logger.error("备用方案激活失败")
                        return []
                    if self._page and self._logged_in:
                        try:
                            return self._run(
                                self._search_impl, keyword, city,
                                page_num, timeout=60,
                            )
                        except Exception:
                            pass
            return []
        except Exception as e:
            logger.error("搜索异常 (%s): %s", self._mode, e)
            return []

    def _save_debug_screenshot(self, name: str):
        try:
            from app.core.config import DATA_DIR
            debug_dir = DATA_DIR / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            path = debug_dir / f"{name}.png"
            self._page.screenshot(path=str(path))
            logger.info("调试截图: %s", path)
        except Exception as e:
            logger.warning("截图失败: %s", e)

    def _search_impl(self, keyword: str, city: str,
                     page_num: int) -> list[dict]:
        city_code = CITY_CODES.get(city, "100010000")
        encoded_kw = quote(keyword)
        url = (
            f"https://www.zhipin.com/web/geek/job"
            f"?query={encoded_kw}&city={city_code}&page={page_num}"
        )
        try:
            logger.info(
                "搜索: %s (城市=%s, 页=%d, 模式=%s)",
                keyword, city, page_num, self._mode,
            )
            self._safe_goto(url, timeout=20000)
            self._delay(3, 5)

            for _ in range(5):
                current_url = self._page.url or ""
                if "_security_check" in current_url:
                    logger.info("安全检查中: %s", current_url)
                    self._delay(2, 4)
                else:
                    break

            current_url = self._page.url or ""
            logger.info("搜索页 URL: %s", current_url)

            if any(kw in current_url for kw in (
                "login", "/web/user/", "passport",
            )):
                self._logged_in = False
                self._save_debug_screenshot("search_redirect")
                raise CrawlerError("搜索被重定向到登录页: " + current_url)

            if "_security_check" in current_url:
                self._save_debug_screenshot("search_security_stuck")
                raise CrawlerError("安全检查未通过: " + current_url)

            self._scroll()
            self._delay(1, 2)

            selectors = [
                ".search-job-result",
                ".job-list-box",
                "li.job-card-wrapper",
                "[class*='job-card']",
                ".search-job-result .job-list",
            ]
            found = False
            for sel in selectors:
                try:
                    self._page.wait_for_selector(sel, timeout=5000)
                    found = True
                    break
                except Exception:
                    continue

            if not found:
                logger.warning("未找到结果容器, URL: %s", self._page.url)
                self._save_debug_screenshot("search_no_container")
                try:
                    page_text = self._page.inner_text("body")[:800]
                    logger.info("页面文本: %s", page_text)
                except Exception:
                    pass
                raise CrawlerError("未找到搜索结果容器")

            card_selectors = [
                "li.job-card-wrapper",
                ".job-card-wrapper",
                "[class*='job-card-wrapper']",
                ".search-job-result li",
                ".job-list-box li",
            ]
            cards = None
            for sel in card_selectors:
                c = self._page.locator(sel)
                if c.count() > 0:
                    cards = c
                    break

            if cards is None or cards.count() == 0:
                logger.warning("未找到岗位卡片")
                self._save_debug_screenshot("search_no_cards")
                return []

            jobs: list[dict] = []
            for i in range(min(cards.count(), 30)):
                try:
                    card = cards.nth(i)
                    name = self._card_text(
                        card,
                        ".job-name, [class*='job-name'], .job-title",
                    )
                    area = self._card_text(
                        card,
                        ".job-area, [class*='job-area'], "
                        ".job-area-wrapper",
                    )
                    salary = self._card_text(
                        card,
                        ".salary, [class*='salary'], .job-salary",
                    )
                    company = self._card_text(
                        card,
                        ".company-name a, [class*='company-name'] a, "
                        "[class*='company-name'], .company-text",
                    )
                    hr_active = self._card_text(
                        card,
                        ".boss-online-tag, [class*='boss-online'], "
                        "[class*='online-tag'], .job-status",
                    )

                    tags: list[str] = []
                    tag_els = card.locator(
                        ".tag-list li, [class*='tag'] li, .job-tags span",
                    )
                    for t in range(min(tag_els.count(), 5)):
                        try:
                            txt = (
                                tag_els.nth(t)
                                .inner_text(timeout=1000)
                                .strip()
                            )
                            if txt:
                                tags.append(txt)
                        except Exception:
                            continue

                    href = ""
                    link = card.locator("a").first
                    if link.count() > 0:
                        href = (
                            link.get_attribute("href", timeout=2000) or ""
                        )
                    if href and not href.startswith("http"):
                        href = f"https://www.zhipin.com{href}"

                    if name:
                        jobs.append({
                            "title": name,
                            "company": company,
                            "salary": salary,
                            "area": area,
                            "hr_active": hr_active,
                            "tags": " | ".join(tags) if tags else "",
                            "url": href,
                            "applied": href in self._applied_urls,
                        })
                except Exception:
                    continue

            logger.info("搜索到 %d 个岗位 (关键词: %s)", len(jobs), keyword)
            if not jobs:
                self._save_debug_screenshot("search_empty_result")
            return jobs

        except CrawlerError:
            raise
        except Exception as e:
            logger.error("搜索失败: %s", e)
            self._save_debug_screenshot("search_exception")
            raise CrawlerError(f"搜索异常: {e}") from e

    @staticmethod
    def _card_text(card, selector: str) -> str:
        try:
            el = card.locator(selector).first
            if el.count() > 0:
                return el.inner_text(timeout=2000).strip()
        except Exception:
            pass
        return ""

    # ================================================================
    # Job detail
    # ================================================================

    def get_job_detail(self, job_url: str) -> dict:
        if not self._page or not job_url:
            return {}
        return self._run(self._detail_impl, job_url, timeout=30)

    def _detail_impl(self, job_url: str) -> dict:
        try:
            self._safe_goto(job_url, timeout=20000)
            self._delay(1, 3)
            return {
                "title": self._text(
                    ".name h1, .info-primary .name .title, .job-title",
                ),
                "salary": self._text(
                    ".salary, .info-primary .salary, .job-salary",
                ),
                "company": self._text(
                    ".company-info .name, .sider-company .name, "
                    ".company-name",
                ),
                "description": self._text(
                    ".job-detail-section .job-sec-text, "
                    ".job-detail .text, .job-sec-text, "
                    "[class*='job-detail'] [class*='text']"
                ),
                "url": job_url,
            }
        except Exception as e:
            logger.error("获取详情失败: %s", e)
            return {}

    # ================================================================
    # Start chat — with greeting template & dedup
    # ================================================================

    def start_chat(self, job_url: str, greeting: str = "") -> str:
        if not self._page:
            return "请先启动浏览器"
        if not self._logged_in:
            return "请先登录 BOSS 直聘"
        if greeting:
            self._greeting = greeting
        return self._run(self._chat_impl, job_url, timeout=35)

    def _chat_impl(self, job_url: str) -> str:
        try:
            self._safe_goto(job_url, timeout=20000)
            self._delay(2, 4)

            current_url = self._page.url or ""
            if current_url == "about:blank":
                logger.warning("导航到岗位页后仍为 about:blank")
                return "页面加载异常 (about:blank), 请检查网络或重新连接"

            btn = self._page.locator(
                "a.btn-startchat, .btn-container .btn, "
                "[class*='btn-startchat'], [class*='start-chat']"
            )
            if btn.count() == 0:
                return "未找到沟通按钮, 岗位可能已关闭或需要登录"

            new_pages: list = []

            def _on_page(page):
                new_pages.append(page)

            self._context.on("page", _on_page)
            btn.first.click()
            self._delay(2, 3)

            if new_pages:
                new_page = new_pages[-1]
                try:
                    new_page.wait_for_load_state(
                        "domcontentloaded", timeout=10000,
                    )
                except Exception:
                    pass
                new_url = new_page.url or ""
                if new_url != "about:blank":
                    self._page = new_page
                    logger.info("沟通按钮打开了新页面: %s", new_url)

            try:
                self._context.remove_listener("page", _on_page)
            except Exception:
                pass

            if self._greeting and "chat" in (self._page.url or ""):
                try:
                    input_box = self._page.locator(
                        ".chat-input textarea, "
                        "[class*='chat-input'] textarea, "
                        ".input-area textarea, #chat-input"
                    )
                    if input_box.count() > 0:
                        input_box.first.fill(self._greeting)
                        self._delay(0.5, 1)
                        send_btn = self._page.locator(
                            ".btn-send, [class*='btn-send'], "
                            "button[type='submit'], .send-message-btn"
                        )
                        if send_btn.count() > 0:
                            send_btn.first.click()
                            self._delay(0.5, 1)
                except Exception as e:
                    logger.warning("发送招呼失败: %s", e)

            self.mark_applied(job_url)

            if "chat" in (self._page.url or ""):
                return "沟通已发起"
            dialog = self._page.locator(
                ".dialog-container, .greet-boss, [class*='dialog']",
            )
            if dialog.count() > 0:
                return "沟通已发起"
            return "已点击沟通按钮"
        except Exception as e:
            logger.error("发起沟通失败: %s", e)
            return f"发起沟通失败: {e}"


# --------------- Global singleton ---------------

_crawler: Optional[BossCrawler] = None


def get_crawler() -> BossCrawler:
    global _crawler
    if _crawler is None:
        _crawler = BossCrawler()
    return _crawler
