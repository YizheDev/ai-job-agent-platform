"""Dashboard page for the AI job copilot workspace."""

from __future__ import annotations

from datetime import datetime
from html import escape

import gradio as gr

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD
from app.ui.view_model import get_ui_snapshot, render_empty_state, tab_switch_js

logger = get_logger(__name__)

_STATUS_MAP = {
    "pending": ("待投递", "tag-gray"),
    "confirmed": ("待确认", "tag-blue"),
    "delivering": ("投递中", "tag-orange"),
    "success": ("已投递", "tag-green"),
    "failed": ("失败", "tag-red"),
    "cancelled": ("已取消", "tag-gray"),
    "error": ("异常", "tag-red"),
}


def _load_dashboard_data():
    """Load the lightweight data used on the dashboard."""
    try:
        settings = get_settings()
        today_count = DeliveryRecordCRUD.get_today_count()
        total_count = DeliveryRecordCRUD.get_total_count()
        avg_score = DeliveryRecordCRUD.get_avg_score(7)
        remaining = max(0, settings.MAX_DAILY_DELIVERY - today_count)

        recent = DeliveryRecordCRUD.get_recent(5)
        table_rows = [
            [row["company"], row["position"], row["match_score"], row["create_time"], row["status"]]
            for row in recent
        ]

        risk_msg = ""
        current_hour = datetime.now().hour
        if not (settings.DELIVERY_START_HOUR <= current_hour < settings.DELIVERY_END_HOUR):
            risk_msg = (
                "当前不在建议投递时段，推荐在 "
                f"{settings.DELIVERY_START_HOUR}:00 - {settings.DELIVERY_END_HOUR}:00 操作。"
            )
        if today_count >= settings.MAX_DAILY_DELIVERY:
            risk_msg = "今日投递已达到上限，建议暂停执行，等下一个时段再继续。"

        return remaining, today_count, total_count, float(avg_score), table_rows, risk_msg
    except Exception as exc:
        logger.error("加载工作台数据失败: %s", exc)
        return 0, 0, 0, 0.0, [], f"数据加载失败：{exc}"


def _build_metric_html(remaining: int, today: int, total: int, avg: float) -> str:
    return f"""
    <div class="glass-card hero-card">
        <div class="quota-orb">
            <div class="orb-inner">
                <span class="orb-value">{remaining}</span>
                <span class="orb-meta">剩余投递额度</span>
            </div>
        </div>
        <div class="hero-copy">
            <div class="eyebrow">今日总览</div>
            <h2>求职工作流正在稳定运行</h2>
            <p>多智能体已完成今日岗位扫描与任务预排，当前适合继续执行 JD 匹配、简历优化与人工确认投递。</p>
            <div class="hero-metrics">
                <div class="hero-metric">
                    <div class="label">今日已投</div>
                    <div class="value">{today}</div>
                </div>
                <div class="hero-metric">
                    <div class="label">累计投递总数</div>
                    <div class="value">{total}</div>
                </div>
                <div class="hero-metric">
                    <div class="label">近 7 日匹配均分</div>
                    <div class="value">{avg:.1f}</div>
                </div>
            </div>
        </div>
    </div>
    """


def _build_agent_status_html(avg: float, remaining: int, today: int) -> str:
    analyst_load = max(38, min(96, int(avg) if avg else 42))
    execution_load = max(18, min(92, int((today / max(1, today + remaining)) * 100)))
    agents = [
        ("Parser Agent", "结构化解析稳定", 96, "online"),
        ("Analyst Agent", "JD 图谱分析中", analyst_load, "online"),
        ("Matchmaker", "匹配评分生成中", max(32, analyst_load - 6), "warn" if avg < 70 else "online"),
        ("Execution RPA", "等待人工确认", execution_load, "idle" if remaining else "warn"),
    ]
    cards = []
    for name, meta, value, state in agents:
        cards.append(
            f"""
            <div class="agent-item">
                <div class="top">
                    <span class="name">{escape(name)}</span>
                    <span class="dot {state}"></span>
                </div>
                <div class="meta">{escape(meta)}</div>
                <div class="bar"><span style="width:{value}%"></span></div>
            </div>
            """
        )
    return """
    <div class="glass-card agent-panel">
        <div class="eyebrow">智能体状态</div>
        <div class="section-title">多智能体运行面板</div>
        <div class="agent-grid">%s</div>
    </div>
    """ % "".join(cards)


