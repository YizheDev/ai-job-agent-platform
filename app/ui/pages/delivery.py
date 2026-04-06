"""Semi-automated delivery page."""

from __future__ import annotations

import gradio as gr

from app.agents.risk_agent import risk_check_node
from app.core.config import get_settings
from app.db.crud import DeliveryRecordCRUD, ResumeCRUD
from app.ui.view_model import (
    get_ui_snapshot,
    invalidate_ui_snapshot,
    render_empty_state,
    render_skeleton_card,
    tab_switch_js,
)

_STEP_NAMES = ["创建任务", "风控校验", "人工确认", "投递完成"]


def _render_progress(current: int) -> str:
    """Render the delivery progress steps."""
    html = '<div class="progress-steps">'
    for index, name in enumerate(_STEP_NAMES):
        if index < current:
            dot_cls, name_cls, dot_text = "done", "done", "OK"
        elif index == current:
            dot_cls, name_cls, dot_text = "active", "active", str(index + 1)
        else:
            dot_cls, name_cls, dot_text = "", "", str(index + 1)

        html += (
            f'<div class="step-node"><div class="step-dot {dot_cls}">{dot_text}</div>'
            f'<div class="step-name {name_cls}">{name}</div></div>'
        )
        if index < len(_STEP_NAMES) - 1:
            html += f'<div class="step-line {"done" if index < current else ""}"></div>'
    html += "</div>"
    return html


def _render_task_card(company: str, position: str, url: str, resume_name: str = "") -> str:
    """Render a compact task review card."""
    rows = [("公司", company or "未填写"), ("岗位", position or "未填写"), ("链接", url or "未填写")]
    if resume_name:
        rows.append(("简历", resume_name))

    body = "".join(
        f'<div class="ic-row"><div class="ic-label">{label}</div><div class="ic-value">{value}</div></div>'
        for label, value in rows
    )
    return f'<div class="info-card">{body}</div>'


def _get_resume_choices() -> list[str]:
    try:
        resumes = ResumeCRUD.get_all()
        return [f"{item['id']}:{item['file_name']}" for item in resumes]
    except Exception:
        return []


def _create_task(resume_choice, position_url, company, position):
    """Create a delivery task and return status plus task payload."""
    empty = {"record_id": "", "progress": _render_progress(0), "card_html": ""}
    if not resume_choice:
        return "请选择简历。", empty
    if not position_url:
        return "请输入岗位链接。", empty

    company = company or "未知公司"
    position = position or "未知岗位"
    try:
        resume_id = int(resume_choice.split(":")[0])
        record_id = DeliveryRecordCRUD.create(
            company=company,
            position=position,
            position_url=position_url,
            resume_id=resume_id,
            status="pending",
        )
        invalidate_ui_snapshot()
        resume_name = resume_choice.split(":", 1)[1] if ":" in resume_choice else ""
        return (
            f"任务已创建（ID: {record_id}），请先执行风控校验。",
            {
                "record_id": str(record_id),
                "progress": _render_progress(1),
                "card_html": _render_task_card(company, position, position_url, resume_name),
            },
        )
    except Exception as exc:
        return f"任务创建失败：{exc}", empty


def _create_task_ui(resume_choice, position_url, company, position):
    message, detail = _create_task(resume_choice, position_url, company, position)
    return message, detail.get("record_id", ""), detail.get("progress", _render_progress(0)), detail.get("card_html", "")


def _check_and_deliver(record_id_str):
    """Run risk checks before delivery."""
    if not record_id_str:
        return "请先创建投递任务。", ""

    try:
        record_id = int(record_id_str)
        record = DeliveryRecordCRUD.get_by_id(record_id)
        if not record:
            return "任务不存在。", ""

        result = risk_check_node({})
        if not result.get("risk_passed", False):
            risk_msg = result.get("risk_message", "风控未通过")
            DeliveryRecordCRUD.update_status(record_id, "cancelled", error_msg=risk_msg)
            invalidate_ui_snapshot()
            return f"风控拦截：{risk_msg}", _render_progress(1)

        DeliveryRecordCRUD.update_status(record_id, "confirmed")
        invalidate_ui_snapshot()
        return "风控校验通过，请人工确认后再提交。", _render_progress(2)
    except Exception as exc:
        return f"校验失败：{exc}", ""


def _confirm_delivery(record_id_str):
    """Confirm delivery submission."""
    if not record_id_str:
        return "没有待提交任务。", ""
    try:
        record_id = int(record_id_str)
        DeliveryRecordCRUD.update_status(record_id, "success")
        invalidate_ui_snapshot()
        return f"投递完成，记录已更新（ID: {record_id}）。", _render_progress(3)
    except Exception as exc:
        return f"投递失败：{exc}", ""


def _cancel_delivery(record_id_str):
    """Cancel a delivery."""
    if not record_id_str:
        return "没有待取消任务。", ""
    try:
        record_id = int(record_id_str)
        DeliveryRecordCRUD.update_status(record_id, "cancelled")
        invalidate_ui_snapshot()
        return "投递已取消。", _render_progress(0)
    except Exception as exc:
        return f"取消失败：{exc}", ""


def _render_delivery_metrics() -> str:
    settings = get_settings()
    return f"""
    <div class="stitch-stats-4">
        <div class="metric-pill-soft"><div class="label">每日上限</div><div class="value">{settings.MAX_DAILY_DELIVERY}</div></div>
        <div class="metric-pill-soft"><div class="label">开始时段</div><div class="value">{settings.DELIVERY_START_HOUR}:00</div></div>
        <div class="metric-pill-soft"><div class="label">结束时段</div><div class="value">{settings.DELIVERY_END_HOUR}:00</div></div>
        <div class="metric-pill-soft"><div class="label">最低匹配分</div><div class="value">{settings.MATCH_THRESHOLD}</div></div>
    </div>
    """


