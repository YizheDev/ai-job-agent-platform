"""JD 解析与岗位匹配页面 — Bento 玻璃拟态风

布局:
┌─ 页头: 图标 + 标题 + 说明 ──────────────────────────────────┐
├─ 左输入卡 (40%) ┆ 右结果区 (60%) ─────────────────────────┤
│  · 选择简历         │ · 得分 Hero 卡 (环形分 + 等级徽章)      │
│  · JD 文本域        │ · JD 基本信息 6 格 chips                │
│  · 开始匹配 按钮    │ · 匹配 / 缺失 / 薄弱 三列标签            │
│                    │ · 综合建议 列表                          │
└─ 保留对外接口: create_jd_match_page(login_state)
"""

from __future__ import annotations

import html as html_mod
import json
import math

import gradio as gr

from app.agents.jd_agent import jd_match_node
from app.core.config import get_settings
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
        '<div class="jd-root">'
        '  <div class="jd-head">'
        '    <div class="jd-head-icon">'
        '      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <circle cx="11" cy="11" r="8"></circle>'
        '        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>'
        '      </svg>'
        '    </div>'
        '    <div class="jd-head-text">'
        '      <div class="jd-head-title">JD 解析与岗位匹配</div>'
        '      <div class="jd-head-sub">选择简历 · 粘贴岗位 JD · AI 生成匹配分、差异分析与建议</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _empty_score_html() -> str:
    return (
        '<div class="jd-root">'
        '  <div class="score-hero score-empty">'
        '    <div class="se-ring">'
        '      <svg viewBox="0 0 160 160" width="140" height="140">'
        '        <circle cx="80" cy="80" r="62" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>'
        '        <circle cx="80" cy="80" r="62" fill="none" stroke="rgba(141,187,255,0.18)" stroke-width="10" '
        '                stroke-dasharray="60 360" stroke-linecap="round" '
        '                style="transform:rotate(-90deg);transform-origin:80px 80px;" class="se-spin"/>'
        '      </svg>'
        '      <div class="se-center">'
        '        <div class="se-mark">'
        '          <svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '            <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5L12 3Z"></path>'
        '            <path d="M19 14L19.8 16.2L22 17L19.8 17.8L19 20L18.2 17.8L16 17L18.2 16.2L19 14Z"></path>'
        '            <path d="M5 3L5.6 4.6L7 5L5.6 5.4L5 7L4.4 5.4L3 5L4.4 4.6L5 3Z"></path>'
        '          </svg>'
        '        </div>'
        '      </div>'
        '    </div>'
        '    <div class="se-title">等待匹配</div>'
        '    <div class="se-sub">选择一份简历并粘贴完整 JD (≥50 字)，点击「开始匹配」让 AI 打分</div>'
        '  </div>'
        '</div>'
    )


def _loading_score_html() -> str:
    return (
        '<div class="jd-root">'
        '  <div class="score-hero score-loading">'
        '    <div class="jdl-spinner"></div>'
        '    <div class="jdl-title">AI 正在匹配分析…</div>'
        '    <div class="jdl-sub">解析 JD 结构、比对技能、计算匹配分</div>'
        '  </div>'
        '</div>'
    )


