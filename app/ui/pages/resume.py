"""简历管理页面

简历上传、解析、版本管理、预览、导出、删除。
商务极简卡片布局。通过 login_state 实现数据隔离。
"""

from __future__ import annotations

import json

import gradio as gr

from app.agents.resume_agent import parse_resume_node, save_resume_file
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.utils.file_util import format_file_size, save_uploaded_file

logger = get_logger(__name__)


def _get_resume_list(user_name: str = ""):
    """获取当前用户的简历列表数据"""
    try:
        resumes = ResumeCRUD.get_all(user_name=user_name)
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


def create_resume_page(login_state):
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
                value=[],
                interactive=False,
            )

            selected_id = gr.Textbox(
                label="已选简历 ID (点击表格行自动填入)",
                placeholder="点击上方表格任意行选中",
                interactive=True,
            )
            with gr.Row():
                view_btn = gr.Button("查看详情", variant="secondary", scale=1)
                default_btn = gr.Button("设为默认", variant="secondary", scale=1)
                delete_btn = gr.Button("删除", variant="stop", scale=1)
                refresh_btn = gr.Button("刷新列表", variant="secondary", scale=1)

            detail_display = gr.Markdown(value="")

    # ---- 回调 (闭包捕获 login_state) ----

    def _upload_and_parse(file, state):
        user_name = state.get("user_name", "") if state else ""
        if file is None:
            yield "请选择文件", "", _get_resume_list(user_name)
            return

        yield "⏳ 正在上传并解析简历, 请稍候...", "", gr.update()

        try:
            saved_path = save_uploaded_file(file.name if hasattr(file, "name") else str(file))
            agent_state = {"resume_path": saved_path, "user_name": user_name}
            result = parse_resume_node(agent_state)
            if result.get("error_code"):
                yield f"解析失败: {result.get('error_msg', '')}", "", _get_resume_list(user_name)
                return
            struct = result.get("resume_struct", {})
            info_lines = [
                f"**姓名**: {struct.get('name', '未提取')}",
                f"**手机**: {struct.get('phone', '未提取')}",
                f"**邮箱**: {struct.get('email', '未提取')}",
                f"**学历**: {struct.get('education', '未提取')}",
                f"**工作年限**: {struct.get('experience_years', 0)} 年",
                f"**技能**: {', '.join(struct.get('skills', []))}",
            ]
            yield "✓ 解析成功", "\n".join(info_lines), _get_resume_list(user_name)
        except Exception as e:
            logger.error("简历上传失败: %s", e)
            yield f"上传失败: {e}", "", _get_resume_list(user_name)

    def _view_resume(sel_id, state):
        user_name = state.get("user_name", "") if state else ""
        if not sel_id:
            return "请选择简历"
        try:
            resume = ResumeCRUD.get_by_id(int(sel_id), user_name=user_name)
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

    def _delete_resume(sel_id, state):
        user_name = state.get("user_name", "") if state else ""
        if not sel_id:
            return "请选择简历", _get_resume_list(user_name)
        try:
            ok = ResumeCRUD.delete(int(sel_id), user_name=user_name)
            if ok:
                return "✓ 删除成功", _get_resume_list(user_name)
            return "删除失败", _get_resume_list(user_name)
        except Exception as e:
            return f"删除失败: {e}", _get_resume_list(user_name)

    def _set_default(sel_id, state):
        user_name = state.get("user_name", "") if state else ""
        if not sel_id:
            return "请选择简历", _get_resume_list(user_name)
        try:
            ResumeCRUD.set_default(int(sel_id), user_name=user_name)
            return "✓ 已设为默认简历", _get_resume_list(user_name)
        except Exception as e:
            return f"操作失败: {e}", _get_resume_list(user_name)

    def _refresh_list(state):
        user_name = state.get("user_name", "") if state else ""
        return _get_resume_list(user_name)

    def _on_row_select(evt: gr.SelectData, state):
        user_name = state.get("user_name", "") if state else ""
        try:
            data = _get_resume_list(user_name)
            row_idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            if 0 <= row_idx < len(data):
                return str(data[row_idx][0])
        except Exception:
            pass
        return ""

    # ---- 事件绑定 ----
    resume_table.select(fn=_on_row_select, inputs=[login_state], outputs=[selected_id])
    upload_btn.click(
        fn=_upload_and_parse,
        inputs=[file_input, login_state],
        outputs=[status_msg, parse_result, resume_table],
    )
    view_btn.click(fn=_view_resume, inputs=[selected_id, login_state], outputs=[detail_display])
    delete_btn.click(
        fn=_delete_resume,
        inputs=[selected_id, login_state],
        outputs=[status_msg, resume_table],
    )
    default_btn.click(
        fn=_set_default,
        inputs=[selected_id, login_state],
        outputs=[status_msg, resume_table],
    )
    refresh_btn.click(fn=_refresh_list, inputs=[login_state], outputs=[resume_table])
