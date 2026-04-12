"""JD 解析与岗位匹配页面

双栏布局: 左输入 / 右结果, 纯CSS环形图展示匹配分, 标签化差异项。
通过 login_state 实现数据隔离。
"""

from __future__ import annotations

import json
import math

import gradio as gr

from app.agents.jd_agent import jd_match_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD

logger = get_logger(__name__)


def _render_score_ring(score: int) -> str:
    """渲染带动画的 SVG 环形图"""
    if score >= 85:
        color, level, glow = "#00B42A", "高匹配", "rgba(0,180,42,0.2)"
    elif score >= 60:
        color, level, glow = "#FF7D00", "一般匹配", "rgba(255,125,0,0.2)"
    else:
        color, level, glow = "#F53F3F", "低匹配", "rgba(245,63,63,0.2)"

    r = 62
    circumference = 2 * math.pi * r
    offset = circumference - (circumference * score / 100)

    return (
        '<div class="ring-chart-wrap">'
        '<div class="ring-chart">'
        f'<svg width="160" height="160" viewBox="0 0 160 160">'
        f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="#F2F3F5" stroke-width="10"/>'
        f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="{color}" stroke-width="10" '
        f'stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{offset:.1f}" '
        f'stroke-linecap="round" class="animated-ring" '
        f'style="transform:rotate(-90deg);transform-origin:80px 80px;'
        f'filter:drop-shadow(0 0 6px {glow});"/>'
        "</svg>"
        '<div class="rt">'
        f'<div class="rs" style="color:{color}">{score}</div>'
        f'<div class="rl">{level}</div>'
        "</div>"
        "</div>"
        "</div>"
    )


def _render_match_tags(match_items: list, missing_items: list, weak_items: list) -> str:
    """渲染匹配/缺失/薄弱项标签"""
    html = ""

    if match_items:
        html += '<div style="margin-bottom:16px;"><div style="font-size:13px;color:#86909C;margin-bottom:8px;">匹配项</div><div class="match-tags">'
        for s in match_items:
            html += f'<span class="match-tag hit">✓ {s}</span>'
        html += "</div></div>"

    if missing_items:
        html += '<div style="margin-bottom:16px;"><div style="font-size:13px;color:#86909C;margin-bottom:8px;">缺失项</div><div class="match-tags">'
        for s in missing_items:
            html += f'<span class="match-tag miss">✗ {s}</span>'
        html += "</div></div>"

    if weak_items:
        html += '<div style="margin-bottom:16px;"><div style="font-size:13px;color:#86909C;margin-bottom:8px;">薄弱项</div><div class="match-tags">'
        for s in weak_items:
            html += f'<span class="match-tag weak">! {s}</span>'
        html += "</div></div>"

    return html or '<div style="color:#86909C;padding:16px 0;">暂无匹配数据</div>'


def create_jd_match_page(login_state):
    """创建 JD 匹配页面"""
    gr.Markdown("## JD 解析与岗位匹配")

    with gr.Row():
        # 左栏: 输入区
        with gr.Column(scale=2):
            gr.Markdown("### 输入区")
            resume_dropdown = gr.Dropdown(
                choices=[],
                label="选择简历",
                interactive=True,
            )

            def _refresh_choices(state):
                user_name = state.get("user_name", "") if state else ""
                try:
                    resumes = ResumeCRUD.get_all(original_only=True, user_name=user_name)
                    return gr.Dropdown(choices=[f"{r['id']}:{r['file_name']}" for r in resumes])
                except Exception:
                    return gr.Dropdown(choices=[])

            refresh_resume_btn = gr.Button("刷新简历列表", size="sm")
            jd_input = gr.Textbox(
                label="JD 岗位描述",
                placeholder="请粘贴完整的岗位描述文本 (至少 50 字)...",
                lines=12,
            )
            match_btn = gr.Button("开始匹配", variant="primary", size="lg")

        # 右栏: 结果区
        with gr.Column(scale=3):
            gr.Markdown("### 匹配结果")
            score_display = gr.HTML(value='<div style="color:#86909C;padding:24px;text-align:center;">等待匹配...</div>')
            jd_info_display = gr.Markdown(value="")
            gr.Markdown("### 差异分析")
            diff_display = gr.HTML(value="")
            gr.Markdown("### 综合建议")
            feedback_display = gr.Markdown(value="")
            matched_resume = gr.Textbox(visible=False)

    def _do_match(resume_choice, jd_text, state):
        user_name = state.get("user_name", "") if state else ""
        if not resume_choice:
            yield "", "请先选择简历", "", "", ""
            return
        if not jd_text or len(jd_text.strip()) < 50:
            yield "", "JD 文本过短, 请输入至少 50 字的岗位描述", "", "", ""
            return

        yield (
            '<div style="color:#165DFF;padding:24px;text-align:center;">'
            "⏳ 正在调用 AI 匹配分析, 请稍候...</div>",
            "AI 匹配分析中...", "", "", "",
        )

        try:
            resume_id = int(resume_choice.split(":")[0])
            resume = ResumeCRUD.get_by_id(resume_id, user_name=user_name)
            if not resume:
                yield "", "简历不存在", "", "", ""
                return

            resume_struct = json.loads(resume.get("struct_data", "{}"))
            agent_state = {
                "jd_text": jd_text,
                "resume_struct": resume_struct,
                "resume_id": resume_id,
                "user_name": user_name,
            }

            result = jd_match_node(agent_state)
            if result.get("error_code"):
                yield "", f"匹配失败: {result.get('error_msg')}", "", "", ""
                return

            score = result.get("match_score", 0)
            score_html = _render_score_ring(score)

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
            tags_html = _render_match_tags(match_items, missing_items, weak_items)

            feedback_lines = result.get("match_feedback", [])
            feedback = "\n".join(f"- {f}" for f in feedback_lines)
            threshold = get_settings().MATCH_THRESHOLD
            if score < threshold:
                feedback += f"\n\n⚠ 匹配分数低于阈值 ({threshold}), 建议优化简历后再投递"

            yield score_html, jd_info, tags_html, feedback, resume_choice
        except Exception as e:
            logger.error("匹配异常: %s", e)
            yield "", f"匹配异常: {e}", "", "", ""

    refresh_resume_btn.click(
        fn=_refresh_choices,
        inputs=[login_state],
        outputs=[resume_dropdown],
    )
    match_btn.click(
        fn=_do_match,
        inputs=[resume_dropdown, jd_input, login_state],
        outputs=[score_display, jd_info_display, diff_display, feedback_display, matched_resume],
    )
