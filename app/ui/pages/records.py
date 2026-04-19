"""投递记录与数据统计页面 — Bento 玻璃拟态风

布局:
┌─ 页头: 图标 + 标题 + 副标题
├─ 筛选 & 导出卡: 时间范围 + 状态 + 筛选 + 导出 Excel
├─ 操作结果状态条 (HTML 富化)
├─ 记录列表卡: Dataframe
├─ 批量操作卡: 记录 ID + 新状态 + 更新 / 删除
└─ 数据统计卡: 柱状图 + 环形图 + 汇总数字

对外接口保持: create_records_page(login_state)
"""

from __future__ import annotations

import html as html_mod
import math

import gradio as gr

from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.utils.file_util import export_delivery_records_excel

logger = get_logger(__name__)

_STATUS_LABEL = {
    "pending": "待投递",
    "confirmed": "已确认",
    "delivering": "投递中",
    "success": "已投递",
    "failed": "投递失败",
    "cancelled": "已取消",
    "error": "异常",
}
_LABEL_TO_STATUS = {v: k for k, v in _STATUS_LABEL.items()}

_STATUS_OPTIONS = ["全部"] + list(_STATUS_LABEL.values())
_UPDATE_STATUS_OPTIONS = ["已投递", "投递失败", "已取消", "异常"]
_TIME_OPTIONS = ["全部", "今日", "近7日", "近30日"]


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


def _zh_status(en: str) -> str:
    return _STATUS_LABEL.get(en, en)


def _en_status(zh_or_en: str) -> str:
    if not zh_or_en:
        return ""
    return _LABEL_TO_STATUS.get(zh_or_en, zh_or_en)


# ------------------------------------------------------------------
# HTML renderers
# ------------------------------------------------------------------

