"""Resume management page."""

from __future__ import annotations

import json

import gradio as gr

from app.agents.resume_agent import parse_resume_node
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.ui.view_model import (
    get_ui_snapshot,
    invalidate_ui_snapshot,
    render_empty_state,
    render_skeleton_card,
)
from app.utils.file_util import save_uploaded_file

logger = get_logger(__name__)


def _upload_and_parse(file):
    """Upload and parse a resume file."""
    if file is None:
        return "", "", _get_resume_list()

    try:
        saved_path = save_uploaded_file(file.name if hasattr(file, "name") else str(file))
        result = parse_resume_node({"resume_path": saved_path})
        if result.get("error_code"):
            return "", "", _get_resume_list()

        struct = result.get("resume_struct", {})
        info_lines = [
            f"**姓名**：{struct.get('name', '未识别')}",
            f"**手机**：{struct.get('phone', '未识别')}",
            f"**邮箱**：{struct.get('email', '未识别')}",
            f"**学历**：{struct.get('education', '未识别')}",
            f"**工作年限**：{struct.get('experience_years', 0)} 年",
            f"**技能**：{', '.join(struct.get('skills', [])) or '未识别'}",
        ]
        invalidate_ui_snapshot()
        return "", "\n".join(info_lines), _get_resume_list()
    except Exception as exc:
        logger.error("简历上传失败: %s", exc)
        return "", "", _get_resume_list()


def _get_resume_list():
    """Return the resume list for the table."""
    try:
        resumes = sorted(ResumeCRUD.get_all(), key=lambda item: int(item["id"]))
        return [
            [
                item["id"],
                item["file_name"],
                item["file_type"],
                "原始版" if item["is_original"] else "优化版",
                "是" if item["is_default"] else "",
                item["create_time"],
            ]
            for item in resumes
        ]
    except Exception:
        return []


def _view_resume(selected_id):
    """View a resume by id."""
    if not selected_id:
        return "请选择简历 ID。"

    try:
        resume_id = int(selected_id)
        resume = ResumeCRUD.get_by_id(resume_id)
        if not resume:
            return "简历不存在"

        struct = json.loads(resume.get("struct_data", "{}"))
        parts = [f"### {resume['file_name']}"]
        labels = [
            ("name", "姓名"),
            ("phone", "手机"),
            ("email", "邮箱"),
            ("education", "学历"),
            ("experience_years", "工作年限"),
        ]
        for key, label in labels:
            value = struct.get(key, "未知")
            if key == "experience_years":
                value = f"{value} 年"
            parts.append(f"- **{label}**：{value}")

        skills = struct.get("skills", [])
        if skills:
            parts.append(f"- **技能**：{', '.join(skills)}")

        work_experience = struct.get("work_experience", [])
        if work_experience:
            parts.append("")
            parts.append("**工作经历**")
            for exp in work_experience:
                parts.append(f"- {exp.get('company', '')} | {exp.get('position', '')} | {exp.get('duration', '')}")
        return "\n".join(parts)
    except Exception as exc:
        return f"查看失败：{exc}"


def _delete_resume(selected_id):
    """Delete a resume by id."""
    if not selected_id:
        return "请选择简历 ID。", _get_resume_list()

    try:
        resume_id = int(selected_id)
        deleted = ResumeCRUD.delete(resume_id)
        if not deleted:
            return "删除失败：原始版简历不允许直接删除。", _get_resume_list()
        invalidate_ui_snapshot()
        return "删除成功。", _get_resume_list()
    except Exception as exc:
        return f"删除失败：{exc}", _get_resume_list()


def _set_default(selected_id):
    """Set a resume as default."""
    if not selected_id:
        return "请选择简历 ID。", _get_resume_list()

    try:
        ResumeCRUD.set_default(int(selected_id))
        invalidate_ui_snapshot()
        return "默认简历已更新。", _get_resume_list()
    except Exception as exc:
        return f"设置失败：{exc}", _get_resume_list()


def _render_resume_metrics() -> str:
    snapshot = get_ui_snapshot()
    return f"""
    <div class="stitch-stats-4">
        <div class="metric-pill-soft"><div class="label">简历资产</div><div class="value">{snapshot['resume_total']}</div></div>
        <div class="metric-pill-soft"><div class="label">原始文件</div><div class="value">{snapshot['resume_original']}</div></div>
        <div class="metric-pill-soft"><div class="label">优化版本</div><div class="value">{snapshot['resume_optimized']}</div></div>
        <div class="metric-pill-soft"><div class="label">默认简历</div><div class="value" style="font-size:18px;">{snapshot['default_resume_name']}</div></div>
    </div>
    """


def _render_resume_detail(detail_markdown: str) -> str:
    if not detail_markdown.strip():
        return render_empty_state(
            "等待查看详情",
            "选择一份简历后，这里会显示结构化解析结果和关键信息。",
            "建议先查看默认简历，再决定是否创建优化版本。",
            "CV",
        )
    return '<div class="feature-note">详情已同步到下方 Markdown 视图，可继续设为默认简历。</div>'


def _upload_and_parse_ui(file):
    status, result, table = _upload_and_parse(file)
    return result, table, _render_resume_metrics()


def _delete_resume_ui(selected_id):
    status, table = _delete_resume(selected_id)
    return table, _render_resume_metrics(), ""


def _set_default_ui(selected_id):
    status, table = _set_default(selected_id)
    return table, _render_resume_metrics()


