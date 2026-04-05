"""投递记录与数据统计页面

投递记录列表、筛选排序、纯CSS柱状图/环形图、Excel 导出。
通过 login_state 实现数据隔离。
"""

from __future__ import annotations

import math

import gradio as gr

from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.utils.file_util import export_delivery_records_excel

logger = get_logger(__name__)

_STATUS_OPTIONS = [
    "全部", "pending", "confirmed", "delivering",
    "success", "failed", "cancelled", "error",
]
_TIME_OPTIONS = ["全部", "今日", "近7日", "近30日"]


def _render_bar_chart(daily_data: list) -> str:
    """渲染纯CSS柱状图 (近7日投递量)"""
    if not daily_data:
        return (
            '<div style="color:#86909C;text-align:center;padding:40px 0;">'
            "暂无投递数据</div>"
        )

    max_count = max((d["count"] for d in daily_data), default=1) or 1
    bars = ""
    for d in daily_data:
        pct = d["count"] / max_count * 100
        label = d["date"][-5:]  # MM-DD
        bars += (
            f'<div class="bar-item">'
            f'<div class="bv">{d["count"]}</div>'
            f'<div class="bar" style="height:{max(pct, 3):.0f}%"></div>'
            f'<div class="bl">{label}</div>'
            f"</div>"
        )
    return f'<div class="bar-chart">{bars}</div>'


def _render_dist_ring(dist: dict) -> str:
    """渲染带动画的 SVG 环形图 (匹配分分布)"""
    high = dist.get("high", 0)
    medium = dist.get("medium", 0)
    low = dist.get("low", 0)
    total = high + medium + low

    if total == 0:
        return (
            '<div style="color:var(--c-text-3,#86909C);text-align:center;'
            'padding:48px 0;font-size:14px;">'
            "📊 暂无分布数据</div>"
        )

    r = 54
    circumference = 2 * math.pi * r
    segments = [
        (high / total, "#00B42A"),
        (medium / total, "#FF7D00"),
        (low / total, "#F53F3F"),
    ]

    arcs = ""
    offset = 0
    for ratio, color in segments:
        length = circumference * ratio
        arcs += (
            f'<circle cx="70" cy="70" r="{r}" fill="none" '
            f'stroke="{color}" stroke-width="12" '
            f'stroke-dasharray="{length:.1f} {circumference - length:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" '
            f'stroke-linecap="round" class="animated-ring" '
            f'style="transform:rotate(-90deg);transform-origin:70px 70px;"/>'
        )
        offset += length

    legend = (
        '<div style="margin-top:20px;">'
        f'<div class="legend-row"><div class="legend-dot" style="background:#00B42A"></div>'
        f'高匹配 (≥85): <strong>{high}</strong> 条</div>'
        f'<div class="legend-row"><div class="legend-dot" style="background:#FF7D00"></div>'
        f'一般匹配 (60-84): <strong>{medium}</strong> 条</div>'
        f'<div class="legend-row"><div class="legend-dot" style="background:#F53F3F"></div>'
        f'低匹配 (<60): <strong>{low}</strong> 条</div>'
        "</div>"
    )

    return (
        '<div style="text-align:center;padding:8px 0;">'
        '<svg width="140" height="140" viewBox="0 0 140 140">'
        f'<circle cx="70" cy="70" r="{r}" fill="none" stroke="#F2F3F5" stroke-width="12"/>'
        f"{arcs}"
        "</svg>"
        f'<div style="font-size:14px;color:var(--c-text-1,#1D2129);font-weight:700;'
        f'margin-top:12px;letter-spacing:-0.3px;">'
        f"共 {total} 条</div>"
        f"{legend}"
        "</div>"
    )


