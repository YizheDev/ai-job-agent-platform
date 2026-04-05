"""Minimal BrowserState test - final"""
import gradio as gr
import time


def save_data(name):
    data = {"name": name, "saved": True}
    print(f"[SERVER] save_data called: {data}")
    return data, data, f"Saved: {name}"


def load_data(stored):
    print(f"[SERVER] load_data called with: {stored} (type={type(stored).__name__})")
    if stored and isinstance(stored, dict) and stored.get("saved"):
        n = stored.get("name", "?")
        return f"Restored: {n}"
    return "No saved data"


with gr.Blocks() as demo:
    bs = gr.BrowserState({"saved": False}, storage_key="test_key_v3", secret="fixed_secret_123")
    state = gr.State()
    inp = gr.Textbox(label="Name")
    btn = gr.Button("Save")
    out = gr.Textbox(label="Result", interactive=False)

    btn.click(fn=save_data, inputs=[inp], outputs=[state, bs, out])
    demo.load(fn=load_data, inputs=[bs], outputs=[out])

demo.launch(server_port=7865, prevent_thread_lock=True)
time.sleep(3)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("http://127.0.0.1:7865", wait_until="domcontentloaded")
    time.sleep(5)

    # Type and save
    page.locator("textarea").first.fill("hello")
    time.sleep(1)
    page.get_by_role("button", name="Save").click()
    time.sleep(5)

    # Refresh
    print("\n--- Refreshing ---")
    page.reload(wait_until="domcontentloaded")

    # Wait for specific text to appear
    try:
        page.wait_for_function(
            "() => document.querySelector('textarea') && document.querySelector('textarea').value.includes('Restored')",
            timeout=15000,
        )
        result = page.locator("textarea").first.input_value()
        print(f"PASS - After refresh result: '{result}'")
    except Exception:
        time.sleep(5)
        # Try innerHTML / textContent
        all_text = page.evaluate("""() => {
            const tas = document.querySelectorAll('textarea');
            return Array.from(tas).map(t => ({value: t.value, text: t.textContent}));
        }""")
        print(f"FAIL - Textareas: {all_text}")

        # Check if load event fired at all
        result_el = page.locator("textarea").nth(1)
        if result_el.count() > 0:
            print(f"  Second textarea value: '{result_el.input_value()}'")

    browser.close()

demo.close()
print("Done")