def _task_loading_state():
    return "正在创建投递任务...", _render_progress(0), render_skeleton_card(lines=4, with_block=False)


def _risk_loading_state():
    return "正在进行风控校验...", _render_progress(1)


def _confirm_loading_state():
    return "正在提交投递动作...", _render_progress(2)


def create_delivery_page():
    """Create the delivery page."""
    snapshot = get_ui_snapshot()

    gr.HTML(
        f"""
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">Execution RPA 只负责执行浏览器动作，真正的提交必须经过风控校验和人工确认。整个流程默认遵循半自动安全模式。</div>
                    <div class="page-dock">
                        <span class="dock-pill"><strong>待处理任务</strong> {snapshot['delivery_pending'] + snapshot['delivery_confirmed']} 个</span>
                        <span class="dock-pill"><strong>今日剩余额度</strong> {snapshot['delivery_remaining']}</span>
                        <span class="dock-pill"><strong>投递窗口</strong> {snapshot['window_label']}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    gr.HTML(f'<div class="page-shell page-stack">{_render_delivery_metrics()}</div>')
    gr.HTML(
        """
        <div class="page-shell page-stack">
            <div class="alert-bar">所有投递都必须经过人工确认后提交，禁止静默批量投递。请确保平台账号已登录，并控制单次会话的岗位数量。</div>
        </div>
        """
    )

    with gr.Group(elem_classes=["page-stack", "stitch-card", "stitch-section"]):
        gr.HTML(
            """
            <div class="stitch-toolbar">
                <div>
                    <div class="eyebrow">执行步骤</div>
                    <div class="stitch-panel-title">投递工作流</div>
                </div>
                
            </div>
            """
        )
        progress_html = gr.HTML(value=_render_progress(0))

    with gr.Row(elem_classes=["page-row", "workspace-grid"]):
        with gr.Column(elem_classes=["workspace-column", "sticky-pane"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">任务创建</div>
                            <div class="stitch-panel-title">输入投递任务</div>
                        </div>

                    </div>
                    """
                )
                resume_dropdown = gr.Dropdown(choices=_get_resume_choices(), label="选择简历", interactive=True)
                refresh_btn = gr.Button("刷新简历列表", variant="secondary")
                company_input = gr.Textbox(label="公司名称", placeholder="例如：字节跳动")
                position_input = gr.Textbox(label="岗位名称", placeholder="例如：Python 后端工程师")
                url_input = gr.Textbox(
                    label="岗位链接（BOSS 直聘）",
                    placeholder="https://www.zhipin.com/job_detail/...",
                )
                create_btn = gr.Button("创建任务", variant="primary")
                task_status = gr.Textbox(label="任务状态", interactive=False, max_lines=1)
                record_id_state = gr.Textbox(visible=False)



        with gr.Column(elem_classes=["workspace-column"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">任务确认</div>
                            <div class="stitch-panel-title">投递确认台</div>
                        </div>

                    </div>
                    """
                )
                task_card = gr.HTML(
                    value=render_empty_state(
                        "等待创建任务",
                        "创建任务后，这里会显示公司、岗位、投递链接和所选简历。",
                        "所有提交都需要先做风控校验，再由你手动确认。",
                        "GO",
                    )
                )
                check_btn = gr.Button("执行风控校验", variant="secondary")
                check_status = gr.Textbox(label="校验状态", interactive=False, max_lines=1)
                with gr.Row():
                    confirm_btn = gr.Button("确认投递", variant="primary", size="lg")
                    cancel_btn = gr.Button("取消投递", variant="stop", size="lg")
                    go_records_btn = gr.Button("查看投递记录", variant="secondary", size="lg")
                delivery_result = gr.Textbox(label="投递结果", interactive=False, max_lines=2)

            with gr.Group(elem_classes=["stitch-card", "stitch-section-tight"]):
                gr.HTML(
                    """
                    <div class="feature-note">
                        建议先在 JD 匹配页确认匹配分，再回到本页创建任务。若风控未通过，请优先调整时段、会话节奏或岗位优先级。
                    </div>
                    """
                )

    refresh_btn.click(fn=lambda: gr.Dropdown(choices=_get_resume_choices()), outputs=[resume_dropdown])
    create_btn.click(
        fn=_task_loading_state,
        outputs=[task_status, progress_html, task_card],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=_create_task_ui,
        inputs=[resume_dropdown, url_input, company_input, position_input],
        outputs=[task_status, record_id_state, progress_html, task_card],
        show_progress="minimal",
    )
    check_btn.click(
        fn=_risk_loading_state,
        outputs=[check_status, progress_html],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=_check_and_deliver,
        inputs=[record_id_state],
        outputs=[check_status, progress_html],
        show_progress="minimal",
    )
    confirm_btn.click(
        fn=_confirm_loading_state,
        outputs=[delivery_result, progress_html],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=_confirm_delivery,
        inputs=[record_id_state],
        outputs=[delivery_result, progress_html],
        show_progress="minimal",
    )
    cancel_btn.click(fn=_cancel_delivery, inputs=[record_id_state], outputs=[delivery_result, progress_html])
    go_records_btn.click(fn=None, js=tab_switch_js("投递记录"))
