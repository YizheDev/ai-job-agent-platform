"""简历管理页面 — Bento 玻璃拟态风 (与工作台同一视觉语言)

布局:
┌─ 页头: 图标 + 标题 + 说明 ────────────────────────────────────┐
├─ KPI 条: 简历总数 / 原始 / 优化版 / 默认简历 ─────────────────┤
├─ 主区: [上传卡 40%] [列表卡 60%] ────────────────────────────┤
└─ 详情卡 (懒显示) ────────────────────────────────────────────┘

数据流 & 对外接口保持:
    _get_resume_list(user_name) -> list[list]   (pytest 依赖)
    create_resume_page(login_state) -> None
回调全部保留, 只在 outputs 里多挂一个 KPI/详情 HTML slot.
"""

from __future__ import annotations

import html as html_mod
import json

import gradio as gr

from app.agents.resume_agent import parse_resume_node
from app.core.logger import get_logger
from app.db.crud import ResumeCRUD
from app.utils.file_util import save_uploaded_file

logger = get_logger(__name__)


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


# ================================================================
# 数据获取 (pytest 依赖 _get_resume_list 签名)
# ================================================================
def _get_resume_list(user_name: str = ""):
    """获取当前用户的简历列表数据 (dataframe 行格式)"""
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


def _get_resume_stats(user_name: str = "") -> dict:
    """返回 KPI 统计: total / original / optimized / default_name."""
    try:
        resumes = ResumeCRUD.get_all(user_name=user_name)
        total = len(resumes)
        original = sum(1 for r in resumes if r.get("is_original"))
        optimized = total - original
        default_name = ""
        default_id = None
        for r in resumes:
            if r.get("is_default"):
                default_name = r.get("file_name", "")
                default_id = r.get("id")
                break
        return {
            "total": total,
            "original": original,
            "optimized": optimized,
            "default_name": default_name,
            "default_id": default_id,
        }
    except Exception:
        return {"total": 0, "original": 0, "optimized": 0, "default_name": "", "default_id": None}


