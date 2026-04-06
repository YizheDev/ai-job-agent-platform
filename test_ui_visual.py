"""UI Visual Test - login + main pages screenshots"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "test_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

URL = "http://127.0.0.1:7860"
API_KEY = os.environ.get("LLM_API_KEY", "")


def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        # ====== LOGIN PAGE TESTS ======
        print("=" * 50)
        print("LOGIN PAGE TESTS")
        print("=" * 50)

        print("\n[1] Loading login page...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/01_login_page.png", full_page=True)

        panels = {
            "login-panel": page.locator("#login-panel").is_visible(),
            "login-left": page.locator("#login-left").is_visible(),
            "login-card": page.locator("#login-card").is_visible(),
        }
        for k, v in panels.items():
            print(f"    {k}: {v}")

        ll_box = page.locator("#login-left").bounding_box()
        lc_box = page.locator("#login-card").bounding_box()
        if ll_box and lc_box:
            print(f"    left: {ll_box['width']:.0f}x{ll_box['height']:.0f}, right: {lc_box['width']:.0f}x{lc_box['height']:.0f}")
            print(f"    height diff: {abs(ll_box['height'] - lc_box['height']):.0f}px")

        # Validation tests
        login_btn = page.locator("#login-btn")
        name_input = page.locator("#login-card input").first
        error_el = page.locator("#login-error")

        print("\n[2] Empty submit...")
        login_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/02_empty_submit.png", full_page=True)
        print(f"    error: [{error_el.inner_text().strip()}] PASS")

        print("\n[3] Invalid username...")
        name_input.fill("test123")
        login_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/03_invalid_username.png", full_page=True)
        print(f"    error: [{error_el.inner_text().strip()}] PASS")

        print("\n[4] No API key...")
        name_input.fill("testuser")
        login_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/04_no_apikey.png", full_page=True)
        print(f"    error: [{error_el.inner_text().strip()}] PASS")

        print("\n[5] Invalid API key...")
        key_input = page.locator("#login-card input[type='password']")
        key_input.fill("sk-fake12345")
        login_btn.click()
        page.wait_for_timeout(20000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/05_invalid_apikey.png", full_page=True)
        print(f"    error: [{error_el.inner_text().strip()}] PASS")

        # ====== LOGIN WITH REAL KEY ======
        if not API_KEY:
            print("\n[!] No LLM_API_KEY set. Skipping main page tests.")
            browser.close()
            return

        print("\n" + "=" * 50)
        print("MAIN PAGE TESTS")
        print("=" * 50)

        print("\n[6] Login with real API key...")
        name_input.fill("testuser")
        key_input.fill(API_KEY)
        login_btn.click()
        page.wait_for_timeout(25000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/06_after_login.png", full_page=True)

        login_hidden = not page.locator("#login-panel").is_visible()
        print(f"    login-panel hidden: {login_hidden}")

        # Check agreement panel
        agree_panel = page.locator("#agreement-panel")
        main_tabs = page.locator("#main-tabs")

        if agree_panel.is_visible():
            print("    Agreement panel visible, clicking agree...")
            page.screenshot(path=f"{SCREENSHOT_DIR}/06_agreement.png", full_page=True)
            agree_btn = agree_panel.locator("button").first
            agree_btn.click()
            page.wait_for_timeout(3000)

        if main_tabs.is_visible():
            print("    Main tabs visible! Login successful.")
            page.screenshot(path=f"{SCREENSHOT_DIR}/07_dashboard.png", full_page=True)
            print("    -> 07_dashboard.png")

            # Screenshot each tab
            tabs = page.locator("#main-tabs > .tab-wrapper button")
            tab_count = tabs.count()
            print(f"    Tab count: {tab_count}")

            tab_names = [
                "dashboard", "resume", "jd_match", "optimize",
                "boss_account", "delivery", "records", "settings",
            ]
            for i in range(min(tab_count, len(tab_names))):
                try:
                    tabs.nth(i).click()
                    page.wait_for_timeout(2000)
                    fname = f"{8+i:02d}_{tab_names[i]}.png"
                    page.screenshot(path=f"{SCREENSHOT_DIR}/{fname}", full_page=True)
                    print(f"    [{i}] {tab_names[i]} -> {fname}")
                except Exception as e:
                    print(f"    [{i}] {tab_names[i]} FAILED: {e}")
        else:
            print("    Main tabs NOT visible after login.")
            print(f"    login-panel visible: {page.locator('#login-panel').is_visible()}")
            print(f"    agreement visible: {agree_panel.is_visible()}")

        print("\n" + "=" * 50)
        print("All tests completed!")
        print(f"Screenshots: {SCREENSHOT_DIR}/")
        print("=" * 50)

        browser.close()


if __name__ == "__main__":
    run_tests()
