"""E2E test: Login, BrowserState persistence, delivery page, search"""

import json
import os
import time

from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:7860/"
TEST_USER = "testzhangsan"
API_KEY = "sk-1e44ceee06de48ad97e68d5003608a22"

os.makedirs("test_screenshots", exist_ok=True)


def _click_agree(page) -> bool:
    """Find and click the agreement button using multiple strategies"""
    time.sleep(2)

    # Strategy 1: find by CSS class (primary button in agreement panel)
    agree_panel = page.locator("#agreement-panel")
    if agree_panel.count() > 0 and agree_panel.is_visible():
        primary_btn = agree_panel.locator("button")
        if primary_btn.count() > 0:
            primary_btn.first.click()
            time.sleep(3)
            return True

    # Strategy 2: Use JS to find by text content directly
    clicked = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.textContent || '';
            if (text.includes('同意') || text.includes('开始使用')) {
                btn.click();
                return true;
            }
        }
        return false;
    }""")
    if clicked:
        time.sleep(3)
        return True

    # Strategy 3: find any visible large primary button
    all_btns = page.locator("button")
    for i in range(all_btns.count()):
        try:
            btn = all_btns.nth(i)
            if btn.is_visible():
                cls = btn.get_attribute("class") or ""
                if "primary" in cls and "lg" in cls:
                    btn.click()
                    time.sleep(3)
                    return True
        except Exception:
            continue

    return False


def test_all():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        # ================================================================
        # TEST 1: Login
        # ================================================================
        print("=" * 60)
        print("[TEST 1] Login flow")
        print("=" * 60)

        page.goto(APP_URL, wait_until="domcontentloaded")
        time.sleep(5)

        login_panel = page.locator("#login-panel")
        print(f"  Login panel visible: {login_panel.is_visible()}")

        name_input = page.locator("#login-card textarea").first
        if name_input.count() == 0:
            name_input = page.locator("#login-card input[type='text']").first
        name_input.fill(TEST_USER)
        time.sleep(0.5)

        key_input = page.locator("#login-card input[type='password']").first
        key_input.fill(API_KEY)
        time.sleep(0.5)

        login_btn = page.locator("#login-btn")
        login_btn.click()
        print("  Login button clicked, waiting for API validation...")
        time.sleep(15)

        page.screenshot(path="test_screenshots/01_after_login.png")

        login_visible = login_panel.is_visible()
        print(f"  Login panel visible: {login_visible}")

        if login_visible:
            error_el = page.locator("#login-error")
            if error_el.count() > 0 and error_el.is_visible():
                print(f"  Error: {error_el.inner_text()}")
            print("  [FAIL] Login failed")
            browser.close()
            return

        # Check and handle agreement panel
        page.screenshot(path="test_screenshots/01b_check_agree.png")
        if _click_agree(page):
            print("  Agreement accepted")
        else:
            print("  Agreement panel not shown (already accepted or direct to main)")

        time.sleep(3)
        page.screenshot(path="test_screenshots/02_main_panel.png")
        print("  [PASS] Login successful")

        # ================================================================
        # TEST 2: BrowserState persistence
        # ================================================================
        print("\n" + "=" * 60)
        print("[TEST 2] BrowserState session persistence")
        print("=" * 60)

        stored_before = page.evaluate("() => JSON.stringify(localStorage)")
        has_session = "ai_job_agent_session" in stored_before
        print(f"  Session in localStorage: {has_session}")

        print("  Refreshing page...")
        page.reload(wait_until="domcontentloaded")
        time.sleep(10)

        page.screenshot(path="test_screenshots/03_after_refresh.png")

        # After refresh, check that login panel is NOT visible
        login_visible_after = login_panel.is_visible() if login_panel.count() > 0 else True
        print(f"  Login panel visible after refresh: {login_visible_after}")

        # Also check that main panel IS visible (not agreement panel)
        # Try to see if any tabs are accessible
        body_text = page.inner_text("body")
        has_main_content = "工作台" in body_text or "简历管理" in body_text
        has_agreement = "免责声明" in body_text and "已阅读" in body_text

        if has_agreement:
            print("  [INFO] Agreement panel showing after refresh (not yet accepted)")
            _click_agree(page)
            time.sleep(3)
            body_text = page.inner_text("body")
            has_main_content = "工作台" in body_text or "简历管理" in body_text

        if not login_visible_after and has_main_content:
            print("  [PASS] Session persisted — main panel visible after refresh!")
        elif not login_visible_after:
            print("  [PASS] Session persisted (login panel hidden)")
        else:
            print("  [FAIL] Session lost after refresh")

        page.screenshot(path="test_screenshots/03b_final_state.png")

        # ================================================================
        # TEST 3: Delivery page
        # ================================================================
        print("\n" + "=" * 60)
        print("[TEST 3] Delivery page step-based layout")
        print("=" * 60)

        # Use JS dispatch to click Gradio tab buttons (they may have display:none)
        delivery_clicked = page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                if ((btn.textContent || '').includes('自动投递')) {
                    btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                    return true;
                }
            }
            return false;
        }""")
        if delivery_clicked:
            print("  Clicked delivery tab via JS dispatch")
            time.sleep(3)
        else:
            btn_info = page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                return Array.from(btns)
                    .map(b => b.textContent.trim().substring(0, 30))
                    .filter(t => t.length > 0);
            }""")
            print(f"  All buttons: {btn_info}")

        if delivery_clicked:
            page.screenshot(path="test_screenshots/04_delivery_page.png")

            has_step1 = page.locator("text=Step 1").count() > 0
            has_step2 = page.locator("text=Step 2").count() > 0
            has_step3 = page.locator("text=Step 3").count() > 0
            print(f"  Step 1: {has_step1}, Step 2: {has_step2}, Step 3: {has_step3}")

            connect_btn = page.locator("button:has-text('连接 BOSS')")
            has_connect = connect_btn.count() > 0
            print(f"  Connect button: {has_connect}")

            has_profile_section = True  # will check after connect

            if has_step1 and has_step2 and has_connect:
                print("  [PASS] Delivery page has step-based layout")

                # ========================================================
                # TEST 4: BOSS connect + search
                # ========================================================
                print("\n" + "=" * 60)
                print("[TEST 4] BOSS connect + search")
                print("=" * 60)

                print("  Clicking 'Connect BOSS'...")
                connect_btn.click()
                time.sleep(25)

                page.screenshot(path="test_screenshots/05_after_connect.png")

                status_tags = page.locator(".status-tag")
                status_text = ""
                if status_tags.count() > 0:
                    status_text = status_tags.first.inner_text()
                    print(f"  Status: {status_text}")

                if "已登录" in status_text:
                    print("  BOSS logged in via cookies!")

                    # Check if profile section is visible
                    body_text = page.inner_text("body")
                    if "BOSS" in body_text and "个人信息" in body_text:
                        print("  [PASS] Profile info displayed after login!")
                    else:
                        print("  [INFO] Profile section not detected in body text")

                    page.screenshot(path="test_screenshots/06_boss_logged_in.png")

                    # Try search
                    print("  Attempting search for 'Python工程师'...")
                    textareas = page.locator("textarea")
                    for i in range(textareas.count()):
                        ta = textareas.nth(i)
                        if ta.is_visible() and ta.is_enabled():
                            placeholder = ta.get_attribute("placeholder") or ""
                            if "关键词" in placeholder or "Python" in placeholder or "搜索" in placeholder:
                                ta.fill("Python工程师")
                                print("  Filled keyword input")
                                break

                    search_btn = page.locator("button:has-text('搜索岗位')")
                    if search_btn.count() > 0:
                        search_btn.click()
                        print("  Waiting for search results (30s)...")
                        time.sleep(30)

                        page.screenshot(path="test_screenshots/07_search_results.png")

                        # Check op status
                        textareas = page.locator("textarea")
                        for i in range(textareas.count()):
                            val = textareas.nth(i).input_value()
                            if val and ("搜索" in val or "岗位" in val or "未" in val):
                                print(f"  Result: {val}")
                                break

                        print("  [INFO] Search test completed")
                    else:
                        print("  [SKIP] Search button not found")
                else:
                    print(f"  Status: {status_text}")
                    print("  [INFO] BOSS not logged in via cookies, need QR scan")
            else:
                print(f"  [INFO] Step layout incomplete: step1={has_step1}, step2={has_step2}, connect={has_connect}")
        else:
            print("  [SKIP] Could not navigate to delivery page")

        # ================================================================
        # Summary
        # ================================================================
        print("\n" + "=" * 60)
        print("[SUMMARY]")
        print("=" * 60)
        print(f"  JS errors: {len(errors)}")
        for e in errors[:3]:
            print(f"    - {e[:150]}")
        print("  Screenshots in test_screenshots/")
        print("  Done!")

        browser.close()


if __name__ == "__main__":
    test_all()