def create_records_page(login_state):
    """创建投递记录与统计页面"""
    gr.Markdown("## 投递记录与数据统计")

    # 筛选栏
    with gr.Row():
        time_filter = gr.Dropdown(
            choices=_TIME_OPTIONS, value="全部", label="时间范围", scale=1
        )
        status_filter = gr.Dropdown(
            choices=_STATUS_OPTIONS, value="全部", label="投递状态", scale=1
        )
        filter_btn = gr.Button("筛选", variant="primary", scale=0)
        export_btn = gr.Button("导出 Excel", variant="secondary", scale=0)

    # 投递表格
    records_table = gr.Dataframe(
        headers=["ID", "公司", "岗位", "匹配分", "投递时间", "状态", "备注"],
        datatype=["number", "str", "str", "number", "str", "str", "str"],
        value=[],
        interactive=False,
    )
    export_msg = gr.Textbox(label="操作结果", interactive=False, max_lines=1)

    # 记录操作
    with gr.Row():
        record_id_input = gr.Textbox(
            label="记录 ID (点击表格行自动填入)",
            placeholder="点击上方表格行选中",
            scale=2,
        )
        status_select = gr.Dropdown(
            choices=["success", "failed", "cancelled", "error"],
            label="新状态",
            scale=2,
        )
        update_btn = gr.Button("更新状态", variant="secondary", scale=1)
        delete_btn = gr.Button("删除", variant="stop", scale=1)

    gr.Markdown("---")
    gr.Markdown("### 数据统计")

    with gr.Row(equal_height=True):
        with gr.Column():
            gr.Markdown("**近7日投递量**")
            daily_chart = gr.HTML(value=_render_bar_chart([]))
        with gr.Column():
            gr.Markdown("**匹配分分布**")
            dist_chart = gr.HTML(value=_render_dist_ring({}))

    summary_text = gr.Markdown(value="")
    stats_btn = gr.Button("刷新统计", variant="secondary", size="sm")

    # ---- 回调 ----

    def _load_records(time_f, status_f, state):
        user_name = state.get("user_name", "") if state else ""
        try:
            days = {"今日": 1, "近7日": 7, "近30日": 30}.get(time_f)
            status = None if status_f == "全部" else status_f
            records = DeliveryRecordCRUD.get_all(
                status=status, days=days, limit=200, user_name=user_name
            )
            return [
                [
                    r["id"], r["company"], r["position"], r["match_score"],
                    r["create_time"], r["status"], r.get("error_msg", ""),
                ]
                for r in records
            ]
        except Exception as e:
            logger.error("加载投递记录失败: %s", e)
            return []

    def _load_stats(state):
        user_name = state.get("user_name", "") if state else ""
        try:
            daily = DeliveryRecordCRUD.get_daily_stats(7, user_name=user_name)
            dist = DeliveryRecordCRUD.get_score_distribution(user_name=user_name)
            total = DeliveryRecordCRUD.get_total_count(user_name=user_name)
            avg = DeliveryRecordCRUD.get_avg_score(7, user_name=user_name)
            return (
                _render_bar_chart(daily),
                _render_dist_ring(dist),
                f"**累计投递**: {total} 条 | **近7日平均匹配分**: {avg}",
            )
        except Exception as e:
            return f'<div class="alert-bar error">统计加载失败: {e}</div>', "", ""

    def _export_records(time_f, status_f, state):
        user_name = state.get("user_name", "") if state else ""
        try:
            days = {"今日": 1, "近7日": 7, "近30日": 30}.get(time_f)
            status = None if status_f == "全部" else status_f
            records = DeliveryRecordCRUD.get_all(
                status=status, days=days, limit=1000, user_name=user_name
            )
            if not records:
                return "无投递记录可导出"
            path = export_delivery_records_excel(records)
            return f"✓ 导出成功: {path}"
        except Exception as e:
            return f"导出失败: {e}"

    def _update_status(rid_str, new_status):
        if not rid_str or not new_status:
            return "请输入记录 ID 和新状态"
        try:
            DeliveryRecordCRUD.update_status(int(rid_str), new_status)
            return f"✓ 状态已更新: ID {rid_str} → {new_status}"
        except Exception as e:
            return f"更新失败: {e}"

    def _delete_record(rid_str):
        if not rid_str:
            return "请输入记录 ID"
        try:
            DeliveryRecordCRUD.delete(int(rid_str))
            return "✓ 删除成功"
        except Exception as e:
            return f"删除失败: {e}"

    def _on_record_select(table_data, evt: gr.SelectData):
        try:
            row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            if hasattr(table_data, "iloc"):
                return str(table_data.iloc[row, 0])
            if isinstance(table_data, list) and 0 <= row < len(table_data):
                return str(table_data[row][0])
        except Exception:
            pass
        return ""

    # ---- 事件绑定 ----
    records_table.select(
        fn=_on_record_select,
        inputs=[records_table],
        outputs=[record_id_input],
    )
    filter_btn.click(
        fn=_load_records,
        inputs=[time_filter, status_filter, login_state],
        outputs=[records_table],
    )
    export_btn.click(
        fn=_export_records,
        inputs=[time_filter, status_filter, login_state],
        outputs=[export_msg],
    )
    update_btn.click(
        fn=_update_status,
        inputs=[record_id_input, status_select],
        outputs=[export_msg],
    )
    delete_btn.click(
        fn=_delete_record, inputs=[record_id_input], outputs=[export_msg]
    )
    stats_btn.click(
        fn=_load_stats,
        inputs=[login_state],
        outputs=[daily_chart, dist_chart, summary_text],
    )
