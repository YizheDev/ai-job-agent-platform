"""Browser-level UI smoke and regression check for the Gradio app."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT.parent / ".venv" / "Scripts" / "python.exe"
SCREENSHOT_DIR = ROOT / "ui-regression"
PORT = int(os.getenv("UI_REGRESSION_PORT", "7869"))
BASE_URL = f"http://127.0.0.1:{PORT}"
TABS = [
    ("dashboard", 0, "nav"),
    ("resume", 1, "nav"),
    ("jd-match", 2, "nav"),
    ("optimize", 3, "nav"),
    ("delivery", 4, "nav"),
    ("records", 5, "nav"),
    ("settings", 1, "settings"),
]


def wait_for_server(timeout_seconds: float = 45.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(BASE_URL, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"应用未能在 {timeout_seconds} 秒内启动：{BASE_URL}")


def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["GRADIO_SERVER_PORT"] = str(PORT)
    env["GRADIO_INBROWSER"] = "0"

    proc = subprocess.Popen(
        [str(PYTHON), str(ROOT / "main.py")],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    report: dict[str, dict] = {}
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1680, "height": 1180})
            page.goto(BASE_URL, wait_until="networkidle")

            agreement_button = page.locator("#agreement-panel button").first
            if agreement_button.count() and agreement_button.is_visible():
                agreement_button.click()
                page.wait_for_timeout(800)

            labels = ["工作台", "简历管理", "JD匹配", "简历优化", "自动投递", "投递记录", "系统设置"]
            for (slug, index, _mode), label in zip(TABS, labels):
                page.evaluate(
                    """(target) => {
                        const tabs = [...document.querySelectorAll('#main-tabs > .tab-wrapper > .tab-container[role="tablist"] button')];
                        const button = tabs.find((btn) => btn.textContent.trim() === target);
                        if (button) {
                            button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                        }
                    }""",
                    label,
                )
                page.wait_for_timeout(500)
                visible_subtitle = page.locator(".page-subtitle:visible").first
                visible_subtitle.wait_for(state="visible", timeout=5000)
                screenshot_path = SCREENSHOT_DIR / f"{slug}.png"
                page.screenshot(path=str(screenshot_path), full_page=True)

                title = visible_subtitle.inner_text() if visible_subtitle.count() else ""
                cards = page.locator(".stitch-card, .glass-card").count()
                report[slug] = {
                    "title": title,
                    "cards": cards,
                    "screenshot": str(screenshot_path),
                }

            browser.close()

        report_path = SCREENSHOT_DIR / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"UI 回归检查通过，报告已写入：{report_path}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