def _render_header_html() -> str:
    return (
        '<div class="rc-root">'
        '  <div class="rc-head">'
        '    <div class="rc-head-icon">'
        '      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>'
        '        <polyline points="14 2 14 8 20 8"></polyline>'
        '        <line x1="16" y1="13" x2="8" y2="13"></line>'
        '        <line x1="16" y1="17" x2="8" y2="17"></line>'
        '        <polyline points="10 9 9 9 8 9"></polyline>'
        '      </svg>'
        '    </div>'
        '    <div class="rc-head-text">'
        '      <div class="rc-head-title">投递记录 &amp; 数据统计</div>'
        '      <div class="rc-head-sub">筛选 · 排序 · 导出 Excel · 可视化图表</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _status_html(msg: str, kind: str = "info") -> str:
    dot_cls = {"info": "rcs-blue", "err": "rcs-red", "ok": "rcs-green", "warn": "rcs-orange"}.get(kind, "rcs-blue")
    return (
        '<div class="rc-root">'
        f'  <div class="rc-status"><span class="rcs-dot {dot_cls}"></span>'
        f'<span class="rcs-txt">{_safe(msg)}</span></div>'
        '</div>'
    )


def _empty_status_html() -> str:
    return (
        '<div class="rc-root">'
        '  <div class="rc-status rc-status-empty">'
        '    <span class="rcs-dot rcs-gray"></span>'
        '    <span class="rcs-txt">等待操作…</span>'
        '  </div>'
        '</div>'
    )


def _render_bar_chart(daily_data: list) -> str:
    """渲染纯CSS柱状图 (近7日投递量)"""
    if not daily_data:
        return (
            '<div class="rc-root">'
            '  <div class="rc-chart-empty">'
            '    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            '      <line x1="18" y1="20" x2="18" y2="10"></line>'
            '      <line x1="12" y1="20" x2="12" y2="4"></line>'
            '      <line x1="6" y1="20" x2="6" y2="14"></line>'
            '    </svg>'
            '    <div class="rc-chart-empty-txt">暂无投递数据</div>'
            '  </div>'
            '</div>'
        )

    max_count = max((d["count"] for d in daily_data), default=1) or 1
    bars = ""
    total_7d = 0
    for d in daily_data:
        count = int(d.get("count", 0))
        total_7d += count
        pct = count / max_count * 100
        label = d["date"][-5:]
        bars += (
            f'<div class="rc-bar-item">'
            f'  <div class="rc-bv">{count}</div>'
            f'  <div class="rc-bar-wrap">'
            f'    <div class="rc-bar" style="height:{max(pct, 4):.0f}%"></div>'
            f'  </div>'
            f'  <div class="rc-bl">{_safe(label)}</div>'
            f"</div>"
        )
    return (
        '<div class="rc-root">'
        '  <div class="rc-bar-chart">'
        f'    <div class="rc-bar-sum">近 7 日合计 <b>{total_7d}</b> 次</div>'
        f'    <div class="rc-bar-grid">{bars}</div>'
        '  </div>'
        '</div>'
    )


def _render_dist_ring(dist: dict) -> str:
    """渲染带动画的 SVG 环形图 (匹配分分布)"""
    high = int(dist.get("high", 0))
    medium = int(dist.get("medium", 0))
    low = int(dist.get("low", 0))
    total = high + medium + low

    if total == 0:
        return (
            '<div class="rc-root">'
            '  <div class="rc-chart-empty">'
            '    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            '      <circle cx="12" cy="12" r="10"></circle>'
            '      <path d="M12 2a10 10 0 0 1 10 10"></path>'
            '    </svg>'
            '    <div class="rc-chart-empty-txt">暂无分布数据</div>'
            '  </div>'
            '</div>'
        )

    r = 54
    circumference = 2 * math.pi * r
    segments = [
        ("high", high / total, "#34D399", "rgba(52,211,153,0.55)"),
        ("medium", medium / total, "#FB923C", "rgba(251,146,60,0.55)"),
        ("low", low / total, "#F87171", "rgba(248,113,113,0.55)"),
    ]

    arcs = ""
    offset = 0
    for _, ratio, color, _shadow in segments:
        length = circumference * ratio
        arcs += (
            f'<circle cx="70" cy="70" r="{r}" fill="none" '
            f'stroke="{color}" stroke-width="12" '
            f'stroke-dasharray="{length:.1f} {circumference - length:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" '
            f'stroke-linecap="round" class="rc-ring-seg" '
            f'style="transform:rotate(-90deg);transform-origin:70px 70px;'
            f'filter:drop-shadow(0 0 6px {color}66);"/>'
        )
        offset += length

    legend_rows = (
        ("#34D399", "高匹配 (≥85)", high, total),
        ("#FB923C", "一般 (60-84)", medium, total),
        ("#F87171", "低 (<60)", low, total),
    )
    legend_html = "".join(
        f'<div class="rc-legend-row">'
        f'  <div class="rc-legend-dot" style="background:{c};'
        f'  box-shadow:0 0 8px {c}99;"></div>'
        f'  <div class="rc-legend-k">{_safe(label)}</div>'
        f'  <div class="rc-legend-v"><b>{n}</b><span> / {t}</span></div>'
        f'</div>'
        for c, label, n, t in legend_rows
    )

    return (
        '<div class="rc-root">'
        '  <div class="rc-ring-card">'
        '    <div class="rc-ring-svg-wrap">'
        '      <svg width="140" height="140" viewBox="0 0 140 140">'
        f'        <circle cx="70" cy="70" r="{r}" fill="none" '
        '          stroke="rgba(255,255,255,0.06)" stroke-width="12"/>'
        f'        {arcs}'
        '      </svg>'
        '      <div class="rc-ring-center">'
        f'        <div class="rc-ring-num">{total}</div>'
        '        <div class="rc-ring-lbl">总条数</div>'
        '      </div>'
        '    </div>'
        f'    <div class="rc-legend">{legend_html}</div>'
        '  </div>'
        '</div>'
    )


def _render_summary_html(total: int, avg: float, last_7d_count: int = 0) -> str:
    """累计投递 + 7日均分 + 近 7 日投递量 — 3 块数字墙."""
    avg_safe = f"{avg:.1f}" if isinstance(avg, (int, float)) and avg > 0 else "0"
    return (
        '<div class="rc-root">'
        '  <div class="rc-kpi">'
        '    <div class="rc-kpi-box rc-kpi-blue">'
        '      <div class="rc-kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>'
        '          <polyline points="17 8 12 3 7 8"></polyline>'
        '          <line x1="12" y1="3" x2="12" y2="15"></line>'
        '        </svg>'
        '      </div>'
        f'      <div class="rc-kpi-num">{total}</div>'
        '      <div class="rc-kpi-lbl">累计投递</div>'
        '    </div>'
        '    <div class="rc-kpi-box rc-kpi-green">'
        '      <div class="rc-kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>'
        '        </svg>'
        '      </div>'
        f'      <div class="rc-kpi-num">{avg_safe}</div>'
        '      <div class="rc-kpi-lbl">近 7 日均分</div>'
        '    </div>'
        '    <div class="rc-kpi-box rc-kpi-violet">'
        '      <div class="rc-kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>'
        '        </svg>'
        '      </div>'
        f'      <div class="rc-kpi-num">{last_7d_count}</div>'
        '      <div class="rc-kpi-lbl">近 7 日投递</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


# ------------------------------------------------------------------
# Page builder
# ------------------------------------------------------------------

def create_records_page(login_state):
    """创建投递记录与统计页面 (Bento 玻璃风)"""
    gr.HTML(_RC_STYLE)

    with gr.Column(elem_id="rc-page-root", elem_classes=["rc-scope"]):
        gr.HTML(_render_header_html())

        # ============ 筛选 & 导出卡 ============
        with gr.Column(elem_classes=["rc-card", "rc-card-filter"]):
            gr.HTML(
                '<div class="rc-card-head">'
                '  <div class="rc-ch-icon rc-ch-blue">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>'
                '    </svg>'
                '  </div>'
                '  <div class="rc-ch-title">筛选 &amp; 导出</div>'
                '  <div class="rc-ch-sub">按时间范围 / 投递状态筛选 · 一键导出 Excel</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["rc-filter-row"]):
                time_filter = gr.Dropdown(
                    choices=_TIME_OPTIONS, value="全部", label="时间范围",
                    scale=2, elem_classes=["rc-input-field"],
                )
                status_filter = gr.Dropdown(
                    choices=_STATUS_OPTIONS, value="全部", label="投递状态",
                    scale=2, elem_classes=["rc-input-field"],
                )
                filter_btn = gr.Button(
                    "筛选", variant="primary", scale=1,
                    elem_classes=["rc-btn", "rc-btn-primary"],
                )
                export_btn = gr.Button(
                    "导出 Excel", variant="secondary", scale=1,
                    elem_classes=["rc-btn", "rc-btn-info"],
                )

        # ============ 操作结果状态条 ============
        export_msg = gr.HTML(value=_empty_status_html(), elem_id="rc-status-slot")

        # ============ 记录列表卡 ============
        with gr.Column(elem_classes=["rc-card", "rc-card-table"]):
            gr.HTML(
                '<div class="rc-card-head">'
                '  <div class="rc-ch-icon rc-ch-violet">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <line x1="8" y1="6" x2="21" y2="6"></line>'
                '      <line x1="8" y1="12" x2="21" y2="12"></line>'
                '      <line x1="8" y1="18" x2="21" y2="18"></line>'
                '      <line x1="3" y1="6" x2="3.01" y2="6"></line>'
                '      <line x1="3" y1="12" x2="3.01" y2="12"></line>'
                '      <line x1="3" y1="18" x2="3.01" y2="18"></line>'
                '    </svg>'
                '  </div>'
                '  <div class="rc-ch-title">记录列表</div>'
                '  <div class="rc-ch-sub">点击行选中记录, 可在下方更新状态或删除</div>'
                '</div>'
                '<div class="rc-table-hint" aria-hidden="true">'
                '  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
                '    <polyline points="9 6 15 12 9 18"></polyline>'
                '  </svg>'
                '  <span>表格可左右滑动查看完整字段</span>'
                '</div>'
            )
            records_table = gr.Dataframe(
                headers=["ID", "公司", "岗位", "匹配分", "投递时间", "状态", "备注"],
                datatype=["number", "str", "str", "number", "str", "str", "str"],
                value=[],
                interactive=False,
                elem_classes=["rc-table"],
            )

        # ============ 批量操作卡 ============
        with gr.Column(elem_classes=["rc-card", "rc-card-ops"]):
            gr.HTML(
                '<div class="rc-card-head">'
                '  <div class="rc-ch-icon rc-ch-pink">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>'
                '      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>'
                '    </svg>'
                '  </div>'
                '  <div class="rc-ch-title">记录操作</div>'
                '  <div class="rc-ch-sub">调整状态 / 删除单条记录</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["rc-ops-row"]):
                record_id_input = gr.Textbox(
                    label="记录 ID (点击表格行自动填入)",
                    placeholder="点击上方表格行选中",
                    scale=3, elem_classes=["rc-input-field"],
                )
                status_select = gr.Dropdown(
                    choices=_UPDATE_STATUS_OPTIONS,
                    label="新状态",
                    scale=3, elem_classes=["rc-input-field"],
                )
                update_btn = gr.Button(
                    "更新状态", variant="secondary", scale=1,
                    elem_classes=["rc-btn", "rc-btn-info"],
                )
                delete_btn = gr.Button(
                    "删除", variant="stop", scale=1,
                    elem_classes=["rc-btn", "rc-btn-danger"],
                )

        # ============ 数据统计卡 ============
        with gr.Column(elem_classes=["rc-card", "rc-card-stats"]):
            gr.HTML(
                '<div class="rc-card-head">'
                '  <div class="rc-ch-icon rc-ch-green">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <line x1="18" y1="20" x2="18" y2="10"></line>'
                '      <line x1="12" y1="20" x2="12" y2="4"></line>'
                '      <line x1="6" y1="20" x2="6" y2="14"></line>'
                '    </svg>'
                '  </div>'
                '  <div class="rc-ch-title">数据统计</div>'
                '  <div class="rc-ch-sub">近 7 日投递趋势 · 匹配分分布 · 核心指标</div>'
                '</div>'
            )
            stats_btn = gr.Button(
                "⟳  刷新统计", variant="secondary", size="sm",
                elem_classes=["rc-stats-action-btn"],
            )

            summary_slot = gr.HTML(value=_render_summary_html(0, 0.0, 0))

            with gr.Row(equal_height=True, elem_classes=["rc-stats-row"]):
                with gr.Column(elem_classes=["rc-stats-col"]):
                    gr.HTML(
                        '<div class="rc-subtitle">'
                        '  <span class="rc-subtitle-dot" style="background:#8DBBFF;"></span>'
                        '  近 7 日投递量'
                        '</div>'
                    )
                    daily_chart = gr.HTML(value=_render_bar_chart([]))
                with gr.Column(elem_classes=["rc-stats-col"]):
                    gr.HTML(
                        '<div class="rc-subtitle">'
                        '  <span class="rc-subtitle-dot" style="background:#34D399;"></span>'
                        '  匹配分分布'
                        '</div>'
                    )
                    dist_chart = gr.HTML(value=_render_dist_ring({}))

    # ==================== Callbacks (签名保持) ====================

    def _load_records(time_f, status_f, state):
        user_name = state.get("user_name", "") if state else ""
        try:
            days = {"今日": 1, "近7日": 7, "近30日": 30}.get(time_f)
            status = None if status_f == "全部" else _en_status(status_f)
            records = DeliveryRecordCRUD.get_all(
                status=status, days=days, limit=200, user_name=user_name
            )
            return [
                [
                    r["id"], r["company"], r["position"], r["match_score"],
                    r["create_time"], _zh_status(r["status"]), r.get("error_msg", ""),
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
            delta = sum(int(d.get("count", 0)) for d in (daily or []))
            return (
                _render_bar_chart(daily),
                _render_dist_ring(dist),
                _render_summary_html(total, float(avg or 0), delta),
            )
        except Exception as e:
            logger.error("统计加载失败: %s", e)
            return (
                _render_bar_chart([]),
                _render_dist_ring({}),
                _render_summary_html(0, 0.0, 0),
            )

    def _export_records(time_f, status_f, state):
        user_name = state.get("user_name", "") if state else ""
        try:
            days = {"今日": 1, "近7日": 7, "近30日": 30}.get(time_f)
            status = None if status_f == "全部" else _en_status(status_f)
            records = DeliveryRecordCRUD.get_all(
                status=status, days=days, limit=1000, user_name=user_name
            )
            if not records:
                return _status_html("无投递记录可导出", "warn")
            path = export_delivery_records_excel(records)
            return _status_html(f"导出成功: {path}", "ok")
        except Exception as e:
            return _status_html(f"导出失败: {e}", "err")

    def _update_status(rid_str, new_status, time_f, status_f, state):
        user_name = state.get("user_name", "") if state else ""
        if not rid_str or not new_status:
            return (
                _status_html("请输入记录 ID 和新状态", "err"),
                _load_records(time_f, status_f, state),
            )
        try:
            new_status_en = _en_status(new_status)
            ok = DeliveryRecordCRUD.update_status(int(rid_str), new_status_en, user_name=user_name)
            if ok:
                return (
                    _status_html(f"状态已更新: ID {rid_str} → {new_status}", "ok"),
                    _load_records(time_f, status_f, state),
                )
            return (
                _status_html("记录不存在或无权操作", "warn"),
                _load_records(time_f, status_f, state),
            )
        except Exception as e:
            return (
                _status_html(f"更新失败: {e}", "err"),
                _load_records(time_f, status_f, state),
            )

    def _delete_record(rid_str, time_f, status_f, state):
        user_name = state.get("user_name", "") if state else ""
        if not rid_str:
            return (
                _status_html("请输入记录 ID", "err"),
                _load_records(time_f, status_f, state),
            )
        try:
            ok = DeliveryRecordCRUD.delete(int(rid_str), user_name=user_name)
            if ok:
                return (
                    _status_html("删除成功", "ok"),
                    _load_records(time_f, status_f, state),
                )
            return (
                _status_html("记录不存在或无权删除", "warn"),
                _load_records(time_f, status_f, state),
            )
        except Exception as e:
            return (
                _status_html(f"删除失败: {e}", "err"),
                _load_records(time_f, status_f, state),
            )

    def _on_record_select(evt: gr.SelectData, table_data):
        try:
            row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            if hasattr(table_data, "iloc"):
                return str(table_data.iloc[row, 0])
            if isinstance(table_data, list) and 0 <= row < len(table_data):
                return str(table_data[row][0])
        except Exception:
            pass
        return ""

    # ==================== Event bindings ====================
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
        inputs=[record_id_input, status_select, time_filter, status_filter, login_state],
        outputs=[export_msg, records_table],
    )
    delete_btn.click(
        fn=_delete_record,
        inputs=[record_id_input, time_filter, status_filter, login_state],
        outputs=[export_msg, records_table],
    )
    stats_btn.click(
        fn=_load_stats,
        inputs=[login_state],
        outputs=[daily_chart, dist_chart, summary_slot],
    )


# ================================================================
# 作用域 CSS (限定在 .rc-scope / .rc-root 下)
# ================================================================
# fmt: off
_RC_STYLE = """
<style>
/* =========================================================
   Records Page — Bento 玻璃拟态风
   ========================================================= */
.rc-scope { color: var(--c-text-1); }
.rc-scope *, .rc-root * { box-sizing: border-box; }
#rc-page-root {
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 16px !important;
}
#rc-page-root > .block:first-child,
#rc-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* 页头 */
.rc-root .rc-head {
    display: flex; align-items: center; gap: 14px;
    margin: -10px 0 4px;
}
.rc-root .rc-head-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(79,139,255,0.22));
    border: 1px solid rgba(167,139,250,0.35);
    display: flex; align-items: center; justify-content: center;
    color: #DDD6FE;
    box-shadow: 0 8px 20px rgba(167,139,250,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.rc-root .rc-head-title { font-size: 22px; font-weight: 700; color: #F0F2FA; }
.rc-root .rc-head-sub { font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px; }

/* 通用卡片 */
.rc-scope .rc-card {
    position: relative;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.5) !important;
    backdrop-filter: blur(20px) saturate(130%);
    -webkit-backdrop-filter: blur(20px) saturate(130%);
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 20px !important;
    padding: 22px !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.05) inset,
        0 12px 32px rgba(0,0,0,0.32) !important;
    overflow: hidden;
    gap: 12px !important;
    display: flex !important;
    flex-direction: column !important;
    transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease,
                border-color 0.28s ease !important;
    will-change: transform;
}
.rc-scope .rc-card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(255,255,255,0.16) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 22px 50px rgba(0,0,0,0.5),
        0 6px 18px rgba(79,139,255,0.12) !important;
}
.rc-scope .rc-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.rc-scope .rc-card > * { position: relative; z-index: 1; }

/* 卡头 */
.rc-scope .rc-card-head {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
}
.rc-scope .rc-ch-icon {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.rc-scope .rc-ch-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.rc-scope .rc-ch-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(79,139,255,0.22));
    color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.35);
    box-shadow: 0 4px 14px rgba(167,139,250,0.22);
}
.rc-scope .rc-ch-pink {
    background: linear-gradient(135deg, rgba(244,114,182,0.28), rgba(251,146,60,0.22));
    color: #F9A8D4;
    border: 1px solid rgba(244,114,182,0.35);
    box-shadow: 0 4px 14px rgba(244,114,182,0.22);
}
.rc-scope .rc-ch-green {
    background: linear-gradient(135deg, rgba(52,211,153,0.28), rgba(79,139,255,0.22));
    color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.35);
    box-shadow: 0 4px 14px rgba(52,211,153,0.22);
}
.rc-scope .rc-ch-title { font-size: 16px; font-weight: 700; color: #F0F2FA; flex: 1; }
.rc-scope .rc-ch-sub { font-size: 12px; color: rgba(230,233,245,0.55); }

/* ---- 数据统计卡: 刷新统计按钮浮在卡头右上角 ---- */
.rc-scope .rc-card-stats { position: relative !important; }
.rc-scope .rc-stats-action-btn {
    position: absolute !important;
    top: 16px !important;
    right: 18px !important;
    width: auto !important;
    max-width: 130px !important;
    z-index: 5 !important;
    margin: 0 !important;
}
.rc-scope .rc-stats-action-btn button {
    background: rgba(52,211,153,0.10) !important;
    color: #6EE7B7 !important;
    border: 1px solid rgba(52,211,153,0.32) !important;
    border-radius: 999px !important;
    padding: 6px 14px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px !important;
    backdrop-filter: blur(12px) saturate(140%) !important;
    -webkit-backdrop-filter: blur(12px) saturate(140%) !important;
    box-shadow:
        0 4px 14px rgba(52,211,153,0.18),
        inset 0 1px 0 rgba(255,255,255,0.08) !important;
    transition: all 0.22s cubic-bezier(0.2,0.8,0.2,1) !important;
}
.rc-scope .rc-stats-action-btn button:hover {
    background: rgba(52,211,153,0.20) !important;
    color: #A7F3D0 !important;
    border-color: rgba(52,211,153,0.50) !important;
    transform: translateY(-1px);
    box-shadow:
        0 8px 22px rgba(52,211,153,0.32),
        inset 0 1px 0 rgba(255,255,255,0.14) !important;
}

/* 输入字段 */
.rc-scope .rc-input-field textarea,
.rc-scope .rc-input-field input,
.rc-scope .rc-input-field .wrap-inner {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    border-radius: 12px !important;
}
.rc-scope .rc-input-field textarea:focus,
.rc-scope .rc-input-field input:focus {
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.12) !important;
}

/* 按钮 */
.rc-scope .rc-btn,
.rc-scope .rc-btn button,
.rc-scope .rc-btn-mini,
.rc-scope .rc-btn-mini button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease, background 0.25s ease !important;
    letter-spacing: 0.3px !important;
}
.rc-scope .rc-btn button { padding: 11px 16px !important; font-size: 13.5px !important; }
.rc-scope .rc-btn-mini button { padding: 7px 14px !important; font-size: 12.5px !important; }
.rc-scope .rc-btn-primary,
.rc-scope .rc-btn-primary button {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 8px 20px rgba(79,139,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.rc-scope .rc-btn-primary:hover,
.rc-scope .rc-btn-primary button:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(79,139,255,0.45), inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.rc-scope .rc-btn-info,
.rc-scope .rc-btn-info button {
    background: rgba(56,189,248,0.12) !important;
    color: #7DD3FC !important;
    border: 1px solid rgba(56,189,248,0.30) !important;
}
.rc-scope .rc-btn-info:hover,
.rc-scope .rc-btn-info button:hover {
    background: rgba(56,189,248,0.18) !important;
    border-color: rgba(56,189,248,0.45) !important;
}
.rc-scope .rc-btn-danger,
.rc-scope .rc-btn-danger button {
    background: rgba(248,113,113,0.12) !important;
    color: #FCA5A5 !important;
    border: 1px solid rgba(248,113,113,0.30) !important;
}
.rc-scope .rc-btn-danger:hover,
.rc-scope .rc-btn-danger button:hover {
    background: rgba(248,113,113,0.18) !important;
    border-color: rgba(248,113,113,0.45) !important;
}
.rc-scope .rc-btn-muted,
.rc-scope .rc-btn-muted button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.75) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
}
.rc-scope .rc-btn-muted:hover,
.rc-scope .rc-btn-muted button:hover {
    background: rgba(79,139,255,0.12) !important;
    color: #AFC7FF !important;
    border-color: rgba(79,139,255,0.35) !important;
}

/* 筛选行 */
.rc-scope .rc-filter-row,
.rc-scope .rc-ops-row { gap: 10px !important; align-items: flex-end !important; }

/* 状态条 */
.rc-root .rc-status {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    font-size: 12.5px;
    color: rgba(230,233,245,0.85);
    backdrop-filter: blur(10px);
}
.rc-root .rc-status-empty { color: rgba(230,233,245,0.45); font-style: italic; }
.rc-root .rcs-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.rc-root .rcs-blue   { background: #8DBBFF; box-shadow: 0 0 10px rgba(141,187,255,0.6); }
.rc-root .rcs-green  { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.6); }
.rc-root .rcs-red    { background: #F87171; box-shadow: 0 0 10px rgba(248,113,113,0.6); }
.rc-root .rcs-orange { background: #FB923C; box-shadow: 0 0 10px rgba(251,146,60,0.6); }
.rc-root .rcs-gray   { background: rgba(200,200,220,0.35); }

/* 副标题 */
.rc-root .rc-subtitle {
    font-size: 13.5px; font-weight: 700;
    color: #F0F2FA;
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 10px;
    padding: 4px 0;
}
.rc-root .rc-subtitle-dot {
    width: 8px; height: 8px; border-radius: 50%;
    box-shadow: 0 0 10px currentColor;
}

/* ---- KPI 数字墙 ---- */
.rc-root .rc-kpi {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 4px;
}
.rc-root .rc-kpi-box {
    position: relative;
    padding: 14px 16px;
    border-radius: 14px;
    border: 1px solid transparent;
    overflow: hidden;
}
.rc-root .rc-kpi-box::after {
    content: ''; position: absolute;
    top: -30px; right: -30px;
    width: 120px; height: 120px; border-radius: 50%;
    opacity: 0.12; filter: blur(20px);
    pointer-events: none;
}
.rc-root .rc-kpi-icon {
    display: inline-flex; width: 28px; height: 28px;
    align-items: center; justify-content: center;
    border-radius: 8px; margin-bottom: 8px;
}
.rc-root .rc-kpi-num {
    font-size: 26px; font-weight: 800; letter-spacing: -0.5px;
    color: #F0F2FA; line-height: 1.1;
}
.rc-root .rc-kpi-lbl {
    font-size: 11.5px; color: rgba(230,233,245,0.55);
    margin-top: 4px;
    font-weight: 600; letter-spacing: 0.5px;
}
.rc-root .rc-kpi-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.12), rgba(121,90,255,0.06));
    border-color: rgba(79,139,255,0.22);
}
.rc-root .rc-kpi-blue .rc-kpi-icon { background: rgba(79,139,255,0.2); color: #AFC7FF; }
.rc-root .rc-kpi-blue::after { background: #4F8BFF; }
.rc-root .rc-kpi-green {
    background: linear-gradient(135deg, rgba(52,211,153,0.12), rgba(79,139,255,0.06));
    border-color: rgba(52,211,153,0.22);
}
.rc-root .rc-kpi-green .rc-kpi-icon { background: rgba(52,211,153,0.2); color: #6EE7B7; }
.rc-root .rc-kpi-green::after { background: #34D399; }
.rc-root .rc-kpi-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.12), rgba(244,114,182,0.06));
    border-color: rgba(167,139,250,0.22);
}
.rc-root .rc-kpi-violet .rc-kpi-icon { background: rgba(167,139,250,0.22); color: #DDD6FE; }
.rc-root .rc-kpi-violet::after { background: #A78BFA; }

/* ---- 柱状图 ---- */
.rc-scope .rc-stats-row { gap: 16px !important; align-items: stretch !important; }
.rc-scope .rc-stats-col { flex: 1 !important; }
.rc-root .rc-bar-chart {
    padding: 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 14px;
    display: flex; flex-direction: column; gap: 12px;
    min-height: 200px;
}
.rc-root .rc-bar-sum {
    font-size: 12px; color: rgba(230,233,245,0.55);
    letter-spacing: 0.3px;
}
.rc-root .rc-bar-sum b { color: #8DBBFF; font-weight: 700; font-size: 13px; }
.rc-root .rc-bar-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
    height: 150px;
    align-items: end;
}
.rc-root .rc-bar-item {
    display: flex; flex-direction: column; align-items: center;
    gap: 4px;
    height: 100%;
    justify-content: flex-end;
}
.rc-root .rc-bv {
    font-size: 11px; font-weight: 700; color: rgba(230,233,245,0.75);
    line-height: 1;
}
.rc-root .rc-bar-wrap {
    width: 100%;
    flex: 1;
    display: flex; align-items: flex-end;
    padding: 0 4px;
}
.rc-root .rc-bar {
    width: 100%;
    background: linear-gradient(180deg, #795AFF 0%, #4F8BFF 100%);
    border-radius: 6px 6px 2px 2px;
    box-shadow: 0 0 14px rgba(79,139,255,0.35), inset 0 1px 0 rgba(255,255,255,0.18);
    animation: rcBarRise 0.8s ease-out both;
    min-height: 4px;
}
@keyframes rcBarRise {
    0%   { height: 0 !important; opacity: 0; }
    100% { opacity: 1; }
}
.rc-root .rc-bl {
    font-size: 11px; color: rgba(230,233,245,0.55);
    line-height: 1;
}

/* ---- 环形图 ---- */
.rc-root .rc-ring-card {
    padding: 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 14px;
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 16px;
    align-items: center;
    min-height: 200px;
}
.rc-root .rc-ring-svg-wrap {
    position: relative;
    width: 140px; height: 140px;
    margin: 0 auto;
}
.rc-root .rc-ring-seg {
    transition: stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1);
}
.rc-root .rc-ring-center {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    pointer-events: none;
}
.rc-root .rc-ring-num {
    font-size: 26px; font-weight: 800; letter-spacing: -0.5px;
    color: #F0F2FA; line-height: 1;
}
.rc-root .rc-ring-lbl {
    font-size: 11px; color: rgba(230,233,245,0.55);
    margin-top: 4px; letter-spacing: 0.5px;
}
.rc-root .rc-legend { display: flex; flex-direction: column; gap: 8px; }
.rc-root .rc-legend-row {
    display: grid;
    grid-template-columns: 16px 1fr auto;
    gap: 8px;
    align-items: center;
    padding: 6px 10px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px;
}
.rc-root .rc-legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.rc-root .rc-legend-k { font-size: 12px; color: rgba(230,233,245,0.75); }
.rc-root .rc-legend-v { font-size: 12px; color: #F0F2FA; }
.rc-root .rc-legend-v b { font-weight: 700; font-size: 13px; }
.rc-root .rc-legend-v span { color: rgba(230,233,245,0.4); font-size: 11px; }

/* 空图 */
.rc-root .rc-chart-empty {
    padding: 40px 16px;
    border-radius: 14px;
    background: rgba(17,22,48,0.25);
    border: 1px dashed rgba(255,255,255,0.1);
    text-align: center;
    display: flex; flex-direction: column; align-items: center;
    gap: 8px; min-height: 180px;
    justify-content: center;
}
.rc-root .rc-chart-empty > svg {
    color: rgba(141,187,255,0.45);
    filter: drop-shadow(0 0 10px rgba(79,139,255,0.18));
}
.rc-root .rc-chart-empty-txt {
    color: rgba(230,233,245,0.55); font-size: 13px;
}

/* ================================================================
   响应式 — 多档断点 + 表格横向滚动优化
   ================================================================ */
.rc-scope .rc-table,
.rc-scope .rc-table .table-wrap,
.rc-scope .rc-table > div {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable both-edges;
}
.rc-scope .rc-table table {
    min-width: 720px !important;
}
.rc-scope .rc-table table th,
.rc-scope .rc-table table td {
    white-space: nowrap;
}
/* 表格横滑提示徽章 */
.rc-root .rc-table-hint {
    display: none;
    align-items: center;
    gap: 6px;
    margin: -2px 0 10px;
    padding: 5px 12px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(79,139,255,0.16), rgba(121,90,255,0.10));
    border: 1px dashed rgba(141,187,255,0.32);
    color: rgba(220,228,255,0.80);
    font-size: 11.5px; font-weight: 500;
    letter-spacing: 0.2px;
    width: fit-content;
}
.rc-root .rc-table-hint svg {
    color: #AFC7FF;
    animation: rcTableHintNudge 1.5s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}
@keyframes rcTableHintNudge {
    0%, 100% { transform: translateX(0); opacity: 0.7; }
    50%      { transform: translateX(3px); opacity: 1; }
}

@media (max-width: 1199px) {
    .rc-root .rc-kpi { grid-template-columns: repeat(2, 1fr); }
    .rc-scope .rc-stats-row { gap: 12px !important; }
    .rc-root .rc-table-hint { display: inline-flex; }
}
@media (max-width: 900px) {
    .rc-root .rc-kpi { grid-template-columns: 1fr; }
    .rc-scope .rc-stats-row { flex-direction: column !important; }
    .rc-root .rc-ring-card { grid-template-columns: 1fr; }
    .rc-scope .rc-filter-row,
    .rc-scope .rc-ops-row { flex-direction: column !important; align-items: stretch !important; }
    .rc-scope .rc-stats-action-btn {
        position: static !important;
        margin-top: 12px !important;
        max-width: 100% !important;
    }
    .rc-scope .rc-card { padding: 18px !important; }
    /* 表格横滚提示: 容器右侧叠加渐变阴影 + 增强提示徽章 */
    .rc-scope .rc-table {
        position: relative !important;
        background:
            linear-gradient(90deg, transparent calc(100% - 32px), rgba(0,0,0,0.42)) right center / 32px 100% no-repeat;
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    .rc-root .rc-table-hint {
        background: linear-gradient(135deg, rgba(255,184,77,0.20), rgba(251,146,60,0.12));
        border-color: rgba(251,146,60,0.45);
        color: #FED4A4;
    }
    .rc-root .rc-table-hint svg { color: #FB923C; }
}
@media (max-width: 600px) {
    .rc-scope .rc-card {
        padding: 14px !important;
        border-radius: 14px !important;
    }
    .rc-scope .rc-table table { min-width: 600px !important; font-size: 12px !important; }
    .rc-scope .rc-table table th,
    .rc-scope .rc-table table td { padding: 8px 10px !important; }
    /* 触屏取消 hover transform */
    .rc-scope .rc-card:hover { transform: none !important; }
}
</style>
"""
# fmt: on
