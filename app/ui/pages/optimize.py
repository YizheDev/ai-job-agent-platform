"""Resume optimization page."""

from __future__ import annotations

import json
from html import escape

import gradio as gr

from app.agents.optimize_agent import optimize_resume_node
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.ui.view_model import get_ui_snapshot, render_empty_state, render_skeleton_card, tab_switch_js

logger = get_logger(__name__)


def _get_resume_choices() -> list[str]:
    try:
        resumes = ResumeCRUD.get_all()
        return [f"{item['id']}:{item['file_name']}" for item in resumes]
    except Exception:
        return []


def _render_suggestions(items: list[str]) -> str:
    if not items:
        return render_empty_state(
            "等待优化建议",
            "生成完成后，这里会给出段落级改写建议和关键词补强方向。",
            "所有建议都需要人工确认后再采纳。",
            "AI",
        )
    rows = "".join(
        f'<div class="kv-row"><div class="kv-label">建议 {index}</div><div class="kv-value">{escape(text)}</div></div>'
        for index, text in enumerate(items, start=1)
    )
    return f'<div class="kv-list">{rows}</div>'


def _do_optimize(resume_choice, jd_text):
    """Run resume optimization."""
    if not resume_choice:
        return "请先选择简历。", "", "", "", ""
    if not jd_text or len(jd_text.strip()) < 50:
        return "请先提供完整 JD 文本。", "", "", "", ""

    try:
        resume_id = int(resume_choice.split(":")[0])
        resume = ResumeCRUD.get_by_id(resume_id)
        if not resume:
            return "简历不存在。", "", "", "", ""

        struct = json.loads(resume.get("struct_data", "{}"))
        original_text = struct.get("optimized_text", "") or json.dumps(struct, ensure_ascii=False, indent=2)
        result = optimize_resume_node(
            {
                "resume_text": original_text,
                "jd_text": jd_text,
                "resume_struct": struct,
                "jd_struct": {},
                "missing_items": [],
                "weak_items": [],
                "resume_id": resume_id,
            }
        )
        if result.get("error_code"):
            return f"优化失败：{result.get('error_msg')}", original_text, "", "", ""

        optimized_text = result.get("optimized_resume", "")
        suggestions_html = _render_suggestions(result.get("optimize_suggestions", []))
        cover_letter = result.get("cover_letter", "")
        return "优化建议已生成。", original_text, optimized_text, suggestions_html, cover_letter
    except Exception as exc:
        logger.error("简历优化异常: %s", exc)
        return f"优化异常：{exc}", "", "", "", ""


def _optimize_loading_state():
    return (
        "正在生成优化建议...",
        render_skeleton_card(lines=5, with_block=False, with_pills=True),
        "正在生成求职信草稿，请稍候...",
    )


def create_optimize_page():
    """Create the resume optimization page."""
    snapshot = get_ui_snapshot()

    gr.HTML(
        f"""
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">Writer Agent 会根据 JD 生成改写建议和求职信草稿，但不会自动覆盖你的原始内容。这里始终坚持“建议优先、人工确认”。</div>
                    <div class="page-dock">
                        <span class="dock-pill"><strong>简历资产</strong> {snapshot['resume_total']} 份</span>
                        <span class="dock-pill"><strong>默认母版</strong> {snapshot['default_resume_name']}</span>
                        <span class="dock-pill"><strong>下一步</strong> 进入自动投递</span>
                    </div>
                </div>
            </div>
        </div>
        """
    )

    with gr.Row(elem_classes=["page-row", "workspace-grid"]):
        with gr.Column(elem_classes=["workspace-column", "sticky-pane"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">输入条件</div>
                            <div class="stitch-panel-title">优化参数</div>
                        </div>

                    </div>
                    <div class="stitch-muted">选择简历并提供目标 JD，系统会输出逐段改写建议、关键词强化方向和一版求职信草稿。</div>
                    """
                )
                resume_dropdown = gr.Dropdown(choices=_get_resume_choices(), label="选择简历", interactive=True)
                refresh_btn = gr.Button("刷新简历列表", variant="secondary")
                jd_text = gr.Textbox(
                    label="目标 JD",
                    lines=10,
                    placeholder="请粘贴目标 JD，用于生成更贴合的改写建议。",
                )
                optimize_btn = gr.Button("生成优化建议", variant="primary", size="lg")
                go_delivery_btn = gr.Button("前往自动投递", variant="secondary")
                status = gr.Textbox(label="优化状态", interactive=False, max_lines=1)



        with gr.Column(elem_classes=["workspace-column"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">对比视图</div>
                            <div class="stitch-panel-title">原文与建议稿</div>
                        </div>

                    </div>
                    """
                )
                with gr.Row(equal_height=True):
                    with gr.Column():
                        gr.HTML('<div class="eyebrow">原始内容</div>')
                        original_text = gr.Textbox(label="原始内容", lines=18, interactive=False)
                    with gr.Column():
                        gr.HTML('<div class="eyebrow">优化建议稿</div>')
                        optimized_text = gr.Textbox(label="优化建议稿", lines=18, interactive=True)

            with gr.Row(elem_classes=["workspace-grid-equal"]):
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML(
                            """
                            <div class="stitch-toolbar">
                                <div>
                                    <div class="eyebrow">优化建议</div>
                                    <div class="stitch-panel-title">段落级建议</div>
                                </div>
        
                            </div>
                            """
                        )
                        suggestions_display = gr.HTML(
                            value=render_empty_state(
                                "等待优化建议",
                                "这里会输出段落级建议与关键词补强方向。",
                                "建议逐条审阅后再采纳。",
                                "AI",
                            )
                        )
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML(
                            """
                            <div class="stitch-toolbar">
                                <div>
                                    <div class="eyebrow">求职信</div>
                                    <div class="stitch-panel-title">可复用草稿</div>
                                </div>
        
                            </div>
                            """
                        )
                        cover_letter_display = gr.Textbox(label="AI 生成求职信", lines=10, interactive=True)

    refresh_btn.click(fn=lambda: gr.Dropdown(choices=_get_resume_choices()), outputs=[resume_dropdown])
    optimize_btn.click(
        fn=_optimize_loading_state,
        outputs=[status, suggestions_display, cover_letter_display],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=_do_optimize,
        inputs=[resume_dropdown, jd_text],
        outputs=[status, original_text, optimized_text, suggestions_display, cover_letter_display],
        show_progress="minimal",
    )
    go_delivery_btn.click(fn=None, js=tab_switch_js("自动投递"))
