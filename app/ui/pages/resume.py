"""简历管理页面

简历上传、解析、版本管理、预览、导出、删除。
商务极简卡片布局。
"""

from __future__ import annotations

import json

import gradio as gr

from app.agents.resume_agent import parse_resume_node, save_resume_file
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.utils.file_util import format_file_size, save_uploaded_file

logger = get_logger(__name__)


def _upload_and_parse(file):
    """上传并解析简历"""
    if file is None:
        return "请选择文件", "", []

    try:
        saved_path = save_uploaded_file(file.name if hasattr(file, "name") else str(file))
        state = {"resume_path": saved_path}
        result = parse_resume_node(state)

        if result.get("error_code"):
            return f"解析失败: {result.get('error_msg', '')}", "", _get_resume_list()

        struct = result.get("resume_struct", {})
        info_lines = [
            f"**姓名**: {struct.get('name', '未提取')}",
            f"**手机**: {struct.get('phone', '未提取')}",
            f"**邮箱**: {struct.get('email', '未提取')}",
            f"**学历**: {struct.get('education', '未提取')}",
            f"**工作年限**: {struct.get('experience_years', 0)} 年",
            f"**技能**: {', '.join(struct.get('skills', []))}",
        ]
        info_text = "\n".join(info_lines)
        return "✓ 解析成功", info_text, _get_resume_list()
    except Exception as e:
        logger.error("简历上传失败: %s", e)
        return f"上传失败: {e}", "", _get_resume_list()


def _get_resume_list():
    """获取简历列表数据"""
    try:
        resumes = ResumeCRUD.get_all()
        return [
            [
                r["id"],
                r["file_name"],
                r["file_type"],
                "原始" if r["is_original"] else "优化版",
                "是" if r["is_default"] else "",
                r["create_time"],
            ]
            for r in resumes
        ]
    except Exception:
        return []


def _view_resume(selected_id):
    """查看简历详情"""
    if not selected_id:
        return "请选择简历"
    try:
        resume_id = int(selected_id)
        resume = ResumeCRUD.get_by_id(resume_id)
        if not resume:
            return "简历不存在"
        struct = json.loads(resume.get("struct_data", "{}"))
        parts = [f"### {resume['file_name']}"]
        for key, label in [("name", "姓名"), ("phone", "手机"), ("email", "邮箱"),
                           ("education", "学历"), ("experience_years", "工作年限")]:
            parts.append(f"- **{label}**: {struct.get(key, '未知')}")
        if struct.get("skills"):
            parts.append(f"- **技能**: {', '.join(struct['skills'])}")
        if struct.get("work_experience"):
            parts.append("\n**工作经历:**")
            for exp in struct["work_experience"]:
                parts.append(
                    f"  - {exp.get('company', '')} | "
                    f"{exp.get('position', '')} | "
                    f"{exp.get('duration', '')}"
                )
        return "\n".join(parts)
    except Exception as e:
        return f"查看失败: {e}"


def _delete_resume(selected_id):
    """删除简历"""
    if not selected_id:
        return "请选择简历", _get_resume_list()
    try:
        resume_id = int(selected_id)
        ok = ResumeCRUD.delete(resume_id)
        if ok:
            return "✓ 删除成功", _get_resume_list()
        return "删除失败: 原始简历不可删除", _get_resume_list()
    except Exception as e:
        return f"删除失败: {e}", _get_resume_list()


def _set_default(selected_id):
    """设置默认简历"""
    if not selected_id:
        return "请选择简历", _get_resume_list()
    try:
        ResumeCRUD.set_default(int(selected_id))
        return "✓ 已设为默认简历", _get_resume_list()
    except Exception as e:
        return f"操作失败: {e}", _get_resume_list()


def create_resume_page():
    """创建简历管理页面"""
    gr.Markdown("## 简历管理")

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 上传简历")
            file_input = gr.File(
                label="选择文件 (PDF / DOCX, ≤10MB)",
                file_types=[".pdf", ".docx"],
            )
            upload_btn = gr.Button("上传并解析", variant="primary")
            status_msg = gr.Textbox(label="状态", interactive=False, max_lines=1)
            parse_result = gr.Markdown(label="解析结果", value="")

        with gr.Column(scale=3):
            gr.Markdown("### 简历列表")
            resume_table = gr.Dataframe(
                headers=["ID", "文件名", "格式", "类型", "默认", "创建时间"],
                datatype=["number", "str", "str", "str", "str", "str"],
                value=_get_resume_list(),
                interactive=False,
            )

            selected_id = gr.Textbox(label="简历 ID", placeholder="输入简历 ID 进行操作")
            with gr.Row():
                view_btn = gr.Button("查看详情", variant="secondary")
                default_btn = gr.Button("设为默认", variant="secondary")
                delete_btn = gr.Button("删除", variant="stop")
                refresh_btn = gr.Button("刷新列表", variant="secondary")

            detail_display = gr.Markdown(value="")

    upload_btn.click(fn=_upload_and_parse, inputs=[file_input], outputs=[status_msg, parse_result, resume_table])
    view_btn.click(fn=_view_resume, inputs=[selected_id], outputs=[detail_display])
    delete_btn.click(fn=_delete_resume, inputs=[selected_id], outputs=[status_msg, resume_table])
    default_btn.click(fn=_set_default, inputs=[selected_id], outputs=[status_msg, resume_table])
    refresh_btn.click(fn=lambda: _get_resume_list(), outputs=[resume_table])
