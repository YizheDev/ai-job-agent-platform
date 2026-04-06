"""Debug DOM structure after login"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7860"
API_KEY = os.environ.get("LLM_API_KEY", "")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    print("=== BEFORE LOGIN ===")
    lp = page.locator("#login-panel")
    info = lp.evaluate("""el => ({
        tag: el.tagName,
        cls: el.className,
        style: el.getAttribute('style'),
        display: getComputedStyle(el).display,
        parentTag: el.parentElement.tagName,
        parentCls: el.parentElement.className,
        parentStyle: el.parentElement.getAttribute('style'),
        parentDisplay: getComputedStyle(el.parentElement).display,
    })""")
    for k, v in info.items():
        print(f"  {k}: {v}")

    # Login
    print("\n=== LOGGING IN ===")
    name = page.locator("#login-card input").first
    key = page.locator("#login-card input[type='password']")
    name.fill("testuser")
    key.fill(API_KEY)
    page.locator("#login-btn").click()
    page.wait_for_timeout(25000)

    print("\n=== AFTER LOGIN ===")
    for panel_id in ["login-panel", "agreement-panel"]:
        el = page.locator(f"#{panel_id}")
        try:
            vis = el.is_visible()
            info = el.evaluate("""el => ({
                cls: el.className,
                style: el.getAttribute('style'),
                display: getComputedStyle(el).display,
                parentStyle: el.parentElement.getAttribute('style'),
                parentDisplay: getComputedStyle(el.parentElement).display,
                gpStyle: el.parentElement.parentElement?.getAttribute('style') || 'none',
                gpDisplay: el.parentElement.parentElement ? getComputedStyle(el.parentElement.parentElement).display : 'none',
            })""")
            print(f"\n{panel_id} (visible={vis}):")
            for k, v in info.items():
                print(f"  {k}: {v}")
        except Exception as e:
            print(f"\n{panel_id}: ERROR - {e}")

    # Check main-tabs
    mt = page.locator("#main-tabs")
    try:
        print(f"\nmain-tabs visible: {mt.is_visible()}")
    except Exception:
        print("\nmain-tabs: not found")

    # Get full hierarchy
    print("\n=== DOM HIERARCHY (Blocks children) ===")
    hierarchy = page.evaluate("""() => {
        const app = document.querySelector('.gradio-container .wrap');
        const root = app || document.querySelector('.gradio-container');
        if (!root) return 'no root found';

        function describe(el, depth) {
            if (depth > 4) return [];
            const res = [];
            for (const c of el.children) {
                const id = c.id || '';
                const vis = getComputedStyle(c).display !== 'none';
                const h = c.offsetHeight;
                if (id || depth < 2) {
                    res.push('  '.repeat(depth) + c.tagName +
                        (id ? '#' + id : '') +
                        ' [display=' + getComputedStyle(c).display +
                        ', h=' + h + ']' +
                        (c.getAttribute('style') ? ' style="' + c.getAttribute('style').substring(0, 80) + '"' : ''));
                    res.push(...describe(c, depth + 1));
                }
            }
            return res;
        }
        return describe(root, 0).join('\\n');
    }""")
    print(hierarchy)

    page.screenshot(path="test_screenshots/debug_after_login.png", full_page=True)
    browser.close()