# ================================================================
# HTML 渲染
# ================================================================
def _render_header_html(user_name: str = "") -> str:
    """页头: 图标 + 标题 + KPI 瓦片 4 连."""
    s = _get_resume_stats(user_name)
    default_chip = (
        f'<span class="kpi-default-name" title="{_safe(s["default_name"])}">{_safe(s["default_name"])}</span>'
        if s["default_name"]
        else '<span class="kpi-default-empty">未设置</span>'
    )
    return (
        '<div class="res-root">'
        '  <div class="res-head">'
        '    <div class="res-head-left">'
        '      <div class="res-head-icon">'
        '        <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>'
        '          <polyline points="14 2 14 8 20 8"></polyline>'
        '          <line x1="9" y1="13" x2="15" y2="13"></line>'
        '          <line x1="9" y1="17" x2="13" y2="17"></line>'
        '        </svg>'
        '      </div>'
        '      <div class="res-head-text">'
        '        <div class="res-head-title">简历管理</div>'
        '        <div class="res-head-sub">上传、解析、优化、版本管理一站式搞定</div>'
        '      </div>'
        '    </div>'
        '  </div>'
        '  <div class="res-kpi-grid">'
        '    <div class="res-kpi k-blue">'
        '      <div class="kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>'
        '        </svg>'
        '      </div>'
        '      <div class="kpi-body">'
        f'        <div class="kpi-value">{s["total"]}</div>'
        '        <div class="kpi-label">简历总数</div>'
        '      </div>'
        '    </div>'
        '    <div class="res-kpi k-teal">'
        '      <div class="kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>'
        '          <polyline points="14 2 14 8 20 8"></polyline>'
        '        </svg>'
        '      </div>'
        '      <div class="kpi-body">'
        f'        <div class="kpi-value">{s["original"]}</div>'
        '        <div class="kpi-label">原始简历</div>'
        '      </div>'
        '    </div>'
        '    <div class="res-kpi k-violet">'
        '      <div class="kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>'
        '        </svg>'
        '      </div>'
        '      <div class="kpi-body">'
        f'        <div class="kpi-value">{s["optimized"]}</div>'
        '        <div class="kpi-label">AI 优化版</div>'
        '      </div>'
        '    </div>'
        '    <div class="res-kpi k-pink">'
        '      <div class="kpi-icon">'
        '        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>'
        '        </svg>'
        '      </div>'
        '      <div class="kpi-body">'
        f'        <div class="kpi-value kpi-value-text">{default_chip}</div>'
        '        <div class="kpi-label">默认简历</div>'
        '      </div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _render_parse_info_html(struct: dict, file_name: str = "") -> str:
    """上传并解析成功后的结构化信息卡 (右侧 upload section)."""
    skills = struct.get("skills", [])
    skill_chips = "".join(
        f'<span class="chip chip-blue">{_safe(sk)}</span>' for sk in skills[:10]
    )
    if not skills:
        skill_chips = '<span class="chip chip-muted">暂未提取到技能</span>'

    rows = [
        ("姓名", struct.get("name", "") or "未提取"),
        ("手机", struct.get("phone", "") or "未提取"),
        ("邮箱", struct.get("email", "") or "未提取"),
        ("学历", struct.get("education", "") or "未提取"),
        ("工作年限", f"{struct.get('experience_years', 0)} 年"),
    ]
    row_html = "".join(
        f'<div class="parse-row"><span class="pr-key">{_safe(k)}</span><span class="pr-val">{_safe(v)}</span></div>'
        for k, v in rows
    )
    title = (
        f'<span class="parse-title-txt">✓ 已解析 <b>{_safe(file_name)}</b></span>'
        if file_name
        else '<span class="parse-title-txt">✓ 解析完成</span>'
    )
    return (
        '<div class="parse-card">'
        f'  <div class="parse-title">{title}</div>'
        f'  <div class="parse-rows">{row_html}</div>'
        f'  <div class="parse-skills-title">核心技能</div>'
        f'  <div class="parse-skills">{skill_chips}</div>'
        '</div>'
    )


def _render_parse_empty_html() -> str:
    return (
        '<div class="parse-card parse-empty">'
        '  <div class="pe-icon">'
        '    <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        '      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>'
        '      <polyline points="17 8 12 3 7 8"></polyline>'
        '      <line x1="12" y1="3" x2="12" y2="15"></line>'
        '    </svg>'
        '  </div>'
        '  <div class="pe-title">还没有解析过简历</div>'
        '  <div class="pe-sub">选择 PDF / DOCX 文件, 点击「上传并解析」后这里会显示结构化提取结果</div>'
        '</div>'
    )


def _render_detail_html(resume: dict) -> str:
    """点击「查看详情」后的简历全量卡."""
    if not resume:
        return ""
    try:
        struct = json.loads(resume.get("struct_data", "{}") or "{}")
    except Exception:
        struct = {}

    name = _safe(struct.get("name", "") or resume.get("file_name", ""))
    basic = [
        ("手机", struct.get("phone", "") or "—"),
        ("邮箱", struct.get("email", "") or "—"),
        ("学历", struct.get("education", "") or "—"),
        ("工作年限", f"{struct.get('experience_years', 0)} 年"),
    ]
    basic_html = "".join(
        f'<div class="dt-basic"><span class="db-key">{_safe(k)}</span><span class="db-val">{_safe(v)}</span></div>'
        for k, v in basic
    )

    skills = struct.get("skills", []) or []
    skills_html = (
        "".join(f'<span class="chip chip-blue">{_safe(s)}</span>' for s in skills)
        if skills
        else '<span class="chip chip-muted">无</span>'
    )

    exp_items: list[str] = []
    for exp in struct.get("work_experience", []) or []:
        exp_items.append(
            '<li class="dt-exp-item">'
            f'  <div class="de-company">{_safe(exp.get("company", "—"))}</div>'
            f'  <div class="de-pos">{_safe(exp.get("position", "—"))}</div>'
            f'  <div class="de-dur">{_safe(exp.get("duration", "—"))}</div>'
            "</li>"
        )
    exp_html = (
        f'<ul class="dt-exp-list">{"".join(exp_items)}</ul>'
        if exp_items
        else '<div class="dt-empty">暂无工作经历数据</div>'
    )

    edu_items: list[str] = []
    for edu in struct.get("education_history", []) or []:
        edu_items.append(
            '<li class="dt-exp-item">'
            f'  <div class="de-company">{_safe(edu.get("school", "—"))}</div>'
            f'  <div class="de-pos">{_safe(edu.get("major", "—"))} · {_safe(edu.get("degree", ""))}</div>'
            f'  <div class="de-dur">{_safe(edu.get("duration", "—"))}</div>'
            "</li>"
        )
    edu_html = (
        f'<ul class="dt-exp-list">{"".join(edu_items)}</ul>'
        if edu_items
        else ""
    )

    badge_default = (
        '<span class="dt-badge dt-badge-gold">默认简历</span>' if resume.get("is_default") else ""
    )
    badge_type = (
        '<span class="dt-badge dt-badge-blue">原始</span>'
        if resume.get("is_original")
        else '<span class="dt-badge dt-badge-violet">AI 优化</span>'
    )
    ctime = _safe(resume.get("create_time", ""))
    fname = _safe(resume.get("file_name", ""))

    return (
        '<div class="res-root">'
        '  <div class="dt-card">'
        '    <div class="dt-head">'
        '      <div class="dt-head-left">'
        '        <div class="dt-avatar">'
        f'          <span>{(name[:1] if name else "简").upper()}</span>'
        '        </div>'
        '        <div>'
        f'          <div class="dt-name">{name or "未命名"}</div>'
        f'          <div class="dt-meta">{fname} · {ctime} {badge_default}{badge_type}</div>'
        '        </div>'
        '      </div>'
        '    </div>'
        f'    <div class="dt-basics">{basic_html}</div>'
        '    <div class="dt-section-title">核心技能</div>'
        f'    <div class="dt-skills">{skills_html}</div>'
        '    <div class="dt-section-title">工作经历</div>'
        f'    {exp_html}'
        + (f'    <div class="dt-section-title">教育经历</div>{edu_html}' if edu_items else '')
        + '  </div>'
        '</div>'
    )


# ================================================================
# 页面创建
# ================================================================
def create_resume_page(login_state):
    """创建简历管理页面"""
    gr.HTML(_RES_STYLE)

    with gr.Column(elem_id="resume-page-root", elem_classes=["res-scope"]):
        header_slot = gr.HTML(value=_render_header_html(""), elem_id="res-header-slot")

        with gr.Row(elem_classes=["res-main-row"]):
            # 左: 上传卡
            with gr.Column(scale=2, elem_classes=["res-col"]):
                with gr.Column(elem_classes=["res-card", "res-card-upload"]):
                    gr.HTML(
                        '<div class="res-card-head">'
                        '  <div class="rch-icon rch-icon-blue">'
                        '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>'
                        '      <polyline points="17 8 12 3 7 8"></polyline>'
                        '      <line x1="12" y1="3" x2="12" y2="15"></line>'
                        '    </svg>'
                        '  </div>'
                        '  <div class="rch-title">上传简历</div>'
                        '  <div class="rch-sub">支持 PDF / DOCX · 单文件 ≤10MB</div>'
                        '</div>'
                    )
                    file_input = gr.File(
                        label="选择文件",
                        file_types=[".pdf", ".docx"],
                        elem_classes=["res-file-input"],
                    )
                    upload_btn = gr.Button(
                        "上传并解析",
                        variant="primary",
                        elem_classes=["res-primary-btn"],
                    )
                    status_msg = gr.Textbox(
                        label="状态",
                        interactive=False,
                        max_lines=1,
                        elem_classes=["res-status-box"],
                    )
                    parse_info = gr.HTML(
                        value=_render_parse_empty_html(),
                        elem_id="res-parse-slot",
                    )

            # 右: 列表 + 操作卡
            with gr.Column(scale=3, elem_classes=["res-col"]):
                with gr.Column(elem_classes=["res-card", "res-card-list"]):
                    gr.HTML(
                        '<div class="res-card-head">'
                        '  <div class="rch-icon rch-icon-violet">'
                        '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '      <line x1="8" y1="6" x2="21" y2="6"></line>'
                        '      <line x1="8" y1="12" x2="21" y2="12"></line>'
                        '      <line x1="8" y1="18" x2="21" y2="18"></line>'
                        '      <line x1="3" y1="6" x2="3.01" y2="6"></line>'
                        '      <line x1="3" y1="12" x2="3.01" y2="12"></line>'
                        '      <line x1="3" y1="18" x2="3.01" y2="18"></line>'
                        '    </svg>'
                        '  </div>'
                        '  <div class="rch-title">我的简历</div>'
                        '  <div class="rch-sub">点击行选中, 再执行下方操作</div>'
                        '</div>'
                        '<div class="res-empty-hint" aria-hidden="true">'
                        '  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '    <circle cx="12" cy="12" r="10"></circle>'
                        '    <line x1="12" y1="8" x2="12" y2="12"></line>'
                        '    <line x1="12" y1="16" x2="12.01" y2="16"></line>'
                        '  </svg>'
                        '  <span>列表为空时, 请先在右侧上传一份简历; 或点击「刷新列表」从本地加载</span>'
                        '</div>'
                    )
                    resume_table = gr.Dataframe(
                        headers=["ID", "文件名", "格式", "类型", "默认", "创建时间"],
                        datatype=["number", "str", "str", "str", "str", "str"],
                        value=[],
                        interactive=False,
                        elem_classes=["res-table"],
                    )
                    selected_id = gr.Textbox(
                        label="已选简历 ID",
                        placeholder="点击上方表格任意行选中",
                        interactive=True,
                        elem_classes=["res-selected-box"],
                    )
                    with gr.Row(elem_classes=["res-action-row"]):
                        view_btn = gr.Button(
                            "查看详情",
                            variant="secondary",
                            elem_classes=["res-action-btn", "rab-blue"],
                        )
                        default_btn = gr.Button(
                            "设为默认",
                            variant="secondary",
                            elem_classes=["res-action-btn", "rab-gold"],
                        )
                        delete_btn = gr.Button(
                            "删除",
                            variant="stop",
                            elem_classes=["res-action-btn", "rab-danger"],
                        )
                        refresh_btn = gr.Button(
                            "刷新列表",
                            variant="secondary",
                            elem_classes=["res-action-btn", "rab-info"],
                        )

        detail_display = gr.HTML(value="", elem_id="res-detail-slot")

    # ================================================================
    # 回调 (闭包捕获 login_state)
    # ================================================================
    def _upload_and_parse(file, state):
        user_name = state.get("user_name", "") if state else ""
        if file is None:
            yield (
                "请选择文件",
                _render_parse_empty_html(),
                _get_resume_list(user_name),
                _render_header_html(user_name),
            )
            return

        yield (
            "⏳ 正在上传并解析简历, 请稍候...",
            _render_parse_empty_html(),
            gr.update(),
            gr.update(),
        )

        try:
            saved_path = save_uploaded_file(file.name if hasattr(file, "name") else str(file))
            agent_state = {"resume_path": saved_path, "user_name": user_name}
            result = parse_resume_node(agent_state)
            if result.get("error_code"):
                yield (
                    f"解析失败: {result.get('error_msg', '')}",
                    _render_parse_empty_html(),
                    _get_resume_list(user_name),
                    _render_header_html(user_name),
                )
                return
            struct = result.get("resume_struct", {}) or {}
            file_name = struct.get("file_name", "") or ""
            yield (
                "✓ 解析成功",
                _render_parse_info_html(struct, file_name),
                _get_resume_list(user_name),
                _render_header_html(user_name),
            )
        except Exception as e:
            logger.error("简历上传失败: %s", e)
            yield (
                f"上传失败: {e}",
                _render_parse_empty_html(),
                _get_resume_list(user_name),
                _render_header_html(user_name),
            )

    def _view_resume(sel_id, state):
        user_name = state.get("user_name", "") if state else ""
        if not sel_id:
            return '<div class="res-root"><div class="dt-empty-card">请在上方列表点击一行再查看详情</div></div>'
        try:
            resume = ResumeCRUD.get_by_id(int(sel_id), user_name=user_name)
            if not resume:
                return '<div class="res-root"><div class="dt-empty-card">简历不存在或已被删除</div></div>'
            return _render_detail_html(resume)
        except Exception as e:
            return f'<div class="res-root"><div class="dt-empty-card">查看失败: {_safe(e)}</div></div>'

    def _delete_resume(sel_id, state):
        user_name = state.get("user_name", "") if state else ""
        if not sel_id:
            return (
                "请选择简历",
                _get_resume_list(user_name),
                _render_header_html(user_name),
                "",
            )
        try:
            ok = ResumeCRUD.delete(int(sel_id), user_name=user_name)
            msg = "✓ 删除成功" if ok else "删除失败"
            return (
                msg,
                _get_resume_list(user_name),
                _render_header_html(user_name),
                "",
            )
        except Exception as e:
            return (
                f"删除失败: {e}",
                _get_resume_list(user_name),
                _render_header_html(user_name),
                "",
            )

    def _set_default(sel_id, state):
        user_name = state.get("user_name", "") if state else ""
        if not sel_id:
            return (
                "请选择简历",
                _get_resume_list(user_name),
                _render_header_html(user_name),
            )
        try:
            ResumeCRUD.set_default(int(sel_id), user_name=user_name)
            return (
                "✓ 已设为默认简历",
                _get_resume_list(user_name),
                _render_header_html(user_name),
            )
        except Exception as e:
            return (
                f"操作失败: {e}",
                _get_resume_list(user_name),
                _render_header_html(user_name),
            )

    def _refresh_list(state):
        user_name = state.get("user_name", "") if state else ""
        return _get_resume_list(user_name), _render_header_html(user_name)

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

    # ================================================================
    # 事件绑定
    # ================================================================
    resume_table.select(fn=_on_row_select, inputs=[login_state], outputs=[selected_id])
    upload_btn.click(
        fn=_upload_and_parse,
        inputs=[file_input, login_state],
        outputs=[status_msg, parse_info, resume_table, header_slot],
    )
    view_btn.click(
        fn=_view_resume, inputs=[selected_id, login_state], outputs=[detail_display]
    )
    delete_btn.click(
        fn=_delete_resume,
        inputs=[selected_id, login_state],
        outputs=[status_msg, resume_table, header_slot, detail_display],
    )
    default_btn.click(
        fn=_set_default,
        inputs=[selected_id, login_state],
        outputs=[status_msg, resume_table, header_slot],
    )
    refresh_btn.click(
        fn=_refresh_list,
        inputs=[login_state],
        outputs=[resume_table, header_slot],
    )


# ================================================================
# 作用域 CSS (限定在 .res-scope / .res-root 下, 不影响其他页面)
# ================================================================
# fmt: off
_RES_STYLE = """
<style>
/* =========================================================
   Resume Page — Bento 玻璃拟态风 (作用域: .res-scope/.res-root)
   ========================================================= */
.res-scope { color: var(--c-text-1); }
.res-scope *, .res-root * { box-sizing: border-box; }
#resume-page-root { padding: 0 !important; }
#resume-page-root > .block:first-child,
#resume-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* ---------- 页头 + KPI ---------- */
.res-root .res-head {
    display: flex; align-items: flex-start; justify-content: space-between;
    margin: -10px 0 10px;
    gap: 16px;
}
.res-root .res-head-left {
    display: flex; align-items: center; gap: 14px;
}
.res-root .res-head-icon {
    width: 44px; height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.22));
    border: 1px solid rgba(79,139,255,0.35);
    display: flex; align-items: center; justify-content: center;
    color: #AFC7FF;
    box-shadow: 0 8px 20px rgba(79,139,255,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.res-root .res-head-title {
    font-size: 22px; font-weight: 700; color: #F0F2FA; letter-spacing: 0.2px;
}
.res-root .res-head-sub {
    font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px;
}

.res-root .res-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 22px;
    animation: resFadeIn 0.55s cubic-bezier(0.2,0.8,0.2,1);
}
@keyframes resFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
.res-root .res-kpi {
    position: relative;
    padding: 18px 22px;
    border-radius: 18px;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.55);
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow:
        0 1px 0 rgba(255,255,255,0.06) inset,
        0 12px 28px rgba(0,0,0,0.34);
    display: flex; align-items: center; gap: 16px;
    transition: transform 0.3s cubic-bezier(0.2,0.8,0.2,1), border-color 0.25s ease, box-shadow 0.3s ease;
    overflow: hidden;
    min-height: 96px;
}
.res-root .res-kpi::before {
    content: ''; position: absolute; inset: 0;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), transparent 60%);
    pointer-events: none;
}
.res-root .res-kpi:hover {
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.18);
    box-shadow:
        0 1px 0 rgba(255,255,255,0.10) inset,
        0 18px 40px rgba(0,0,0,0.42),
        0 6px 16px rgba(79,139,255,0.14);
}
.res-root .res-kpi .kpi-icon {
    width: 48px; height: 48px; border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 6px 16px rgba(0,0,0,0.20), inset 0 1px 0 rgba(255,255,255,0.12);
}
.res-root .res-kpi .kpi-icon svg { width: 22px !important; height: 22px !important; }
.res-root .res-kpi .kpi-body { min-width: 0; flex: 1; }
.res-root .res-kpi .kpi-value {
    font-size: 32px; font-weight: 800; line-height: 1.05; color: #F0F2FA;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, #FFFFFF 0%, #C4D2FF 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
}
.res-root .res-kpi .kpi-value-text {
    font-size: 17px; font-weight: 700;
    max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    background: linear-gradient(135deg, #FFFFFF 0%, #FFE0B5 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
}
.res-root .res-kpi .kpi-label {
    font-size: 12.5px; color: rgba(230,233,245,0.65); margin-top: 6px;
    font-weight: 500; letter-spacing: 0.3px;
}
.res-root .res-kpi .kpi-default-name {
    color: #FDBA74; font-weight: 600;
}
.res-root .res-kpi .kpi-default-empty {
    color: rgba(230,233,245,0.35); font-weight: 500;
}

.res-root .k-blue   .kpi-icon { background: linear-gradient(135deg, rgba(79,139,255,0.32), rgba(79,139,255,0.18)); color: #B3CCFF; border: 1px solid rgba(79,139,255,0.4); }
.res-root .k-teal   .kpi-icon { background: linear-gradient(135deg, rgba(52,211,153,0.30), rgba(52,211,153,0.18)); color: #8FF0CB; border: 1px solid rgba(52,211,153,0.4); }
.res-root .k-violet .kpi-icon { background: linear-gradient(135deg, rgba(167,139,250,0.32), rgba(167,139,250,0.20)); color: #D5C5FF; border: 1px solid rgba(167,139,250,0.42); }
.res-root .k-pink   .kpi-icon { background: linear-gradient(135deg, rgba(244,114,182,0.32), rgba(244,114,182,0.20)); color: #FBC2DD; border: 1px solid rgba(244,114,182,0.42); }

/* 简历列表卡: 顶部空态提示徽章 */
.res-root .res-empty-hint {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 4px 0 14px;
    padding: 6px 12px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(79,139,255,0.14), rgba(167,139,250,0.10));
    border: 1px dashed rgba(141,187,255,0.32);
    color: rgba(220,228,255,0.82);
    font-size: 11.5px; font-weight: 500;
    letter-spacing: 0.2px;
}
.res-root .res-empty-hint svg { color: #AFC7FF; flex-shrink: 0; }

/* ---------- 主区两大玻璃卡 ---------- */
/* gr.Row → .res-main-row: 两列等高 */
.res-scope .res-main-row {
    gap: 18px !important;
    align-items: stretch !important;
    display: flex !important;
}
/* gr.Column → .res-col: 让内部卡片撑满 */
.res-scope .res-col {
    display: flex !important;
    flex-direction: column !important;
    align-self: stretch !important;
}
.res-scope .res-col > .res-card {
    flex: 1 1 auto !important;
    min-height: 100% !important;
}

.res-scope .res-card {
    position: relative;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.55) !important;
    backdrop-filter: blur(20px) saturate(130%);
    -webkit-backdrop-filter: blur(20px) saturate(130%);
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 20px !important;
    padding: 22px 22px !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.05) inset,
        0 12px 32px rgba(0,0,0,0.34) !important;
    overflow: hidden;
    gap: 14px !important;
    display: flex !important;
    flex-direction: column !important;
    transition: border-color 0.28s ease,
                transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease !important;
    will-change: transform;
}
.res-scope .res-card::before {
    content: ''; position: absolute; inset: 0;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.res-scope .res-card:hover {
    border-color: rgba(255,255,255,0.16) !important;
    transform: translateY(-3px) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 22px 50px rgba(0,0,0,0.5),
        0 6px 18px rgba(79,139,255,0.12) !important;
}

.res-scope .res-card > * { position: relative; z-index: 1; }

/* 卡头 */
.res-scope .res-card-head {
    display: grid;
    grid-template-columns: 38px 1fr;
    grid-template-rows: auto auto;
    column-gap: 12px;
    align-items: center;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
}
.res-scope .res-card-head .rch-icon {
    grid-row: 1 / span 2;
    width: 38px; height: 38px; border-radius: 11px;
    display: flex; align-items: center; justify-content: center;
}
.res-scope .rch-icon-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.res-scope .rch-icon-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(244,114,182,0.20));
    color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.35);
    box-shadow: 0 4px 14px rgba(167,139,250,0.22);
}
.res-scope .res-card-head .rch-title {
    font-size: 16px; font-weight: 700; color: #F0F2FA; letter-spacing: 0.2px;
}
.res-scope .res-card-head .rch-sub {
    font-size: 12px; color: rgba(230,233,245,0.55); margin-top: 2px;
}

/* ---------- 上传卡内元素 ---------- */
/* Gradio File 组件容器 */
.res-scope .res-file-input {
    border-radius: 14px !important;
    background: transparent !important;
}
.res-scope .res-file-input .wrap {
    background: rgba(17,22,48,0.4) !important;
    border: 1.5px dashed rgba(79,139,255,0.35) !important;
    border-radius: 14px !important;
    padding: 18px !important;
    color: var(--c-text-2) !important;
    transition: border-color 0.3s ease, background 0.3s ease !important;
    min-height: 140px !important;
}
.res-scope .res-file-input .wrap:hover {
    border-color: rgba(79,139,255,0.55) !important;
    background: rgba(79,139,255,0.06) !important;
}
.res-scope .res-file-input svg {
    color: #8DBBFF !important;
    filter: drop-shadow(0 0 8px rgba(79,139,255,0.4));
}
.res-scope .res-file-input .or { color: rgba(230,233,245,0.4) !important; }

/* Primary 按钮 */
.res-scope .res-primary-btn button,
.res-scope button.res-primary-btn,
.res-scope .res-primary-btn {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow:
        0 8px 24px rgba(79,139,255,0.35),
        inset 0 1px 0 rgba(255,255,255,0.18) !important;
    border-radius: 12px !important;
    padding: 12px 20px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease !important;
}
.res-scope .res-primary-btn:hover,
.res-scope .res-primary-btn button:hover {
    transform: translateY(-1px);
    box-shadow:
        0 12px 32px rgba(79,139,255,0.48),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
}

/* 状态框 */
.res-scope .res-status-box textarea,
.res-scope .res-status-box input {
    background: rgba(17,22,48,0.45) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: var(--c-text-2) !important;
    border-radius: 10px !important;
    font-size: 13px !important;
}

/* 解析结果卡: 让它在 upload card 末尾撑开 */
.res-scope #res-parse-slot {
    flex: 1 1 auto !important;
    display: flex !important;
    flex-direction: column !important;
}
.res-scope .parse-card {
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 18px 18px;
    margin-top: 4px;
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
}
.res-scope .parse-card.parse-empty {
    align-items: center;
    justify-content: center;
    text-align: center;
    min-height: 160px;
    color: rgba(230,233,245,0.5);
}
.res-scope .pe-icon {
    color: rgba(79,139,255,0.55);
    margin-bottom: 10px;
    filter: drop-shadow(0 0 10px rgba(79,139,255,0.2));
}
.res-scope .pe-title { font-size: 14px; font-weight: 600; color: rgba(230,233,245,0.75); }
.res-scope .pe-sub {
    font-size: 12px; margin-top: 6px; line-height: 1.7;
    max-width: 280px;
    color: rgba(230,233,245,0.5);
}
.res-scope .parse-title {
    font-size: 13px; font-weight: 600; color: #6EE7B7;
    margin-bottom: 12px;
    display: flex; align-items: center; gap: 6px;
}
.res-scope .parse-title-txt b { color: #F0F2FA; font-weight: 700; }
.res-scope .parse-rows {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px;
    margin-bottom: 12px;
}
.res-scope .parse-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 10px;
    background: rgba(255,255,255,0.025);
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.04);
}
.res-scope .pr-key { color: rgba(230,233,245,0.55); font-size: 12px; }
.res-scope .pr-val {
    color: #F0F2FA; font-size: 13px; font-weight: 600;
    max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.res-scope .parse-skills-title {
    font-size: 12px; color: rgba(230,233,245,0.55); margin-bottom: 6px; letter-spacing: 0.3px;
}
.res-scope .parse-skills { display: flex; flex-wrap: wrap; gap: 6px; }

/* ---------- 通用 chip ---------- */
.res-scope .chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.2px;
    border: 1px solid transparent;
}
.res-scope .chip-blue {
    background: rgba(79,139,255,0.14);
    color: #AFC7FF;
    border-color: rgba(79,139,255,0.28);
}
.res-scope .chip-muted {
    background: rgba(255,255,255,0.04);
    color: rgba(230,233,245,0.45);
    border-color: rgba(255,255,255,0.06);
}

/* ---------- 列表卡内 ---------- */
.res-scope .res-selected-box {
    margin-top: 2px;
}
.res-scope .res-selected-box textarea,
.res-scope .res-selected-box input {
    background: rgba(17,22,48,0.45) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    font-family: 'JetBrains Mono', 'Consolas', monospace !important;
    font-size: 13px !important;
    border-radius: 10px !important;
}

.res-scope .res-action-row { gap: 10px !important; margin-top: 4px; }

/* 动作按钮: 4 色语义 */
.res-scope .res-action-btn,
.res-scope .res-action-btn button {
    border-radius: 11px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    border: 1px solid transparent !important;
    transition: all 0.25s cubic-bezier(0.2,0.8,0.2,1) !important;
}
.res-scope .rab-blue,
.res-scope .rab-blue button {
    background: rgba(79,139,255,0.14) !important;
    color: #AFC7FF !important;
    border-color: rgba(79,139,255,0.28) !important;
}
.res-scope .rab-blue:hover,
.res-scope .rab-blue button:hover {
    background: rgba(79,139,255,0.24) !important;
    border-color: rgba(79,139,255,0.45) !important;
    transform: translateY(-1px);
}
.res-scope .rab-gold,
.res-scope .rab-gold button {
    background: rgba(251,146,60,0.14) !important;
    color: #FDBA74 !important;
    border-color: rgba(251,146,60,0.28) !important;
}
.res-scope .rab-gold:hover,
.res-scope .rab-gold button:hover {
    background: rgba(251,146,60,0.22) !important;
    border-color: rgba(251,146,60,0.45) !important;
    transform: translateY(-1px);
}
.res-scope .rab-danger,
.res-scope .rab-danger button {
    background: rgba(248,113,113,0.12) !important;
    color: #FCA5A5 !important;
    border-color: rgba(248,113,113,0.25) !important;
}
.res-scope .rab-danger:hover,
.res-scope .rab-danger button:hover {
    background: rgba(248,113,113,0.22) !important;
    border-color: rgba(248,113,113,0.42) !important;
    transform: translateY(-1px);
}
.res-scope .rab-muted,
.res-scope .rab-muted button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.75) !important;
    border-color: rgba(255,255,255,0.10) !important;
}
.res-scope .rab-muted:hover,
.res-scope .rab-muted button:hover {
    background: rgba(255,255,255,0.09) !important;
    border-color: rgba(255,255,255,0.18) !important;
    transform: translateY(-1px);
}
/* Info (cyan) glass — 用于刷新/次要蓝色动作 */
.res-scope .rab-info,
.res-scope .rab-info button {
    background: rgba(34,211,238,0.18) !important;
    color: #67E8F9 !important;
    border: 1px solid rgba(34,211,238,0.42) !important;
    box-shadow:
        0 4px 14px rgba(34,211,238,0.18),
        inset 0 1px 0 rgba(255,255,255,0.08) !important;
}
.res-scope .rab-info:hover,
.res-scope .rab-info button:hover {
    background: rgba(34,211,238,0.28) !important;
    border-color: rgba(34,211,238,0.62) !important;
    color: #A5F3FC !important;
    transform: translateY(-1px);
    box-shadow:
        0 8px 22px rgba(34,211,238,0.32),
        inset 0 1px 0 rgba(255,255,255,0.14) !important;
}

/* ---------- 简历详情卡 ---------- */
.res-root .dt-card {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.55);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 24px;
    margin-top: 18px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.05);
    animation: resFadeIn 0.45s cubic-bezier(0.2,0.8,0.2,1);
}
.res-root .dt-empty-card {
    background: rgba(17,22,48,0.35);
    border: 1px dashed rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 24px;
    margin-top: 18px;
    color: rgba(230,233,245,0.55);
    text-align: center;
    font-size: 13px;
}
.res-root .dt-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 14px;
    padding-bottom: 18px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 18px;
}
.res-root .dt-head-left { display: flex; align-items: center; gap: 14px; }
.res-root .dt-avatar {
    width: 48px; height: 48px; border-radius: 14px;
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 800; font-size: 22px;
    box-shadow: 0 8px 22px rgba(79,139,255,0.38), inset 0 1px 0 rgba(255,255,255,0.22);
}
.res-root .dt-name { font-size: 18px; font-weight: 700; color: #F0F2FA; }
.res-root .dt-meta {
    font-size: 12px; color: rgba(230,233,245,0.55); margin-top: 3px;
    display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.res-root .dt-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    border: 1px solid transparent;
}
.res-root .dt-badge-gold {
    background: rgba(251,146,60,0.16); color: #FDBA74; border-color: rgba(251,146,60,0.3);
}
.res-root .dt-badge-blue {
    background: rgba(79,139,255,0.16); color: #8DBBFF; border-color: rgba(79,139,255,0.3);
}
.res-root .dt-badge-violet {
    background: rgba(167,139,250,0.18); color: #C4B5FD; border-color: rgba(167,139,250,0.32);
}

.res-root .dt-basics {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
    margin-bottom: 18px;
}
.res-root .dt-basic {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 10px 12px;
    display: flex; flex-direction: column; gap: 2px;
}
.res-root .db-key { font-size: 11px; color: rgba(230,233,245,0.55); }
.res-root .db-val { font-size: 14px; color: #F0F2FA; font-weight: 600; }

.res-root .dt-section-title {
    font-size: 12.5px; font-weight: 600;
    color: rgba(230,233,245,0.55);
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin: 18px 0 10px;
    display: flex; align-items: center; gap: 8px;
}
.res-root .dt-section-title::after {
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,0.08), transparent);
}
.res-root .dt-skills { display: flex; flex-wrap: wrap; gap: 6px; }
.res-root .dt-exp-list {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 10px;
}
.res-root .dt-exp-item {
    position: relative;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 12px 14px 12px 16px;
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 10px;
    align-items: center;
}
.res-root .dt-exp-item::before {
    content: '';
    position: absolute; left: 0; top: 10px; bottom: 10px;
    width: 3px; border-radius: 2px;
    background: linear-gradient(180deg, #4F8BFF, #795AFF);
}
.res-root .de-company { font-size: 14px; font-weight: 700; color: #F0F2FA; }
.res-root .de-pos { font-size: 13px; color: rgba(230,233,245,0.75); }
.res-root .de-dur { font-size: 12px; color: rgba(230,233,245,0.5); white-space: nowrap; }
.res-root .dt-empty {
    color: rgba(230,233,245,0.5); font-size: 13px;
    padding: 10px 14px;
    background: rgba(255,255,255,0.02);
    border: 1px dashed rgba(255,255,255,0.08);
    border-radius: 10px;
}

/* 窄屏自适应 */
@media (max-width: 960px) {
    .res-root .res-kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .res-root .dt-basics { grid-template-columns: repeat(2, 1fr); }
    .res-root .dt-exp-item { grid-template-columns: 1fr; }
}
</style>
"""
# fmt: on