def _build_analysis_html(records: list[list], avg: float, risk_msg: str) -> tuple[str, str]:
    if records:
        rows = []
        for company, position, score, _created_at, status in records[:4]:
            status_label, status_class = _STATUS_MAP.get(str(status), (str(status), "tag-gray"))
            score_value = int(float(score or 0))
            rows.append(
                f"""
                <div class="kv-row">
                    <div class="kv-label">{escape(str(company))}</div>
                    <div class="kv-value">
                        <div style="font-weight:700;color:#1f2937;">{escape(str(position))}</div>
                        <div style="display:flex;gap:10px;align-items:center;margin-top:6px;">
                            <span class="status-tag {status_class}">{escape(status_label)}</span>
                            <span style="color:#1E90FF;font-weight:800;">{score_value} 分</span>
                        </div>
                    </div>
                </div>
                """
            )
        trend_html = """
        <div class="stitch-card stitch-section">
            <div class="stitch-toolbar">
                <div>
                    <div class="eyebrow">近期表现</div>
                    <div class="stitch-panel-title">优先跟进岗位</div>
                </div>

            </div>
            <div class="kv-list">%s</div>
        </div>
        """ % (avg, "".join(rows))
    else:
        trend_html = f"""
        <div class="stitch-card stitch-section">
            <div class="stitch-toolbar">
                <div>
                    <div class="eyebrow">近期表现</div>
                    <div class="stitch-panel-title">优先跟进岗位</div>
                </div>

            </div>
            {render_empty_state("还没有匹配数据", "先导入 JD 并完成首轮分析，系统会在这里标出值得优先跟进的岗位。", "建议先去 JD 匹配页创建第一条分析记录。", "JD")}
        </div>
        """

    risk_items = []
    if risk_msg:
        risk_items.append(f'<div class="risk-item danger"><h4>投递窗口提醒</h4><p>{escape(risk_msg)}</p></div>')
    else:
        risk_items.append(
            '<div class="risk-item"><h4>当前执行节奏正常</h4><p>当前投递窗口、频率和额度均在安全范围内，可以继续推进任务。</p></div>'
        )
    risk_items.append(
        '<div class="risk-item"><h4>关键词补强建议</h4><p>优先处理匹配分高但仍存在技能缺口的岗位，先补关键词，再进入人工确认。</p></div>'
    )
    risk_items.append(
        '<div class="risk-item"><h4>账号安全建议</h4><p>建议保持单次会话岗位数量和操作间隔接近人工节奏，避免高频连续点击。</p></div>'
    )
    risk_html = """
    <div class="risk-panel">
        <div class="eyebrow">风控观察</div>
        <h3>风险与合规观察</h3>
        <div class="risk-list">%s</div>
    </div>
    """ % "".join(risk_items)
    return trend_html, risk_html


def _build_pending_tasks_html(records: list[list]) -> str:
    if not records:
        return """
        <div class="glass-card pending-card">
            <div class="eyebrow">待处理队列</div>
            <div class="section-title">现在最值得做的两件事</div>
            <div class="pending-list">
                <div class="pending-item">
                    <div class="pending-main">
                        <div class="pending-icon">CV</div>
                        <div>
                            <div class="pending-title">上传第一份简历</div>
                            <div class="pending-sub">先建立职业资产库，后续的匹配、优化和投递都会围绕它展开。</div>
                        </div>
                    </div>
                    <span class="pending-pill">开始使用</span>
                </div>
                <div class="pending-item">
                    <div class="pending-main">
                        <div class="pending-icon">JD</div>
                        <div>
                            <div class="pending-title">导入目标 JD</div>
                            <div class="pending-sub">让 Analyst Agent 先拆解岗位要求，再判断是否值得投入优化成本。</div>
                        </div>
                    </div>
                    <span class="pending-pill">推荐</span>
                </div>
            </div>
        </div>
        """

    items = []
    for company, position, score, _created_at, _status in records[:3]:
        badge = "高优先级" if int(float(score or 0)) >= 85 else "待处理"
        items.append(
            f"""
            <div class="pending-item">
                <div class="pending-main">
                    <div class="pending-icon">AI</div>
                    <div>
                        <div class="pending-title">{escape(str(company))} · {escape(str(position))}</div>
                        <div class="pending-sub">当前匹配分 {escape(str(score))}，建议先完成简历优化和用户确认。</div>
                    </div>
                </div>
                <span class="pending-pill">{badge}</span>
            </div>
            """
        )
    return """
    <div class="glass-card pending-card">
        <div class="eyebrow">待处理队列</div>
        <div class="section-title">优先跟进任务</div>
        <div class="pending-list">%s</div>
    </div>
    """ % "".join(items)


