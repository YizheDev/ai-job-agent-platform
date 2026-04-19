"""Take a focused crop of the bottom-left to find the exact white line position."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline3_log.txt"


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
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
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

        # Focused crop on bottom-left of sidebar
        page.screenshot(path=str(out / "_wl_focused.png"), clip={"x": 50, "y": 700, "width": 350, "height": 200})

        # Sample pixels along x=150 (sidebar middle) from y=700 to y=900 to detect bright pixel rows
        sampled = page.evaluate(
            r"""
            async () => {
                // grab snapshot via canvas:
                const w = window.innerWidth, h = window.innerHeight;
                const canvas = document.createElement('canvas');
                canvas.width = w; canvas.height = h;
                const ctx = canvas.getContext('2d');
                // We can't getImageData of the page directly, so use different approach:
                // Use document.elementFromPoint at very fine Y resolution
                const rows = [];
                for (let y = 700; y < 900; y += 1) {
                    const els = document.elementsFromPoint(150, y);
                    const summary = [];
                    for (const el of els) {
                        if (!el || !el.tagName) continue;
                        const cs = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        // include all elements with a meaningful background or border at this point
                        const bg = cs.backgroundColor;
                        const bs = cs.boxShadow;
                        const bbW = parseFloat(cs.borderBottomWidth);
                        const btW = parseFloat(cs.borderTopWidth);
                        if (bbW > 0 || btW > 0 || (bs && bs !== 'none')) {
                            summary.push({
                                tag: el.tagName, id: el.id || '',
                                cls: (el.className||'').toString().substring(0,60),
                                rect: {x:Math.round(r.x), y:Math.round(r.y), h:Math.round(r.height)},
                                bbW, btW,
                                btC: cs.borderTopColor,
                                bbC: cs.borderBottomColor,
                                bs: bs.substring(0, 80),
                            });
                        }
                        if (summary.length > 4) break;
                    }
                    rows.push({y, items: summary.slice(0, 3)});
                }
                return rows.filter(r => r.items.length > 0);
            }
            """
        )
        log(f"rows: {len(sampled)}")
        for r in sampled[:30]:
            log(r)

        # Also check #login-panel and #agreement-panel for any leftover horizontal lines
        misc = page.evaluate(
            """
            () => {
                // Find all elements at left side <= 250 and y between 800 and 900
                const r = [];
                for (const el of document.querySelectorAll('*')) {
                    const b = el.getBoundingClientRect();
                    if (b.x > 250 || b.x + b.width < 50) continue;
                    if (b.y < 700 || b.y > 900) continue;
                    if (b.height > 6) continue;
                    if (b.width < 30) continue;
                    const cs = getComputedStyle(el);
                    r.push({
                        tag: el.tagName, id: el.id, cls: (el.className||'').toString().substring(0,80),
                        rect: {x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)},
                        bg: cs.backgroundColor,
                        bt: cs.borderTopWidth+' '+cs.borderTopColor,
                        bb: cs.borderBottomWidth+' '+cs.borderBottomColor,
                    });
                }
                return r;
            }
            """
        )
        log("== short elements in bottom-left zone ==")
        for it in misc:
            log(it)

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
