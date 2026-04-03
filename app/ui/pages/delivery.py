"""自动化投递页面

投递任务创建, 风控校验, 投递进度展示, 人工确认。
纯CSS进度步骤指示器。
"""

from __future__ import annotations

import gradio as gr

from app.agents.risk_agent import risk_check_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD, ResumeCRUD

logger = get_logger(__name__)

_STEP_NAMES = ["创建任务", "风控校验", "人工确认", "投递完成"]


def _render_progress(current: int) -> str:
    """渲染纯CSS进度步骤指示器, current: 0-3"""
    html = '<div class="progress-steps">'
    for i, name in enumerate(_STEP_NAMES):
        if i < current:
            dot_cls, name_cls = "done", "done"
            dot_text = "✓"
        elif i == current:
            dot_cls, name_cls = "active", "active"
            dot_text = str(i + 1)
        else:
            dot_cls, name_cls = "", ""
            dot_text = str(i + 1)

        html += (
            f'<div class="step-node">'
            f'<div class="step-dot {dot_cls}">{dot_text}</div>'
            f'<div class="step-name {name_cls}">{name}</div>'
            f"</div>"
        )
        if i < len(_STEP_NAMES) - 1:
            line_cls = "done" if i < current else ""
            html += f'<div class="step-line {line_cls}"></div>'

    html += "</div>"
    return html


def _render_task_card(company: str, position: str, url: str, resume_name: str = "") -> str:
    """渲染任务信息卡片"""
    rows = [
        ("公司", company or "—"),
        ("岗位", position or "—"),
        ("链接", f'<a href="{url}" target="_blank" style="color:#165DFF;text-decoration:none;">{url[:60]}...</a>' if url and len(url) > 60 else (f'<a href="{url}" target="_blank" style="color:#165DFF;text-decoration:none;">{url}</a>' if url else "—")),
    ]
    if resume_name:
        rows.append(("简历", resume_name))

    html = '<div class="info-card">'
    for label, value in rows:
        html += (
            f'<div class="ic-row">'
            f'<div class="ic-label">{label}</div>'
            f'<div class="ic-value">{value}</div>'
            f"</div>"
        )
    html += "</div>"
    return html


def _get_resume_choices():
    try:
        resumes = ResumeCRUD.get_all()
        return [f"{r['id']}:{r['file_name']}" for r in resumes]
    except Exception:
        return []


def _create_task(resume_choice, position_url, company, position):
    """创建投递任务"""
    if not resume_choice:
        return "请选择简历", "", _render_progress(0), ""
    if not position_url:
        return "请输入岗位链接", "", _render_progress(0), ""
    if not company:
        company = "未知公司"
    if not position:
        position = "未知岗位"

    try:
        resume_id = int(resume_choice.split(":")[0])
        record_id = DeliveryRecordCRUD.create(
            company=company,
            position=position,
            position_url=position_url,
            resume_id=resume_id,
            status="pending",
        )
        resume_name = resume_choice.split(":", 1)[1] if ":" in resume_choice else ""
        card_html = _render_task_card(company, position, position_url, resume_name)
        return (
            f"✓ 任务已创建 (ID: {record_id}), 请进行风控校验",
            str(record_id),
            _render_progress(1),
            card_html,
        )
    except Exception as e:
        return f"任务创建失败: {e}", "", _render_progress(0), ""


def _check_and_deliver(record_id_str):
    """风控校验并准备投递"""
    if not record_id_str:
        return "请先创建投递任务", ""

    try:
        record_id = int(record_id_str)
        record = DeliveryRecordCRUD.get_by_id(record_id)
        if not record:
            return "任务不存在", ""

        result = risk_check_node({})

        if not result.get("risk_passed", False):
            risk_msg = result.get("risk_message", "风控未通过")
            DeliveryRecordCRUD.update_status(record_id, "cancelled", error_msg=risk_msg)
            return f"风控拦截: {risk_msg}", _render_progress(1)

        DeliveryRecordCRUD.update_status(record_id, "confirmed")
        return "✓ 风控校验通过, 请确认投递", _render_progress(2)
    except Exception as e:
        return f"校验失败: {e}", ""


def _confirm_delivery(record_id_str):
    """确认投递"""
    if not record_id_str:
        return "无待投递任务", ""
    try:
        record_id = int(record_id_str)
        DeliveryRecordCRUD.update_status(record_id, "success")
        return f"✓ 投递完成! 记录已更新 (ID: {record_id})", _render_progress(3)
    except Exception as e:
        return f"投递失败: {e}", ""


def _cancel_delivery(record_id_str):
    """取消投递"""
    if not record_id_str:
        return "无待投递任务", ""
    try:
        record_id = int(record_id_str)
        DeliveryRecordCRUD.update_status(record_id, "cancelled")
        return "投递已取消", _render_progress(0)
    except Exception as e:
        return f"取消失败: {e}", ""


def create_delivery_page():
    """创建自动化投递页面"""
    gr.Markdown("## 自动化投递")

    gr.HTML(
        '<div class="alert-bar info">'
        "⚠ 所有投递必须人工确认后提交, 禁止全自动无确认投递。请确保已登录招聘平台。"
        "</div>"
    )

    # 进度指示器
    progress_html = gr.HTML(value=_render_progress(0))

    with gr.Row():
        # 左栏: 创建任务
        with gr.Column(scale=2):
            gr.Markdown("### 创建投递任务")
            resume_dropdown = gr.Dropdown(
                choices=_get_resume_choices(), label="选择简历", interactive=True
            )
            gr.Button("刷新简历", size="sm").click(
                fn=lambda: gr.Dropdown(choices=_get_resume_choices()),
                outputs=[resume_dropdown],
            )
            company_input = gr.Textbox(label="公司名称", placeholder="如: 字节跳动")
            position_input = gr.Textbox(
                label="岗位名称", placeholder="如: Python 后端工程师"
            )
            url_input = gr.Textbox(
                label="岗位链接 (BOSS 直聘)",
                placeholder="https://www.zhipin.com/job_detail/...",
            )
            create_btn = gr.Button("创建任务", variant="primary")
            task_status = gr.Textbox(label="任务状态", interactive=False, max_lines=1)
            record_id_state = gr.Textbox(visible=False)

        # 右栏: 投递确认
        with gr.Column(scale=3):
            gr.Markdown("### 投递确认")
            task_card = gr.HTML(value="")

            check_btn = gr.Button("风控校验", variant="secondary")
            check_status = gr.Textbox(label="校验状态", interactive=False, max_lines=1)

            with gr.Row():
                confirm_btn = gr.Button("确认投递", variant="primary", size="lg")
                cancel_btn = gr.Button("取消投递", variant="stop", size="lg")

            delivery_result = gr.Textbox(
                label="投递结果", interactive=False, max_lines=2
            )

    create_btn.click(
        fn=_create_task,
        inputs=[resume_dropdown, url_input, company_input, position_input],
        outputs=[task_status, record_id_state, progress_html, task_card],
    )
    check_btn.click(
        fn=_check_and_deliver,
        inputs=[record_id_state],
        outputs=[check_status, progress_html],
    )
    confirm_btn.click(
        fn=_confirm_delivery,
        inputs=[record_id_state],
        outputs=[delivery_result, progress_html],
    )
    cancel_btn.click(
        fn=_cancel_delivery,
        inputs=[record_id_state],
        outputs=[delivery_result, progress_html],
    )