def _build_recent_table_html(records: list[list]) -> str:
    if not records:
        tbody = f"""
        <tr>
            <td colspan="5" style="padding:22px 18px;">
                {render_empty_state("还没有投递记录", "先上传简历或导入 JD，系统会在这里持续追踪你的投递轨迹。", "推荐动作：先完成首轮 JD 匹配。", "GO")}
            </td>
        </tr>
        """
    else:
        rows = []
        for company, position, score, create_time, status in records:
            label, cls = _STATUS_MAP.get(str(status), (str(status), "tag-gray"))
            rows.append(
                f"""
                <tr>
                    <td>{escape(str(company))}</td>
                    <td>{escape(str(position))}</td>
                    <td>{escape(str(score))}</td>
                    <td>{escape(str(create_time))}</td>
                    <td><span class="status-tag {cls}">{escape(label)}</span></td>
                </tr>
                """
            )
        tbody = "".join(rows)
    return """
    <div class="glass-card records-card">
        <div class="stitch-toolbar">
            <div>
                <div class="eyebrow">最近记录</div>
                <div class="stitch-panel-title">最近投递记录</div>
            </div>
            
        </div>
        <div class="table-shell">
            <table class="custom-table">
                <thead>
                    <tr>
                        <th>公司</th>
                        <th>岗位</th>
                        <th>匹配分</th>
                        <th>创建时间</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>%s</tbody>
            </table>
        </div>
    </div>
    """ % tbody


def _render_dashboard_sections() -> tuple[str, str, str, str, str, str]:
    remaining, today, total, avg, records, risk_msg = _load_dashboard_data()
    metrics = _build_metric_html(remaining, today, total, avg)
    agents = _build_agent_status_html(avg, remaining, today)
    trend, risk = _build_analysis_html(records, avg, risk_msg)
    pending = _build_pending_tasks_html(records)
    recent = _build_recent_table_html(records)
    return metrics, agents, trend, risk, pending, recent


def create_dashboard_page():
    """Create the dashboard page."""
    metrics, agents, trend, risk, pending, recent = _render_dashboard_sections()
    snapshot = get_ui_snapshot()

    gr.HTML(
        f"""
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">集中查看简历资产、岗位匹配、投递节奏和风险提醒，让整个求职流程保持透明、可控、可追踪。</div>
                    <div class="page-dock">
                        <span class="dock-pill"><strong>默认简历</strong> {escape(snapshot['default_resume_name'])}</span>
                        <span class="dock-pill"><strong>关注岗位</strong> {escape(snapshot['top_company'])} / {escape(snapshot['top_position'])}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    with gr.Row(elem_classes=["page-row", "workspace-grid"]):
        with gr.Column(elem_classes=["workspace-column", "sticky-pane"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section-tight"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">快捷入口</div>
                            <div class="stitch-panel-title">先做这三步</div>
                        </div>

                    </div>
                    """
                )
                with gr.Row(elem_classes=["quick-actions"]):
                    go_resume_btn = gr.Button("上传简历", variant="primary", size="lg")
                    go_delivery_btn = gr.Button("新建投递任务", variant="secondary", size="lg")
                    go_records_btn = gr.Button("查看投递记录", variant="secondary", size="lg")
                refresh_btn = gr.Button("刷新工作台", variant="secondary", size="sm")

            pending_html = gr.HTML(value=pending)
            analysis_html = gr.HTML(value=f'<div class="analysis-grid">{trend}{risk}</div>')

        with gr.Column(elem_classes=["workspace-column"]):
            overview_html = gr.HTML(value=metrics)
            agents_html = gr.HTML(value=agents)
            recent_html = gr.HTML(value=recent)

    def _refresh_dashboard_html():
        next_metrics, next_agents, next_trend, next_risk, next_pending, next_recent = _render_dashboard_sections()
        return (
            next_pending,
            f'<div class="analysis-grid">{next_trend}{next_risk}</div>',
            next_metrics,
            next_agents,
            next_recent,
        )

    refresh_btn.click(
        fn=_refresh_dashboard_html,
        outputs=[pending_html, analysis_html, overview_html, agents_html, recent_html],
    )
    go_resume_btn.click(fn=None, js=tab_switch_js("简历管理"))
    go_delivery_btn.click(fn=None, js=tab_switch_js("自动投递"))
    go_records_btn.click(fn=None, js=tab_switch_js("投递记录"))
