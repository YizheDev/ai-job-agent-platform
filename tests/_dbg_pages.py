"""Capture screenshots of all pages and look for white-line elements."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_pages_log.txt"


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

        targets = [
            ("dashboard", "📊 工作台"),
            ("resume", "📄 简历管理"),
            ("jd_match", "🔍 JD匹配"),
            ("optimize", "✨ 简历优化"),
            ("boss", "🔗 BOSS账号"),
            ("delivery", "🚀 自动投递"),
            ("records", "📋 投递记录"),
            ("settings", "⚙ 系统设置"),
        ]
        buttons = page.locator("#main-tabs .tab-wrapper button")
        bcount = buttons.count()
        log(f"buttons: {bcount}")

        for slug, label in targets:
            for i in range(bcount):
                try:
                    if label.split(" ", 1)[1] in buttons.nth(i).inner_text():
                        buttons.nth(i).click(force=True)
                        break
                except Exception:
                    continue
            page.wait_for_timeout(2500)
            page.screenshot(path=str(out / f"_v2_{slug}.png"), full_page=True)
            log(f"saved {slug}")

            # Find white-ish lines for issue 9
            info = page.evaluate(
                """
                () => {
                    const out = [];
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const r = el.getBoundingClientRect();
                        if (r.width < 80) continue;
                        if (r.height > 6 || r.height < 0.5) continue;
                        const cs = getComputedStyle(el);
                        const bg = cs.backgroundColor;
                        const isWhiteBg = bg && /rgba?\\(2[0-5]\\d,\\s*2[0-5]\\d,\\s*2[0-5]\\d/.test(bg);
                        if (isWhiteBg && parseFloat((bg.match(/\\d?\\.?\\d+\\)$/) || ['1)'])[0]) > 0.5) {
                            out.push({
                                tag: el.tagName + '.' + (typeof el.className === 'string' ? el.className.split(' ').slice(0,3).join('.') : ''),
                                x: Math.round(r.x), y: Math.round(r.y),
                                w: Math.round(r.width), h: Math.round(r.height),
                                bg, parent: el.parentElement ? el.parentElement.tagName + '.' + (typeof el.parentElement.className === 'string' ? el.parentElement.className.split(' ')[0] : '') : '',
                            });
                            if (out.length >= 8) break;
                        }
                    }
                    return out;
                }
                """
            )
            if info:
                log(f"[{slug}] white-line elements:")
                for it in info:
                    log(f"  {it}")
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
