"""Header zoom screenshot — 仅验证顶部通栏的新元素 (bell + user dropdown)."""

from __future__ import annotations

import sys
import time
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
    out_dir = PROJECT_ROOT / "test_screenshots"
    out_dir.mkdir(exist_ok=True)
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

        # Try to detect if we're on login screen
        if page.locator("#login-panel").is_visible():
            print("Login required, filling form...")
            api_key = _read_env("LLM_API_KEY")
            page.locator('#login-card input[type="text"]').first.fill("zhangsan")
            page.locator('#login-card input[type="password"]').first.fill(api_key)
            page.locator("#login-btn").click()
            deadline = time.time() + 60
            while time.time() < deadline:
                page.wait_for_timeout(800)
                if not page.locator("#login-panel").is_visible():
                    break
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            for _ in range(45):
                if page.locator("#main-panel").count() > 0 and page.locator("#main-panel").is_visible():
                    break
                if page.locator("#agreement-panel").is_visible():
                    btn = page.locator('#agreement-panel button').first
                    try:
                        btn.click(timeout=3000)
                    except Exception:
                        pass
                    page.wait_for_timeout(2000)
                    continue
                page.wait_for_timeout(800)
            page.evaluate(
                "() => { const p=document.querySelector('#main-panel'); if(p) p.classList.remove('hide'); }"
            )
            page.wait_for_timeout(1500)

        # Crop header area
        bar = page.locator(".app-header-bar").first
        if bar.count() == 0:
            print("header bar not found after login")
            page.screenshot(path=str(out_dir / "header_full.png"))
            return
        bar.screenshot(path=str(out_dir / "header_normal.png"))
        print("[1] header_normal.png saved")

        # Hover over bell — pop the panel
        bell = page.locator(".header-bell-trigger").first
        if bell.count() > 0:
            bell.hover()
            page.wait_for_timeout(700)
            page.screenshot(
                path=str(out_dir / "header_bell_hover.png"),
                clip={"x": 800, "y": 0, "width": 640, "height": 360},
            )
            print("[2] header_bell_hover.png saved")

        # Hover over user dropdown — use bigger clip to capture full menu
        user = page.locator(".header-user-trigger").first
        if user.count() > 0:
            user.hover()
            page.wait_for_timeout(700)
            page.screenshot(
                path=str(out_dir / "header_user_hover.png"),
                clip={"x": 800, "y": 0, "width": 640, "height": 520},
            )
            print("[3] header_user_hover.png saved")

        # Move mouse out of header first to clear popovers
        page.mouse.move(50, 50)
        page.wait_for_timeout(400)

        # Hover sidebar item — must skip visually-hidden tab container
        try:
            sidebar_item = page.locator(
                "#main-tabs .tab-container:not(.visually-hidden) > button"
            ).nth(2)
            sidebar_item.hover()
            page.wait_for_timeout(500)
            page.screenshot(
                path=str(out_dir / "sidebar_hover.png"),
                clip={"x": 100, "y": 280, "width": 240, "height": 400},
            )
            print("[4] sidebar_hover.png saved")
        except Exception as e:
            print(f"sidebar hover failed: {e}")

        browser.close()
    print("done")


if __name__ == "__main__":
    main()
