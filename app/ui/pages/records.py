"""投递记录与数据统计页面

投递记录列表、筛选排序、数据统计图表、Excel 导出。
"""

from __future__ import annotations

import gradio as gr

from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.utils.file_util import export_delivery_records_excel

logger = get_logger(__name__)

_STATUS_OPTIONS = ["全部", "pending", "confirmed", "delivering", "success", "failed", "cancelled", "error"]
_TIME_OPTIONS = ["全部", "今日", "近7日", "近30日"]


def _load_records(time_filter, status_filter):
    """加载投递记录"""
    try:
        days = None
        if time_filter == "今日":
            days = 1
        elif time_filter == "近7日":
            days = 7
        elif time_filter == "近30日":
            days = 30

        status = None if status_filter == "全部" else status_filter
        records = DeliveryRecordCRUD.get_all(status=status, days=days, limit=200)
        table_data = [
            [r["id"], r["company"], r["position"], r["match_score"],
             r["create_time"], r["status"], r.get("error_msg", "")]
            for r in records
        ]
        return table_data
    except Exception as e:
        logger.error("加载投递记录失败: %s", e)
        return []


def _load_stats():
    """加载统计数据"""
    try:
        daily = DeliveryRecordCRUD.get_daily_stats(7)
        dist = DeliveryRecordCRUD.get_score_distribution()
        total = DeliveryRecordCRUD.get_total_count()
        avg = DeliveryRecordCRUD.get_avg_score(7)

        daily_text = "### 近7日投递量\n"
        if daily:
            for d in daily:
                bar = "█" * d["count"]
                daily_text += f"- {d['date']}: {bar} ({d['count']})\n"
        else:
            daily_text += "暂无数据\n"

        dist_text = "### 匹配分分布\n"
        dist_text += f"- 🟢 高匹配 (≥85): {dist.get('high', 0)} 条\n"
        dist_text += f"- 🟡 一般匹配 (60-84): {dist.get('medium', 0)} 条\n"
        dist_text += f"- 🔴 低匹配 (<60): {dist.get('low', 0)} 条\n"

        summary = f"**累计投递**: {total} 条 | **近7日平均匹配分**: {avg}"
        return daily_text, dist_text, summary
    except Exception as e:
        return f"统计加载失败: {e}", "", ""


def _export_records(time_filter, status_filter):
    """导出投递记录为 Excel"""
    try:
        days = {"今日": 1, "近7日": 7, "近30日": 30}.get(time_filter)
        status = None if status_filter == "全部" else status_filter
        records = DeliveryRecordCRUD.get_all(status=status, days=days, limit=1000)
        if not records:
            return "无投递记录可导出"
        path = export_delivery_records_excel(records)
        return f"导出成功: {path}"
    except Exception as e:
        return f"导出失败: {e}"


def _update_status(record_id_str, new_status):
    """更新投递状态"""
    if not record_id_str or not new_status:
        return "请输入记录 ID 和新状态"
    try:
        record_id = int(record_id_str)
        DeliveryRecordCRUD.update_status(record_id, new_status)
        return f"状态已更新: ID {record_id} → {new_status}"
    except Exception as e:
        return f"更新失败: {e}"


def _delete_record(record_id_str):
    """删除投递记录"""
    if not record_id_str:
        return "请输入记录 ID"
    try:
        DeliveryRecordCRUD.delete(int(record_id_str))
        return "删除成功"
    except Exception as e:
        return f"删除失败: {e}"


def create_records_page():
    """创建投递记录与统计页面"""
    gr.Markdown("## 投递记录与数据统计")

    with gr.Row():
        time_filter = gr.Dropdown(choices=_TIME_OPTIONS, value="全部", label="时间范围", scale=1)
        status_filter = gr.Dropdown(choices=_STATUS_OPTIONS, value="全部", label="投递状态", scale=1)
        filter_btn = gr.Button("筛选", variant="primary", scale=0)
        export_btn = gr.Button("导出 Excel", variant="secondary", scale=0)

    records_table = gr.Dataframe(
        headers=["ID", "公司", "岗位", "匹配分", "投递时间", "状态", "备注"],
        datatype=["number", "str", "str", "number", "str", "str", "str"],
        value=[],
        interactive=False,
    )
    export_msg = gr.Textbox(label="操作结果", interactive=False, max_lines=1)

    with gr.Row():
        record_id_input = gr.Textbox(label="记录 ID", placeholder="输入 ID", scale=1)
        status_select = gr.Dropdown(
            choices=["success", "failed", "cancelled", "error"],
            label="新状态", scale=1,
        )
        update_btn = gr.Button("更新状态", scale=0)
        delete_btn = gr.Button("删除", variant="stop", scale=0)

    gr.Markdown("---")
    with gr.Row():
        with gr.Column():
            daily_stats = gr.Markdown(value="")
        with gr.Column():
            dist_stats = gr.Markdown(value="")
    summary_text = gr.Markdown(value="")
    stats_btn = gr.Button("刷新统计", variant="secondary", size="sm")

    filter_btn.click(fn=_load_records, inputs=[time_filter, status_filter], outputs=[records_table])
    export_btn.click(fn=_export_records, inputs=[time_filter, status_filter], outputs=[export_msg])
    update_btn.click(fn=_update_status, inputs=[record_id_input, status_select], outputs=[export_msg])
    delete_btn.click(fn=_delete_record, inputs=[record_id_input], outputs=[export_msg])
    stats_btn.click(fn=_load_stats, outputs=[daily_stats, dist_stats, summary_text])
