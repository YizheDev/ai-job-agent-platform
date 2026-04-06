"""Delivery records and analytics page."""

from __future__ import annotations

import math

import gradio as gr

from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.ui.view_model import (
    get_ui_snapshot,
    invalidate_ui_snapshot,
    render_empty_state,
    render_skeleton_card,
    tab_switch_js,
)
from app.utils.file_util import export_delivery_records_excel

logger = get_logger(__name__)

_STATUS_OPTIONS = ["全部", "pending", "confirmed", "delivering", "success", "failed", "cancelled", "error"]
_TIME_OPTIONS = ["全部", "今日", "近 7 日", "近 30 日"]


def _render_bar_chart(daily_data: list[dict]) -> str:
    if not daily_data:
        return render_empty_state(
            "暂无趋势数据",
            "当你开始产生投递记录后，这里会自动展示最近 7 日投递量变化。",
            "先创建任务并完成一次投递。",
            "GO",
        )

    max_count = max((item["count"] for item in daily_data), default=1) or 1
    bars = []
    for item in daily_data:
        pct = item["count"] / max_count * 100
        bars.append(
            f"""
            <div class="bar-item">
                <div class="bv">{item['count']}</div>
                <div class="bar" style="height:{max(pct, 3):.0f}%"></div>
                <div class="bl">{item['date'][-5:]}</div>
            </div>
            """
        )
    return f'<div class="bar-chart">{"".join(bars)}</div>'


def _render_dist_ring(dist: dict) -> str:
    high = dist.get("high", 0)
    medium = dist.get("medium", 0)
    low = dist.get("low", 0)
    total = high + medium + low
    if total == 0:
        return render_empty_state(
            "暂无分布数据",
            "匹配分分布会在有投递记录后更新，帮助你判断岗位质量。",
            "建议先在 JD 匹配页筛出高优先级岗位。",
            "AI",
        )

    radius = 50
    circumference = 2 * math.pi * radius
    segments = [(high / total, "#18B56A"), (medium / total, "#FF9A3C"), (low / total, "#E35D57")]
    arcs = []
    offset = 0.0
    for ratio, color in segments:
        length = circumference * ratio
        arcs.append(
            f'<circle cx="65" cy="65" r="{radius}" fill="none" stroke="{color}" stroke-width="14" '
            f'stroke-dasharray="{length:.1f} {circumference - length:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" style="transform:rotate(-90deg);transform-origin:65px 65px;"/>'
        )
        offset += length

    legend = (
        '<div style="margin-top:16px;">'
        f'<div class="legend-row"><div class="legend-dot" style="background:#18B56A"></div>高匹配（≥85） {high} 条</div>'
        f'<div class="legend-row"><div class="legend-dot" style="background:#FF9A3C"></div>中匹配（60-84） {medium} 条</div>'
        f'<div class="legend-row"><div class="legend-dot" style="background:#E35D57"></div>低匹配（<60） {low} 条</div>'
        "</div>"
    )
    return (
        '<div style="text-align:center;">'
        '<svg width="130" height="130" viewBox="0 0 130 130">'
        f'<circle cx="65" cy="65" r="{radius}" fill="none" stroke="#F2F3F5" stroke-width="14"/>'
        f"{''.join(arcs)}</svg>"
        f'<div style="font-size:13px;color:#1D2129;font-weight:700;margin-top:10px;">共 {total} 条记录</div>'
        f"{legend}</div>"
    )


def _load_records(time_filter, status_filter):
    """Load records with filters."""
    try:
        days = {"今日": 1, "近 7 日": 7, "近 30 日": 30}.get(time_filter)
        status = None if status_filter == "全部" else status_filter
        records = DeliveryRecordCRUD.get_all(status=status, days=days, limit=200)
        return [
            [
                row["id"],
                row["company"],
                row["position"],
                row["match_score"],
                row["create_time"],
                row["status"],
                row.get("error_msg", ""),
            ]
            for row in records
        ]
    except Exception as exc:
        logger.error("加载投递记录失败: %s", exc)
        return []


def _load_stats():
    """Load records analytics."""
    try:
        daily = DeliveryRecordCRUD.get_daily_stats(7)
        dist = DeliveryRecordCRUD.get_score_distribution()
        total = DeliveryRecordCRUD.get_total_count()
        avg = DeliveryRecordCRUD.get_avg_score(7)
        success = len(DeliveryRecordCRUD.get_all(status="success", limit=1000))
        summary = (
            f"**累计投递**：{total} 条  \n"
            f"**近 7 日平均匹配分**：{avg}  \n"
            f"**成功投递记录**：{success} 条"
        )
        return _render_bar_chart(daily), _render_dist_ring(dist), summary
    except Exception as exc:
        return f'<div class="alert-bar error">统计加载失败：{exc}</div>', "", ""


def _export_records(time_filter, status_filter):
    """Export records to Excel."""
    try:
        days = {"今日": 1, "近 7 日": 7, "近 30 日": 30}.get(time_filter)
        status = None if status_filter == "全部" else status_filter
        records = DeliveryRecordCRUD.get_all(status=status, days=days, limit=1000)
        if not records:
            return "没有可导出的投递记录。"
        path = export_delivery_records_excel(records)
        return f"导出成功：{path}"
    except Exception as exc:
        return f"导出失败：{exc}"


def _update_status(record_id_str, new_status):
    """Update one record status."""
    if not record_id_str or not new_status:
        return "请输入记录 ID 和新状态。"
    try:
        record_id = int(record_id_str)
        DeliveryRecordCRUD.update_status(record_id, new_status)
        invalidate_ui_snapshot()
        return f"状态已更新：ID {record_id} -> {new_status}"
    except Exception as exc:
        return f"更新失败：{exc}"


