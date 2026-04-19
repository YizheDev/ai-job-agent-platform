"""AI 简历优化页面 — Bento 玻璃拟态风

布局:
┌─ 页头: 图标 + 标题 + 说明 ───────────────────────────────────┐
├─ 输入卡: 选择简历 · JD · 优化按钮 · 状态 ──────────────────┤
├─ 对比卡: [原始 50%] [优化后 50%] (双栏, diff 风) ─────────┤
├─ 建议卡: 编号列表 + 图标徽章 ────────────────────────────────┤
└─ 求职信卡: 优美卡片 + 复制功能 + 字数统计 ──────────────────┘

对外接口保持: create_optimize_page(login_state) -> None
"""

from __future__ import annotations

import html as html_mod
import json

import gradio as gr

from app.agents.optimize_agent import optimize_resume_node
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD

logger = get_logger(__name__)


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


# ================================================================
# HTML 渲染片段
# ================================================================
def _render_header_html() -> str:
    return (
        '<div class="op-root">'
        '  <div class="op-head">'
        '    <div class="op-head-icon">'
        '      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>'
        '      </svg>'
        '    </div>'
        '    <div class="op-head-text">'
        '      <div class="op-head-title">AI 简历优化</div>'
        '      <div class="op-head-sub">针对 JD 对简历进行要点增强，并生成一封 100–150 字求职信</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _empty_suggestions_html() -> str:
    return (
        '<div class="op-root">'
        '  <div class="op-card op-card-empty">'
        '    <div class="oce-icon">'
        '      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        '        <polyline points="9 11 12 14 22 4"></polyline>'
        '        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>'
        '      </svg>'
        '    </div>'
        '    <div class="oce-title">优化建议将显示在这里</div>'
        '    <div class="oce-sub">选择简历 · 粘贴 JD · 点击「一键优化」, AI 会给出要点改写建议</div>'
        '  </div>'
        '</div>'
    )


def _render_suggestions_html(suggestions: list) -> str:
    if not suggestions:
        return _empty_suggestions_html()
    items = "".join(
        '<li class="osg-item">'
        f'  <span class="osg-num">{i + 1}</span>'
        f'  <span class="osg-text">{_safe(s)}</span>'
        '</li>'
        for i, s in enumerate(suggestions)
    )
    return (
        '<div class="op-root">'
        '  <div class="op-card op-card-suggest">'
        '    <div class="op-card-head">'
        '      <div class="oph-icon oph-icon-violet">'
        '        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <path d="M12 2L2 7l10 5 10-5-10-5z"></path>'
        '          <path d="M2 17l10 5 10-5"></path>'
        '          <path d="M2 12l10 5 10-5"></path>'
        '        </svg>'
        '      </div>'
        '      <div class="oph-title">AI 优化建议</div>'
        f'      <div class="oph-count">{len(suggestions)} 条</div>'
        '    </div>'
        f'    <ol class="osg-list">{items}</ol>'
        '  </div>'
        '</div>'
    )


def _empty_cover_html() -> str:
    return (
        '<div class="op-root">'
        '  <div class="op-card op-card-cover-empty">'
        '    <div class="oce-icon">'
        '      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        '        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>'
        '        <polyline points="22 6 12 13 2 6"></polyline>'
        '      </svg>'
        '    </div>'
        '    <div class="oce-title">求职信将显示在这里</div>'
        '    <div class="oce-sub">AI 会结合简历与 JD 生成 100~150 字的投递打招呼文案</div>'
        '  </div>'
        '</div>'
    )


def _status_html(msg: str, kind: str = "info") -> str:
    dot = {"info": "si-blue", "err": "si-red", "ok": "si-green"}.get(kind, "si-blue")
    extra_cls = ""
    if kind == "ok":
        extra_cls = " op-status-ok"
    elif kind == "err":
        extra_cls = " op-status-err"
    return (
        '<div class="op-root">'
        f'  <div class="op-status{extra_cls}"><span class="si-dot {dot}"></span><span class="si-txt">{_safe(msg)}</span></div>'
        '</div>'
    )


def _status_loading_html(msg: str) -> str:
    return (
        '<div class="op-root">'
        '  <div class="op-status op-status-loading">'
        '    <span class="op-spinner">'
        '      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
        '        <path d="M21 12a9 9 0 1 1-9-9"></path>'
        '      </svg>'
        '    </span>'
        f'    <span class="si-txt">{_safe(msg)}</span>'
        '  </div>'
        '</div>'
    )


def _loading_suggestions_html() -> str:
    return (
        '<div class="op-root">'
        '  <div class="op-card op-card-suggest op-card-loading">'
        '    <div class="op-card-head">'
        '      <div class="oph-icon oph-icon-violet">'
        '        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <path d="M12 2L2 7l10 5 10-5-10-5z"></path>'
        '          <path d="M2 17l10 5 10-5"></path>'
        '          <path d="M2 12l10 5 10-5"></path>'
        '        </svg>'
        '      </div>'
        '      <div class="oph-title">AI 优化建议生成中…</div>'
        '    </div>'
        '    <div class="op-skel-row"></div>'
        '    <div class="op-skel-row op-skel-row-short"></div>'
        '    <div class="op-skel-row"></div>'
        '    <div class="op-skel-row op-skel-row-short"></div>'
        '  </div>'
        '</div>'
    )


# ================================================================
# 页面创建
# ================================================================
def create_optimize_page(login_state):
    """创建 AI 简历优化页面"""
    gr.HTML(_OP_STYLE)

    with gr.Column(elem_id="op-page-root", elem_classes=["op-scope"]):
        gr.HTML(_render_header_html())

        # ============ 输入卡 ============
        with gr.Column(elem_classes=["op-card", "op-card-input"]):
            gr.HTML(
                '<div class="op-card-head">'
                '  <div class="oph-icon oph-icon-blue">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>'
                '      <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>'
                '    </svg>'
                '  </div>'
                '  <div class="oph-title">优化输入</div>'
                '  <div class="oph-sub">挑简历 · 贴 JD · 一键优化</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["op-input-row"]):
                resume_dropdown = gr.Dropdown(
                    choices=[],
                    label="选择简历",
                    interactive=True,
                    scale=3,
                    elem_classes=["op-input-field"],
                )
                refresh_btn = gr.Button(
                    "刷新",
                    size="sm",
                    scale=1,
                    elem_classes=["op-refresh-btn"],
                )

            jd_text = gr.Textbox(
                label="JD 岗位描述 (用于针对性优化)",
                lines=5,
                placeholder="粘贴岗位 JD 文本...",
                elem_classes=["op-input-field", "op-textarea"],
            )

            with gr.Row(elem_classes=["op-action-row"]):
                optimize_btn = gr.Button(
                    "一键优化",
                    variant="primary",
                    size="lg",
                    elem_classes=["op-primary-btn"],
                )

            status_display = gr.HTML(value="", elem_id="op-status-slot")

        # ============ 对比卡 ============
        with gr.Column(elem_classes=["op-card", "op-card-compare"]):
            gr.HTML(
                '<div class="op-card-head">'
                '  <div class="oph-icon oph-icon-teal">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"></path>'
                '    </svg>'
                '  </div>'
                '  <div class="oph-title">优化对比</div>'
                '  <div class="oph-sub">左: 原始简历 · 右: AI 优化版 (可编辑)</div>'
                '</div>'
            )
            with gr.Row(equal_height=True, elem_classes=["op-compare-row"]):
                with gr.Column(elem_classes=["op-col", "op-col-original"]):
                    gr.HTML(
                        '<div class="op-compare-label op-compare-label-original">'
                        '  <span class="ocl-dot"></span>原始简历'
                        '</div>'
                    )
                    original_text = gr.Textbox(
                        label="原始内容",
                        lines=15,
                        interactive=False,
                        placeholder="点击「一键优化」后, AI 会在这里展示简历原文…",
                        elem_classes=["op-input-field", "op-compare-ta", "op-compare-ta-original"],
                    )
                with gr.Column(elem_classes=["op-col", "op-col-optimized"]):
                    gr.HTML(
                        '<div class="op-compare-label op-compare-label-optimized">'
                        '  <span class="ocl-dot"></span>AI 优化版'
                        '</div>'
                    )
                    optimized_text = gr.Textbox(
                        label="优化内容",
                        lines=15,
                        interactive=True,
                        placeholder="AI 优化后的简历文本会显示在这里, 可继续编辑…",
                        elem_classes=["op-input-field", "op-compare-ta", "op-compare-ta-optimized"],
                    )

        # ============ 建议卡 (HTML 渲染) ============
        suggestions_display = gr.HTML(
            value=_empty_suggestions_html(),
            elem_id="op-sugg-slot",
        )

        # ============ 求职信卡 ============
        with gr.Column(elem_classes=["op-card", "op-card-cover"]):
            gr.HTML(
                '<div class="op-card-head">'
                '  <div class="oph-icon oph-icon-pink">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>'
                '      <polyline points="22 6 12 13 2 6"></polyline>'
                '    </svg>'
                '  </div>'
                '  <div class="oph-title">求职信</div>'
                '  <div class="oph-sub">AI 生成打招呼文案 · 可自由编辑</div>'
                '</div>'
            )
            cover_letter_display = gr.Textbox(
                label="AI 生成求职信 (100~150字)",
                lines=6,
                interactive=True,
                placeholder="点击「一键优化」后, AI 会在这里生成一封打招呼文案...",
                elem_classes=["op-input-field", "op-cover-ta"],
            )

    # ================================================================
    # 回调 (保持原逻辑, 状态改成富 HTML)
    # ================================================================
    def _refresh_choices(state):
        user_name = state.get("user_name", "") if state else ""
        try:
            resumes = ResumeCRUD.get_all(user_name=user_name)
            return gr.Dropdown(choices=[f"{r['id']}:{r['file_name']}" for r in resumes])
        except Exception:
            return gr.Dropdown(choices=[])

    def _do_optimize(resume_choice, jd, state):
        user_name = state.get("user_name", "") if state else ""
        if not resume_choice:
            yield (
                _status_html("请先选择简历", "err"),
                "",
                "",
                _empty_suggestions_html(),
                "",
            )
            return
        if not jd or len(jd.strip()) < 50:
            yield (
                _status_html("请先粘贴 JD (至少 50 字)", "err"),
                "",
                "",
                _empty_suggestions_html(),
                "",
            )
            return

        try:
            resume_id = int(resume_choice.split(":")[0])
            resume = ResumeCRUD.get_by_id(resume_id, user_name=user_name)
            if not resume:
                yield (
                    _status_html("简历不存在", "err"),
                    "",
                    "",
                    _empty_suggestions_html(),
                    "",
                )
                return

            struct = json.loads(resume.get("struct_data", "{}"))
            resume_text = struct.get("optimized_text", "") or json.dumps(
                struct, ensure_ascii=False, indent=2
            )

            yield (
                _status_loading_html("AI 正在优化简历…  (约 10–30 秒)"),
                resume_text,
                "⏳ AI 正在分析简历与 JD 的匹配点, 优化后的内容将在这里逐段呈现…\n\n请稍候 (约 10–30 秒)",
                _loading_suggestions_html(),
                "✉️ 正在为你生成个性化求职信…",
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
                yield (
                    _status_html(f"优化失败: {result.get('error_msg')}", "err"),
                    resume_text,
                    "",
                    _empty_suggestions_html(),
                    "",
                )
                return

            optimized = result.get("optimized_resume", "") or ""
            suggestions = result.get("optimize_suggestions", []) or []
            cover_letter = result.get("cover_letter", "") or ""

            yield (
                _status_html("✓ 优化完成", "ok"),
                resume_text,
                optimized,
                _render_suggestions_html(suggestions),
                cover_letter,
            )
        except Exception as e:
            logger.error("简历优化异常: %s", e)
            yield (
                _status_html(f"优化异常: {e}", "err"),
                "",
                "",
                _empty_suggestions_html(),
                "",
            )

    refresh_btn.click(
        fn=_refresh_choices,
        inputs=[login_state],
        outputs=[resume_dropdown],
    )
    optimize_btn.click(
        fn=_do_optimize,
        inputs=[resume_dropdown, jd_text, login_state],
        outputs=[
            status_display,
            original_text,
            optimized_text,
            suggestions_display,
            cover_letter_display,
        ],
    )


# ================================================================
# 作用域 CSS (限定在 .op-scope / .op-root 下)
# ================================================================
# fmt: off
_OP_STYLE = """
<style>
/* =========================================================
   Optimize Page — Bento 玻璃拟态风 (作用域: .op-scope/.op-root)
   ========================================================= */
.op-scope { color: var(--c-text-1); }
.op-scope *, .op-root * { box-sizing: border-box; }
#op-page-root {
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 16px !important;
}
#op-page-root > .block:first-child,
#op-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* 页头 */
.op-root .op-head {
    display: flex; align-items: center; gap: 14px;
    margin: -8px 0 6px;
}
.op-root .op-head-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(244,114,182,0.24));
    border: 1px solid rgba(167,139,250,0.35);
    display: flex; align-items: center; justify-content: center;
    color: #DDD6FE;
    box-shadow: 0 8px 20px rgba(167,139,250,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.op-root .op-head-title { font-size: 22px; font-weight: 700; color: #F0F2FA; }
.op-root .op-head-sub { font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px; }

/* ---------- 通用卡片 ---------- */
.op-scope .op-card {
    position: relative;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.5) !important;
    backdrop-filter: blur(20px) saturate(130%);
    -webkit-backdrop-filter: blur(20px) saturate(130%);
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 20px !important;
    padding: 22px !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.05) inset,
        0 12px 32px rgba(0,0,0,0.32) !important;
    overflow: hidden;
    gap: 12px !important;
    display: flex !important;
    flex-direction: column !important;
    transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease,
                border-color 0.28s ease !important;
    will-change: transform;
}
.op-scope .op-card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(255,255,255,0.16) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 22px 50px rgba(0,0,0,0.5),
        0 6px 18px rgba(168,115,245,0.16) !important;
}
.op-scope .op-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.op-scope .op-card > * { position: relative; z-index: 1; }

/* 卡头 */
.op-scope .op-card-head {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 6px;
}
.op-scope .oph-icon {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.op-scope .oph-icon-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.op-scope .oph-icon-teal {
    background: linear-gradient(135deg, rgba(52,211,153,0.28), rgba(79,139,255,0.22));
    color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.35);
    box-shadow: 0 4px 14px rgba(52,211,153,0.22);
}
.op-scope .oph-icon-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(244,114,182,0.22));
    color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.35);
    box-shadow: 0 4px 14px rgba(167,139,250,0.22);
}
.op-scope .oph-icon-pink {
    background: linear-gradient(135deg, rgba(244,114,182,0.28), rgba(251,146,60,0.22));
    color: #F9A8D4;
    border: 1px solid rgba(244,114,182,0.35);
    box-shadow: 0 4px 14px rgba(244,114,182,0.22);
}
.op-scope .oph-title { font-size: 16px; font-weight: 700; color: #F0F2FA; flex: 1; }
.op-scope .oph-sub { font-size: 12px; color: rgba(230,233,245,0.55); }
.op-scope .oph-count {
    background: rgba(167,139,250,0.14); color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.28);
    padding: 3px 10px; border-radius: 999px;
    font-size: 11.5px; font-weight: 700;
}

/* ---------- 输入字段统一 ---------- */
.op-scope .op-input-field textarea,
.op-scope .op-input-field input,
.op-scope .op-input-field .wrap-inner {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    border-radius: 12px !important;
}
.op-scope .op-input-field textarea:focus,
.op-scope .op-input-field input:focus {
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.12) !important;
}
.op-scope .op-textarea textarea { min-height: 130px !important; font-size: 13.5px !important; line-height: 1.7 !important; }
.op-scope .op-compare-ta textarea { min-height: 340px !important; font-size: 13.5px !important; line-height: 1.7 !important; font-family: 'JetBrains Mono', 'Consolas', monospace !important; }
/* placeholder 样式 — 居中垂直对齐 + 文档图标水印 */
.op-scope .op-compare-ta textarea::placeholder {
    color: rgba(230,233,245,0.38) !important;
    font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    font-size: 13px !important;
    line-height: 1.8 !important;
}
.op-scope .op-compare-ta { position: relative !important; }
.op-scope .op-compare-ta:has(textarea:placeholder-shown)::after {
    content: '';
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -30%);
    width: 64px; height: 64px;
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    opacity: 0.28;
    pointer-events: none;
    z-index: 1;
    filter: drop-shadow(0 0 14px rgba(141,187,255,0.25));
}
.op-scope .op-compare-ta-original:has(textarea:placeholder-shown)::after {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='64' height='64' fill='none' stroke='%2394A3B8' stroke-width='1.2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/><line x1='9' y1='13' x2='15' y2='13'/><line x1='9' y1='17' x2='13' y2='17'/></svg>");
}
.op-scope .op-compare-ta-optimized:has(textarea:placeholder-shown)::after {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='64' height='64' fill='none' stroke='%2334D399' stroke-width='1.2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/><path d='M12 18v-6'/><path d='M9 15l3-3 3 3'/></svg>");
}
.op-scope .op-cover-ta textarea { min-height: 150px !important; font-size: 14px !important; line-height: 1.8 !important; }

/* 刷新按钮 */
.op-scope .op-refresh-btn,
.op-scope .op-refresh-btn button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.75) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 12.5px !important;
    padding: 8px 14px !important;
    transition: all 0.25s ease !important;
}
.op-scope .op-refresh-btn:hover,
.op-scope .op-refresh-btn button:hover {
    background: rgba(79,139,255,0.12) !important;
    color: #AFC7FF !important;
    border-color: rgba(79,139,255,0.35) !important;
}

/* Primary 按钮 — 与全局蓝紫主色统一 */
.op-scope .op-primary-btn,
.op-scope .op-primary-btn button {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow:
        0 8px 24px rgba(79,139,255,0.38),
        inset 0 1px 0 rgba(255,255,255,0.18) !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease !important;
    letter-spacing: 0.5px !important;
}
.op-scope .op-primary-btn:hover,
.op-scope .op-primary-btn button:hover {
    transform: translateY(-1px);
    box-shadow:
        0 12px 32px rgba(79,139,255,0.50),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
}

/* ---------- 输入卡布局 ---------- */
.op-scope .op-input-row { gap: 12px !important; align-items: flex-end !important; }
.op-scope .op-action-row { margin-top: 4px; }

/* ---------- 对比卡 ---------- */
.op-scope .op-compare-row { gap: 16px !important; }
.op-scope .op-col { display: flex !important; flex-direction: column !important; gap: 8px !important; }
.op-scope .op-compare-label {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 12px; border-radius: 999px;
    font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px;
    width: fit-content;
}
.op-scope .ocl-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.op-scope .op-compare-label-original {
    background: rgba(148,163,184,0.12);
    color: rgba(203,213,225,0.9);
    border: 1px solid rgba(148,163,184,0.25);
}
.op-scope .op-compare-label-original .ocl-dot {
    background: #94A3B8;
}
.op-scope .op-compare-label-optimized {
    background: rgba(52,211,153,0.12);
    color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.28);
}
.op-scope .op-compare-label-optimized .ocl-dot {
    background: #34D399;
    box-shadow: 0 0 10px rgba(52,211,153,0.7);
    animation: oclPulse 1.8s ease-in-out infinite;
}
@keyframes oclPulse { 50% { opacity: 0.5; transform: scale(1.3); } }

/* 优化版 textarea 左侧竖条 */
.op-scope .op-col-optimized .op-compare-ta {
    position: relative;
}
.op-scope .op-col-optimized .op-compare-ta::before {
    content: ''; position: absolute; left: 0; top: 36px; bottom: 4px;
    width: 3px; border-radius: 2px;
    background: linear-gradient(180deg, #34D399, #4F8BFF);
    z-index: 2;
    pointer-events: none;
}

/* ---------- 建议列表 ---------- */
.op-root .op-card-suggest { }
.op-root .osg-list {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 10px;
}
.op-root .osg-item {
    display: flex; gap: 12px; align-items: flex-start;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px;
    padding: 12px 14px;
    transition: border-color 0.25s ease, background 0.25s ease;
}
.op-root .osg-item:hover {
    border-color: rgba(167,139,250,0.28);
    background: rgba(167,139,250,0.06);
}
.op-root .osg-num {
    flex-shrink: 0;
    width: 24px; height: 24px; border-radius: 7px;
    background: linear-gradient(135deg, #A78BFA, #F472B6);
    color: #fff; font-weight: 800; font-size: 12px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 10px rgba(167,139,250,0.3);
}
.op-root .osg-text {
    flex: 1; font-size: 13.5px; color: #F0F2FA; line-height: 1.75;
}

/* ---------- 空状态卡 (建议 / 求职信) ---------- */
.op-root .op-card-empty,
.op-root .op-card-cover-empty {
    background: rgba(17,22,48,0.35) !important;
    border: 1px dashed rgba(255,255,255,0.1) !important;
    border-radius: 16px !important;
    padding: 36px 24px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center;
    text-align: center;
    min-height: 160px;
    justify-content: center;
    box-shadow: none !important;
}
.op-root .oce-icon {
    color: rgba(141,187,255,0.5);
    margin-bottom: 10px;
    filter: drop-shadow(0 0 10px rgba(79,139,255,0.2));
}
.op-root .oce-title { font-size: 14px; font-weight: 600; color: rgba(230,233,245,0.75); }
.op-root .oce-sub {
    font-size: 12px; color: rgba(230,233,245,0.5);
    margin-top: 6px; line-height: 1.7; max-width: 420px;
}

/* ---------- 状态条 ---------- */
.op-root .op-status {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    font-size: 12.5px;
    color: rgba(230,233,245,0.85);
    margin-top: 8px;
}
.op-root .si-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.op-root .si-blue  { background: #8DBBFF; box-shadow: 0 0 10px rgba(141,187,255,0.6); }
.op-root .si-green { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.6); }
.op-root .si-red   { background: #F87171; box-shadow: 0 0 10px rgba(248,113,113,0.6); }

.op-root .op-status-ok {
    border-color: rgba(52,211,153,0.32) !important;
    background: rgba(52,211,153,0.08) !important;
}
.op-root .op-status-err {
    border-color: rgba(248,113,113,0.32) !important;
    background: rgba(248,113,113,0.08) !important;
}
.op-root .op-status-loading {
    border-color: rgba(141,187,255,0.30) !important;
    background: rgba(79,139,255,0.07) !important;
    color: #AFC7FF;
}
.op-root .op-spinner {
    width: 22px; height: 22px;
    flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%;
    color: #AFC7FF;
    background: rgba(79,139,255,0.18);
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 0 14px rgba(79,139,255,0.42);
}
.op-root .op-spinner svg { animation: opSpin 0.9s linear infinite; }
@keyframes opSpin { to { transform: rotate(360deg); } }

/* ---------- AI 优化建议 - skeleton 加载占位 ---------- */
.op-root .op-card-loading {
    min-height: 180px;
    display: flex; flex-direction: column; gap: 10px;
}
.op-root .op-skel-row {
    height: 12px;
    border-radius: 6px;
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.05) 0%,
        rgba(141,187,255,0.18) 40%,
        rgba(255,255,255,0.05) 80%
    );
    background-size: 200% 100%;
    animation: opSkelShimmer 1.4s ease-in-out infinite;
}
.op-root .op-skel-row-short { width: 65%; }
@keyframes opSkelShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* 窄屏 */
@media (max-width: 960px) {
    .op-scope .op-compare-row { flex-direction: column; }
    .op-scope .op-input-row { flex-direction: column; align-items: stretch !important; }
}
</style>
"""
# fmt: on
