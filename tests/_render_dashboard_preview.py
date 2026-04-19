"""离线渲染 Dashboard 预览 HTML 并用 Playwright 截图.

用途: 验证 Bento Grid 暗色风格设计效果. 不依赖 Gradio 运行.
产物: test_screenshots/dashboard_bento.png
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.pages.dashboard import _render_stats_html, _render_recent_table, _render_alert


def build_preview_html() -> str:
    stats = _render_stats_html(
        remaining=85,
        today_count=15,
        total_count=312,
        avg_score=78.4,
        daily_stats=[
            {"date": "2026-04-12", "count": 8},
            {"date": "2026-04-13", "count": 12},
            {"date": "2026-04-14", "count": 6},
            {"date": "2026-04-15", "count": 18},
            {"date": "2026-04-16", "count": 9},
            {"date": "2026-04-17", "count": 22},
            {"date": "2026-04-18", "count": 15},
        ],
        score_dist={"high": 45, "medium": 120, "low": 32},
        all_records=[
            *([{"status": "success"}] * 120),
            *([{"status": "failed"}] * 28),
            *([{"status": "delivering"}] * 14),
            *([{"status": "pending"}] * 32),
            *([{"status": "confirmed"}] * 11),
            *([{"status": "cancelled"}] * 4),
        ],
        max_daily=100,
        start_hour=9,
        end_hour=19,
        user_name="zhangsan",
    )
    alert = _render_alert("⚠ 当前 14:23 在投递时段；额度充足，建议优先高匹配岗位")
    table = _render_recent_table(
        [
            ["阿里巴巴", "高级前端工程师", 88, "2026-04-18 14:23", "success"],
            ["字节跳动", "资深产品经理", 76, "2026-04-18 11:05", "delivering"],
            ["美团", "Python 后端开发", 92, "2026-04-18 09:40", "success"],
            ["腾讯", "AI 算法工程师", 55, "2026-04-17 18:12", "failed"],
            ["百度", "全栈开发工程师", 71, "2026-04-17 15:08", "confirmed"],
        ]
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Dashboard Bento Preview</title>
<style>
    html, body {{
        margin: 0; padding: 0; min-height: 100vh;
        font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif;
        background: #000;
    }}
    /* 模拟 Gradio 容器环境 (见 app.py 的 #main-tabs) */
    #gradio-sim {{
        padding: 24px 32px;
        background: #F0F2F5;
        min-height: 100vh;
    }}
    /* 模拟快捷操作按钮 (三色渐变) */
    .mock-actions-row {{
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 16px; margin: 4px 0 20px;
    }}
    .mock-btn {{
        height: 58px; border-radius: 16px;
        font-size: 15px; font-weight: 600; color: #FFF;
        border: 1px solid rgba(255,255,255,0.08);
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; letter-spacing: 0.3px;
        box-shadow: 0 1px 0 rgba(255,255,255,0.12) inset, 0 10px 30px rgba(0,0,0,0.35);
    }}
    .mock-btn.blue   {{ background: linear-gradient(135deg, #4F8BFF 0%, #2763EA 100%); }}
    .mock-btn.pink   {{ background: linear-gradient(135deg, #FF5F8F 0%, #C73075 100%); }}
    .mock-btn.violet {{ background: linear-gradient(135deg, #A873F5 0%, #6E43D8 100%); }}
    .mock-refresh {{
        text-align: right; margin-top: 4px;
    }}
    .mock-refresh span {{
        display: inline-block; padding: 6px 14px; border-radius: 10px;
        background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.12);
        color: rgba(230,233,245,0.75); font-size: 12px;
    }}
</style>
</head>
<body>
<div id="gradio-sim">
  <div id="bento-dashboard-root" style="margin:0 !important; border-radius: 24px;">
    {stats}
    {alert}
    <div class="bento-dash">
      <div class="mock-actions-row">
        <div class="mock-btn blue">📄 上传简历</div>
        <div class="mock-btn pink">🚀 新建投递任务</div>
        <div class="mock-btn violet">📋 查看投递记录</div>
      </div>
    </div>
    {table}
    <div class="bento-dash">
      <div class="mock-refresh"><span>刷新数据</span></div>
    </div>
  </div>
</div>
</body>
</html>
"""


def main() -> None:
    out_dir = PROJECT_ROOT / "test_screenshots"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / "_dashboard_preview.html"
    png_path = out_dir / "dashboard_bento.png"

    html_path.write_text(build_preview_html(), encoding="utf-8")
    print(f"HTML written: {html_path}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(png_path), full_page=True)
        browser.close()

    print(f"Screenshot saved: {png_path}")


if __name__ == "__main__":
    main()