def _delete_record(record_id_str):
    """Delete one record."""
    if not record_id_str:
        return "请输入记录 ID。"
    try:
        DeliveryRecordCRUD.delete(int(record_id_str))
        invalidate_ui_snapshot()
        return "删除成功。"
    except Exception as exc:
        return f"删除失败：{exc}"


def _render_records_metrics() -> str:
    snapshot = get_ui_snapshot()
    active = snapshot["delivery_pending"] + snapshot["delivery_confirmed"]
    return f"""
    <div class="stitch-stats-4">
        <div class="metric-pill-soft"><div class="label">总记录</div><div class="value">{snapshot['delivery_total']}</div></div>
        <div class="metric-pill-soft"><div class="label">成功投递</div><div class="value">{snapshot['delivery_success']}</div></div>
        <div class="metric-pill-soft"><div class="label">活跃队列</div><div class="value">{active}</div></div>
        <div class="metric-pill-soft"><div class="label">平均分</div><div class="value">{snapshot['avg_score_7d']}</div></div>
    </div>
    """


def _stats_loading_state():
    skeleton = render_skeleton_card(lines=4, with_block=True)
    return skeleton, skeleton, "正在刷新统计面板..."


def create_records_page():
    """Create the records page."""
    initial_records = _load_records("全部", "全部")
    initial_bar, initial_ring, initial_summary = _load_stats()
    snapshot = get_ui_snapshot()

    gr.HTML(
        f"""
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">集中追踪岗位、匹配分、投递时间和状态变化。你可以在这里筛选记录、导出报表、维护状态，并观察近阶段投递质量。</div>
                    <div class="page-dock">
                        <span class="dock-pill"><strong>累计投递</strong> {snapshot['delivery_total']} 条</span>
                        <span class="dock-pill"><strong>成功记录</strong> {snapshot['delivery_success']} 条</span>
                        <span class="dock-pill"><strong>下一步</strong> 调整系统设置</span>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    metrics_html = gr.HTML(value=f'<div class="page-shell page-stack">{_render_records_metrics()}</div>')

    with gr.Row(elem_classes=["page-row", "workspace-grid"]):
        with gr.Column(elem_classes=["workspace-column", "sticky-pane"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">筛选与导出</div>
                            <div class="stitch-panel-title">过滤器</div>
                        </div>

                    </div>
                    """
                )
                with gr.Row():
                    time_filter = gr.Dropdown(choices=_TIME_OPTIONS, value="全部", label="时间范围")
                    status_filter = gr.Dropdown(choices=_STATUS_OPTIONS, value="全部", label="投递状态")
                with gr.Row():
                    filter_btn = gr.Button("筛选记录", variant="primary")
                    export_btn = gr.Button("导出 Excel", variant="secondary")
                export_msg = gr.Textbox(label="操作结果", interactive=False, max_lines=1)

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">状态维护</div>
                            <div class="stitch-panel-title">人工修正</div>
                        </div>

                    </div>
                    """
                )
                record_id_input = gr.Textbox(label="记录 ID", placeholder="输入记录 ID")
                status_select = gr.Dropdown(
                    choices=["success", "failed", "cancelled", "error"],
                    label="新状态",
                )
                with gr.Row():
                    update_btn = gr.Button("更新状态", variant="secondary")
                    delete_btn = gr.Button("删除记录", variant="stop")

        with gr.Column(elem_classes=["workspace-column"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">历史表格</div>
                            <div class="stitch-panel-title">投递历史</div>
                        </div>

                    </div>
                    """
                )
                records_table = gr.Dataframe(
                    headers=["ID", "公司", "岗位", "匹配分", "投递时间", "状态", "备注"],
                    datatype=["number", "str", "str", "number", "str", "str", "str"],
                    value=initial_records,
                    interactive=False,
                )

            with gr.Row(elem_classes=["workspace-grid-equal"]):
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML('<div class="eyebrow">投递趋势</div><div class="stitch-panel-title">近 7 日投递量</div>')
                        daily_chart = gr.HTML(value=initial_bar)
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML('<div class="eyebrow">分数分布</div><div class="stitch-panel-title">匹配分区间</div>')
                        dist_chart = gr.HTML(value=initial_ring)

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">统计摘要</div>
                            <div class="stitch-panel-title">阶段复盘</div>
                        </div>

                    </div>
                    """
                )
                summary_text = gr.Markdown(value=initial_summary)
                with gr.Row():
                    stats_btn = gr.Button("刷新统计", variant="secondary")
                    go_settings_btn = gr.Button("前往系统设置", variant="secondary")

    filter_btn.click(fn=_load_records, inputs=[time_filter, status_filter], outputs=[records_table])
    export_btn.click(fn=_export_records, inputs=[time_filter, status_filter], outputs=[export_msg])
    update_btn.click(fn=_update_status, inputs=[record_id_input, status_select], outputs=[export_msg])
    delete_btn.click(fn=_delete_record, inputs=[record_id_input], outputs=[export_msg])
    stats_btn.click(
        fn=_stats_loading_state,
        outputs=[daily_chart, dist_chart, summary_text],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=lambda: (*_load_stats(), f'<div class="page-shell page-stack">{_render_records_metrics()}</div>'),
        outputs=[daily_chart, dist_chart, summary_text, metrics_html],
        show_progress="minimal",
    )
    go_settings_btn.click(fn=None, js=tab_switch_js("系统设置"))
