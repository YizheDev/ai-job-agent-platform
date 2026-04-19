"""调试 haju-nav 抽屉脚本是否注入成功."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _read_env(key: str, default: str = "") -> str:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def main() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 540, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        page.on(
            "console",
            lambda msg: print(f"  [console {msg.type}] {msg.text}"[:300]),
        )
        page.on(
            "pageerror",
            lambda err: print(f"  [pageerror] {err}"[:300]),
        )
        page.goto("http://127.0.0.1:7860/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        if not page.locator("#main-tabs").is_visible():
            api_key = _read_env("LLM_API_KEY")
            page.locator('#login-card input[type="text"]').first.fill("zhangsan")
            page.locator('#login-card input[type="password"]').first.fill(api_key)
            page.locator("#login-btn").click()
            page.wait_for_timeout(5000)
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            if page.locator("#agreement-panel").is_visible():
                page.locator(
                    '#agreement-panel button:has-text("已阅读并同意")'
                ).first.click()
                page.wait_for_timeout(2000)

        # 检查脚本是否注入并暴露 __hajuNav
        info = page.evaluate("""
            () => {
                // 检查所有注入的 script slot 是否存在 + 是否含 <script>
                const slots = ['bg-fx-slot','font-loader','a11y-svg-tagger','haju-low-fx','haju-nav-drawer'];
                const slotInfo = {};
                slots.forEach(id => {
                    const el = document.getElementById(id);
                    slotInfo[id] = {
                        exists: !!el,
                        hasScript: el ? el.querySelectorAll('script').length : 0,
                        hasLink: el ? el.querySelectorAll('link').length : 0,
                    };
                });
                // 检查 a11y 脚本是否执行了 (会给 svg 加 data-a11y)
                const a11ySvgTagged = document.querySelectorAll('svg[data-a11y]').length;
                return {
                    hasNav: typeof window.__hajuNav,
                    hasFn: window.__hajuNav ? Object.keys(window.__hajuNav) : null,
                    isMobile: window.__hajuNav ? window.__hajuNav.isMobile() : null,
                    bodyW: window.innerWidth,
                    bodyH: window.innerHeight,
                    matchMQ: window.matchMedia('(max-width: 720px)').matches,
                    hlExists: !!document.querySelector('.app-header-bar .hl'),
                    hlText: (document.querySelector('.app-header-bar .hl') || {}).innerText,
                    bgFx: !!document.querySelector('.bg-fx'),
                    fontLoader: !!document.querySelector('#font-loader'),
                    a11ySvgTagged: a11ySvgTagged,
                    hajuLowFxOnBody: document.body.classList.contains('haju-low-fx'),
                    slotInfo: slotInfo,
                };
            }
        """)
        print("DOM probe:")
        for k, v in info.items():
            print(f"  {k}: {v}")

        # 触发 .hl 点击, 检查 toggle
        if info.get("hasNav") == "object":
            page.evaluate("window.__hajuNav.open()")
            page.wait_for_timeout(500)
            opened = page.evaluate("document.body.classList.contains('haju-nav-open')")
            print(f"manual __hajuNav.open() -> opened={opened}")
            page.screenshot(path="test_screenshots/responsive/dbg_drawer_manual_open.png")
            page.evaluate("window.__hajuNav.close()")
            page.wait_for_timeout(300)

        # 模拟用户点击 .hl
        try:
            page.locator(".app-header-bar .hl").first.click(timeout=3000)
            page.wait_for_timeout(800)
            opened2 = page.evaluate("document.body.classList.contains('haju-nav-open')")
            print(f"user click .hl -> opened={opened2}")
        except Exception as e:
            print(f"click .hl FAIL: {e}")

        # 走精确坐标 (绕 hover-handler)
        try:
            box = page.locator(".app-header-bar .hl").first.bounding_box()
            print(f".hl bbox: {box}")
            if box:
                page.mouse.click(box["x"] + 12, box["y"] + box["height"] / 2)
                page.wait_for_timeout(800)
                opened3 = page.evaluate("document.body.classList.contains('haju-nav-open')")
                print(f"mouse click on logo -> opened={opened3}")
        except Exception as e:
            print(f"mouse click FAIL: {e}")

        ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
