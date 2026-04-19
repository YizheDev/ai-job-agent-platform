"""Locate the white line at bottom-left using elementsFromPoint and border/box-shadow inspection."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline2_log.txt"


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
    out.mkdir(parents=True, exist_ok=True)
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

        # zoom to bottom-left of sidebar (~ x=150, y=860 in 1440x900 view)
        # capture screenshot focused on bottom-left
        page.screenshot(path=str(out / "_wl_dashboard_full.png"), full_page=False)

        # inspect 30 candidate Y positions in the bottom-left region
        report = page.evaluate(
            """
            () => {
                const xs = [80, 120, 150, 180, 200, 220, 260];
                const ys = [];
                for (let y = 800; y < 900; y += 2) ys.push(y);
                const lines = new Map();
                for (const y of ys) {
                    for (const x of xs) {
                        const el = document.elementFromPoint(x, y);
                        if (!el) continue;
                        const cs = getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        // check border colors and widths
                        const bts = ['Top','Right','Bottom','Left'];
                        for (const b of bts) {
                            const w = parseFloat(cs['border'+b+'Width']);
                            const c = cs['border'+b+'Color'];
                            if (w > 0 && /rgb/.test(c)) {
                                const m = c.match(/rgba?\\(([^)]+)\\)/);
                                if (m) {
                                    const parts = m[1].split(',').map(s=>parseFloat(s));
                                    const r2 = parts[0], g2 = parts[1], b2 = parts[2];
                                    const a = parts[3] !== undefined ? parts[3] : 1;
                                    if (r2 > 200 && g2 > 200 && b2 > 200 && a > 0.4 && w < 6) {
                                        const key = `${el.tagName}#${el.id}.${(el.className||'').toString().split(' ').slice(0,2).join('.')}_b=${b}`;
                                        if (!lines.has(key)) {
                                            lines.set(key, {
                                                tag: el.tagName,
                                                id: el.id,
                                                cls: (el.className||'').toString().substring(0, 80),
                                                border: b, w, c,
                                                rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                                                bg: cs.backgroundColor,
                                                outline: cs.outlineWidth + ' ' + cs.outlineColor,
                                                bs: cs.boxShadow.substring(0, 100),
                                            });
                                        }
                                    }
                                }
                            }
                        }
                        // check outline
                        const ow = parseFloat(cs.outlineWidth);
                        const oc = cs.outlineColor;
                        if (ow > 0 && /rgb/.test(oc)) {
                            const m = oc.match(/rgba?\\(([^)]+)\\)/);
                            if (m) {
                                const parts = m[1].split(',').map(s=>parseFloat(s));
                                if (parts[0]>200 && parts[1]>200 && parts[2]>200) {
                                    const key = `OUTLINE_${el.tagName}#${el.id}`;
                                    if (!lines.has(key)) lines.set(key, {tag: el.tagName, id: el.id, outline: cs.outline});
                                }
                            }
                        }
                        // check background-color
                        const bg = cs.backgroundColor;
                        if (bg && /rgba?\\(([^)]+)\\)/.test(bg)) {
                            const m = bg.match(/rgba?\\(([^)]+)\\)/);
                            const parts = m[1].split(',').map(s=>parseFloat(s));
                            const a = parts[3] !== undefined ? parts[3] : 1;
                            if (parts[0]>200 && parts[1]>200 && parts[2]>200 && a > 0.5 && r.height < 8 && r.width > 30) {
                                const key = `BG_${el.tagName}#${el.id}`;
                                if (!lines.has(key)) lines.set(key, {tag: el.tagName, id: el.id, cls: (el.className||'').toString().substring(0, 80), rect: {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}, bg});
                            }
                        }
                    }
                }
                return Array.from(lines.values());
            }
            """
        )
        log(f"items: {len(report)}")
        for it in report:
            log(it)

        # Also dump the entire ancestor chain of element at the most probable spot
        deep = page.evaluate(
            """
            () => {
                const points = [[120, 860], [150, 858], [180, 866], [200, 870], [120, 880]];
                const out = [];
                for (const [x,y] of points) {
                    const el = document.elementFromPoint(x, y);
                    if (!el) { out.push({pt:[x,y], chain:'(none)'}); continue; }
                    const chain = [];
                    let n = el;
                    while (n && n.tagName) {
                        const r = n.getBoundingClientRect();
                        const cs = getComputedStyle(n);
                        chain.push({
                            tag: n.tagName,
                            id: n.id,
                            cls: (n.className||'').toString().substring(0,80),
                            x: Math.round(r.x), y: Math.round(r.y),
                            w: Math.round(r.width), h: Math.round(r.height),
                            bg: cs.backgroundColor,
                            bb: cs.borderBottomWidth + ' ' + cs.borderBottomStyle + ' ' + cs.borderBottomColor,
                            bt: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
                        });
                        n = n.parentElement;
                        if (chain.length > 8) break;
                    }
                    out.push({pt:[x,y], chain});
                }
                return out;
            }
            """
        )
        log("== ELEMENT CHAINS ==")
        for c in deep:
            log(f"point {c['pt']}:")
            for n in c['chain']:
                log(f"  {n}")
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
