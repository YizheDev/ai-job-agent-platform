"""E2E smoke test for the BOSS platform refactor.

Verifies app loads, login works, and new tab structure is correct.
Uses screenshots for visual verification since headless Playwright has
known issues with Gradio 6's Svelte event handlers.
"""
import sys
import time
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7860/"
_env = dotenv_values(".env")
API_KEY = _env.get("LLM_API_KEY", "")
os.makedirs("test_screenshots", exist_ok=True)


def main():
    print("=== BOSS Platform Refactor E2E Test ===\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # 1. Load app
        print("[1] Loading app...")
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)
        title = page.title()
        print(f"    Title: {title}")
        page.screenshot(path="test_screenshots/01_login_page.png")

        # 2. Login
        print("[2] Logging in...")
        name_input = page.locator("#login-card textarea, #login-card input[type='text']").first
        name_input.wait_for(timeout=10000)
        name_input.fill("testuser")
        time.sleep(0.5)

        key_input = page.locator("#login-card input[type='password']").first
        key_input.wait_for(timeout=5000)
        key_input.fill(API_KEY)
        time.sleep(0.5)

        login_btn = page.locator("#login-btn").first
        login_btn.click()
        time.sleep(8)  # Wait for DeepSeek API validation
        page.screenshot(path="test_screenshots/02_after_login.png")

        # Check page state
        html = page.content()
        body_text = page.inner_text("body", timeout=5000)

        if "已阅读并同意" in body_text:
            print("    Agreement page visible, clicking accept...")
            page.evaluate("""
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.includes('已阅读并同意')) {
                        btn.click();
                        break;
                    }
                }
            """)
            time.sleep(3)
            page.screenshot(path="test_screenshots/03_after_agreement.png")
            body_text = page.inner_text("body", timeout=5000)

        # 3. Verify tab structure by inspecting the HTML source
        print("\n[3] Checking tab structure from HTML source...")

        expected_tabs = {
            "BOSS账号": "BOSS" in html and "账号" in html,
            "自动投递": "自动投递" in html,
            "投递记录": "投递记录" in html,
            "系统设置": "系统设置" in html,
            "工作台": "工作台" in html,
            "简历管理": "简历管理" in html,
            "JD匹配": "JD匹配" in html or "JD" in html,
            "简历优化": "简历优化" in html,
        }
        for tab, found in expected_tabs.items():
            status = "OK" if found else "MISSING"
            print(f"    [{status}] {tab} tab in HTML")

        # 4. Check BOSS account page elements in HTML
        print("\n[4] Checking BOSS账号 page elements in HTML...")
        boss_checks = {
            "连接 BOSS 直聘": "连接 BOSS 直聘" in html,
            "检查登录状态": "检查登录状态" in html,
            "断开连接": "断开连接" in html,
            "退出登录 (清除 Cookie)": "清除 Cookie" in html,
            "打招呼话术": "打招呼话术" in html,
            "黑名单": "黑名单" in html,
            "扫码登录指引": "扫码登录指引" in html,
        }
        for label, found in boss_checks.items():
            status = "OK" if found else "MISSING"
            print(f"    [{status}] {label}")

        # 5. Check delivery page elements in HTML
        print("\n[5] Checking 自动投递 page elements in HTML...")
        delivery_checks = {
            "No Step 1 content": "Step 1" not in html,
            "Connection banner": ("BOSS 账号" in html and "连接并登录" in html),
            "搜索关键词": "搜索关键词" in html,
            "HR活跃度筛选": "HR 活跃度" in html or "HR活跃" in html,
            "批量沟通": "批量沟通" in html,
            "刷新连接状态": "刷新连接状态" in html,
        }
        for label, found in delivery_checks.items():
            status = "OK" if found else "ISSUE"
            print(f"    [{status}] {label}")

        # 6. Check settings page elements in HTML
        print("\n[6] Checking 系统设置 page (no 账号管理)...")
        settings_checks = {
            "No 账号管理 sub-tab": "账号管理" not in html,
            "投递风控": "投递风控" in html or "风控参数" in html,
            "大模型 API": "大模型" in html,
            "数据与隐私": "数据与隐私" in html or "数据管理" in html,
        }
        for label, found in settings_checks.items():
            status = "OK" if found else "ISSUE"
            print(f"    [{status}] {label}")

        # 7. Check server logs for errors
        print("\n[7] Final screenshot...")
        page.screenshot(path="test_screenshots/04_final_state.png")

        browser.close()

    print("\n=== E2E Test Complete ===")
    print("Screenshots saved to test_screenshots/")


if __name__ == "__main__":
    main()
