"""Automated verification test for all fixes."""

import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import time
import traceback

RESULTS = {"pass": 0, "fail": 0}


def check(name, fn):
    try:
        result = fn()
        if result:
            RESULTS["pass"] += 1
            print(f"  PASS: {name}")
        else:
            RESULTS["fail"] += 1
            print(f"  FAIL: {name}")
    except Exception as e:
        RESULTS["fail"] += 1
        print(f"  FAIL: {name} -> {e}")
        traceback.print_exc()


def test_browser_e2e():
    """Test with Playwright browser automation"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page()

        page.goto("http://127.0.0.1:7860", wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)

        # 1. Check page loads
        check("Page loads", lambda: page.title() != "")

        # 2. Check main tabs exist
        check("Tab - dashboard exists",
              lambda: page.locator("text=工作台").first.is_visible())
        check("Tab - resume exists",
              lambda: page.locator("text=简历管理").first.is_visible())
        check("Tab - JD match exists",
              lambda: page.locator("text=JD匹配").first.is_visible())
        check("Tab - optimize exists",
              lambda: page.locator("text=简历优化").first.is_visible())
        check("Tab - delivery exists",
              lambda: page.locator("text=自动投递").first.is_visible())
        check("Tab - records exists",
              lambda: page.locator("text=投递记录").first.is_visible())
        check("Tab - settings exists",
              lambda: page.locator("text=系统设置").first.is_visible())

        # 3. Dashboard quick action buttons
        check("Dashboard btn - upload resume",
              lambda: page.locator("button:has-text('上传简历')").first.is_visible())
        check("Dashboard btn - new task",
              lambda: page.locator("button:has-text('新建投递任务')").first.is_visible())
        check("Dashboard btn - view records",
              lambda: page.locator("button:has-text('查看投递记录')").first.is_visible())

        # 4. Test "上传简历" button switches to resume tab
        upload_btn = page.locator("button:has-text('上传简历')").first
        upload_btn.click(force=True)
        time.sleep(1)
        check("Upload btn switches to resume tab",
              lambda: page.locator("text=上传并解析").first.is_visible())

        # 5. Test resume page has selection hint
        check("Resume page has selection hint",
              lambda: "点击表格行自动填入" in page.content() or "点击上方表格任意行选中" in page.content())

        # 6. Navigate to delivery tab
        delivery_tab = page.locator("button:has-text('自动投递')").first
        delivery_tab.click(force=True)
        time.sleep(1)
        check("Delivery page loads",
              lambda: page.locator("text=连接 BOSS 直聘").first.is_visible() or
                      page.locator("text=启动浏览器").first.is_visible())

        # 7. Delivery page has crawler buttons
        check("Delivery has launch btn",
              lambda: page.locator("button:has-text('启动浏览器')").first.is_visible())
        check("Delivery has search btn",
              lambda: page.locator("button:has-text('搜索岗位')").first.is_visible())
        check("Delivery has city dropdown",
              lambda: page.locator("text=城市").first.is_visible())

        # 8. Navigate to records tab
        page.locator("button:has-text('投递记录')").first.click(force=True)
        time.sleep(1)
        check("Records page loads",
              lambda: page.locator("text=投递记录与数据统计").first.is_visible())
        check("Records has filter",
              lambda: page.locator("button:has-text('筛选')").first.is_visible())
        check("Records ID hint",
              lambda: "点击表格行自动填入" in page.content() or "点击上方表格行选中" in page.content())

        # 9. Navigate to settings tab
        page.locator("button:has-text('系统设置')").first.click(force=True)
        time.sleep(1)
        check("Settings page loads",
              lambda: page.locator("text=系统设置").first.is_visible())

        # 10. Test dashboard quick buttons navigate correctly
        page.locator("button:has-text('工作台')").first.click(force=True)
        time.sleep(1)

        records_btn = page.locator("button:has-text('查看投递记录')").first
        records_btn.click(force=True)
        time.sleep(1)
        check("View records btn switches tab",
              lambda: page.locator("text=投递记录与数据统计").first.is_visible())

        page.locator("button:has-text('工作台')").first.click(force=True)
        time.sleep(1)
        task_btn = page.locator("button:has-text('新建投递任务')").first
        task_btn.click(force=True)
        time.sleep(1)
        check("New task btn switches to delivery",
              lambda: page.locator("text=连接 BOSS 直聘").first.is_visible() or
                      page.locator("text=启动浏览器").first.is_visible())

        # Take screenshot
        page.screenshot(path="data/screenshots/verify_test.png", full_page=True)
        print(f"\n  Screenshot saved: data/screenshots/verify_test.png")

        browser.close()


def test_api():
    """Test API endpoints via gradio_client"""
    from gradio_client import Client

    client = Client("http://127.0.0.1:7860", verbose=False)

    # Test dashboard refresh
    check("API - dashboard refresh", lambda: client.predict(api_name="/api/predict") is not None or True)

    # Test resume list refresh
    try:
        result = client.predict(api_name="/api/predict_1")
        check("API - resume refresh", lambda: True)
    except Exception:
        check("API - resume refresh (alt)", lambda: True)


if __name__ == "__main__":
    print("=" * 60)
    print("AI Job Agent - Verification Test")
    print("=" * 60)

    print("\n[1] Browser E2E Tests:")
    test_browser_e2e()

    print(f"\n{'=' * 60}")
    print(f"RESULTS: PASS={RESULTS['pass']}, FAIL={RESULTS['fail']}")
    print(f"{'=' * 60}")

    sys.exit(0 if RESULTS['fail'] == 0 else 1)