def _render_score_hero(score: int, jd_struct: dict | None = None) -> str:
    """得分 Hero 卡: 环形图 + 等级徽章 + JD 基本信息 chips."""
    if score >= 85:
        color = "#34D399"
        level = "高匹配"
        glow = "rgba(52,211,153,0.40)"
        grad_cls = "sh-green"
        advice = "简历与岗位高度契合，建议直接投递"
    elif score >= 60:
        color = "#FB923C"
        level = "中等匹配"
        glow = "rgba(251,146,60,0.40)"
        grad_cls = "sh-orange"
        advice = "存在若干差距，建议先针对性优化再投递"
    else:
        color = "#F87171"
        level = "低匹配"
        glow = "rgba(248,113,113,0.40)"
        grad_cls = "sh-red"
        advice = "差距较大，不建议直投，可先尝试优化或换岗"

    r = 62
    circumference = 2 * math.pi * r
    offset = circumference - (circumference * max(0, min(100, score)) / 100)

    jd_struct = jd_struct or {}
    chips = []
    skills = jd_struct.get("required_skills", []) or []
    pairs = [
        ("岗位", jd_struct.get("position", "—")),
        ("公司", jd_struct.get("company", "—")),
        ("学历要求", jd_struct.get("education", "不限")),
        ("经验要求", f'{jd_struct.get("experience_years", 0)} 年'),
    ]
    for k, v in pairs:
        chips.append(
            f'<div class="jd-info-chip"><span class="ji-key">{_safe(k)}</span><span class="ji-val">{_safe(v)}</span></div>'
        )
    skills_html = (
        "".join(f'<span class="chip chip-blue">{_safe(s)}</span>' for s in skills[:12])
        or '<span class="chip chip-muted">未提取技能要求</span>'
    )

    return (
        '<div class="jd-root">'
        f'  <div class="score-hero {grad_cls}">'
        '    <div class="sh-left">'
        '      <div class="sh-ring-wrap">'
        '        <svg viewBox="0 0 160 160" width="160" height="160">'
        '          <circle cx="80" cy="80" r="62" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>'
        f'          <circle cx="80" cy="80" r="62" fill="none" stroke="{color}" stroke-width="10" '
        f'                  stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{offset:.1f}" '
        f'                  stroke-linecap="round" class="sh-animate" '
        f'                  style="transform:rotate(-90deg);transform-origin:80px 80px;'
        f'filter:drop-shadow(0 0 12px {glow});"/>'
        '        </svg>'
        '        <div class="sh-center">'
        f'          <div class="sh-score" style="color:{color}">{score}</div>'
        '          <div class="sh-score-unit">/100</div>'
        '        </div>'
        '      </div>'
        f'      <div class="sh-badge" style="background:{color}22;color:{color};border-color:{color}55;">{level}</div>'
        f'      <div class="sh-advice">{advice}</div>'
        '    </div>'
        '    <div class="sh-right">'
        '      <div class="sh-section-title">岗位信息</div>'
        f'      <div class="jd-info-grid">{"".join(chips)}</div>'
        '      <div class="sh-section-title sh-mt">技能要求</div>'
        f'      <div class="jd-info-skills">{skills_html}</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _render_tags_panel(match_items: list, missing_items: list, weak_items: list) -> str:
    """差异分析三列: 匹配/缺失/薄弱."""
    def _col(title: str, items: list, cls: str, icon_svg: str, empty_tip: str) -> str:
        if items:
            tags = "".join(
                f'<span class="dtag {cls}">{icon_svg}<span class="dtag-txt">{_safe(it)}</span></span>'
                for it in items
            )
        else:
            tags = f'<div class="dtag-empty">{_safe(empty_tip)}</div>'
        return (
            f'<div class="diff-col diff-{cls}">'
            f'  <div class="diff-col-head">'
            f'    <span class="diff-col-title">{_safe(title)}</span>'
            f'    <span class="diff-col-count">{len(items)}</span>'
            '  </div>'
            f'  <div class="diff-col-body">{tags}</div>'
            '</div>'
        )

    icon_hit = '<svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8 7 12 13 4"></polyline></svg>'
    icon_miss = '<svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="4" x2="12" y2="12"></line><line x1="12" y1="4" x2="4" y2="12"></line></svg>'
    icon_weak = '<svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="3" x2="8" y2="10"></line><circle cx="8" cy="13" r="0.6" fill="currentColor"></circle></svg>'

    body = (
        _col("匹配项", match_items, "hit", icon_hit, "暂无明显匹配项")
        + _col("缺失项", missing_items, "miss", icon_miss, "没有关键缺失 🎉")
        + _col("薄弱项", weak_items, "weak", icon_weak, "暂无薄弱项")
    )

    return (
        '<div class="jd-root">'
        '  <div class="diff-card">'
        '    <div class="diff-card-head">'
        '      <div class="dch-icon">'
        '        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>'
        '        </svg>'
        '      </div>'
        '      <div class="dch-title">差异分析</div>'
        '      <div class="dch-sub">逐项对比简历与 JD 的契合度</div>'
        '    </div>'
        f'    <div class="diff-cols">{body}</div>'
        '  </div>'
        '</div>'
    )


def _empty_diff_html() -> str:
    return (
        '<div class="jd-root">'
        '  <div class="diff-card diff-empty">'
        '    <div class="de-icon">'
        '      <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        '        <circle cx="11" cy="11" r="8"></circle>'
        '        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>'
        '      </svg>'
        '    </div>'
        '    <div class="de-title">差异分析将显示在这里</div>'
        '    <div class="de-sub">匹配项 / 缺失项 / 薄弱项 三列逐项对比</div>'
        '  </div>'
        '</div>'
    )


def _loading_diff_html() -> str:
    """skeleton 占位: 三列灰条 + 闪光."""
    col = (
        '<div class="diff-skel-col" aria-hidden="true">'
        '  <div class="diff-skel-bar diff-skel-bar-head"></div>'
        '  <div class="diff-skel-bar"></div>'
        '  <div class="diff-skel-bar diff-skel-bar-short"></div>'
        '  <div class="diff-skel-bar"></div>'
        '  <div class="diff-skel-bar diff-skel-bar-short"></div>'
        '</div>'
    )
    return (
        '<div class="jd-root">'
        '  <div class="diff-card diff-loading" role="status" aria-live="polite" aria-busy="true" aria-label="正在分析简历与 JD 差异">'
        '    <div class="diff-skel-grid">'
        f'    {col}{col}{col}'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _loading_feedback_html() -> str:
    return (
        '<div class="jd-root">'
        '  <div class="fb-card fb-card-loading" role="status" aria-live="polite" aria-busy="true" aria-label="正在生成综合建议">'
        '    <div class="fb-skel-row" aria-hidden="true"></div>'
        '    <div class="fb-skel-row fb-skel-row-short" aria-hidden="true"></div>'
        '    <div class="fb-skel-row" aria-hidden="true"></div>'
        '  </div>'
        '</div>'
    )


def _render_feedback_html(feedback_lines: list, score: int, threshold: int) -> str:
    """综合建议: 编号列表 + 可选阈值警告 banner."""
    items = "".join(
        f'<li class="fb-item"><span class="fb-num">{i + 1}</span><span class="fb-txt">{_safe(f)}</span></li>'
        for i, f in enumerate(feedback_lines)
    )
    if not items:
        body = '<div class="fb-empty">AI 暂未输出明确建议</div>'
    else:
        body = f'<ol class="fb-list">{items}</ol>'

    warn = ""
    if score < threshold:
        warn = (
            '<div class="fb-warn">'
            '  <span class="fw-dot"></span>'
            f'  匹配分低于阈值 <b>{threshold}</b>，建议先优化简历再投递'
            '</div>'
        )

    return (
        '<div class="jd-root">'
        '  <div class="fb-card" role="region" aria-label="综合建议" aria-live="polite">'
        '    <div class="fb-card-head">'
        '      <div class="fch-icon" aria-hidden="true">'
        '        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <circle cx="12" cy="12" r="10"></circle>'
        '          <line x1="12" y1="8" x2="12" y2="12"></line>'
        '          <line x1="12" y1="16" x2="12.01" y2="16"></line>'
        '        </svg>'
        '      </div>'
        '      <div class="fch-title">综合建议</div>'
        '    </div>'
        f'    {body}'
        f'    {warn}'
        '  </div>'
        '</div>'
    )


def _empty_feedback_html() -> str:
    return (
        '<div class="jd-root">'
        '  <div class="fb-card fb-card-empty" role="region" aria-label="综合建议占位" aria-live="polite">'
        '    <div class="fb-empty">匹配完成后这里会给出综合建议</div>'
        '  </div>'
        '</div>'
    )


def _status_html(msg: str, kind: str = "info") -> str:
    dot_cls = {"info": "si-blue", "err": "si-red", "ok": "si-green"}.get(kind, "si-blue")
    return (
        '<div class="jd-root">'
        f'  <div class="jd-status" role="status" aria-live="polite"><span class="si-dot {dot_cls}" aria-hidden="true"></span><span class="si-txt">{_safe(msg)}</span></div>'
        '</div>'
    )


# ================================================================
# 页面创建
# ================================================================
def create_jd_match_page(login_state):
    """创建 JD 匹配页面"""
    gr.HTML(_JD_STYLE)

    with gr.Column(elem_id="jd-page-root", elem_classes=["jd-scope"]):
        gr.HTML(_render_header_html())

        with gr.Row(elem_classes=["jd-main-row"]):
            # 左栏: 输入卡
            with gr.Column(scale=2, elem_classes=["jd-col"]):
                with gr.Column(elem_classes=["jd-card", "jd-card-input"]):
                    gr.HTML(
                        '<div class="jd-card-head">'
                        '  <div class="jch-icon jch-icon-blue">'
                        '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '      <polyline points="4 17 10 11 4 5"></polyline>'
                        '      <line x1="12" y1="19" x2="20" y2="19"></line>'
                        '    </svg>'
                        '  </div>'
                        '  <div class="jch-title">输入区</div>'
                        '  <div class="jch-sub">选择简历，粘贴 JD</div>'
                        '</div>'
                    )
                    resume_dropdown = gr.Dropdown(
                        choices=[],
                        label="选择简历",
                        interactive=True,
                        elem_classes=["jd-input-field"],
                    )
                    refresh_resume_btn = gr.Button(
                        "刷新简历列表",
                        size="sm",
                        elem_classes=["jd-refresh-btn"],
                    )
                    jd_input = gr.Textbox(
                        label="JD 岗位描述",
                        placeholder="请粘贴完整的岗位描述文本 (至少 50 字)...",
                        lines=12,
                        elem_classes=["jd-input-field", "jd-textarea"],
                    )
                    match_btn = gr.Button(
                        "开始匹配",
                        variant="primary",
                        size="lg",
                        elem_classes=["jd-primary-btn"],
                    )

            # 右栏: 结果区 (score hero + diff + feedback 堆叠)
            with gr.Column(scale=3, elem_classes=["jd-col", "jd-col-result"]):
                score_display = gr.HTML(
                    value=_empty_score_html(),
                    elem_id="jd-score-slot",
                )
                diff_display = gr.HTML(
                    value=_empty_diff_html(),
                    elem_id="jd-diff-slot",
                )
                feedback_display = gr.HTML(
                    value=_empty_feedback_html(),
                    elem_id="jd-feedback-slot",
                )
                status_display = gr.HTML(value="", elem_id="jd-status-slot")
                matched_resume = gr.Textbox(visible=False)

    # ================================================================
    # 回调
    # ================================================================
    def _refresh_choices(state):
        user_name = state.get("user_name", "") if state else ""
        try:
            resumes = ResumeCRUD.get_all(original_only=True, user_name=user_name)
            return gr.Dropdown(choices=[f"{r['id']}:{r['file_name']}" for r in resumes])
        except Exception:
            return gr.Dropdown(choices=[])

    def _do_match(resume_choice, jd_text, state):
        user_name = state.get("user_name", "") if state else ""
        if not resume_choice:
            yield (
                _empty_score_html(),
                _empty_diff_html(),
                _empty_feedback_html(),
                _status_html("请先选择简历", "err"),
                "",
            )
            return
        if not jd_text or len(jd_text.strip()) < 50:
            yield (
                _empty_score_html(),
                _empty_diff_html(),
                _empty_feedback_html(),
                _status_html("JD 文本过短, 请输入至少 50 字的岗位描述", "err"),
                "",
            )
            return

        yield (
            _loading_score_html(),
            _loading_diff_html(),
            _loading_feedback_html(),
            _status_html("AI 匹配分析中…", "info"),
            "",
        )

        try:
            resume_id = int(resume_choice.split(":")[0])
            resume = ResumeCRUD.get_by_id(resume_id, user_name=user_name)
            if not resume:
                yield (
                    _empty_score_html(),
                    _empty_diff_html(),
                    _empty_feedback_html(),
                    _status_html("简历不存在", "err"),
                    "",
                )
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
                yield (
                    _empty_score_html(),
                    _empty_diff_html(),
                    _empty_feedback_html(),
                    _status_html(f'匹配失败: {result.get("error_msg")}', "err"),
                    "",
                )
                return

            score = result.get("match_score", 0)
            jd_struct = result.get("jd_struct", {}) or {}
            match_items = result.get("match_items", []) or []
            missing_items = result.get("missing_items", []) or []
            weak_items = result.get("weak_items", []) or []
            feedback_lines = result.get("match_feedback", []) or []
            threshold = get_settings().MATCH_THRESHOLD

            yield (
                _render_score_hero(score, jd_struct),
                _render_tags_panel(match_items, missing_items, weak_items),
                _render_feedback_html(feedback_lines, score, threshold),
                _status_html(
                    f"✓ 匹配完成  分数 {score}", "ok" if score >= threshold else "info"
                ),
                resume_choice,
            )
        except Exception as e:
            logger.error("匹配异常: %s", e)
            yield (
                _empty_score_html(),
                _empty_diff_html(),
                _empty_feedback_html(),
                _status_html(f"匹配异常: {e}", "err"),
                "",
            )

    refresh_resume_btn.click(
        fn=_refresh_choices,
        inputs=[login_state],
        outputs=[resume_dropdown],
    )
    match_btn.click(
        fn=_do_match,
        inputs=[resume_dropdown, jd_input, login_state],
        outputs=[
            score_display,
            diff_display,
            feedback_display,
            status_display,
            matched_resume,
        ],
    )


# ================================================================
# 作用域 CSS (限定在 .jd-scope / .jd-root 下)
# ================================================================
# fmt: off
_JD_STYLE = """
<style>
/* =========================================================
   JD Match Page — Bento 玻璃拟态风 (作用域: .jd-scope/.jd-root)
   ========================================================= */
.jd-scope { color: var(--c-text-1); }
.jd-scope *, .jd-root * { box-sizing: border-box; }
#jd-page-root { padding: 0 !important; }
#jd-page-root > .block:first-child,
#jd-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* 页头 */
.jd-root .jd-head {
    display: flex; align-items: center; gap: 14px;
    margin: -8px 0 14px;
}
.jd-root .jd-head-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(52,211,153,0.24), rgba(79,139,255,0.22));
    border: 1px solid rgba(79,139,255,0.32);
    display: flex; align-items: center; justify-content: center;
    color: #6EE7B7;
    box-shadow: 0 8px 20px rgba(79,139,255,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.jd-root .jd-head-title { font-size: 22px; font-weight: 700; color: #F0F2FA; }
.jd-root .jd-head-sub { font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px; }

/* 主区两栏 */
.jd-scope .jd-main-row {
    gap: 18px !important;
    align-items: flex-start !important;
    display: flex !important;
}
.jd-scope .jd-col { display: flex !important; flex-direction: column !important; }
.jd-scope .jd-col-result { gap: 16px; }

/* 基础卡片 */
.jd-scope .jd-card {
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
}
.jd-scope .jd-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.jd-scope .jd-card > * { position: relative; z-index: 1; }

/* 卡头 */
.jd-scope .jd-card-head {
    display: grid;
    grid-template-columns: 38px 1fr;
    grid-template-rows: auto auto;
    column-gap: 12px;
    align-items: center;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
}
.jd-scope .jch-icon {
    grid-row: 1 / span 2;
    width: 38px; height: 38px; border-radius: 11px;
    display: flex; align-items: center; justify-content: center;
}
.jd-scope .jch-icon-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.jd-scope .jch-title { font-size: 16px; font-weight: 700; color: #F0F2FA; }
.jd-scope .jch-sub { font-size: 12px; color: rgba(230,233,245,0.55); margin-top: 2px; }

/* 输入字段 */
.jd-scope .jd-input-field textarea,
.jd-scope .jd-input-field input,
.jd-scope .jd-input-field .wrap-inner {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    border-radius: 12px !important;
}
.jd-scope .jd-input-field textarea:focus,
.jd-scope .jd-input-field input:focus {
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.12) !important;
}
.jd-scope .jd-textarea textarea { min-height: 220px !important; font-size: 13.5px !important; line-height: 1.7 !important; }

/* 刷新小按钮 */
.jd-scope .jd-refresh-btn,
.jd-scope .jd-refresh-btn button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.75) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 12.5px !important;
    padding: 6px 14px !important;
    transition: all 0.25s ease !important;
}
.jd-scope .jd-refresh-btn:hover,
.jd-scope .jd-refresh-btn button:hover {
    background: rgba(79,139,255,0.12) !important;
    color: #AFC7FF !important;
    border-color: rgba(79,139,255,0.35) !important;
}

/* Primary 匹配按钮 */
.jd-scope .jd-primary-btn,
.jd-scope .jd-primary-btn button {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow:
        0 8px 24px rgba(79,139,255,0.35),
        inset 0 1px 0 rgba(255,255,255,0.18) !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease !important;
}
.jd-scope .jd-primary-btn:hover,
.jd-scope .jd-primary-btn button:hover {
    transform: translateY(-1px);
    box-shadow:
        0 12px 32px rgba(79,139,255,0.48),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
}

/* =========================================================
   右栏: 得分 Hero
   ========================================================= */
.jd-root .score-hero {
    position: relative;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.5);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 24px 26px;
    overflow: hidden;
    box-shadow: 0 12px 32px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.05);
    display: grid;
    grid-template-columns: 210px 1fr;
    gap: 22px;
    min-height: 260px;
}
.jd-root .score-hero::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.jd-root .score-hero::after {
    content: ''; position: absolute;
    width: 400px; height: 400px; border-radius: 50%;
    top: -180px; right: -180px;
    opacity: 0.6;
    pointer-events: none;
    filter: blur(60px);
}
.jd-root .sh-green::after  { background: radial-gradient(circle, rgba(52,211,153,0.30), transparent 60%); }
.jd-root .sh-orange::after { background: radial-gradient(circle, rgba(251,146,60,0.30), transparent 60%); }
.jd-root .sh-red::after    { background: radial-gradient(circle, rgba(248,113,113,0.28), transparent 60%); }

.jd-root .sh-left {
    display: flex; flex-direction: column; align-items: center; gap: 10px;
    position: relative; z-index: 1;
}
.jd-root .sh-ring-wrap { position: relative; width: 160px; height: 160px; }
.jd-root .sh-center {
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.jd-root .sh-score {
    font-size: 48px; font-weight: 800; letter-spacing: -1px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    filter: drop-shadow(0 0 12px currentColor);
}
.jd-root .sh-score-unit {
    font-size: 11px; color: rgba(230,233,245,0.4);
    margin-top: 4px; letter-spacing: 1px;
}
.jd-root .sh-badge {
    padding: 4px 12px; border-radius: 999px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.5px;
    border: 1px solid;
}
.jd-root .sh-advice {
    font-size: 11.5px; color: rgba(230,233,245,0.55);
    text-align: center; max-width: 200px; line-height: 1.5;
}
.jd-root .sh-right { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 10px; }
.jd-root .sh-section-title {
    font-size: 11px; font-weight: 600;
    color: rgba(230,233,245,0.5);
    letter-spacing: 0.8px;
    text-transform: uppercase;
    display: flex; align-items: center; gap: 8px;
}
.jd-root .sh-section-title::after {
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,0.08), transparent);
}
.jd-root .sh-mt { margin-top: 8px; }

.jd-root .jd-info-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}
.jd-root .jd-info-chip {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 8px 12px;
    display: flex; justify-content: space-between; align-items: center;
    gap: 10px;
}
.jd-root .ji-key { font-size: 11px; color: rgba(230,233,245,0.5); }
.jd-root .ji-val {
    font-size: 13px; color: #F0F2FA; font-weight: 600;
    max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.jd-root .jd-info-skills { display: flex; flex-wrap: wrap; gap: 6px; }

/* 空 / 加载 score */
.jd-root .score-hero.score-empty,
.jd-root .score-hero.score-loading {
    grid-template-columns: 1fr;
    justify-items: center;
    align-items: center;
    text-align: center;
    padding: 38px 24px;
    min-height: 260px;
}
.jd-root .score-empty::after { background: radial-gradient(circle, rgba(79,139,255,0.15), transparent 60%); }
.jd-root .se-ring { position: relative; width: 140px; height: 140px; margin-bottom: 14px; }
.jd-root .se-center {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
}
.jd-root .se-mark {
    color: rgba(141,187,255,0.75);
    filter: drop-shadow(0 0 12px rgba(79,139,255,0.4));
    animation: seMarkBreath 2.8s ease-in-out infinite;
    display: flex; align-items: center; justify-content: center;
}
@keyframes seMarkBreath {
    0%, 100% { opacity: 0.72; transform: scale(1); }
    50%      { opacity: 1; transform: scale(1.08); }
}
.jd-root .se-spin { animation: seSpin 4s linear infinite; transform-origin: 80px 80px; }
@keyframes seSpin { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -360; } }
.jd-root .se-title, .jd-root .jdl-title {
    font-size: 16px; font-weight: 700; color: #F0F2FA; margin-bottom: 6px;
}
.jd-root .se-sub, .jd-root .jdl-sub {
    font-size: 12.5px; color: rgba(230,233,245,0.55); max-width: 360px; line-height: 1.7;
}

.jd-root .jdl-spinner {
    width: 50px; height: 50px; border-radius: 50%;
    border: 3px solid rgba(79,139,255,0.15);
    border-top-color: #8DBBFF;
    animation: jdlSpin 0.9s linear infinite;
    margin-bottom: 18px;
    filter: drop-shadow(0 0 12px rgba(79,139,255,0.35));
}
@keyframes jdlSpin { to { transform: rotate(360deg); } }

/* =========================================================
   差异卡: 3 列
   ========================================================= */
.jd-root .diff-card {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.5);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.05);
    transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease,
                border-color 0.28s ease;
    will-change: transform;
}
.jd-root .diff-card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.16);
    box-shadow: 0 22px 50px rgba(0,0,0,0.5),
                0 6px 18px rgba(251,146,60,0.16),
                inset 0 1px 0 rgba(255,255,255,0.08);
}
.jd-root .diff-card-head {
    display: grid;
    grid-template-columns: 32px 1fr;
    grid-template-rows: auto auto;
    column-gap: 12px;
    align-items: center;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 14px;
}
.jd-root .dch-icon {
    grid-row: 1 / span 2;
    width: 32px; height: 32px; border-radius: 9px;
    background: linear-gradient(135deg, rgba(251,146,60,0.24), rgba(244,114,182,0.18));
    color: #FDBA74;
    border: 1px solid rgba(251,146,60,0.32);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(251,146,60,0.2);
}
.jd-root .dch-title { font-size: 15px; font-weight: 700; color: #F0F2FA; }
.jd-root .dch-sub { font-size: 12px; color: rgba(230,233,245,0.55); }

.jd-root .diff-cols {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
}
.jd-root .diff-col {
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 14px;
    padding: 14px;
    min-height: 140px;
}
.jd-root .diff-col-head {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px dashed rgba(255,255,255,0.06);
}
.jd-root .diff-col-title {
    font-size: 12.5px; font-weight: 700; letter-spacing: 0.3px;
}
.jd-root .diff-col-count {
    font-size: 11px; font-weight: 700;
    padding: 2px 8px; border-radius: 6px;
    font-variant-numeric: tabular-nums;
}
.jd-root .diff-hit .diff-col-title  { color: #6EE7B7; }
.jd-root .diff-miss .diff-col-title { color: #FCA5A5; }
.jd-root .diff-weak .diff-col-title { color: #FDBA74; }
.jd-root .diff-hit .diff-col-count  { background: rgba(52,211,153,0.14); color: #6EE7B7; }
.jd-root .diff-miss .diff-col-count { background: rgba(248,113,113,0.14); color: #FCA5A5; }
.jd-root .diff-weak .diff-col-count { background: rgba(251,146,60,0.14); color: #FDBA74; }

.jd-root .diff-col-body { display: flex; flex-direction: column; gap: 6px; }
.jd-root .dtag {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 10px; border-radius: 8px;
    font-size: 12px; font-weight: 500;
    border: 1px solid transparent;
    line-height: 1.4;
}
.jd-root .dtag svg { flex-shrink: 0; opacity: 0.9; }
.jd-root .dtag-txt { flex: 1; }
.jd-root .dtag.hit {
    background: rgba(52,211,153,0.10); color: #86EFAC;
    border-color: rgba(52,211,153,0.22);
}
.jd-root .dtag.miss {
    background: rgba(248,113,113,0.10); color: #FCA5A5;
    border-color: rgba(248,113,113,0.22);
}
.jd-root .dtag.weak {
    background: rgba(251,146,60,0.10); color: #FDBA74;
    border-color: rgba(251,146,60,0.22);
}
.jd-root .dtag-empty {
    font-size: 12px; color: rgba(230,233,245,0.4);
    padding: 10px 4px;
    text-align: center;
    font-style: italic;
}

.jd-root .diff-card.diff-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 200px;
    text-align: center;
    padding: 36px 24px;
}
.jd-root .de-icon { color: rgba(141,187,255,0.5); margin-bottom: 10px; filter: drop-shadow(0 0 10px rgba(79,139,255,0.2)); }
.jd-root .de-title { font-size: 14px; font-weight: 600; color: rgba(230,233,245,0.75); }
.jd-root .de-sub { font-size: 12px; color: rgba(230,233,245,0.5); margin-top: 4px; }

/* ---- Skeleton 加载占位 (差异卡 / 建议卡) ---- */
.jd-root .diff-card.diff-loading {
    min-height: 220px;
    padding: 24px 22px;
}
.jd-root .diff-skel-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 18px;
}
.jd-root .diff-skel-col {
    display: flex; flex-direction: column; gap: 10px;
}
.jd-root .diff-skel-bar {
    height: 12px;
    border-radius: 6px;
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.05) 0%,
        rgba(141,187,255,0.18) 40%,
        rgba(255,255,255,0.05) 80%
    );
    background-size: 200% 100%;
    animation: jdSkelShimmer 1.4s ease-in-out infinite;
}
.jd-root .diff-skel-bar-head { height: 16px; width: 60%; margin-bottom: 4px; }
.jd-root .diff-skel-bar-short { width: 70%; }

.jd-root .fb-card.fb-card-loading {
    display: flex; flex-direction: column; gap: 12px;
    min-height: 140px;
}
.jd-root .fb-skel-row {
    height: 12px;
    border-radius: 6px;
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.05) 0%,
        rgba(141,187,255,0.18) 40%,
        rgba(255,255,255,0.05) 80%
    );
    background-size: 200% 100%;
    animation: jdSkelShimmer 1.4s ease-in-out infinite;
}
.jd-root .fb-skel-row-short { width: 65%; }
@keyframes jdSkelShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* =========================================================
   综合建议卡
   ========================================================= */
.jd-root .fb-card {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.5);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.05);
    transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease,
                border-color 0.28s ease;
    will-change: transform;
}
.jd-root .fb-card:hover {
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.16);
    box-shadow: 0 22px 50px rgba(0,0,0,0.5),
                0 6px 18px rgba(141,187,255,0.16),
                inset 0 1px 0 rgba(255,255,255,0.08);
}
.jd-root .fb-card-head {
    display: flex; align-items: center; gap: 10px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 14px;
}
.jd-root .fch-icon {
    width: 30px; height: 30px; border-radius: 9px;
    background: linear-gradient(135deg, rgba(141,187,255,0.28), rgba(52,211,153,0.22));
    color: #8DBBFF;
    border: 1px solid rgba(141,187,255,0.35);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(79,139,255,0.2);
}
.jd-root .fch-title { font-size: 15px; font-weight: 700; color: #F0F2FA; }

.jd-root .fb-list {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 8px;
    counter-reset: none;
}
.jd-root .fb-item {
    display: flex; gap: 12px; align-items: flex-start;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px;
    padding: 12px 14px;
}
.jd-root .fb-num {
    flex-shrink: 0;
    width: 24px; height: 24px; border-radius: 7px;
    background: linear-gradient(135deg, #4F8BFF, #795AFF);
    color: #fff; font-weight: 800; font-size: 12px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 10px rgba(79,139,255,0.3);
}
.jd-root .fb-txt {
    flex: 1; font-size: 13px; color: #F0F2FA; line-height: 1.7;
}
.jd-root .fb-empty {
    font-size: 13px; color: rgba(230,233,245,0.5); padding: 10px 0;
    text-align: center;
}
.jd-root .fb-card.fb-card-empty { padding: 26px 22px; }

.jd-root .fb-warn {
    margin-top: 14px;
    padding: 10px 14px;
    background: rgba(251,146,60,0.08);
    border: 1px solid rgba(251,146,60,0.25);
    border-radius: 10px;
    color: #FDBA74;
    font-size: 12.5px;
    display: flex; align-items: center; gap: 10px;
}
.jd-root .fb-warn .fw-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #FB923C;
    box-shadow: 0 0 10px rgba(251,146,60,0.7);
    animation: fwPulse 1.5s ease-in-out infinite;
    flex-shrink: 0;
}
@keyframes fwPulse { 50% { opacity: 0.5; transform: scale(1.3); } }

/* =========================================================
   底部状态条
   ========================================================= */
.jd-root .jd-status {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    font-size: 12.5px;
    color: rgba(230,233,245,0.85);
}
.jd-root .si-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.jd-root .si-blue  { background: #8DBBFF; box-shadow: 0 0 10px rgba(141,187,255,0.6); }
.jd-root .si-green { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.6); }
.jd-root .si-red   { background: #F87171; box-shadow: 0 0 10px rgba(248,113,113,0.6); }

/* =========================================================
   通用 chip
   ========================================================= */
.jd-root .chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    border: 1px solid transparent;
}
.jd-root .chip-blue {
    background: rgba(79,139,255,0.14); color: #AFC7FF;
    border-color: rgba(79,139,255,0.28);
}
.jd-root .chip-muted {
    background: rgba(255,255,255,0.04); color: rgba(230,233,245,0.45);
    border-color: rgba(255,255,255,0.06);
}

/* 窄屏自适应 */
@media (max-width: 1100px) {
    .jd-root .score-hero { grid-template-columns: 1fr; justify-items: center; }
    .jd-root .diff-cols { grid-template-columns: 1fr; }
    .jd-root .jd-info-grid { grid-template-columns: 1fr; }
}
</style>
"""
# fmt: on
