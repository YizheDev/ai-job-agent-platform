"""窄屏响应式截图: 验证 P1-6 (1024px 顶栏) / P4-23 (汉堡菜单) / P4-24 (768px 顶栏).

使用单一 context 切换 viewport, 保留登录态.
"""

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


VIEWPORTS: list[tuple[int, int, str]] = [
    (1280, 900, "1280-tablet-wide"),
    (1024, 800, "1024-tablet"),
    (900, 800, "0900-mid"),
    (768, 1024, "0768-tablet-narrow"),
    (540, 900, "0540-mobile"),
    (375, 812, "0375-iphone"),
]


def _read_env(key: str, default: str = "") -> str:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def main() -> None:
    out_dir = PROJECT_ROOT / "test_screenshots" / "responsive"
    out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    url = "http://127.0.0.1:7860/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        # 1) 进入主面板 (优先恢复 session)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)

        # 没登录则登录
        if not page.locator("#main-tabs").is_visible():
            print("登录中...")
            api_key = _read_env("LLM_API_KEY")
            page.locator('#login-card input[type="text"]').first.fill("zhangsan")
            page.locator('#login-card input[type="password"]').first.fill(api_key)
            page.locator("#login-btn").click()
            for _ in range(25):
                page.wait_for_timeout(800)
                if not page.locator("#login-panel").is_visible():
                    break
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            if page.locator("#agreement-panel").is_visible():
                btn = page.locator(
                    '#agreement-panel button:has-text("已阅读并同意")'
                ).first
                if btn.count():
                    btn.click()
                    page.wait_for_timeout(2000)
            print("登录完成")

        # 2) 在每个 viewport 截 dashboard 默认 + 抽屉打开 + settings
        for w, h, slug in VIEWPORTS:
            print(f"\n=== {slug} ({w}x{h}) ===")
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(800)
            # 切到 工作台 (确保统一基准)
            try:
                btn = page.locator(
                    '#main-tabs [role="tab"]:has-text("工作台")'
                ).first
                if btn.count():
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1200)
            except Exception:
                pass
            shot = out_dir / f"dash_{slug}.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"  dashboard -> {shot.name}")

            # 抽屉模式 (≤720px)
            if w <= 720:
                try:
                    hl = page.locator(".app-header-bar .hl").first
                    if hl.count():
                        hl.click(timeout=3000)
                        page.wait_for_timeout(700)
                        shot2 = out_dir / f"nav_{slug}.png"
                        page.screenshot(path=str(shot2), full_page=True)
                        print(f"  nav drawer  -> {shot2.name}")
                        # 关闭抽屉 (统一调 navClose, 同时清 body + #main-tabs)
                        page.evaluate("""
                            () => {
                                if (window.__hajuNav && window.__hajuNav.close) {
                                    window.__hajuNav.close();
                                } else {
                                    document.body.classList.remove('haju-nav-open');
                                    var mt = document.getElementById('main-tabs');
                                    if (mt) mt.classList.remove('haju-nav-open');
                                }
                            }
                        """)
                        page.wait_for_timeout(300)
                except Exception as e:
                    print(f"  nav drawer FAIL: {e}")

            # 设置页 dropdown 验证
            try:
                btn = page.locator(
                    '#main-tabs [role="tab"]:has-text("系统设置")'
                ).first
                if btn.count():
                    btn.scroll_into_view_if_needed(timeout=3000)
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1200)
                    # 切到 大模型 API tab (那里有更多 dropdown)
                    sub = page.locator(
                        '.st-scope [role="tab"]:has-text("大模型 API")'
                    ).first
                    if sub.count():
                        sub.click(timeout=3000)
                        page.wait_for_timeout(800)
                    shot3 = out_dir / f"settings_{slug}.png"
                    page.screenshot(path=str(shot3), full_page=True)
                    print(f"  settings    -> {shot3.name}")
            except Exception as e:
                print(f"  settings FAIL: {e}")

        ctx.close()
        browser.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
