"""Test main pages - click visible tab buttons and screenshot"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "test_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

URL = "http://127.0.0.1:7860"
API_KEY = os.environ.get("LLM_API_KEY", "")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()

    # Load page
    print("[1] Loading page...")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # Login if needed
    lp = page.locator("#login-panel")
    if lp.is_visible():
        print("    Logging in...")
        name = page.locator("#login-card input").first
        key = page.locator("#login-card input[type='password']")
        name.fill("testuser")
        key.fill(API_KEY)
        page.locator("#login-btn").click()
        page.wait_for_timeout(25000)
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)

        agree = page.locator("#agreement-panel")
        if agree.is_visible():
            agree.locator("button").first.click()
            page.wait_for_timeout(60000)

    # Find VISIBLE tab buttons only
    visible_tabs = page.evaluate("""() => {
        const tabs = document.querySelectorAll('#main-tabs button');
        const result = [];
        for (let i = 0; i < tabs.length; i++) {
            const btn = tabs[i];
            if (btn.offsetHeight > 0 && btn.offsetWidth > 0) {
                const text = btn.textContent.trim();
                if (text && !text.includes('上传') && !text.includes('新建') && !text.includes('查看') && !text.includes('刷新')) {
                    result.push({domIndex: i, text: text});
                }
            }
        }
        return result;
    }""")

    print(f"\n[2] Found {len(visible_tabs)} visible tab buttons:")
    for t in visible_tabs:
        print(f"    [{t['domIndex']}] {t['text']}")

    tab_names = ["dashboard", "resume", "jd_match", "optimize",
                 "boss_account", "delivery", "records", "settings"]

    print("\n[3] Screenshotting each tab page...")
    for i, tab in enumerate(visible_tabs):
        if i >= len(tab_names):
            break
        idx = tab['domIndex']
        page.evaluate(f"""() => {{
            const tabs = document.querySelectorAll('#main-tabs button');
            if (tabs[{idx}]) tabs[{idx}].click();
        }}""")
        page.wait_for_timeout(2000)
        fname = f"main_{tab_names[i]}.png"
        page.screenshot(path=f"{SCREENSHOT_DIR}/{fname}", full_page=True)
        print(f"    [{i}] {tab['text']} -> {fname}")

    print("\n" + "=" * 50)
    print("All tab screenshots captured!")
    print(f"Screenshots in: {SCREENSHOT_DIR}/")
    print("=" * 50)

    browser.close()
