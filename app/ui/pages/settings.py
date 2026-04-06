"""System settings page."""

from __future__ import annotations

import gradio as gr

from app.core.config import get_settings, reload_settings, update_env_file
from app.core.logger import get_logger
from app.ui.view_model import get_ui_snapshot, invalidate_ui_snapshot
from app.utils.security_util import clear_cookie, wipe_all_data

logger = get_logger(__name__)

_USER_AGREEMENT = """## 用户使用须知

1. 本工具仅用于个人求职辅助，不代表任何招聘平台官方。
2. 用户需遵守招聘平台相关协议，不得用于批量恶意投递。
3. 用户需自行承担账号安全与平台风控风险。
4. 数据默认保存在本地环境，请自行做好备份。

## 免责声明

1. 本工具只提供技术辅助，不保证投递成功或账号绝对安全。
2. 平台策略变化可能导致功能波动，系统会逐步适配。
3. 所有投递行为均由用户发起并确认，最终结果取决于用户条件与招聘方决策。
"""


def _load_settings():
    """Load current settings."""
    try:
        settings = get_settings()
        return (
            settings.MAX_DAILY_DELIVERY,
            settings.MIN_DELAY_SECONDS,
            settings.MAX_DELAY_SECONDS,
            settings.DELIVERY_START_HOUR,
            settings.DELIVERY_END_HOUR,
            settings.MATCH_THRESHOLD,
            settings.LLM_API_KEY[:8] + "..." if len(settings.LLM_API_KEY) > 8 else settings.LLM_API_KEY,
            settings.LLM_BASE_URL,
            settings.LLM_MODEL,
        )
    except Exception:
        return 20, 2, 4, 9, 18, 70, "", "", ""


def _save_risk_settings(max_daily, min_delay, max_delay, start_hour, end_hour, threshold):
    """Persist risk-control settings."""
    try:
        update_env_file(
            {
                "MAX_DAILY_DELIVERY": str(int(max_daily)),
                "MIN_DELAY_SECONDS": str(int(min_delay)),
                "MAX_DELAY_SECONDS": str(int(max_delay)),
                "DELIVERY_START_HOUR": str(int(start_hour)),
                "DELIVERY_END_HOUR": str(int(end_hour)),
                "MATCH_THRESHOLD": str(int(threshold)),
            }
        )
        reload_settings()
        invalidate_ui_snapshot()
        logger.info("风控设置已保存")
        return "风控设置保存成功。"
    except Exception as exc:
        return f"保存失败：{exc}"


def _save_api_settings(api_key, base_url, model):
    """Persist LLM API settings."""
    try:
        update_env_file(
            {
                "LLM_API_KEY": api_key,
                "LLM_BASE_URL": base_url,
                "LLM_MODEL": model,
            }
        )
        reload_settings()
        logger.info("API 设置已保存")
        return "API 配置保存成功，已立即生效。"
    except Exception as exc:
        return f"保存失败：{exc}"


def _do_logout():
    """Clear login cookies."""
    clear_cookie()
    return "已退出登录，Cookie 已清除。"


def _do_wipe():
    """Wipe all local data."""
    ok = wipe_all_data()
    invalidate_ui_snapshot()
    return "所有本地数据已清除。" if ok else "数据清除失败。"


def _render_settings_metrics() -> str:
    settings = get_settings()
    return f"""
    <div class="settings-grid">
        <div class="metric-pill-soft"><div class="label">每日上限</div><div class="value">{settings.MAX_DAILY_DELIVERY}</div></div>
        <div class="metric-pill-soft"><div class="label">投递窗口</div><div class="value">{settings.DELIVERY_START_HOUR}:00-{settings.DELIVERY_END_HOUR}:00</div></div>
        <div class="metric-pill-soft"><div class="label">模型</div><div class="value" style="font-size:18px;">{settings.LLM_MODEL}</div></div>
    </div>
    """


def _save_risk_settings_ui(max_daily, min_delay, max_delay, start_hour, end_hour, threshold):
    return _save_risk_settings(max_daily, min_delay, max_delay, start_hour, end_hour, threshold), _render_settings_metrics()


def _save_api_settings_ui(api_key, base_url, model):
    return _save_api_settings(api_key, base_url, model), _render_settings_metrics()


