"""Pixel-level scanning of the bottom-left for the white line."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline4_log.txt"


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
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
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

        # Take viewport screenshot at 1x
        png_path = out / "_wl_viewport.png"
        page.screenshot(path=str(png_path), full_page=False)

        # Also full page
        page.screenshot(path=str(out / "_wl_fullpage.png"), full_page=True)

        # Now scan pixel rows for bright (white-ish) horizontal patches
        img = Image.open(png_path).convert("RGB")
        W, H = img.size
        log(f"viewport size: {W}x{H}")
        # Scan only sidebar area (x: 80-300) to find bright horizontal runs
        bright_rows = []
        for y in range(H):
            count_bright = 0
            run_start = None
            longest_run = 0
            curr_run = 0
            for x in range(60, min(320, W)):
                r, g, b = img.getpixel((x, y))
                if r > 200 and g > 200 and b > 200:
                    curr_run += 1
                    if curr_run > longest_run:
                        longest_run = curr_run
                    count_bright += 1
                else:
                    curr_run = 0
            if longest_run >= 30:
                bright_rows.append((y, count_bright, longest_run))
        log(f"bright rows in sidebar zone (x 60-320): {len(bright_rows)}")
        for r in bright_rows[:30]:
            log(r)

        # Now scan the entire bottom area for any horizontal bright run
        log("== entire viewport bottom (y 800-900) bright runs ==")
        for y in range(800, H):
            for xstart in range(0, W, 50):
                run = 0
                max_run = 0
                for x in range(xstart, min(xstart + 50, W)):
                    r, g, b = img.getpixel((x, y))
                    if r > 200 and g > 200 and b > 200:
                        run += 1
                        if run > max_run:
                            max_run = run
                    else:
                        run = 0
                if max_run >= 20:
                    log(f"y={y} xstart={xstart} max_run={max_run} sample_color={img.getpixel((xstart + max_run // 2, y))}")
                    break

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
