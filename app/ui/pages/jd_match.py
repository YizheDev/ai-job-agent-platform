"""JD analysis and matching page."""

from __future__ import annotations

import json
import math
from html import escape

import gradio as gr

from app.agents.jd_agent import jd_match_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.ui.view_model import get_ui_snapshot, render_empty_state, render_skeleton_card, tab_switch_js

logger = get_logger(__name__)


def _get_resume_choices() -> list[str]:
    """Return selectable original resumes."""
    try:
        resumes = ResumeCRUD.get_all(original_only=True)
        return [f"{item['id']}:{item['file_name']}" for item in resumes]
    except Exception:
        return []


def _render_score_ring(score: int) -> str:
    """Render the score ring."""
    if score >= 85:
        color, level = "#18B56A", "高匹配"
    elif score >= 60:
        color, level = "#FF9A3C", "中匹配"
    else:
        color, level = "#E35D57", "低匹配"

    radius = 54
    circumference = 2 * math.pi * radius
    offset = circumference - (circumference * score / 100)
    return (
        '<div class="ring-chart-wrap">'
        '<div class="eyebrow" style="margin-bottom:12px;">匹配评分</div>'
        '<div class="ring-chart">'
        '<svg width="140" height="140" viewBox="0 0 140 140">'
        f'<circle cx="70" cy="70" r="{radius}" fill="none" stroke="#E5EAF0" stroke-width="12"/>'
        f'<circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="12" '
        f'stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{offset:.1f}" '
        'stroke-linecap="round" style="transform:rotate(-90deg);transform-origin:70px 70px;"/>'
        "</svg>"
        '<div class="rt">'
        f'<div class="rs" style="color:{color}">{score}</div>'
        f'<div class="rl">{level}</div>'
        "</div></div></div>"
    )


def _render_match_tags(match_items: list, missing_items: list, weak_items: list) -> str:
    """Render match, missing and weak-signal tags."""
    sections = [
        ("已覆盖项", match_items, "hit", "简历中已经被识别到的技能与经历要点"),
        ("缺失项", missing_items, "miss", "建议优先补强的硬性条件"),
        ("薄弱项", weak_items, "weak", "可以通过项目描述和关键词增强的内容"),
    ]
    blocks = []
    for title, items, cls, subtitle in sections:
        if not items:
            continue
        tags = "".join(f'<span class="match-tag {cls}">{escape(str(item))}</span>' for item in items)
        blocks.append(
            f"""
            <div style="margin-bottom:18px;">
                <div class="eyebrow" style="margin-bottom:8px;">{escape(title)}</div>
                <div class="stitch-muted" style="margin-bottom:10px;">{escape(subtitle)}</div>
                <div class="match-tags">{tags}</div>
            </div>
            """
        )
    return "".join(blocks) or render_empty_state(
        "等待分析结果",
        "开始匹配后，这里会显示优势项、缺失项和可补强内容。",
        "建议先粘贴完整 JD 文本。",
        "JD",
    )


def _render_match_metrics(score: int, match_items: list, missing_items: list, weak_items: list) -> str:
    return f"""
    <div class="stitch-stats-4">
        <div class="metric-pill-soft"><div class="label">评分</div><div class="value">{score}</div></div>
        <div class="metric-pill-soft"><div class="label">已匹配</div><div class="value">{len(match_items)}</div></div>
        <div class="metric-pill-soft"><div class="label">缺失项</div><div class="value">{len(missing_items)}</div></div>
        <div class="metric-pill-soft"><div class="label">薄弱项</div><div class="value">{len(weak_items)}</div></div>
    </div>
    """


def _render_feedback_block(feedback_lines: list[str], score: int) -> str:
    if not feedback_lines:
        content = render_empty_state(
            "等待综合建议",
            "分析完成后，这里会生成优化优先级、风险提醒和后续动作建议。",
            "你可以据此判断是否值得进入简历优化。",
            "AI",
        )
    else:
        rows = "".join(
            f'<div class="kv-row"><div class="kv-label">建议</div><div class="kv-value">{escape(item)}</div></div>'
            for item in feedback_lines
        )
        content = f'<div class="kv-list">{rows}</div>'

    threshold = get_settings().MATCH_THRESHOLD
    if score and score < threshold:
        content += (
            f'<div class="feature-note" style="margin-top:16px;">当前匹配分低于系统阈值 {threshold}，'
            "建议先做关键词补强和项目表述优化，再进入投递流程。</div>"
        )
    return content


def _do_match(resume_choice, jd_text):
    """Run JD matching for the selected resume."""
    if not resume_choice:
        return "", "请先选择简历。", "", "", ""
    if not jd_text or len(jd_text.strip()) < 50:
        return "", "JD 文本过短，请至少提供 50 字。", "", "", ""

    try:
        resume_id = int(resume_choice.split(":")[0])
        resume = ResumeCRUD.get_by_id(resume_id)
        if not resume:
            return "", "简历不存在。", "", "", ""

        resume_struct = json.loads(resume.get("struct_data", "{}"))
        result = jd_match_node(
            {
                "jd_text": jd_text,
                "resume_struct": resume_struct,
                "resume_id": resume_id,
            }
        )
        if result.get("error_code"):
            return "", f"匹配失败：{result.get('error_msg')}", "", "", ""

        score = int(result.get("match_score", 0))
        jd_struct = result.get("jd_struct", {})
        match_items = result.get("match_items", [])
        missing_items = result.get("missing_items", [])
        weak_items = result.get("weak_items", [])

        score_html = _render_score_ring(score) + _render_match_metrics(
            score, match_items, missing_items, weak_items
        )
        jd_info = (
            f"**岗位**：{jd_struct.get('position', '未知')}\n"
            f"**公司**：{jd_struct.get('company', '未知')}\n"
            f"**学历要求**：{jd_struct.get('education', '不限')}\n"
            f"**经验要求**：{jd_struct.get('experience_years', 0)} 年\n"
            f"**技能要求**：{', '.join(jd_struct.get('required_skills', [])) or '暂无'}"
        )
        return (
            score_html,
            jd_info,
            _render_match_tags(match_items, missing_items, weak_items),
            _render_feedback_block(result.get("match_feedback", []), score),
            resume_choice,
        )
    except Exception as exc:
        logger.error("JD 匹配异常: %s", exc)
        return "", f"匹配异常：{exc}", "", "", ""


