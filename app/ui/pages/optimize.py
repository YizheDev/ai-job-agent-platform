"""AI 简历优化页面

岗位信息 → 双栏对比 → 优化建议 → 求职信, 商务极简。
通过 login_state 实现数据隔离。
"""

from __future__ import annotations

import json

import gradio as gr

from app.agents.optimize_agent import optimize_resume_node
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD

logger = get_logger(__name__)


def create_optimize_page(login_state):
    """创建 AI 简历优化页面"""
    gr.Markdown("## AI 简历优化")

    with gr.Row():
        resume_dropdown = gr.Dropdown(
            choices=[],
            label="选择简历",
            interactive=True,
            scale=2,
        )

        def _refresh_choices(state):
            user_name = state.get("user_name", "") if state else ""
            try:
                resumes = ResumeCRUD.get_all(user_name=user_name)
                return gr.Dropdown(choices=[f"{r['id']}:{r['file_name']}" for r in resumes])
            except Exception:
                return gr.Dropdown(choices=[])

        gr.Button("刷新", size="sm", scale=0).click(
            fn=_refresh_choices,
            inputs=[login_state],
            outputs=[resume_dropdown],
        )

    jd_text = gr.Textbox(
        label="JD 岗位描述 (用于针对性优化)",
        lines=5,
        placeholder="粘贴 JD 文本...",
    )
    optimize_btn = gr.Button("一键优化", variant="primary", size="lg")
    status = gr.Textbox(label="状态", interactive=False, max_lines=1)

    # 双栏对比
    gr.Markdown("### 优化对比")
    with gr.Row(equal_height=True):
        with gr.Column():
            gr.Markdown("**原始简历**")
            original_text = gr.Textbox(
                label="原始内容", lines=15, interactive=False,
            )
        with gr.Column():
            gr.Markdown("**优化后简历**")
            optimized_text = gr.Textbox(
                label="优化内容", lines=15, interactive=True,
            )

    # 优化建议
    gr.Markdown("### 优化建议")
    suggestions_display = gr.Markdown(value="")

    # 求职信
    gr.Markdown("### 求职信")
    cover_letter_display = gr.Textbox(
        label="AI 生成求职信 (100~150字)",
        lines=6,
        interactive=True,
    )

    def _do_optimize(resume_choice, jd, state):
        user_name = state.get("user_name", "") if state else ""
        if not resume_choice:
            return "请先选择简历", "", "", "", ""
        if not jd or len(jd.strip()) < 50:
            return "请先完成 JD 匹配", "", "", "", ""

        try:
            resume_id = int(resume_choice.split(":")[0])
            resume = ResumeCRUD.get_by_id(resume_id)
            if not resume:
                return "简历不存在", "", "", "", ""

            struct = json.loads(resume.get("struct_data", "{}"))
            resume_text = struct.get("optimized_text", "") or json.dumps(
                struct, ensure_ascii=False, indent=2
            )

            agent_state = {
                "resume_text": resume_text,
                "jd_text": jd,
                "resume_struct": struct,
                "jd_struct": {},
                "missing_items": [],
                "weak_items": [],
                "resume_id": resume_id,
                "user_name": user_name,
            }

            result = optimize_resume_node(agent_state)
            if result.get("error_code"):
                return f"优化失败: {result.get('error_msg')}", resume_text, "", "", ""

            optimized = result.get("optimized_resume", "")
            suggestions = result.get("optimize_suggestions", [])
            cover_letter = result.get("cover_letter", "")

            suggestion_text = "\n\n".join(
                f"**{i + 1}. {s}**" for i, s in enumerate(suggestions)
            )

            return "✓ 优化完成", resume_text, optimized, suggestion_text, cover_letter
        except Exception as e:
            logger.error("简历优化异常: %s", e)
            return f"优化异常: {e}", "", "", "", ""

    optimize_btn.click(
        fn=_do_optimize,
        inputs=[resume_dropdown, jd_text, login_state],
        outputs=[
            status,
            original_text,
            optimized_text,
            suggestions_display,
            cover_letter_display,
        ],
    )
