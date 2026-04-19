"""Pixel-scan the full-page screenshot for bright horizontal runs."""
import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline5_log.txt"


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg, flush=True)


def scan(png):
    img = Image.open(png).convert("RGB")
    W, H = img.size
    log(f"== {png.name}: {W}x{H} ==")
    # Bright rows over a wide horizontal swath
    rows = []
    for y in range(H):
        max_run = 0
        run = 0
        for x in range(0, W):
            r, g, b = img.getpixel((x, y))
            if r > 200 and g > 200 and b > 200:
                run += 1
                if run > max_run:
                    max_run = run
            else:
                run = 0
        if max_run >= 30:
            rows.append((y, max_run))
    log(f"  total bright rows: {len(rows)}")
    for r in rows[:50]:
        log(f"  row y={r[0]} max_run={r[1]}")
    return rows


def main():
    LOG.unlink(missing_ok=True)
    out = PROJECT_ROOT / "test_screenshots"
    for fn in ["_wl_fullpage.png", "_v2_dashboard.png", "_v2_resume.png", "_v2_settings.png"]:
        path = out / fn
        if path.exists():
            scan(path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
