"""BOSS 直聘自动化爬虫

支持 DrissionPage (主方案) + Playwright (Docker/无头备用) + 熔断恢复:
  1. DrissionPage 模式: 内置 Chromium + 用户数据目录 + Cookie, 绕过 BOSS 对 Playwright 的 about:blank 拦截
  2. Playwright 模式 (备用): 内置 Chromium + Cookie 持久化 + 反检测增强

熔断降级策略:
  - Playwright 连续搜索失败场景主要针对旧 CDP 逻辑保留; 半开恢复时改为主方案 DrissionPage 重连
  - 熔断后定时探测 → 尝试恢复 DrissionPage

注意: Gradio 6 运行在 asyncio 事件循环中, Playwright Sync API
无法直接在 asyncio 循环内调用。所有 Playwright 操作通过
ThreadPoolExecutor(max_workers=1) 派发到同一后台线程执行。
DrissionPage 可在调用线程工作; 为与现有入口一致仍通过 _run 提交。
"""

from __future__ import annotations

import os
import random
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.core.config import DATA_DIR
from app.core.logger import get_logger
from app.utils.security_util import load_cookie, save_cookie

# ---------------------------------------------------------------------------
# BOSS 直聘薪资字体解码
# ---------------------------------------------------------------------------

def _build_font_map_from_urls(mix_url: str, reg_url: str) -> dict[int, str]:
    """Download kanzhun-mix & kanzhun-Regular fonts and cross-compare glyphs
    to build PUA -> digit mapping."""
    import requests
    from io import BytesIO
    from fontTools.ttLib import TTFont

    mapping: dict[int, str] = {}
    try:
        mix_resp = requests.get(mix_url, timeout=10)
        reg_resp = requests.get(reg_url, timeout=10)
        if mix_resp.status_code != 200 or reg_resp.status_code != 200:
            return mapping

        font_mix = TTFont(BytesIO(mix_resp.content))
        font_reg = TTFont(BytesIO(reg_resp.content))

        cmap_mix = font_mix.getBestCmap()
        cmap_reg = font_reg.getBestCmap()

        glyf_mix = font_mix.get("glyf")
        glyf_reg = font_reg.get("glyf")
        if not glyf_mix or not glyf_reg:
            font_mix.close()
            font_reg.close()
            return mapping

        def _glyph_sig(glyf_table, gname):
            try:
                g = glyf_table[gname]
                if not g.numberOfContours:
                    return None
                coords = g.coordinates
                if not coords:
                    return None
                return (g.numberOfContours,
                        tuple(tuple(c) for c in coords),
                        tuple(g.flags) if g.flags else ())
            except Exception:
                return None

        reg_digit_sigs: dict[str, tuple | None] = {}
        for code, gname in cmap_reg.items():
            if 0x30 <= code <= 0x39:
                reg_digit_sigs[chr(code)] = _glyph_sig(glyf_reg, gname)

        for code, gname in cmap_mix.items():
            if not (0xE000 <= code <= 0xF8FF):
                continue
            pua_sig = _glyph_sig(glyf_mix, gname)
            if not pua_sig:
                continue
            for digit_char, digit_sig in reg_digit_sigs.items():
                if digit_sig and pua_sig == digit_sig:
                    mapping[code] = digit_char
                    break

        font_mix.close()
        font_reg.close()
    except Exception as exc:
        logger.warning("字体解析异常: %s", exc)
    return mapping

logger = get_logger(__name__)

_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

DRISSION_PROFILE_DIR = DATA_DIR / "drission_profile"

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
# Anti-detection & anti-anti-debug scripts
# ------------------------------------------------------------------

_ANTI_DETECT_JS = """
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh','en']});
(function(){
  var _origOpen=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){
    if(typeof u==='string'&&/localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0/.test(u))
      u='https://0.0.0.0:1/__blocked__';
    return _origOpen.apply(this,arguments);
  };
  var _origFetch=window.fetch;
  window.fetch=function(u,o){
    if(typeof u==='string'&&/localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0/.test(u))
      return Promise.reject(new TypeError('Network request failed'));
    return _origFetch.apply(this,arguments);
  };
})();
"""


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

    default_profile = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data",
    )
    use_default = os.path.isdir(default_profile)

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-blink-features=AutomationControlled",
        "--hide-crash-restore-bubble",
        "--disable-session-crashed-bubble",
        "--disable-infobars",
        "about:blank",
    ]
    if use_default:
        cmd.insert(2, f"--user-data-dir={default_profile}")
        logger.info("使用 Chrome 默认 profile: %s", default_profile)
    else:
        CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        cmd.insert(2, f"--user-data-dir={CHROME_PROFILE_DIR}")
        logger.info("使用隔离 profile: %s", CHROME_PROFILE_DIR)

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
    DRISSION = "drission"
    PLAYWRIGHT = "playwright"


