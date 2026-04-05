"""BOSS 直聘自动化爬虫

Playwright 同步 API + 专用后台线程。
扫码登录 / Cookie 持久化 / 岗位搜索 / 一键沟通。
内置防风控: 随机延时、模拟滚动、Cookie 复用、导航重试。

借鉴 Jobs_helper (HR活跃过滤/去重/话术) 和 browser-use (稳定导航) 最佳实践。

注意: Gradio 6 运行在 asyncio 事件循环中, Playwright Sync API
无法直接在 asyncio 循环内调用。所有 Playwright 操作通过
ThreadPoolExecutor(max_workers=1) 派发到同一后台线程执行。
"""

from __future__ import annotations

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.core.config import get_settings
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


class BossCrawler:
    """BOSS 直聘同步爬虫（集成 HR 过滤 / 去重 / 话术 / 稳定导航）"""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._logged_in = False
        self._applied_urls: set[str] = set()
        self._greeting: str = ""

    # --- Properties ---

    @property
    def is_running(self) -> bool:
        return self._browser is not None

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

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

    # --- Internal helpers ---

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

    # ------------------------------------------------------------------
    # Thread dispatch
    # ------------------------------------------------------------------

    def _run(self, fn, *args, timeout: float = 30, **kwargs):
        future = _pw_executor.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout)

    # ------------------------------------------------------------------
    # Safe navigation — handles BOSS redirect interruptions & retries
    # ------------------------------------------------------------------

    def _safe_goto(self, url: str, wait_until: str = "domcontentloaded",
                   timeout: int = 20000, retries: int = 2) -> str:
        """Navigate handling BOSS zhipin JS redirect interruptions.

        BOSS frequently redirects login/search URLs mid-navigation, causing
        Playwright's goto to throw "interrupted by another navigation" or
        "ERR_ABORTED". This wrapper catches those and waits for the redirect
        target page to load instead of crashing.
        """
        for attempt in range(retries + 1):
            try:
                self._page.goto(url, wait_until=wait_until, timeout=timeout)
                return self._page.url or ""
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
                        self._page.wait_for_load_state(
                            "domcontentloaded", timeout=10000,
                        )
                    except Exception:
                        pass
                    self._delay(1, 2)
                    final_url = self._page.url or ""
                    logger.info("重定向后最终 URL: %s", final_url)
                    return final_url
                is_retryable = (
                    "timeout" in err.lower()
                    or "net::" in err.lower()
                )
                if attempt < retries and is_retryable:
                    logger.warning(
                        "导航尝试 %d/%d 失败: %s, 重试中...",
                        attempt + 1, retries + 1, err[:120],
                    )
                    self._delay(2, 4)
                else:
                    raise
        return self._page.url or ""

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def launch(self, headless: bool = False) -> str:
        if self._browser:
            return "浏览器已处于运行状态"
        return self._run(self._launch_impl, headless, timeout=30)

    def _launch_impl(self, headless: bool) -> str:
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._context = self._browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )

            cookies = load_cookie("boss_zhipin")
            if cookies:
                try:
                    self._context.add_cookies(cookies)
                    logger.info("已加载 BOSS 直聘 Cookie (%d 条)", len(cookies))
                except Exception:
                    logger.warning("Cookie 加载失败, 需重新登录")

            self._page = self._context.new_page()

            if cookies:
                if self._verify_login():
                    self._persist_cookies()
                    logger.info("Cookie 验证通过, 已登录")
                else:
                    logger.info("Cookie 已过期, 需重新扫码登录")

            logger.info("浏览器已启动 (headless=%s)", headless)
            return "浏览器启动成功"
        except Exception as e:
            logger.error("浏览器启动失败: %s", e)
            self._cleanup_refs()
            return f"启动失败: {e}"

    def close(self) -> str:
        return self._run(self._close_impl, timeout=15)

    def _close_impl(self) -> str:
        try:
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
            return f"关闭异常: {e}"

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
        self._logged_in = False

    # ------------------------------------------------------------------
    # Login — stable navigation with redirect handling
    # ------------------------------------------------------------------

    def open_login_page(self) -> str:
        if not self._page:
            return "请先启动浏览器"
        return self._run(self._open_login_impl, timeout=30)

    def _open_login_impl(self) -> str:
        try:
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
        """Check login from current page DOM without navigating away."""
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
        if user_el.count() > 0:
            return True
        return False

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
        """Navigate to a protected page to confirm login status."""
        try:
            self._safe_goto(
                "https://www.zhipin.com/web/geek/job",
                timeout=15000,
            )
            self._delay(3, 5)

            current_url = self._page.url or ""
            if any(kw in current_url for kw in (
                "login", "/web/user/", "passport", "captcha",
            )):
                logger.info("登录检测: 被重定向到登录页 %s", current_url)
                return False

            try:
                body_text = self._page.inner_text("body", timeout=5000)
                if "登录/注册" in body_text or "APP扫码登录" in body_text:
                    logger.info("登录检测: 页面含登录文本, 判定未登录")
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

            logger.info("登录检测: 未能确认登录状态, 默认未登录")
            return False
        except Exception as e:
            logger.warning("登录检测异常: %s", e)
            return False

    def _persist_cookies(self):
        if self._context:
            cookies = self._context.cookies()
            save_cookie(cookies, "boss_zhipin")
            self._logged_in = True
            logger.info("BOSS 直聘 Cookie 已持久化 (%d 条)", len(cookies))

    # ------------------------------------------------------------------
    # User profile
    # ------------------------------------------------------------------

    def get_user_profile(self) -> dict:
        if not self._page or not self._logged_in:
            return {}
        return self._run(self._profile_impl, timeout=25)

    def _profile_impl(self) -> dict:
        try:
            self._safe_goto(
                "https://www.zhipin.com/web/geek/resume",
                timeout=15000,
            )
            self._delay(1, 2)

            profile: dict = {}

            name = self._text(".geek-name, .resume-name, [class*='geek-name']")
            if name:
                profile["name"] = name

            for sel, key in [
                (".expect-position, .expect-job, [class*='expect-position']", "expect_position"),
                (".geek-geek-status, [class*='geek-status']", "job_status"),
                (".geek-advantage, [class*='advantage']", "advantage"),
            ]:
                val = self._text(sel)
                if val:
                    profile[key] = val

            info_items = self._page.locator(
                ".resume-info-line li, .base-info li, [class*='resume-info'] li"
            )
            basics = []
            for i in range(min(info_items.count(), 8)):
                txt = info_items.nth(i).inner_text(timeout=2000).strip()
                if txt:
                    basics.append(txt)
            if basics:
                profile["basics"] = " | ".join(basics)

            logger.info("获取 BOSS 用户信息: %s", profile.get("name", "unknown"))
            return profile
        except Exception as e:
            logger.error("获取用户信息失败: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Job search — with HR activity extraction
    # ------------------------------------------------------------------

    def search_jobs(self, keyword: str, city: str = "全国",
                    page_num: int = 1) -> list[dict]:
        if not self._page:
            return []
        if not self._logged_in:
            logger.warning("搜索岗位失败: 未登录 BOSS 直聘")
            return []
        return self._run(self._search_impl, keyword, city, page_num, timeout=60)

    def _save_debug_screenshot(self, name: str):
        try:
            from app.core.config import DATA_DIR
            debug_dir = DATA_DIR / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            path = debug_dir / f"{name}.png"
            self._page.screenshot(path=str(path))
            logger.info("调试截图已保存: %s", path)
        except Exception as e:
            logger.warning("保存调试截图失败: %s", e)

    def _search_impl(self, keyword: str, city: str, page_num: int) -> list[dict]:
        city_code = CITY_CODES.get(city, "100010000")
        encoded_kw = quote(keyword)
        url = (
            f"https://www.zhipin.com/web/geek/job"
            f"?query={encoded_kw}&city={city_code}&page={page_num}"
        )
        try:
            logger.info("搜索岗位: %s (城市=%s, 页码=%d)", keyword, city, page_num)
            self._safe_goto(url, timeout=20000)
            self._delay(3, 5)

            for _ in range(5):
                current_url = self._page.url or ""
                if "_security_check" in current_url:
                    logger.info("安全检查中, 等待跳转... URL: %s", current_url)
                    self._delay(2, 4)
                else:
                    break

            current_url = self._page.url or ""
            logger.info("搜索页面 URL: %s", current_url)

            if any(kw in current_url for kw in ("login", "/web/user/", "passport")):
                logger.warning("搜索被重定向到登录页: %s", current_url)
                self._save_debug_screenshot("search_redirect")
                self._logged_in = False
                return []

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
                logger.warning("未找到搜索结果容器, 当前URL: %s", self._page.url)
                self._save_debug_screenshot("search_no_container")
                try:
                    page_text = self._page.inner_text("body")[:800]
                    logger.info("页面文本: %s", page_text)
                except Exception:
                    pass
                return []

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
                cnt = c.count()
                if cnt > 0:
                    cards = c
                    break

            if cards is None or cards.count() == 0:
                logger.warning("未找到岗位卡片元素")
                self._save_debug_screenshot("search_no_cards")
                return []

            jobs: list[dict] = []
            for i in range(min(cards.count(), 30)):
                try:
                    c = cards.nth(i)
                    name = self._card_text(
                        c, ".job-name, [class*='job-name'], .job-title",
                    )
                    area = self._card_text(
                        c, ".job-area, [class*='job-area'], .job-area-wrapper",
                    )
                    salary = self._card_text(
                        c, ".salary, [class*='salary'], .job-salary",
                    )
                    company = self._card_text(
                        c,
                        ".company-name a, [class*='company-name'] a, "
                        "[class*='company-name'], .company-text",
                    )

                    hr_active = self._card_text(
                        c,
                        ".boss-online-tag, [class*='boss-online'], "
                        "[class*='online-tag'], .job-status",
                    )

                    tags: list[str] = []
                    tag_els = c.locator(
                        ".tag-list li, [class*='tag'] li, .job-tags span",
                    )
                    for t in range(min(tag_els.count(), 5)):
                        try:
                            txt = tag_els.nth(t).inner_text(timeout=1000).strip()
                            if txt:
                                tags.append(txt)
                        except Exception:
                            continue

                    href = ""
                    link = c.locator("a").first
                    if link.count() > 0:
                        href = link.get_attribute("href", timeout=2000) or ""
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

            logger.info(
                "搜索到 %d 个岗位 (关键词: %s, 城市: %s)",
                len(jobs), keyword, city,
            )
            if not jobs:
                self._save_debug_screenshot("search_empty_result")
            return jobs
        except Exception as e:
            logger.error("搜索岗位失败: %s", e)
            self._save_debug_screenshot("search_exception")
            return []

    @staticmethod
    def _card_text(card, selector: str) -> str:
        try:
            el = card.locator(selector).first
            if el.count() > 0:
                return el.inner_text(timeout=2000).strip()
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Job detail
    # ------------------------------------------------------------------

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
                    ".company-info .name, .sider-company .name, .company-name",
                ),
                "description": self._text(
                    ".job-detail-section .job-sec-text, .job-detail .text, "
                    ".job-sec-text, [class*='job-detail'] [class*='text']"
                ),
                "url": job_url,
            }
        except Exception as e:
            logger.error("获取岗位详情失败: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Start chat — with greeting template & dedup
    # ------------------------------------------------------------------

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

            btn = self._page.locator(
                "a.btn-startchat, .btn-container .btn, "
                "[class*='btn-startchat'], [class*='start-chat']"
            )
            if btn.count() == 0:
                return "未找到沟通按钮, 岗位可能已关闭或需要登录"

            btn.first.click()
            self._delay(2, 3)

            if self._greeting and "chat" in (self._page.url or ""):
                try:
                    input_box = self._page.locator(
                        ".chat-input textarea, [class*='chat-input'] textarea, "
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
                    logger.warning("发送打招呼消息失败: %s", e)

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
