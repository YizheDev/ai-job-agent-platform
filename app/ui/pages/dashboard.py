"""工作台 Dashboard 页面

展示核心数据概览、快捷操作入口、最近投递记录、风险提示。
"""

from __future__ import annotations

from datetime import datetime

import gradio as gr

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD

logger = get_logger(__name__)


def _load_dashboard_data():
    """加载工作台数据"""
    try:
        settings = get_settings()
        today_count = DeliveryRecordCRUD.get_today_count()
        total_count = DeliveryRecordCRUD.get_total_count()
        avg_score = DeliveryRecordCRUD.get_avg_score(7)
        remaining = max(0, settings.MAX_DAILY_DELIVERY - today_count)

        recent = DeliveryRecordCRUD.get_recent(5)
        table_data = [
            [r["company"], r["position"], r["match_score"], r["create_time"], r["status"]]
            for r in recent
        ]

        hour = datetime.now().hour
        risk_msg = ""
        if not (settings.DELIVERY_START_HOUR <= hour < settings.DELIVERY_END_HOUR):
            risk_msg = f"⚠ 当前非投递时段, 建议在 {settings.DELIVERY_START_HOUR}:00-{settings.DELIVERY_END_HOUR}:00 投递"
        if today_count >= settings.MAX_DAILY_DELIVERY:
            risk_msg = "⚠ 今日投递已达上限, 明日解锁"

        return remaining, today_count, total_count, avg_score, table_data, risk_msg
    except Exception as e:
        logger.error("加载工作台数据失败: %s", e)
        return 0, 0, 0, 0.0, [], f"数据加载失败: {e}"


def create_dashboard_page():
    """创建工作台页面组件"""
    gr.Markdown("## 工作台")

    with gr.Row(equal_height=True):
        remaining = gr.Number(value=20, label="今日可投递额度", interactive=False)
        today_count = gr.Number(value=0, label="今日已投递", interactive=False)
        total_count = gr.Number(value=0, label="累计投递总数", interactive=False)
        avg_score = gr.Number(value=0, label="近7日平均匹配分", interactive=False, precision=1)

    risk_alert = gr.Textbox(label="风险提示", value="", interactive=False, max_lines=1)

    gr.Markdown("### 快捷操作")
    with gr.Row():
        gr.Button("上传简历", variant="primary", size="lg")
        gr.Button("新建投递任务", variant="secondary", size="lg")
        gr.Button("查看投递记录", variant="secondary", size="lg")

    gr.Markdown("### 最近投递记录")
    recent_table = gr.Dataframe(
        headers=["公司", "岗位", "匹配分", "投递时间", "状态"],
        datatype=["str", "str", "number", "str", "str"],
        value=[],
        interactive=False,
        row_count=(5, "fixed"),
    )

    refresh_btn = gr.Button("刷新数据", variant="secondary", size="sm")
    refresh_btn.click(
        fn=_load_dashboard_data,
        outputs=[remaining, today_count, total_count, avg_score, recent_table, risk_alert],
    )

    # 页面首次加载时自动刷新 (通过 Blocks.load 触发, 在 app.py 中统一处理)