MODE_LABELS = {
    ConnectionMode.CDP: "CDP 模式 (真实浏览器)",
    ConnectionMode.DRISSION: "DrissionPage 模式 (主浏览器)",
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
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            logger.warning(
                "熔断器恢复探测失败: 回退到熔断状态 (第 %d 次失败)",
                self.failure_count,
            )
        elif (self.failure_count >= self.failure_threshold
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
    """BOSS 直聘自动化爬虫 (DrissionPage 主方案 + Playwright 备用 + 熔断降级)"""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._dp_browser = None
        self._dp_tab = None
        self._logged_in = False
        self._applied_urls: set[str] = set()
        self._greeting: str = ""

        self._mode: str = ""
        self._is_cdp: bool = False
        self._cdp_port: int = 9222
        self._chrome_proc: Optional[subprocess.Popen] = None
        self._cdp_debug_client = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=300,
        )
        self._salary_font_map: dict[int, str] = {}
        self._salary_map_ready = False

    # ----------------------------------------------------------------
    # Properties
    # ----------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._browser is not None or self._dp_browser is not None

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
        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            for _ in range(random.randint(2, 4)):
                self._dp_tab.scroll.down(random.randint(200, 500))
                time.sleep(random.uniform(0.2, 0.6))
            return
        if self._page:
            for _ in range(random.randint(2, 4)):
                self._page.mouse.wheel(0, random.randint(200, 500))
                time.sleep(random.uniform(0.2, 0.6))

    def _dp_tab_text(self, selector: str) -> str:
        """DrissionPage: 逗号分隔多选择器依次尝试。"""
        if not self._dp_tab:
            return ""
        for part in selector.split(","):
            sel = part.strip()
            if not sel:
                continue
            try:
                el = self._dp_tab.ele(f"css:{sel}", timeout=3)
                if el:
                    t = (getattr(el, "text", None) or "").strip()
                    if t:
                        return t
            except Exception:
                continue
        return ""

    def _text(self, selector: str) -> str:
        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            return self._dp_tab_text(selector)
        try:
            el = self._page.locator(selector).first
            if el.count() > 0:
                return el.inner_text(timeout=3000).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _dp_card_text(card, css_selectors: str) -> str:
        for part in css_selectors.split(","):
            sel = part.strip()
            if not sel:
                continue
            try:
                el = card.ele(f"css:{sel}", timeout=0.5)
                if el:
                    t = (getattr(el, "text", None) or "").strip()
                    if t:
                        return t
            except Exception:
                continue
        return ""

    # ----------------------------------------------------------------
    # Salary font decode
    # ----------------------------------------------------------------

    def _ensure_salary_font_map(self) -> None:
        """Lazy-init: discover font URLs from browser and build PUA mapping."""
        if self._salary_map_ready:
            return
        self._salary_map_ready = True
        if self._mode != ConnectionMode.DRISSION or not self._dp_tab:
            return
        try:
            js_result = self._dp_tab.run_js("""
                var fonts = {};
                for (var i = 0; i < document.styleSheets.length; i++) {
                    try {
                        var rules = document.styleSheets[i].cssRules
                                 || document.styleSheets[i].rules;
                        for (var j = 0; j < rules.length; j++) {
                            if (rules[j] instanceof CSSFontFaceRule) {
                                var family = (rules[j].style.fontFamily || '').replace(/['"]/g, '').trim();
                                var src = rules[j].cssText || '';
                                if (family.indexOf('kanzhun') >= 0) {
                                    var m = src.match(/url\\(['\"]?(https?:\\/\\/[^)\"']+\\.(?:ttf|woff2?))['\"]?\\)/);
                                    if (m) fonts[family] = m[1];
                                }
                            }
                        }
                    } catch(e) {}
                }
                return JSON.stringify(fonts);
            """)
            import json as _json
            font_urls = _json.loads(js_result) if js_result else {}
            mix_url = font_urls.get("kanzhun-mix", "")
            reg_url = font_urls.get("kanzhun-Regular", "")

            if not mix_url or not reg_url:
                logger.debug("未找到 kanzhun 字体 URL, 使用备用地址")
                mix_url = mix_url or "https://img.bosszhipin.com/static/file/2023/30k9dfumyv1693967587404.ttf"
                reg_url = reg_url or "https://img.bosszhipin.com/static/file/2022/16a48d9v961651026858984.ttf"

            self._salary_font_map = _build_font_map_from_urls(mix_url, reg_url)
            if self._salary_font_map:
                logger.info(
                    "薪资字体解码成功: %d 个字符映射",
                    len(self._salary_font_map),
                )
            else:
                logger.warning("薪资字体解码失败: 映射为空")
        except Exception as e:
            logger.warning("薪资字体初始化失败: %s", e)

    def _decode_salary(self, text: str) -> str:
        """Decode PUA-encoded salary text to readable digits."""
        if not text:
            return text
        if not any(0xE000 <= ord(ch) <= 0xF8FF for ch in text):
            return text
        if not self._salary_font_map:
            self._ensure_salary_font_map()
        return "".join(
            self._salary_font_map.get(ord(ch), ch) for ch in text
        )

    def _is_logged_in_on_dp_tab(self, tab) -> bool:
        try:
            current_url = tab.url or ""
        except Exception:
            current_url = ""
        if any(kw in current_url for kw in (
            "login", "/web/user/", "passport", "captcha",
        )):
            return False
        try:
            user_el = tab.ele(
                "css:.nav-figure, .user-nav, .nav-userinfo",
                timeout=3,
            )
            if user_el:
                return True
        except Exception:
            pass
        try:
            body_html = tab.html or ""
            if "APP扫码登录" in body_html:
                return False
        except Exception:
            pass
        return False

    # ----------------------------------------------------------------
    # Anti-debug: skip all debugger pauses via CDP protocol
    # ----------------------------------------------------------------

    def _setup_cdp_anti_debug(self):
        """Apply anti-detection measures (JS-level only).

        Do NOT enable Debugger domain — activating it exposes CDP
        to BOSS's timing-based detection.  Without Debugger.enable,
        ``debugger`` statements are already no-ops when DevTools
        is closed, so nothing needs to be skipped.
        """
        if self._mode == ConnectionMode.DRISSION:
            return
        if not self._page:
            return
        try:
            if self._cdp_debug_client:
                try:
                    self._cdp_debug_client.detach()
                except Exception:
                    pass
                self._cdp_debug_client = None
            logger.info("反检测保护已就位 (JS 级别)")
        except Exception as e:
            logger.debug("反检测设置跳过: %s", e)

    # ----------------------------------------------------------------
    # Page recovery (CDP tab may be closed externally)
    # ----------------------------------------------------------------

    def _ensure_page(self):
        """Verify self._page is usable; recover if tab was closed."""
        if self._mode == ConnectionMode.DRISSION:
            return
        if self._page:
            try:
                _ = self._page.url
                return
            except Exception:
                logger.warning("当前页面已失效, 尝试恢复...")
                self._page = None

        if not self._context:
            return

        try:
            pages = self._context.pages
        except Exception:
            logger.warning("浏览器上下文已断开")
            self._page = None
            return

        for p in pages:
            try:
                page_url = p.url or ""
                if "zhipin.com" in page_url:
                    self._page = p
                    logger.info("恢复页面: 复用 zhipin.com 页面")
                    self._setup_cdp_anti_debug()
                    return
            except Exception:
                continue

        non_blank = [
            p for p in pages
            if (p.url or "") not in ("", "about:blank")
        ]
        if non_blank:
            self._page = non_blank[0]
        elif pages:
            self._page = pages[0]
        else:
            self._page = self._context.new_page()
            logger.info("恢复页面: 创建新页面")

        self._setup_cdp_anti_debug()

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
        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            dp_timeout = max(timeout // 1000, 15)
            for attempt in range(retries + 1):
                try:
                    self._dp_tab.get(url, timeout=dp_timeout)
                    self._delay(0.5, 1.5)
                    final_url = self._dp_tab.url or ""
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
                    is_retryable = (
                        "timeout" in err.lower()
                        or "about:blank" in err.lower()
                    )
                    if attempt < retries and is_retryable:
                        logger.warning(
                            "导航 %d/%d 失败: %s, 重试...",
                            attempt + 1, retries + 1, err[:120],
                        )
                        self._delay(2, 4)
                    else:
                        raise
            return self._dp_tab.url or ""

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
    # Browser lifecycle — DrissionPage (主方案, 原 CDP 入口)
    # ================================================================

    def launch_drission(self) -> str:
        """启动 DrissionPage Chromium (主方案)"""
        if self.is_running:
            return "浏览器已处于运行状态"
        return self._run(self._launch_drission_impl, timeout=60)

    def _launch_drission_impl(self) -> str:
        browser = None
        try:
            from DrissionPage import Chromium, ChromiumOptions

            co = ChromiumOptions()
            co.set_argument("--no-first-run")
            co.set_argument("--no-default-browser-check")
            co.set_argument("--disable-infobars")
            co.set_argument("--hide-crash-restore-bubble")
            co.set_argument("--disable-session-crashed-bubble")

            is_docker = os.environ.get("DOCKER_CONTAINER", "").lower() in ("1", "true")
            if is_docker:
                co.headless()
                co.set_argument("--no-sandbox")
                co.set_argument("--disable-dev-shm-usage")
                co.set_argument("--disable-gpu")

            dp_port = 9333
            co.set_local_port(dp_port)

            DRISSION_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            co.set_user_data_path(str(DRISSION_PROFILE_DIR))
            logger.info("DrissionPage: 使用专属 profile: %s", DRISSION_PROFILE_DIR)

            browser = Chromium(co)

            tab = browser.latest_tab

            tab.get("https://www.zhipin.com", timeout=20)
            self._delay(1, 2)

            cookies = load_cookie("boss_zhipin")
            if cookies:
                loaded = 0
                for c in cookies:
                    try:
                        tab.set.cookies({
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c.get("domain", ".zhipin.com"),
                            "path": c.get("path", "/"),
                        })
                        loaded += 1
                    except Exception:
                        pass
                if loaded > 0:
                    logger.info(
                        "DrissionPage: 已加载 %d/%d 条 Cookie, 刷新页面...",
                        loaded, len(cookies),
                    )
                    tab.get("https://www.zhipin.com", timeout=20)
                    self._delay(2, 3)

            self._dp_browser = browser
            self._dp_tab = tab
            self._browser = browser
            self._page = None
            self._context = None
            self._pw = None
            self._mode = ConnectionMode.DRISSION
            self._is_cdp = False
            self._circuit_breaker.reset()
            browser = None

            try:
                if self._is_logged_in_on_dp_tab(tab):
                    self._logged_in = True
                    self._persist_cookies()
                    logger.info("DrissionPage 启动成功, 用户已登录")
                    return "DrissionPage 连接成功, 已检测到 BOSS 直聘登录状态 ✓"
            except Exception as e:
                logger.warning("登录状态检查失败: %s", e)

            logger.info("DrissionPage 启动成功, 未检测到登录")
            return (
                "浏览器已启动 (DrissionPage), 请在窗口中"
                "登录 BOSS 直聘, 登录后点击「检查登录状态」"
            )
        except Exception as e:
            logger.error("DrissionPage 启动失败: %s", e)
            if browser is not None:
                try:
                    browser.quit()
                except Exception:
                    pass
            self._cleanup_refs()
            return f"DrissionPage 启动失败: {e}"

    def launch_cdp(self, port: int = 9222) -> str:
        """兼容入口: 原 CDP 连接改为 DrissionPage 主方案"""
        if self.is_running:
            return "浏览器已处于运行状态"
        self._cdp_port = port
        return self.launch_drission()

    # ================================================================
    # Browser lifecycle — Playwright (备用方案)
    # ================================================================

    def launch_playwright(self, headless: bool = True) -> str:
        """启动内置 Chromium (Playwright 模式)"""
        if self.is_running:
            return "浏览器已处于运行状态"
        return self._run(self._launch_playwright_impl, headless, timeout=30)

    def _launch_playwright_impl(self, headless: bool) -> str:
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            is_docker = os.environ.get("DOCKER_CONTAINER", "").lower() in ("1", "true")
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
            ]
            if is_docker:
                headless = True
                launch_args.append("--no-sandbox")

            self._browser = self._pw.chromium.launch(
                headless=headless,
                args=launch_args,
            )
            self._context = self._browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
            )

            try:
                from playwright_stealth import Stealth
                stealth = Stealth()
                stealth.apply_stealth_sync(self._context)
                logger.info("playwright-stealth 隐身模式已启用")
            except Exception:
                self._context.add_init_script(_ANTI_DETECT_JS)
                logger.info("stealth 不可用, 使用内置反检测 JS")

            cookies = load_cookie("boss_zhipin")
            if cookies:
                try:
                    self._context.add_cookies(cookies)
                    logger.info("已加载 Cookie (%d 条)", len(cookies))
                except Exception:
                    logger.warning("Cookie 加载失败, 需重新登录")

            self._page = self._context.new_page()
            self._dp_browser = None
            self._dp_tab = None
            self._mode = ConnectionMode.PLAYWRIGHT
            self._is_cdp = False

            self._setup_cdp_anti_debug()

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
        """优先 DrissionPage, 失败则降级 Playwright。显式 Playwright 模式跳过 Drission。"""
        if self.is_running:
            return "浏览器已处于运行状态"

        if mode == ConnectionMode.PLAYWRIGHT:
            return self.launch_playwright(headless)

        self._cdp_port = port
        result = self.launch_drission()
        if "失败" not in result:
            return result
        logger.warning("DrissionPage 不可用, 自动降级到 Playwright")
        return self.launch_playwright(headless)

    # ================================================================
    # Close — mode-aware
    # ================================================================

    def close(self) -> str:
        if not self.is_running:
            return "浏览器未运行"
        return self._run(self._close_impl, timeout=15)

    def _close_impl(self) -> str:
        try:
            if self._mode == ConnectionMode.DRISSION:
                try:
                    self._persist_cookies()
                except Exception:
                    pass
                if self._dp_browser:
                    try:
                        self._dp_browser.quit()
                    except Exception:
                        pass
                self._dp_browser = None
                self._dp_tab = None
                self._browser = None
                self._page = None
                self._context = None
                self._pw = None
                self._logged_in = False
                self._mode = ""
                self._is_cdp = False
                return "DrissionPage 浏览器已关闭"

            if self._is_cdp:
                if self._cdp_debug_client:
                    try:
                        self._cdp_debug_client.detach()
                    except Exception:
                        pass
                    self._cdp_debug_client = None
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
        if self._cdp_debug_client:
            try:
                self._cdp_debug_client.detach()
            except Exception:
                pass
            self._cdp_debug_client = None

        if self._mode == ConnectionMode.DRISSION and self._dp_browser:
            try:
                self._dp_browser.quit()
            except Exception:
                pass
            self._dp_browser = None
            self._dp_tab = None
            self._browser = None
            self._page = None
            self._context = None
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None
            self._logged_in = False
            self._mode = ""
            self._is_cdp = False
            self._kill_chrome()
            return

        for attr in ("_page", "_context", "_browser"):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._dp_browser = None
        self._dp_tab = None
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
    # Fallback activation & primary recovery
    # ================================================================

    def _activate_fallback(self) -> str:
        """熔断后切换到 Playwright (在 executor 线程调用)"""
        logger.warning("正在激活 Playwright 备用方案...")

        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            try:
                self._persist_cookies()
            except Exception:
                pass
        elif self._context:
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
        """熔断器半开时尝试恢复 DrissionPage (在 executor 线程调用)"""
        logger.info("尝试恢复 DrissionPage (原 CDP port=%d 占位)...", self._cdp_port)

        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            try:
                self._persist_cookies()
            except Exception:
                pass
        elif self._context:
            try:
                cookies = self._context.cookies()
                if cookies:
                    save_cookie(cookies, "boss_zhipin")
            except Exception:
                pass

        self._close_impl()

        result = self._launch_drission_impl()
        if "失败" not in result and self._logged_in:
            self._circuit_breaker.record_success()
            logger.info("DrissionPage 恢复成功")
            return True

        logger.info("DrissionPage 恢复失败, 继续使用 Playwright")
        self._circuit_breaker.state = CircuitBreaker.OPEN
        self._circuit_breaker.last_failure_time = time.time()
        if self._browser or self._dp_browser:
            self._close_impl()
        self._launch_playwright_impl(headless=True)
        return False

    # ================================================================
    # Login
    # ================================================================

    def open_login_page(self) -> str:
        if not self._page and not self._dp_tab:
            return "请先启动浏览器"
        return self._run(self._open_login_impl, timeout=30)

    def _open_login_impl(self) -> str:
        try:
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                try:
                    self._dp_tab.get("https://www.zhipin.com/", timeout=15)
                except Exception:
                    pass
                self._delay(1, 2)
                if self._is_logged_in_on_dp_tab(self._dp_tab):
                    self._logged_in = True
                    self._persist_cookies()
                    return "检测到已登录, Cookie 已保存"
                self._safe_goto(
                    "https://www.zhipin.com/web/user/?ka=header-login",
                    timeout=20000,
                )
                self._delay(2, 3)
                for sel in (
                    ".boss-login-qrcode", ".qr-img", "canvas",
                    ".login-scan-code", "[class*='qr']", ".sign-wrap",
                ):
                    try:
                        el = self._dp_tab.ele(f"css:{sel}", timeout=3)
                        if el:
                            break
                    except Exception:
                        continue
                if self._is_logged_in_on_dp_tab(self._dp_tab):
                    self._logged_in = True
                    self._persist_cookies()
                    return "检测到已登录, Cookie 已保存"
                return "请使用 BOSS 直聘 APP 扫描下方二维码登录"

            if self._is_cdp:
                self._ensure_page()
                try:
                    self._page.wait_for_load_state(
                        "domcontentloaded", timeout=5000,
                    )
                except Exception:
                    pass
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
        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            return self._is_logged_in_on_dp_tab(self._dp_tab)
        current_url = self._page.url or ""
        if any(kw in current_url for kw in (
            "login", "/web/user/", "passport", "captcha",
        )):
            return False
        user_el = self._page.locator(
            '.nav-figure, .user-nav, .nav-userinfo'
        )
        if user_el.count() > 0:
            return True
        try:
            body_text = self._page.inner_text("body", timeout=3000)
            if "APP扫码登录" in body_text:
                return False
        except Exception:
            pass
        return False

    def quick_check_login(self) -> bool:
        """Lightweight login check for polling — no page navigation."""
        if (not self._page and not self._dp_tab) or not self.is_running:
            return False
        try:
            return self._run(self._quick_check_impl, timeout=15)
        except Exception:
            return False

    def _quick_check_impl(self) -> bool:
        """Lightweight login probe — URL + locator + HTML text.

        DrissionPage mode checks body HTML for login prompts to avoid
        false positives from avatar placeholders on non-logged-in pages.
        """
        try:
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                return self._is_logged_in_on_dp_tab(self._dp_tab)

            self._ensure_page()
            url = self._page.url or ""
            if any(kw in url for kw in (
                "login", "/web/user/", "passport", "captcha",
            )):
                return False
            if "zhipin.com" not in url:
                return False
            user_el = self._page.locator(
                '.nav-figure, [class*="avatar"], '
                '.header-geek-info, [class*="user-name"], '
                '.user-nav, .nav-userinfo'
            )
            return user_el.count() > 0
        except Exception:
            return False

    def confirm_login_no_navigate(self) -> bool:
        """Confirm login on current page without navigation.

        Used by auto-poll to avoid _verify_login() which navigates and
        causes disruptive page refreshes in CDP mode.
        """
        if (not self._page and not self._dp_tab) or not self.is_running:
            return False
        try:
            return self._run(self._confirm_login_no_nav_impl, timeout=8)
        except Exception:
            return False

    def _confirm_login_no_nav_impl(self) -> bool:
        """Check login using locator only — no inner_text, no navigation.

        For Playwright headless auto-poll.  CDP mode never reaches here
        because the timer is disabled for CDP.
        """
        try:
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                tab = self._dp_tab
                url = tab.url or ""
                if any(kw in url for kw in (
                    "login", "/web/user/", "passport", "captcha",
                )):
                    return False
                if "zhipin.com" not in url:
                    return False
                user_el = tab.ele(
                    "css:.nav-figure, [class*='avatar'], "
                    ".header-geek-info, [class*='user-name'], "
                    ".user-nav, .nav-userinfo",
                    timeout=3,
                )
                if user_el:
                    self._logged_in = True
                    self._persist_cookies()
                    return True
                return False

            self._ensure_page()
            url = self._page.url or ""
            if any(kw in url for kw in (
                "login", "/web/user/", "passport", "captcha",
            )):
                return False
            if "zhipin.com" not in url:
                return False
            user_el = self._page.locator(
                '.nav-figure, [class*="avatar"], '
                '.header-geek-info, [class*="user-name"], '
                '.user-nav, .nav-userinfo'
            )
            if user_el.count() > 0:
                self._logged_in = True
                self._persist_cookies()
                return True
            return False
        except Exception:
            return False

    def capture_login_screenshot(self) -> Optional[bytes]:
        if not self._page and not self._dp_tab:
            return None
        return self._run(self._capture_screenshot_impl, timeout=10)

    def _capture_screenshot_impl(self) -> Optional[bytes]:
        try:
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                return self._dp_tab.get_screenshot(as_bytes="png")
            self._ensure_page()
            if not self._page:
                return None
            return self._page.screenshot(type="png")
        except Exception as e:
            logger.warning("截图失败: %s", e)
            return None

    def check_login(self) -> str:
        if not self._page and not self._dp_tab:
            return "请先启动浏览器"
        return self._run(self._check_login_impl, timeout=30)

    def _check_login_impl(self) -> str:
        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            try:
                self._dp_tab.get("https://www.zhipin.com", timeout=15)
                self._delay(2, 3)
            except Exception:
                pass
            if self._is_logged_in_on_dp_tab(self._dp_tab):
                self._logged_in = True
                self._persist_cookies()
                return "登录成功, Cookie 已保存"
            return "未检测到登录, 请在浏览器窗口中登录 BOSS 直聘"

        if self._is_cdp:
            self._ensure_page()
            if self._is_logged_in_on_page():
                self._logged_in = True
                self._persist_cookies()
                return "登录成功, Cookie 已保存"
            return "未检测到登录, 请在 Chrome 浏览器中登录 BOSS 直聘"
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
        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            try:
                cookies = self._dp_tab.cookies(all_domains=True)
                zhipin = [
                    c for c in (cookies or [])
                    if "zhipin" in (c.get("domain") or "").lower()
                ]
                if zhipin:
                    save_cookie(zhipin, "boss_zhipin")
                self._logged_in = True
                logger.info(
                    "Cookie 已持久化 (%d 条, %s)",
                    len(zhipin) if zhipin else 0, self._mode,
                )
            except Exception as e:
                self._logged_in = True
                logger.warning("Cookie 持久化失败: %s", e)
            return

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
        if (not self._page and not self._dp_tab) or not self._logged_in:
            return {}
        try:
            return self._run(self._profile_impl, timeout=15)
        except Exception as e:
            logger.warning("获取个人信息超时或异常: %s", e)
            return {}

    # JS snippet: call BOSS internal APIs via fetch and return combined JSON
    _PROFILE_API_JS = """
    async function _fetchProfile() {
        const apis = [
            {key: 'user', url: '/wapi/zpuser/wap/getUserInfo.json'},
            {key: 'base', url: '/wapi/zpgeek/resume/baseinfo/query.json'},
            {key: 'expect', url: '/wapi/zpgeek/resume/expect/query.json'},
        ];
        const result = {};
        for (const api of apis) {
            try {
                const resp = await fetch(api.url, {
                    credentials: 'include',
                    headers: {'Accept': 'application/json'}
                });
                if (resp.ok) {
                    const json = await resp.json();
                    if (json && json.code === 0 && json.zpData) {
                        result[api.key] = json.zpData;
                    }
                }
            } catch(e) {}
        }
        return JSON.stringify(result);
    }
    return _fetchProfile();
    """

    def _profile_impl(self) -> dict:
        """通过 BOSS 内部 API 获取个人信息 (无需页面导航, 速度快)"""
        import json as _json

        profile = self._profile_via_api()
        if profile:
            logger.info("获取用户信息 (API): %s", profile.get("name", "unknown"))
            return profile

        logger.info("API 方式获取失败, 尝试页面方式...")
        profile = self._profile_via_page()
        if profile:
            logger.info("获取用户信息 (页面): %s", profile.get("name", "unknown"))
        return profile

    def _profile_via_api(self) -> dict:
        """通过浏览器内 fetch 调用 BOSS API 获取个人信息"""
        import json as _json

        try:
            raw = None
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                raw = self._dp_tab.run_js(self._PROFILE_API_JS, timeout=10)
            elif self._page:
                raw = self._page.evaluate(
                    "(async () => { %s })()" % self._PROFILE_API_JS
                )

            if not raw:
                return {}

            data = _json.loads(raw) if isinstance(raw, str) else raw
            if not data:
                return {}

            profile: dict = {}

            user = data.get("user") or {}
            name = user.get("name") or user.get("nickName") or ""
            if name:
                profile["name"] = name

            base = data.get("base") or {}
            geek_info = base.get("geekInfo") or base
            if not profile.get("name"):
                profile["name"] = geek_info.get("name") or ""

            gender_map = {0: "", 1: "男", 2: "女"}
            gender = gender_map.get(geek_info.get("gender"), "")

            basics_parts = []
            for field in ("cityName", "workCity"):
                v = geek_info.get(field, "")
                if v:
                    basics_parts.append(v)
                    break
            edu = geek_info.get("degreeName") or ""
            if edu:
                basics_parts.append(edu)
            exp = geek_info.get("experienceName") or ""
            if exp:
                basics_parts.append(exp)
            if gender:
                basics_parts.append(gender)
            age = geek_info.get("age") or geek_info.get("ageDesc") or ""
            if age:
                basics_parts.append(str(age))
            if basics_parts:
                profile["basics"] = " | ".join(basics_parts)

            advantage = geek_info.get("advantage") or ""
            if advantage:
                profile["advantage"] = advantage

            status_map = {
                0: "离职-随时到岗",
                1: "在职-暂不考虑",
                2: "在职-考虑机会",
                3: "在职-月内到岗",
            }
            job_status_val = geek_info.get("jobStatus")
            if job_status_val is not None:
                profile["job_status"] = status_map.get(
                    job_status_val, f"状态{job_status_val}",
                )

            expect = data.get("expect") or {}
            expect_list = expect.get("expectList") or expect.get("list") or []
            if isinstance(expect_list, list) and expect_list:
                first = expect_list[0]
                pos = first.get("positionName") or first.get("position") or ""
                if pos:
                    profile["expect_position"] = pos

            return profile
        except Exception as e:
            logger.debug("API 方式获取个人信息失败: %s", e)
            return {}

    def _profile_via_page(self) -> dict:
        """回退方案: 导航到简历页面提取个人信息"""
        try:
            self._safe_goto(
                "https://www.zhipin.com/web/geek/resume", timeout=12000,
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

            basics = []
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                try:
                    items = self._dp_tab.eles(
                        "css:.resume-info-line li, .base-info li, "
                        "[class*='resume-info'] li",
                    )
                    for el in (items or [])[:8]:
                        try:
                            txt = (el.text or "").strip()
                            if txt:
                                basics.append(txt)
                        except Exception:
                            continue
                except Exception:
                    pass
            elif self._page:
                info_items = self._page.locator(
                    ".resume-info-line li, .base-info li, "
                    "[class*='resume-info'] li"
                )
                for i in range(min(info_items.count(), 8)):
                    txt = info_items.nth(i).inner_text(timeout=2000).strip()
                    if txt:
                        basics.append(txt)
            if basics:
                profile["basics"] = " | ".join(basics)

            return profile
        except Exception as e:
            logger.error("页面方式获取用户信息失败: %s", e)
            return {}

    # ================================================================
    # Job search — with circuit breaker failover
    # ================================================================

    def search_jobs(self, keyword: str, city: str = "全国",
                    page_num: int = 1) -> list[dict]:
        if not self._page and not self._dp_tab:
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
                logger.warning("DrissionPage 恢复尝试异常")

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
        except TimeoutError:
            logger.error("搜索超时 (%s): 60 秒内未完成, 页面可能未加载", self._mode)
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
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                self._dp_tab.get_screenshot(path=str(path))
            elif self._page:
                self._page.screenshot(path=str(path))
            logger.info("调试截图: %s", path)
        except Exception as e:
            logger.warning("截图失败: %s", e)

    def _search_impl(self, keyword: str, city: str,
                     page_num: int) -> list[dict]:
        city_code = CITY_CODES.get(city, "100010000")

        if self._mode == ConnectionMode.DRISSION and self._dp_tab:
            try:
                logger.info(
                    "搜索 (Drission): %s (城市=%s, 页=%d)",
                    keyword, city, page_num,
                )

                self._dp_tab.get(
                    "https://www.zhipin.com/web/geek/job", timeout=20,
                )
                self._delay(2, 3)

                current_url = self._dp_tab.url or ""
                logger.info("职位页 URL: %s", current_url)
                if current_url == "about:blank":
                    raise CrawlerError("职位页面被重定向到 about:blank")

                if any(kw in current_url for kw in (
                    "login", "/web/user/", "passport",
                )):
                    self._logged_in = False
                    raise CrawlerError("被重定向到登录页: " + current_url)

                search_input = self._dp_tab.ele(
                    "css:input.ipt-search, "
                    "input[name='query'], "
                    "input[ka='search_input'], "
                    ".search-input-box input, "
                    ".job-search-box input",
                    timeout=8,
                )
                if not search_input:
                    logger.warning("未找到搜索框, 尝试直接 URL...")
                    url = (
                        f"https://www.zhipin.com/web/geek/job?"
                        f"query={quote(keyword)}&city={city_code}"
                        f"&page={page_num}"
                    )
                    self._dp_tab.get(url, timeout=20)
                    time.sleep(random.uniform(3, 5))
                else:
                    search_input.click()
                    self._delay(0.3, 0.5)
                    search_input.clear()
                    self._delay(0.2, 0.4)
                    search_input.input(keyword, clear=True)
                    self._delay(0.5, 1.0)
                    logger.info("搜索框已输入: %s", keyword)

                    search_btn = self._dp_tab.ele(
                        "css:button.btn-search, "
                        "a.btn-search, "
                        "[ka='search_submit'], "
                        ".search-btn, "
                        ".job-search-box button",
                        timeout=5,
                    )
                    if search_btn:
                        search_btn.click()
                    else:
                        from DrissionPage.common import Keys
                        search_input.input(Keys.ENTER)
                    self._delay(3, 5)

                current_url = self._dp_tab.url or ""
                logger.info("搜索后 URL: %s", current_url)

                for _ in range(5):
                    current_url = self._dp_tab.url or ""
                    if "_security_check" in current_url:
                        logger.info("安全检查中: %s", current_url)
                        self._delay(2, 4)
                    else:
                        break

                logger.info("开始滚动页面并解析卡片...")
                self._scroll()
                self._delay(1, 2)

                cards = self._dp_tab.eles("css:li.job-card-box", timeout=8)
                logger.info("li.job-card-box: %d 个", len(cards) if cards else 0)
                if not cards:
                    cards = self._dp_tab.eles("css:li.job-card-wrapper", timeout=5)
                    logger.info("li.job-card-wrapper: %d 个", len(cards) if cards else 0)
                if not cards:
                    cards = self._dp_tab.eles("css:.job-card-wrap", timeout=5)
                    logger.info(".job-card-wrap: %d 个", len(cards) if cards else 0)

                if not cards:
                    logger.warning("未找到岗位卡片 (Drission), URL: %s", current_url)
                    try:
                        self._save_debug_screenshot("search_no_cards_dp")
                    except Exception:
                        pass
                    try:
                        body = (self._dp_tab.ele("css:body", timeout=3).text or "")[:500]
                        logger.info("页面文本: %s", body)
                    except Exception:
                        pass
                    return []

                logger.info("找到 %d 个岗位卡片, 开始提取...", len(cards))
                self._ensure_salary_font_map()
                jobs: list[dict] = []
                for card in cards[:15]:
                    try:
                        name = BossCrawler._dp_card_text(
                            card,
                            ".job-name, .job-title a",
                        )
                        area = BossCrawler._dp_card_text(
                            card,
                            ".company-location, .job-area, .job-area-wrapper",
                        )
                        salary = self._decode_salary(BossCrawler._dp_card_text(
                            card,
                            ".job-salary, .salary",
                        ))
                        company = BossCrawler._dp_card_text(
                            card,
                            ".boss-name, .company-name a, .company-name",
                        )
                        hr_active = BossCrawler._dp_card_text(
                            card,
                            ".boss-online-tag, .boss-online-icon, .job-status",
                        )

                        tags: list[str] = []
                        tag_els = card.eles("css:.tag-list li", timeout=1)
                        for el in tag_els[:5]:
                            try:
                                txt = (el.text or "").strip()
                                if txt:
                                    tags.append(txt)
                            except Exception:
                                continue

                        href = ""
                        link = card.ele(
                            "css:a[href*='job_detail']",
                            timeout=0.5,
                        )
                        if not link:
                            link = card.ele("css:a", timeout=0.5)
                        if link:
                            href = link.attr("href") or ""
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
                    self._save_debug_screenshot("search_empty_result_dp")
                return jobs

            except CrawlerError:
                raise
            except Exception as e:
                logger.error("搜索失败 (Drission): %s", e)
                self._save_debug_screenshot("search_exception_dp")
                raise CrawlerError(f"搜索异常: {e}") from e

        try:
            logger.info(
                "搜索: %s (城市=%s, 页=%d, 模式=%s)",
                keyword, city, page_num, self._mode,
            )

            self._safe_goto(
                "https://www.zhipin.com/web/geek/job",
                timeout=20000,
            )
            self._delay(2, 3)

            current_url = self._page.url or ""
            if current_url == "about:blank":
                raise CrawlerError("职位页面被重定向到 about:blank")

            if any(kw in current_url for kw in (
                "login", "/web/user/", "passport",
            )):
                self._logged_in = False
                raise CrawlerError("被重定向到登录页: " + current_url)

            search_input = self._page.locator(
                'input.ipt-search, '
                'input[name="query"], '
                'input[ka="search_input"], '
                '.search-input-box input, '
                '.job-search-box input'
            ).first
            search_input.wait_for(timeout=8000)
            search_input.click()
            self._delay(0.3, 0.6)
            search_input.fill("")
            self._delay(0.2, 0.4)

            for ch in keyword:
                search_input.type(ch, delay=random.randint(50, 150))
            self._delay(0.5, 1.0)

            logger.info("搜索框已输入: %s", keyword)

            search_btn = self._page.locator(
                'button.btn-search, '
                'a.btn-search, '
                '[ka="search_submit"], '
                '.search-btn, '
                '.job-search-box button'
            ).first
            search_btn.click()
            self._delay(3, 5)

            current_url = self._page.url or ""
            logger.info("搜索后 URL: %s", current_url)

            for _ in range(5):
                current_url = self._page.url or ""
                if "_security_check" in current_url:
                    logger.info("安全检查中: %s", current_url)
                    self._delay(2, 4)
                else:
                    break

            if current_url == "about:blank":
                self._save_debug_screenshot("search_blank")
                raise CrawlerError("搜索后页面被重定向到 about:blank")

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
                "li.job-card-box",
                "li.job-card-wrapper",
                ".job-card-wrapper",
                ".job-card-wrap",
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
                    salary = self._decode_salary(self._card_text(
                        card,
                        ".salary, [class*='salary'], .job-salary",
                    ))
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
        if (not self._page and not self._dp_tab) or not job_url:
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
                "salary": self._decode_salary(self._text(
                    ".salary, .info-primary .salary, .job-salary",
                )),
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
        if not self._page and not self._dp_tab:
            return "请先启动浏览器"
        if not self._logged_in:
            return "请先登录 BOSS 直聘"
        if greeting:
            self._greeting = greeting
        return self._run(self._chat_impl, job_url, timeout=35)

    def _chat_impl(self, job_url: str) -> str:
        try:
            if self._mode == ConnectionMode.DRISSION and self._dp_tab:
                self._safe_goto(job_url, timeout=20000)
                self._delay(2, 4)

                current_url = self._dp_tab.url or ""
                if current_url == "about:blank":
                    logger.warning("导航到岗位页后仍为 about:blank")
                    return "页面加载异常 (about:blank), 请检查网络或重新连接"

                btn = None
                for sel in (
                    "a.btn-startchat",
                    ".btn-container .btn",
                    "[class*='btn-startchat']",
                    "[class*='start-chat']",
                ):
                    try:
                        btn = self._dp_tab.ele(f"css:{sel}", timeout=3)
                        if btn:
                            break
                    except Exception:
                        continue
                if not btn:
                    return "未找到沟通按钮, 岗位可能已关闭或需要登录"

                try:
                    btn.click()
                except Exception:
                    return "点击沟通按钮失败"

                self._delay(2, 3)
                latest = self._dp_browser.latest_tab if self._dp_browser else None
                if latest is not None:
                    self._dp_tab = latest
                    self._browser = self._dp_browser

                if self._greeting and "chat" in (self._dp_tab.url or ""):
                    try:
                        input_box = self._dp_tab.ele(
                            "css:.chat-input textarea, "
                            "[class*='chat-input'] textarea, "
                            ".input-area textarea, #chat-input",
                            timeout=5,
                        )
                        if input_box:
                            input_box.input(self._greeting)
                            self._delay(0.5, 1)
                            send_btn = self._dp_tab.ele(
                                "css:.btn-send, [class*='btn-send'], "
                                "button[type='submit'], .send-message-btn",
                                timeout=3,
                            )
                            if send_btn:
                                send_btn.click()
                                self._delay(0.5, 1)
                    except Exception as e:
                        logger.warning("发送招呼失败: %s", e)

                success = False
                if "chat" in (self._dp_tab.url or ""):
                    success = True
                else:
                    dialog = self._dp_tab.ele(
                        "css:.dialog-container, .greet-boss, [class*='dialog']",
                        timeout=2,
                    )
                    if dialog:
                        success = True

                if success:
                    self.mark_applied(job_url)
                    return "沟通已发起"

                return "已点击沟通按钮, 但未确认沟通是否成功"

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
            try:
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
            finally:
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

            success = False
            if "chat" in (self._page.url or ""):
                success = True
            else:
                dialog = self._page.locator(
                    ".dialog-container, .greet-boss, [class*='dialog']",
                )
                if dialog.count() > 0:
                    success = True

            if success:
                self.mark_applied(job_url)
                return "沟通已发起"

            return "已点击沟通按钮, 但未确认沟通是否成功"
        except Exception as e:
            logger.error("发起沟通失败: %s", e)
            return f"发起沟通失败: {e}"


# --------------- Global singleton ---------------

_crawler: Optional[BossCrawler] = None
_crawler_lock = threading.Lock()


def get_crawler() -> BossCrawler:
    global _crawler
    if _crawler is None:
        with _crawler_lock:
            if _crawler is None:
                _crawler = BossCrawler()
    return _crawler
