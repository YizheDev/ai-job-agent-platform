"""Inspect elements at the exact y of white line (bottom of tab-container)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline6_log.txt"


def _read_env(key: str, default: str = "") -> str:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg, flush=True)


def main():
    LOG.unlink(missing_ok=True)
    out = PROJECT_ROOT / "test_screenshots"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto("http://127.0.0.1:7860/", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        if page.locator("#login-panel").is_visible():
            api_key = _read_env("LLM_API_KEY")
            page.locator('#login-card input[type="text"]').first.fill("zhangsan")
            page.locator('#login-card input[type="password"]').first.fill(api_key)
            page.locator("#login-btn").click()
            for _ in range(25):
                page.wait_for_timeout(800)
                if not page.locator("#login-panel").is_visible():
                    break
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
        for _ in range(15):
            if page.locator("#agreement-panel").is_visible():
                try:
                    page.locator('#agreement-panel button:has-text("已阅读并同意")').first.click(timeout=3000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
            else:
                break
            page.wait_for_timeout(500)

        # Scroll to bottom to bring the white line into the viewport
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(800)

        page.screenshot(path=str(out / "_wl6_scrolled.png"), full_page=False)

        # Get the document scrollable height
        meta = page.evaluate("() => ({sh: document.documentElement.scrollHeight, ih: window.innerHeight, sy: window.scrollY})")
        log(f"meta: {meta}")

        # Compute viewport coordinates of y=1181 in document
        target_y_doc = 1181
        target_y_view = target_y_doc - meta["sy"]
        log(f"target_y_view: {target_y_view}")

        # Inspect all elements at x=150-180, y=1181 in document - using elementsFromPoint after scroll
        for x in [120, 150, 180, 200]:
            els = page.evaluate(f"""
                () => {{
                    const els = document.elementsFromPoint({x}, {target_y_view});
                    return els.slice(0, 5).map(el => ({{
                        tag: el.tagName, id: el.id || '', cls: (el.className||'').toString().substring(0, 80),
                        bg: getComputedStyle(el).backgroundColor,
                        bbW: getComputedStyle(el).borderBottomWidth,
                        bbS: getComputedStyle(el).borderBottomStyle,
                        bbC: getComputedStyle(el).borderBottomColor,
                        btW: getComputedStyle(el).borderTopWidth,
                        btS: getComputedStyle(el).borderTopStyle,
                        btC: getComputedStyle(el).borderTopColor,
                        rect: (() => {{ const r = el.getBoundingClientRect(); return {{x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)}}; }})(),
                    }}));
                }}
            """)
            log(f"x={x} y_view={target_y_view}:")
            for e in els:
                log(f"  {e}")

        # Now look at all elements on the entire page that have a border-bottom OR border-top with white-ish color and width > 0
        report = page.evaluate("""
            () => {
                const out = [];
                for (const el of document.querySelectorAll('*')) {
                    const cs = getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    const sides = [['Top','bt'],['Bottom','bb']];
                    for (const [s, k] of sides) {
                        const w = parseFloat(cs['border'+s+'Width']);
                        const c = cs['border'+s+'Color'];
                        if (w > 0 && c) {
                            const m = c.match(/rgba?\\(([^)]+)\\)/);
                            if (m) {
                                const parts = m[1].split(',').map(s2=>parseFloat(s2));
                                const r2=parts[0], g2=parts[1], b2=parts[2];
                                const a = parts[3] !== undefined ? parts[3] : 1;
                                if (r2 > 200 && g2 > 200 && b2 > 200 && a > 0.3 && r.width > 100 && r.width < 250) {
                                    out.push({
                                        side: s,
                                        tag: el.tagName, id: el.id || '',
                                        cls: (el.className||'').toString().substring(0,80),
                                        rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                                        bw: w, bc: c,
                                    });
                                }
                            }
                        }
                    }
                }
                return out;
            }
        """)
        log(f"\n== white border on narrow elements ({len(report)} items) ==")
        for it in report:
            log(it)

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