def create_settings_page():
    """Create the system settings page."""
    settings = get_settings()
    snapshot = get_ui_snapshot()

    gr.HTML(
        f"""
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">管理账号状态、投递风控、模型 API、隐私策略和使用协议。敏感数据默认只保存在本地环境中。</div>
                    <div class="page-dock">
                        <span class="dock-pill"><strong>简历资产</strong> {snapshot['resume_total']} 份</span>
                        <span class="dock-pill"><strong>投递记录</strong> {snapshot['delivery_total']} 条</span>
                        <span class="dock-pill"><strong>投递窗口</strong> {snapshot['window_label']}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    metrics_html = gr.HTML(value=f'<div class="page-shell page-stack">{_render_settings_metrics()}</div>')
    settings_msg = gr.Textbox(label="操作结果", interactive=False, max_lines=1, elem_classes=["page-stack"])

    with gr.Row(elem_classes=["page-row", "workspace-grid"]):
        with gr.Column(elem_classes=["workspace-column", "sticky-pane"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section-tight"]):
                gr.HTML(
                    """
                    <div class="eyebrow">安全优先</div>
                    <div class="stitch-panel-title">账号安全与隐私</div>
                    <div class="stitch-muted">建议先完成浏览器登录、频率限制和 API 配置，再开始投递流程。涉及账号、Cookie 与本地数据清理的操作都不会静默执行。</div>
                    """
                )

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="eyebrow">账号</div>
                    <div class="stitch-panel-title">招聘平台登录状态</div>
                    <div class="stitch-muted">退出登录会清除本地 Cookie，重新登录需要再次扫码。</div>
                    """
                )
                with gr.Row():
                    gr.Button("退出登录", variant="stop").click(fn=_do_logout, outputs=[settings_msg])
                    gr.Button("重新登录（扫码）", variant="primary")

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="eyebrow">使用协议</div>
                    <div class="stitch-panel-title">条款与说明</div>
                    """
                )
                gr.Markdown(_USER_AGREEMENT)

        with gr.Column(elem_classes=["workspace-column"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">风控参数</div>
                            <div class="stitch-panel-title">执行阈值</div>
                        </div>
                        <span class="stitch-chip">Safe Mode</span>
                    </div>
                    """
                )
                max_daily = gr.Slider(1, 50, value=settings.MAX_DAILY_DELIVERY, step=1, label="每日最大投递量")
                with gr.Row():
                    min_delay = gr.Slider(1, 10, value=settings.MIN_DELAY_SECONDS, step=1, label="最小延时（秒）")
                    max_delay = gr.Slider(1, 10, value=settings.MAX_DELAY_SECONDS, step=1, label="最大延时（秒）")
                with gr.Row():
                    start_hour = gr.Slider(0, 23, value=settings.DELIVERY_START_HOUR, step=1, label="投递开始时段")
                    end_hour = gr.Slider(0, 23, value=settings.DELIVERY_END_HOUR, step=1, label="投递结束时段")
                threshold = gr.Slider(0, 100, value=settings.MATCH_THRESHOLD, step=5, label="最低匹配分阈值")
                gr.Button("保存风控设置", variant="primary").click(
                    fn=_save_risk_settings_ui,
                    inputs=[max_daily, min_delay, max_delay, start_hour, end_hour, threshold],
                    outputs=[settings_msg, metrics_html],
                )

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">模型配置</div>
                            <div class="stitch-panel-title">大模型 API</div>
                        </div>
                        <span class="stitch-chip">Local Only</span>
                    </div>
                    """
                )
                api_key = gr.Textbox(label="API Key", type="password", value=settings.LLM_API_KEY, placeholder="sk-...")
                base_url = gr.Textbox(label="API Base URL", value=settings.LLM_BASE_URL, placeholder="https://api.openai.com/v1")
                model = gr.Dropdown(
                    label="模型名称",
                    choices=[
                        "deepseek-chat",
                        "deepseek-reasoner",
                        "gpt-4o",
                        "gpt-4o-mini",
                        "qwen-plus",
                        "qwen-max",
                        "glm-4",
                    ],
                    value=settings.LLM_MODEL,
                    allow_custom_value=True,
                )
                gr.Button("保存 API 设置", variant="primary").click(
                    fn=_save_api_settings_ui,
                    inputs=[api_key, base_url, model],
                    outputs=[settings_msg, metrics_html],
                )

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="eyebrow">数据</div>
                    <div class="stitch-panel-title">本地数据清理</div>
                    <div class="stitch-muted">清理操作不可恢复，请确认已备份需要的数据。</div>
                    """
                )
                gr.Button("清理全部本地数据", variant="stop").click(fn=_do_wipe, outputs=[settings_msg])
