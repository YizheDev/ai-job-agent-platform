"""验证 mobile 抽屉模式 (P4-23) 的视觉效果."""

from __future__ import annotations

import sys
import time as _time
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


def _ensure_main(page) -> bool:
    """确保 #main-panel 已显示, 必要时登录 + 协议同意."""
    if (
        page.locator("#main-panel").count() > 0
        and page.locator("#main-panel").is_visible()
    ):
        return True
    if page.locator("#login-panel").is_visible():
        api_key = _read_env("LLM_API_KEY")
        page.locator('#login-card input[type="text"]').first.fill("zhangsan")
        page.locator('#login-card input[type="password"]').first.fill(api_key)
        page.locator("#login-btn").click()
        # 等 login-panel 隐藏 (登录成功) 最多 20s
        for _ in range(25):
            page.wait_for_timeout(800)
            if not page.locator("#login-panel").is_visible():
                break
        page.reload(wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

    deadline = _time.time() + 30
    while _time.time() < deadline:
        if (
            page.locator("#main-panel").count() > 0
            and page.locator("#main-panel").is_visible()
        ):
            return True
        if page.locator("#agreement-panel").is_visible():
            try:
                page.locator(
                    '#agreement-panel button:has-text("已阅读并同意")'
                ).first.click(timeout=3000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            continue
        page.wait_for_timeout(500)
    return False


def main() -> None:
    out_dir = PROJECT_ROOT / "test_screenshots" / "responsive"
    out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        page.goto("http://127.0.0.1:7860/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)

        if not _ensure_main(page):
            print("ERROR: 无法进入主面板")
            browser.close()
            return

        # 强制把可能残留的 hide 类移除
        page.evaluate(
            """
            () => {
                const p = document.querySelector('#main-panel');
                if (p) p.classList.remove('hide');
                document.querySelectorAll(
                  '#main-tabs, #main-tabs > .tab-wrapper, #main-tabs > .tabitem, #main-tabs .tab-container'
                ).forEach(el => el.classList.remove('hide'));
            }
            """
        )
        page.wait_for_timeout(500)

        # 尝试切到 dashboard
        try:
            page.locator('#main-tabs [role="tab"]:has-text("工作台")').first.click(
                timeout=5000
            )
        except Exception as e:
            print(f"[warn] 切换到工作台失败: {e}, 保持当前 tab")
        page.wait_for_timeout(1500)

        # 540 mobile - drawer closed
        page.set_viewport_size({"width": 540, "height": 900})
        page.wait_for_timeout(800)
        page.screenshot(
            path=str(out_dir / "drawer_540_closed.png"), full_page=False
        )
        print("drawer_540_closed.png")

        # 540 mobile - drawer opened (调用全局 navOpen, 同时挂 body+#main-tabs)
        page.evaluate("""
            () => {
                if (window.__hajuNav && window.__hajuNav.open) {
                    window.__hajuNav.open();
                } else {
                    document.body.classList.add('haju-nav-open');
                    var mt = document.getElementById('main-tabs');
                    if (mt) mt.classList.add('haju-nav-open');
                }
            }
        """)
        page.wait_for_timeout(500)
        info = page.evaluate("""
            () => {
                var sb = document.querySelector('#main-tabs > .tab-wrapper');
                if (!sb) return {sb: 'NOT FOUND'};
                var cs = window.getComputedStyle(sb);
                var bb = sb.getBoundingClientRect();
                var mt = document.getElementById('main-tabs');
                return {
                    tag: sb.tagName + '.' + sb.className,
                    position: cs.position,
                    transform: cs.transform,
                    zIndex: cs.zIndex,
                    left: cs.left, top: cs.top, width: cs.width,
                    visibility: cs.visibility, display: cs.display,
                    bbox: {x: bb.x, y: bb.y, w: bb.width, h: bb.height},
                    bodyClass: document.body.className,
                    mainTabsClass: mt ? mt.className : '(no main-tabs)',
                    hajuNavExists: typeof window.__hajuNav,
                };
            }
        """)
        print("drawer probe:")
        for k, v in info.items():
            print(f"  {k}: {v}")
        page.screenshot(
            path=str(out_dir / "drawer_540_open.png"), full_page=False
        )
        print("drawer_540_open.png")

        # 测试 click .hl 切换效果 (理论应该能 toggle 关闭)
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
        try:
            page.locator(".app-header-bar .hl").first.click(timeout=2000)
            page.wait_for_timeout(800)
            opened = page.evaluate(
                "document.body.classList.contains('haju-nav-open')"
            )
            print(f"  click .hl -> haju-nav-open={opened}")
            page.screenshot(
                path=str(out_dir / "drawer_540_clickHL.png"), full_page=False
            )
        except Exception as e:
            print(f"  click .hl FAIL: {e}")

        # 375 iPhone - drawer opened
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(600)
        page.evaluate("""
            () => {
                if (window.__hajuNav && window.__hajuNav.open) {
                    window.__hajuNav.open();
                } else {
                    document.body.classList.add('haju-nav-open');
                    var mt = document.getElementById('main-tabs');
                    if (mt) mt.classList.add('haju-nav-open');
                }
            }
        """)
        page.wait_for_timeout(500)
        page.screenshot(
            path=str(out_dir / "drawer_375_open.png"), full_page=False
        )
        print("drawer_375_open.png")

        ctx.close()
        browser.close()
    print("done.")


if __name__ == "__main__":
    main()
