"""E2E test: login + BrowserState persistence + page refresh"""

import time
import json
from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:7860/"
TEST_USER = "testzhangsan"
API_KEY = "sk-1e44ceee06de48ad97e68d5003608a22"


def test_login_and_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Open app
        print("[1] Opening app...")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # Check login panel is visible
        login_panel = page.locator("#login-panel")
        print(f"  Login panel visible: {login_panel.is_visible()}")

        # Step 2: Fill in login form
        print("[2] Filling login form...")
        name_input = page.locator("input").first
        name_input.fill(TEST_USER)
        time.sleep(0.5)

        # Find the password input (API Key)
        password_input = page.locator("input[type='password']").first
        password_input.fill(API_KEY)
        time.sleep(0.5)

        # Step 3: Click login
        print("[3] Clicking login button...")
        login_btn = page.locator("#login-btn")
        login_btn.click()

        # Wait for login to complete (API validation takes time)
        print("  Waiting for login response...")
        time.sleep(15)

        # Check if login was successful
        login_visible = login_panel.is_visible()
        print(f"  Login panel still visible: {login_visible}")

        # Check localStorage for BrowserState
        stored = page.evaluate("""() => {
            const keys = Object.keys(localStorage);
            const result = {};
            for (const k of keys) {
                try {
                    result[k] = JSON.parse(localStorage.getItem(k));
                } catch {
                    result[k] = localStorage.getItem(k);
                }
            }
            return result;
        }""")
        print(f"  localStorage keys: {list(stored.keys())}")
        for k, v in stored.items():
            if isinstance(v, dict) and "logged_in" in str(v):
                print(f"  Session data found in key '{k}': logged_in={v.get('logged_in')}, user={v.get('user_name')}")

        if login_visible:
            print("\n[FAIL] Login did not succeed - checking page content...")
            error_el = page.locator("#login-error")
            if error_el.is_visible():
                print(f"  Error message: {error_el.inner_text()}")

            # Take screenshot for debugging
            page.screenshot(path="test_screenshots/login_failed.png")
            browser.close()
            return

        # Step 4: Page refresh test
        print("[4] Refreshing page...")
        page.reload(wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # Check if still logged in
        login_visible_after = login_panel.is_visible()
        print(f"  Login panel visible after refresh: {login_visible_after}")

        if not login_visible_after:
            print("\n[PASS] Session persisted after refresh!")
        else:
            print("\n[FAIL] Session lost after refresh")
            # Debug localStorage after refresh
            stored_after = page.evaluate("""() => {
                const keys = Object.keys(localStorage);
                const result = {};
                for (const k of keys) {
                    try {
                        result[k] = JSON.parse(localStorage.getItem(k));
                    } catch {
                        result[k] = localStorage.getItem(k);
                    }
                }
                return result;
            }""")
            print(f"  localStorage after refresh: {json.dumps(stored_after, indent=2, default=str)}")

        page.screenshot(path="test_screenshots/after_refresh.png")
        browser.close()


if __name__ == "__main__":
    import os
    os.makedirs("test_screenshots", exist_ok=True)
    test_login_and_session()