def _view_resume_ui(selected_id):
    detail = _view_resume(selected_id)
    return detail, _render_resume_detail(detail)


def _resume_loading_state():
    return "正在解析简历...", render_skeleton_card(lines=5, with_block=False, with_pills=True)


def create_resume_page():
    """Create the resume management page."""
    snapshot = get_ui_snapshot()

    gr.HTML(
        """
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">上传 PDF 或 DOCX 原始简历，建立你的职业资料库。所有解析结果、版本管理和默认简历设置都会集中保存在这里。</div>
                </div>
            </div>
        </div>
        """
    )

    metrics_html = gr.HTML(value=f'<div class="page-shell page-stack">{_render_resume_metrics()}</div>')

    with gr.Row(elem_classes=["page-row", "workspace-grid"]):
        with gr.Column(elem_classes=["workspace-column", "sticky-pane"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">上传与解析</div>
                            <div class="stitch-panel-title">简历导入</div>
                        </div>

                    </div>
                    <div class="stitch-muted">上传原始简历后，系统会自动提取姓名、联系方式、教育背景、技能和工作经历。</div>
                    """
                )
                upload_file = gr.File(label="选择文件（PDF / DOCX，≤10MB）", file_types=[".pdf", ".docx"], elem_id="resume-upload-file")
                upload_btn = gr.Button("上传并解析", variant="primary", size="lg", elem_id="resume-upload-btn")
                parse_preview = gr.Markdown("")

            with gr.Group(elem_classes=["stitch-card", "stitch-section-tight"]):
                gr.HTML(
                    """
                    <div class="eyebrow">操作区</div>
                    <div class="stitch-panel-title">资产操作</div>
                    """
                )
                resume_id_input = gr.Textbox(label="简历 ID", placeholder="输入表格中的简历 ID")
                with gr.Row():
                    view_btn = gr.Button("查看详情", variant="secondary")
                    set_default_btn = gr.Button("设为默认", variant="secondary")
                    delete_btn = gr.Button("删除优化版", variant="stop")

        with gr.Column(elem_classes=["workspace-column"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">简历列表</div>
                            <div class="stitch-panel-title">已导入文件</div>
                        </div>

                    </div>
                    <script>
                        // 点击上传按钮时，如果没有文件，自动触发文件选择
                        document.addEventListener('DOMContentLoaded', function() {
                            setTimeout(function() {
                                const uploadBtn = document.getElementById('resume-upload-btn');
                                const fileInput = document.querySelector('#resume-upload-file input[type="file"]');
                                
                                if (uploadBtn && fileInput) {
                                    uploadBtn.addEventListener('click', function() {
                                        if (!fileInput.value) {
                                            fileInput.click();
                                        }
                                    });
                                }
                                
                                // 禁用表格单元格选择
                                const table = document.querySelector('.gradio-container table');
                                if (table) {
                                    table.style.userSelect = 'none';
                                    table.style.cursor = 'default';
                                    
                                    // 禁用所有单元格的选择
                                    const cells = table.querySelectorAll('td, th');
                                    cells.forEach(cell => {
                                        cell.style.userSelect = 'none';
                                        cell.style.cursor = 'default';
                                    });
                                }
                            }, 1000);
                        });
                    </script>
                    """
                )
                resume_table = gr.Dataframe(
                    headers=["ID", "文件名", "格式", "类型", "默认", "创建时间"],
                    datatype=["number", "str", "str", "str", "str", "str"],
                    value=_get_resume_list(),
                    interactive=False,
                )

            with gr.Row(elem_classes=["workspace-grid-equal"]):
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML(
                            """
                            <div class="stitch-toolbar">
                                <div>
                                    <div class="eyebrow">解析预览</div>
                                    <div class="stitch-panel-title">结构化结果</div>
                                </div>
        
                            </div>
                            """
                        )
                        detail_note = gr.HTML(value=_render_resume_detail(""))
                        detail_markdown = gr.Markdown(value="")
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section-tight"]):
                        gr.HTML(
                            f"""
                            <div class="eyebrow">资产摘要</div>
                            <div class="list-shell">
                                <div class="list-card selected">
                                    <div class="list-card-title">默认母版</div>
                                    <div class="list-card-sub">{snapshot['default_resume_name']}</div>
                                </div>
                                <div class="list-card">
                                    <div class="list-card-title">最近更新</div>
                                    <div class="list-card-sub">{snapshot['latest_resume_time']}</div>
                                </div>
                                <div class="list-card">
                                    <div class="list-card-title">建议动作</div>
                                    <div class="list-card-sub">先查看解析结果，再决定是否创建优化版本。</div>
                                </div>
                            </div>
                            """
                        )

    upload_btn.click(
        fn=lambda: ("正在解析简历..."),
        outputs=[parse_preview],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=_upload_and_parse_ui,
        inputs=[upload_file],
        outputs=[parse_preview, resume_table, metrics_html],
        show_progress="minimal",
    )
    view_btn.click(fn=_view_resume_ui, inputs=[resume_id_input], outputs=[detail_markdown, detail_note])
    set_default_btn.click(fn=_set_default_ui, inputs=[resume_id_input], outputs=[resume_table, metrics_html])
    delete_btn.click(fn=_delete_resume_ui, inputs=[resume_id_input], outputs=[resume_table, metrics_html, detail_markdown])