def _match_loading_state():
    skeleton = render_skeleton_card(lines=4, with_block=True, with_pills=True)
    return (
        skeleton,
        render_skeleton_card(lines=4, with_block=False),
        render_skeleton_card(lines=5, with_block=False, with_pills=True),
        render_skeleton_card(lines=5, with_block=False),
    )


def create_jd_match_page():
    """Create the JD match page."""
    snapshot = get_ui_snapshot()
    resume_choices = _get_resume_choices()

    gr.HTML(
        f"""
        <div class="page-shell">
            <div class="page-header">
                <div>
                    <div class="page-subtitle">先拆解岗位要求，再判断这份岗位值不值得投入优化和投递成本。页面采用左侧输入、右侧结果的招聘产品布局。</div>
                    <div class="page-dock">
                        <span class="dock-pill"><strong>可用简历</strong> {len(resume_choices)} 份</span>
                        <span class="dock-pill"><strong>近 7 日均分</strong> {snapshot['avg_score_7d']}</span>
                        <span class="dock-pill"><strong>下一步</strong> 进入简历优化</span>
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
                            <div class="eyebrow">输入区</div>
                            <div class="stitch-panel-title">岗位输入</div>
                        </div>

                    </div>
                    <div class="stitch-muted">选择原始简历后，粘贴完整 JD 文本。系统会输出匹配分、差异项和后续建议。</div>
                    """
                )
                resume_dropdown = gr.Dropdown(choices=resume_choices, label="选择简历", interactive=True)
                refresh_btn = gr.Button("刷新简历列表", variant="secondary")
                jd_text = gr.Textbox(
                    label="JD 岗位描述",
                    lines=12,
                    placeholder="请粘贴完整的岗位描述文本（至少 50 字）...",
                )
                match_btn = gr.Button("开始匹配分析", variant="primary", size="lg")
                optimize_btn = gr.Button("前往简历优化", variant="secondary")



        with gr.Column(elem_classes=["workspace-column"]):
            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">评分结果</div>
                            <div class="stitch-panel-title">匹配评估</div>
                        </div>

                    </div>
                    """
                )
                score_html = gr.HTML(
                    value=render_empty_state("等待开始分析", "导入完整 JD 后开始匹配，评分环和核心指标会出现在这里。", "建议先选择默认简历。", "AI")
                )

            with gr.Row(elem_classes=["workspace-grid-equal"]):
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML(
                            """
                            <div class="stitch-toolbar">
                                <div>
                                    <div class="eyebrow">岗位画像</div>
                                    <div class="stitch-panel-title">JD 拆解结果</div>
                                </div>
        
                            </div>
                            """
                        )
                        jd_info = gr.Markdown(
                            value="等待开始分析\n\n导入完整 JD 后，这里会显示岗位基础信息、技能要求和经验门槛。"
                        )
                with gr.Column():
                    with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                        gr.HTML(
                            """
                            <div class="stitch-toolbar">
                                <div>
                                    <div class="eyebrow">差异分析</div>
                                    <div class="stitch-panel-title">优势与缺口</div>
                                </div>
        
                            </div>
                            """
                        )
                        tags_html = gr.HTML(
                            value=render_empty_state("等待差异分析", "分析完成后会展示匹配项、缺失项和薄弱项。", "这能帮助你决定是否优化简历。", "JD")
                        )

            with gr.Group(elem_classes=["stitch-card", "stitch-section"]):
                gr.HTML(
                    """
                    <div class="stitch-toolbar">
                        <div>
                            <div class="eyebrow">综合建议</div>
                            <div class="stitch-panel-title">下一步动作</div>
                        </div>

                    </div>
                    """
                )
                feedback_html = gr.HTML(
                    value=render_empty_state("等待综合建议", "分析结果会和系统风控阈值联动，帮助你判断是否值得进入简历优化。", "建议优先处理高分岗位。", "GO")
                )
                chosen_resume = gr.Textbox(visible=False)

    refresh_btn.click(fn=lambda: gr.Dropdown(choices=_get_resume_choices()), outputs=[resume_dropdown])
    match_btn.click(
        fn=_match_loading_state,
        outputs=[score_html, jd_info, tags_html, feedback_html],
        queue=False,
        show_progress="hidden",
    ).then(
        fn=_do_match,
        inputs=[resume_dropdown, jd_text],
        outputs=[score_html, jd_info, tags_html, feedback_html, chosen_resume],
        show_progress="minimal",
    )
    optimize_btn.click(fn=None, js=tab_switch_js("简历优化"))
