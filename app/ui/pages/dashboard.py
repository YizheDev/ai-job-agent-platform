"""工作台 Dashboard 页面

数据概览卡片 → 风险提示 → 快捷操作 → 最近投递记录。
纯CSS渲染, 零图片, 企业级SaaS风格。
通过 login_state 获取 user_name 实现数据隔离。
"""

from __future__ import annotations

import html as html_mod
from datetime import datetime

import gradio as gr

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD

logger = get_logger(__name__)

_STATUS_MAP = {
    "pending": ("待投递", "tag-gray"),
    "confirmed": ("已确认", "tag-blue"),
    "delivering": ("投递中", "tag-orange"),
    "success": ("已投递", "tag-green"),
    "failed": ("投递失败", "tag-red"),
    "cancelled": ("已取消", "tag-gray"),
    "error": ("异常", "tag-red"),
}


def _render_data_cards(remaining: int, today: int, total: int, avg: float) -> str:
    """渲染四宫格数据卡片 HTML (含图标 + 渐变标识)"""
    return (
        '<div class="data-cards">'

        '<div class="data-card">'
        '<div class="dc-icon blue">📬</div>'
        '<div class="dc-label">今日可投递额度</div>'
        f'<div class="dc-value blue">{remaining}</div>'
        "</div>"

        '<div class="data-card">'
        '<div class="dc-icon orange">🚀</div>'
        '<div class="dc-label">今日已投递</div>'
        f'<div class="dc-value">{today}</div>'
        "</div>"

        '<div class="data-card">'
        '<div class="dc-icon gray">📊</div>'
        '<div class="dc-label">累计投递总数</div>'
        f'<div class="dc-value">{total}</div>'
        "</div>"

        '<div class="data-card">'
        '<div class="dc-icon green">⭐</div>'
        '<div class="dc-label">近7日平均匹配分</div>'
        f'<div class="dc-value green">{avg:.1f}</div>'
        "</div>"

        "</div>"
    )


def _render_risk_alert(msg: str) -> str:
    """渲染风险提示条 HTML"""
    if not msg:
        return ""
    return f'<div class="alert-bar">{msg}</div>'


def _render_recent_table(records: list) -> str:
    """渲染最近投递记录 HTML 表格 (含状态标签)"""
    header = (
        "<table class='custom-table'>"
        "<thead><tr>"
        "<th>公司</th><th>岗位</th><th>匹配分</th><th>投递时间</th><th>状态</th>"
        "</tr></thead><tbody>"
    )
    if not records:
        return (
            header
            + '<tr><td colspan="5" style="text-align:center;color:#86909C;'
            'padding:32px 0;">暂无投递记录</td></tr></tbody></table>'
        )

    rows = ""
    for r in records:
        label, cls = _STATUS_MAP.get(r[4], (r[4], "tag-gray"))
        rows += (
            f"<tr><td>{html_mod.escape(str(r[0]))}</td>"
            f"<td>{html_mod.escape(str(r[1]))}</td>"
            f"<td>{html_mod.escape(str(r[2]))}</td>"
            f"<td>{html_mod.escape(str(r[3]))}</td>"
            f'<td><span class="status-tag {cls}">{html_mod.escape(label)}</span></td></tr>'
        )
    return header + rows + "</tbody></table>"


def load_dashboard_data(user_name: str = ""):
    """加载工作台全部数据, 返回三段 HTML (供 app.py 调用)"""
    try:
        settings = get_settings()
        today_count = DeliveryRecordCRUD.get_today_count(user_name=user_name)
        total_count = DeliveryRecordCRUD.get_total_count(user_name=user_name)
        avg_score = DeliveryRecordCRUD.get_avg_score(7, user_name=user_name)
        remaining = max(0, settings.MAX_DAILY_DELIVERY - today_count)

        recent = DeliveryRecordCRUD.get_recent(5, user_name=user_name)
        table_rows = [
            [r["company"], r["position"], r["match_score"], r["create_time"], r["status"]]
            for r in recent
        ]

        hour = datetime.now().hour
        risk_parts: list[str] = []
        if today_count >= settings.MAX_DAILY_DELIVERY:
            risk_parts.append("⚠ 今日投递已达上限, 明日解锁")
        if not (settings.DELIVERY_START_HOUR <= hour < settings.DELIVERY_END_HOUR):
            risk_parts.append(
                f"⚠ 当前非投递时段, 建议在 "
                f"{settings.DELIVERY_START_HOUR}:00 - {settings.DELIVERY_END_HOUR}:00 投递"
            )
        risk_msg = " | ".join(risk_parts)

        return (
            _render_data_cards(remaining, today_count, total_count, avg_score),
            _render_risk_alert(risk_msg),
            _render_recent_table(table_rows),
        )
    except Exception as e:
        logger.error("加载工作台数据失败: %s", e)
        return (
            _render_data_cards(0, 0, 0, 0.0),
            f'<div class="alert-bar error">数据加载失败: {e}</div>',
            _render_recent_table([]),
        )


def create_dashboard_page(login_state):
    """创建工作台页面

    Returns:
        6-tuple: (btn_upload, btn_delivery, btn_records,
                  data_cards, risk_alert, recent_table)
    """
    gr.Markdown("## 工作台")

    init_cards = _render_data_cards(0, 0, 0, 0.0)
    init_alert = ""
    init_table = _render_recent_table([])

    data_cards = gr.HTML(value=init_cards)
    risk_alert = gr.HTML(value=init_alert)

    gr.Markdown("### 快捷操作")
    with gr.Row():
        btn_upload = gr.Button("📄 上传简历", variant="primary", size="lg")
        btn_delivery = gr.Button("🚀 新建投递任务", variant="secondary", size="lg")
        btn_records = gr.Button("📋 查看投递记录", variant="secondary", size="lg")

    gr.Markdown("### 最近投递记录")
    recent_table = gr.HTML(value=init_table)

    def _refresh(state):
        user_name = state.get("user_name", "") if state else ""
        return load_dashboard_data(user_name)

    refresh_btn = gr.Button("刷新数据", variant="secondary", size="sm")
    refresh_btn.click(
        fn=_refresh,
        inputs=[login_state],
        outputs=[data_cards, risk_alert, recent_table],
    )

    return btn_upload, btn_delivery, btn_records, data_cards, risk_alert, recent_table
