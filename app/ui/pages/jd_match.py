"""JD 解析与岗位匹配页面

JD 文本输入, 简历选择, 智能匹配打分, 差异项展示。
"""

from __future__ import annotations

import json

import gradio as gr

from app.agents.jd_agent import jd_match_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD

logger = get_logger(__name__)


def _get_resume_choices() -> list[str]:
    """获取简历下拉选项"""
    try:
        resumes = ResumeCRUD.get_all(original_only=True)
        return [f"{r['id']}:{r['file_name']}" for r in resumes]
    except Exception:
        return []


def _do_match(resume_choice, jd_text):
    """执行简历-JD匹配"""
    if not resume_choice:
        return "请先选择简历", "", "", "", ""
    if not jd_text or len(jd_text.strip()) < 50:
        return "JD 文本过短, 请输入至少 50 字的岗位描述", "", "", "", ""

    try:
        resume_id = int(resume_choice.split(":")[0])
        resume = ResumeCRUD.get_by_id(resume_id)
        if not resume:
            return "简历不存在", "", "", "", ""

        resume_struct = json.loads(resume.get("struct_data", "{}"))
        state = {
            "jd_text": jd_text,
            "resume_struct": resume_struct,
            "resume_id": resume_id,
        }

        result = jd_match_node(state)
        if result.get("error_code"):
            return f"匹配失败: {result.get('error_msg')}", "", "", "", ""

        score = result.get("match_score", 0)
        if score >= 85:
            level = "🟢 高匹配"
        elif score >= 60:
            level = "🟡 一般匹配"
        else:
            level = "🔴 低匹配"

        score_text = f"## 匹配分数: {score} 分 ({level})"

        jd_struct = result.get("jd_struct", {})
        jd_info = (
            f"**岗位**: {jd_struct.get('position', '未知')}\n"
            f"**公司**: {jd_struct.get('company', '未知')}\n"
            f"**学历要求**: {jd_struct.get('education', '不限')}\n"
            f"**经验要求**: {jd_struct.get('experience_years', 0)} 年\n"
            f"**技能要求**: {', '.join(jd_struct.get('required_skills', []))}"
        )

        match_items = result.get("match_items", [])
        missing_items = result.get("missing_items", [])
        weak_items = result.get("weak_items", [])

        diff_text = "### 匹配项\n"
        diff_text += ", ".join(f"✅ {s}" for s in match_items) if match_items else "无"
        diff_text += "\n\n### 缺失项\n"
        diff_text += ", ".join(f"❌ {s}" for s in missing_items) if missing_items else "无"
        diff_text += "\n\n### 薄弱项\n"
        diff_text += "\n".join(f"⚠ {s}" for s in weak_items) if weak_items else "无"

        feedback = "\n".join(f"- {f}" for f in result.get("match_feedback", []))

        threshold = get_settings().MATCH_THRESHOLD
        if score < threshold:
            feedback += f"\n\n⚠ 匹配分数低于阈值 ({threshold}), 建议优化简历后再投递"

        return score_text, jd_info, diff_text, feedback, resume_choice
    except Exception as e:
        logger.error("匹配异常: %s", e)
        return f"匹配异常: {e}", "", "", "", ""


def create_jd_match_page():
    """创建 JD 匹配页面"""
    gr.Markdown("## JD 解析与岗位匹配")

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 输入区")
            resume_dropdown = gr.Dropdown(
                choices=_get_resume_choices(),
                label="选择简历",
                interactive=True,
            )
            refresh_resume_btn = gr.Button("刷新简历列表", size="sm")
            jd_input = gr.Textbox(
                label="JD 岗位描述",
                placeholder="请粘贴完整的岗位描述文本 (至少 50 字)...",
                lines=12,
            )
            match_btn = gr.Button("开始匹配", variant="primary", size="lg")

        with gr.Column(scale=3):
            gr.Markdown("### 匹配结果")
            score_display = gr.Markdown(value="等待匹配...")
            jd_info_display = gr.Markdown(value="")
            diff_display = gr.Markdown(value="")
            feedback_display = gr.Markdown(value="")
            matched_resume = gr.Textbox(visible=False)

    refresh_resume_btn.click(
        fn=lambda: gr.update(choices=_get_resume_choices()),
        outputs=[resume_dropdown],
    )
    match_btn.click(
        fn=_do_match,
        inputs=[resume_dropdown, jd_input],
        outputs=[score_display, jd_info_display, diff_display, feedback_display, matched_resume],
    )
