"""Debug Gradio tab DOM structure - with login first"""
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://127.0.0.1:7860", wait_until="domcontentloaded")
    time.sleep(5)

    # Login first
    name_input = page.locator("#login-card textarea").first
    if name_input.count() == 0:
        name_input = page.locator("#login-card input[type='text']").first
    name_input.fill("testzhangsan")
    time.sleep(0.5)
    key_input = page.locator("#login-card input[type='password']").first
    key_input.fill("sk-1e44ceee06de48ad97e68d5003608a22")
    time.sleep(0.5)
    page.locator("#login-btn").click()
    print("Logging in...")
    time.sleep(15)

    # Handle agreement if needed
    page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            if ((btn.textContent || '').includes('同意') || (btn.textContent || '').includes('开始使用')) {
                btn.click();
                return true;
            }
        }
        return false;
    }""")
    time.sleep(3)

    print("After login, checking DOM...")

    # Get all buttons with delivery text
    btn_info = page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        const result = [];
        for (const btn of btns) {
            if ((btn.textContent || '').includes('自动投递')) {
                const style = getComputedStyle(btn);
                result.push({
                    text: btn.textContent.trim(),
                    visible: btn.offsetParent !== null,
                    display: style.display,
                    className: btn.className.substring(0, 50),
                    parentTag: btn.parentElement ? btn.parentElement.tagName : 'none',
                });
            }
        }
        return result;
    }""")
    print(f"Buttons with '自动投递': {len(btn_info)}")
    for b in btn_info:
        print(f"  {b}")

    # Check #main-tabs
    tab_found = page.evaluate("() => !!document.querySelector('#main-tabs')")
    print(f"#main-tabs found: {tab_found}")

    # Get role=tab elements
    role_tabs = page.evaluate("""() => {
        const tabs = document.querySelectorAll('[role=tab]');
        return Array.from(tabs).map(t => ({
            text: t.textContent.trim().substring(0, 30),
            visible: t.offsetParent !== null,
            tag: t.tagName,
        }));
    }""")
    print(f"Role=tab elements: {len(role_tabs)}")
    for t in role_tabs:
        print(f"  {t}")

    # Get all visible buttons for debugging
    all_btns = page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        return Array.from(btns)
            .filter(b => b.offsetParent !== null)
            .map(b => b.textContent.trim().substring(0, 40))
            .filter(t => t.length > 0);
    }""")
    print(f"All visible buttons ({len(all_btns)}): {all_btns[:15]}")

    # Find the tab nav
    tab_nav = page.evaluate("""() => {
        const el = document.querySelector('#main-tabs');
        if (!el) return 'NOT FOUND';
        return el.outerHTML.substring(0, 3000);
    }""")
    if tab_nav == "NOT FOUND":
        print("main-tabs NOT FOUND!")
        # Look for any tabs-like structure
        tab_alternatives = page.evaluate("""() => {
            const els = document.querySelectorAll('[class*=tab], [class*=Tab]');
            return Array.from(els).slice(0, 10).map(e => ({
                tag: e.tagName,
                class: e.className.substring(0, 60),
                id: e.id,
            }));
        }""")
        print(f"Tab-like elements: {tab_alternatives}")
    else:
        print(f"main-tabs HTML: {tab_nav[:500]}")

    page.screenshot(path="test_screenshots/tab_debug.png")
    browser.close()
