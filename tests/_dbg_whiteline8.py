"""Inspect pseudo-elements and overflow elements for the white line."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline8_log.txt"


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

        # Inspect pseudo-elements on tab-container, tab-wrapper, main-tabs, .selected, .tab-container > *
        report = page.evaluate(
            """
            () => {
                const targets = [
                    document.querySelector('#main-tabs > .tab-wrapper'),
                    document.querySelector('#main-tabs > .tab-wrapper > .tab-container'),
                    document.querySelector('#main-tabs'),
                    document.querySelector('#main-tabs > .tabitem'),
                ];
                const out = [];
                for (const el of targets) {
                    if (!el) continue;
                    const r = el.getBoundingClientRect();
                    out.push({
                        kind: 'self',
                        tag: el.tagName, id: el.id || '', cls: (el.className||'').toString().substring(0,80),
                        rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                    });
                    for (const pe of ['::before', '::after']) {
                        const cs = getComputedStyle(el, pe);
                        if (cs.content && cs.content !== 'none' && cs.content !== '""') {
                            out.push({
                                kind: pe,
                                tag: el.tagName, id: el.id || '', cls: (el.className||'').toString().substring(0,80),
                                content: cs.content, bg: cs.backgroundColor, bs: cs.boxShadow.substring(0,80),
                                bbW: cs.borderBottomWidth + ' ' + cs.borderBottomColor,
                                btW: cs.borderTopWidth + ' ' + cs.borderTopColor,
                                w: cs.width, h: cs.height, pos: cs.position,
                                top: cs.top, bottom: cs.bottom, left: cs.left,
                            });
                        }
                    }
                }

                // Look at all CHILDREN of tab-container as well as scroll-related
                const tc = document.querySelector('#main-tabs > .tab-wrapper > .tab-container');
                if (tc) {
                    for (const c of tc.children) {
                        const r = c.getBoundingClientRect();
                        out.push({
                            kind: 'tc-child',
                            tag: c.tagName, id: c.id || '', cls: (c.className||'').toString().substring(0,80),
                            rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                            bg: getComputedStyle(c).backgroundColor,
                            bb: getComputedStyle(c).borderBottom,
                            bs: getComputedStyle(c).boxShadow.substring(0,80),
                        });
                    }
                }

                // Find any element on the page with a non-zero border-bottom of width <=2 in white-ish color
                for (const el of document.querySelectorAll('*')) {
                    const cs = getComputedStyle(el);
                    const w = parseFloat(cs.borderBottomWidth);
                    const c = cs.borderBottomColor;
                    if (w >= 0.5 && w <= 3) {
                        const m = c.match(/rgba?\\(([^)]+)\\)/);
                        if (m) {
                            const ps = m[1].split(',').map(s => parseFloat(s));
                            if (ps[0] > 200 && ps[1] > 200 && ps[2] > 200) {
                                const r = el.getBoundingClientRect();
                                if (r.width > 100 && r.width < 220) {
                                    out.push({kind: 'whitebb', tag: el.tagName, id: el.id, cls: (el.className||'').toString().substring(0,80), rect: {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}, bw: w, bc: c});
                                }
                            }
                        }
                    }
                    const wt = parseFloat(cs.borderTopWidth);
                    const ct = cs.borderTopColor;
                    if (wt >= 0.5 && wt <= 3) {
                        const m = ct.match(/rgba?\\(([^)]+)\\)/);
                        if (m) {
                            const ps = m[1].split(',').map(s => parseFloat(s));
                            if (ps[0] > 200 && ps[1] > 200 && ps[2] > 200) {
                                const r = el.getBoundingClientRect();
                                if (r.width > 100 && r.width < 220) {
                                    out.push({kind: 'whitebt', tag: el.tagName, id: el.id, cls: (el.className||'').toString().substring(0,80), rect: {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}, bw: wt, bc: ct});
                                }
                            }
                        }
                    }
                    // Also check for white box-shadow inset
                    const sh = cs.boxShadow;
                    if (sh && sh !== 'none' && /229,?\s*231,?\s*235|230,?\s*233,?\s*245|255,?\s*255,?\s*255/.test(sh)) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100 && r.width < 220) {
                            out.push({kind: 'whitebs', tag: el.tagName, id: el.id, cls: (el.className||'').toString().substring(0,80), rect: {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}, bs: sh.substring(0,150)});
                        }
                    }
                }
                return out;
            }
            """
        )
        log(f"items: {len(report)}")
        for it in report:
            log(it)

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
