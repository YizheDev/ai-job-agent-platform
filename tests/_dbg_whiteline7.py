"""Read actual pixel colors along the white-line row."""
import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG = PROJECT_ROOT / "test_screenshots/dbg_whiteline7_log.txt"


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg, flush=True)


def main():
    LOG.unlink(missing_ok=True)
    img = Image.open(PROJECT_ROOT / "test_screenshots/_v2_dashboard.png").convert("RGB")
    W, H = img.size
    log(f"size: {W}x{H}")
    # Sample pixels at y=1181 (bright row) and rows around it
    for y in range(1175, 1190):
        row_summary = []
        for x in range(80, 320, 5):
            row_summary.append(img.getpixel((x, y)))
        log(f"y={y}: " + " ".join(str(p) for p in row_summary))
    # Also check what's at y=1182 (after tab-container should end)
    log("\n== rows just before and after y=1181 ==")
    for y in [1175, 1180, 1181, 1182, 1185, 1190, 1200, 1210, 1220]:
        log(f"y={y} px(150,y)={img.getpixel((150, y))} px(200,y)={img.getpixel((200, y))} px(400,y)={img.getpixel((400, y))}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e!r}")
        sys.exit(1)
