"""自动化投递页面 — Bento 玻璃拟态风

布局:
┌─ 页头: 图标 + 标题 + 说明
├─ 连接状态 Banner 卡 (BOSS 登录态 + 刷新)
├─ 搜索卡: 关键词 + 城市 + HR活跃度 + 搜索按钮
├─ 结果表 + 操作卡:
│    · 岗位列表 Dataframe
│    · 已选岗位 + 简历下拉 + 单个沟通按钮
│    · 岗位详情
├─ 批量沟通卡: 数量滑块 + 批量按钮 + 日志
└─ 操作状态条 (HTML 富化)

对外接口保持: create_delivery_page(login_state)
"""

from __future__ import annotations

import html as html_mod
import random
import time
from datetime import datetime

import gradio as gr

from app.agents.risk_agent import risk_check_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD, ResumeCRUD, SysConfigCRUD
from app.utils.boss_crawler import CITY_LIST, HR_ACTIVITY_OPTIONS, get_crawler

logger = get_logger(__name__)


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


# ------------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------------

def _resume_choices(user_name: str = "") -> list[str]:
    try:
        resumes = ResumeCRUD.get_all(user_name=user_name)
        return [f"{r['id']}:{r['file_name']}" for r in resumes]
    except Exception:
        return []


def _btn_states(has_jobs: bool = False):
    """根据登录状态返回 (apply_btn_update, batch_btn_update)."""
    try:
        c = get_crawler()
        logged_in = bool(c.is_logged_in)
    except Exception:
        logged_in = False
    return (
        gr.update(interactive=False),  # apply_btn 默认禁用, 选中行后由 _on_job_select 启用
        gr.update(interactive=logged_in and has_jobs),
    )


def _connection_banner() -> str:
    """连接状态横幅: 登录则绿色, 未登录则橙色警告, 外加模式/熔断 chip."""
    c = get_crawler()
    if c.is_running and c.is_logged_in:
        mode = c.mode_display
        cb = c.circuit_state
        chips = [
            '<span class="dcb-chip dcb-chip-green">'
            '<span class="dcb-chip-dot"></span>已登录</span>',
            f'<span class="dcb-chip dcb-chip-blue">模式: {_safe(mode)}</span>',
        ]
        if cb != "正常":
            chips.append(f'<span class="dcb-chip dcb-chip-orange">熔断: {_safe(cb)}</span>')

        return (
            '<div class="dlv-root">'
            '  <div class="dcb-banner dcb-ok">'
            '    <div class="dcb-icon dcb-icon-green">'
            '      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '        <polyline points="20 6 9 17 4 12"></polyline>'
            '      </svg>'
            '    </div>'
            '    <div class="dcb-text">'
            '      <div class="dcb-title">BOSS 直聘 · 已连接并登录</div>'
            '      <div class="dcb-sub">可以开始搜索和投递岗位</div>'
            '    </div>'
            f'    <div class="dcb-chips">{"".join(chips)}</div>'
            '  </div>'
            '</div>'
        )
    return (
        '<div class="dlv-root">'
        '  <div class="dcb-banner dcb-warn">'
        '    <div class="dcb-icon dcb-icon-orange">'
        '      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        '        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>'
        '        <line x1="12" y1="9" x2="12" y2="13"></line>'
        '        <line x1="12" y1="17" x2="12.01" y2="17"></line>'
        '      </svg>'
        '    </div>'
        '    <div class="dcb-text">'
        '      <div class="dcb-title">请先连接并登录 BOSS 直聘</div>'
        '      <div class="dcb-sub">前往「BOSS 账号」页面完成连接后, 回到本页即可搜索投递</div>'
        '    </div>'
        '    <div class="dcb-chips">'
        '      <span class="dcb-chip dcb-chip-orange">'
        '        <span class="dcb-chip-dot dcb-chip-dot-warn"></span>未登录'
        '      </span>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _status_html(msg: str, kind: str = "info") -> str:
    """操作状态条: 圆点/图标 + 文本."""
    dot_cls = {"info": "dsi-blue", "err": "dsi-red", "ok": "dsi-green", "warn": "dsi-orange"}.get(kind, "dsi-blue")
    extra_cls = {"ok": " dlv-status-ok", "err": " dlv-status-err", "warn": " dlv-status-warn"}.get(kind, "")
    icon_html = f'<span class="dsi-dot {dot_cls}"></span>'
    if kind == "ok":
        icon_html = (
            '<span class="dsi-icon dsi-icon-ok">'
            '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="20 6 9 17 4 12"></polyline>'
            '</svg></span>'
        )
    elif kind == "err":
        icon_html = (
            '<span class="dsi-icon dsi-icon-err">'
            '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
            '<line x1="6" y1="6" x2="18" y2="18"></line>'
            '<line x1="6" y1="18" x2="18" y2="6"></line>'
            '</svg></span>'
        )
    elif kind == "warn":
        icon_html = (
            '<span class="dsi-icon dsi-icon-warn">'
            '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>'
            '<line x1="12" y1="9" x2="12" y2="13"></line>'
            '<line x1="12" y1="17" x2="12.01" y2="17"></line>'
            '</svg></span>'
        )
    return (
        '<div class="dlv-root">'
        f'  <div class="dlv-status{extra_cls}">{icon_html}'
        f'  <span class="dsi-txt">{_safe(msg)}</span></div>'
        '</div>'
    )


def _status_loading_html(msg: str) -> str:
    """投递耗时操作 loading 态."""
    return (
        '<div class="dlv-root">'
        '  <div class="dlv-status dlv-status-loading">'
        '    <span class="dsi-spinner">'
        '      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
        '        <path d="M21 12a9 9 0 1 1-9-9"></path>'
        '      </svg>'
        '    </span>'
        f'    <span class="dsi-txt">{_safe(msg)}</span>'
        '  </div>'
        '</div>'
    )


def _render_header_html() -> str:
    return (
        '<div class="dlv-root">'
        '  <div class="dlv-head">'
        '    <div class="dlv-head-icon">'
        '      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>'
        '        <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>'
        '        <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>'
        '        <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>'
        '      </svg>'
        '    </div>'
        '    <div class="dlv-head-text">'
        '      <div class="dlv-head-title">自动化投递</div>'
        '      <div class="dlv-head-sub">关键词搜索 · HR 活跃度筛选 · 单个 / 批量沟通</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _render_job_detail_html(job: dict, extra_desc: str = "", full_detail: dict | None = None) -> str:
    """单岗位详情卡 (未登录/未选中 返回空态)."""
    title = _safe(job.get("title", ""))
    company = _safe(job.get("company", ""))
    salary = _safe(job.get("salary", ""))
    area = _safe(job.get("area", ""))
    hr_active = _safe(job.get("hr_active", "") or "未知")
    tags = _safe(job.get("tags", ""))
    applied = job.get("applied", False)
    full = full_detail or {}
    desc = _safe(extra_desc or full.get("description", ""))[:1200]

    applied_badge = (
        '<span class="dj-badge dj-badge-green">'
        '<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8 7 12 13 4"></polyline></svg>'
        '已沟通</span>'
        if applied else ""
    )

    meta_rows = [
        ("薪资", salary),
        ("地区", area),
        ("HR 活跃", hr_active),
    ]
    meta_html = "".join(
        f'<div class="dj-meta-row"><div class="dj-meta-k">{_safe(k)}</div>'
        f'<div class="dj-meta-v">{v}</div></div>'
        for k, v in meta_rows if v
    )

    tag_chips = ""
    if tags:
        chips = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
        tag_chips = "".join(
            f'<span class="dj-chip dj-chip-blue">{_safe(t)}</span>' for t in chips[:10]
        )

    desc_block = (
        f'<div class="dj-desc-title">岗位描述</div>'
        f'<div class="dj-desc-body">{desc}</div>'
        if desc else ""
    )

    return (
        '<div class="dlv-root">'
        '  <div class="dj-card">'
        '    <div class="dj-head">'
        f'      <div class="dj-title">{title or "—"}</div>'
        f'      {applied_badge}'
        '    </div>'
        f'    <div class="dj-company">{company}</div>'
        f'    <div class="dj-meta">{meta_html}</div>'
        + (f'<div class="dj-tags">{tag_chips}</div>' if tag_chips else "")
        + desc_block
        + "  </div>"
        "</div>"
    )


def _empty_detail_html() -> str:
    return (
        '<div class="dlv-root">'
        '  <div class="dj-card dj-empty">'
        '    <div class="dj-empty-icon">'
        '      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        '        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>'
        '        <line x1="9" y1="9" x2="15" y2="9"></line>'
        '        <line x1="9" y1="13" x2="15" y2="13"></line>'
        '        <line x1="9" y1="17" x2="12" y2="17"></line>'
        '      </svg>'
        '    </div>'
        '    <div class="dj-empty-title">请在上方搜索结果中选中岗位</div>'
        '    <div class="dj-empty-sub">选中后可在此查看完整 JD、发起沟通或加入批量队列</div>'
        '  </div>'
        '</div>'
    )


# ------------------------------------------------------------------
# Business logic (签名不变)
# ------------------------------------------------------------------

def _preflight_check(user_name: str) -> str | None:
    """Pre-delivery checks: login, hours, daily limit. Returns None if OK."""
    c = get_crawler()
    if not c.is_running or not c.is_logged_in:
        return "请先前往「BOSS 账号」页面连接并登录 BOSS 直聘"
    settings = get_settings()
    hour = datetime.now().hour
    if not (settings.DELIVERY_START_HOUR <= hour < settings.DELIVERY_END_HOUR):
        return (
            f"当前不在投递时段 ({settings.DELIVERY_START_HOUR}:00 "
            f"- {settings.DELIVERY_END_HOUR}:00), 请稍后再试"
        )
    today_count = DeliveryRecordCRUD.get_today_count(user_name=user_name)
    if today_count >= settings.MAX_DAILY_DELIVERY:
        return f"今日投递已达上限 ({settings.MAX_DAILY_DELIVERY}), 明日再试"
    return None


def _get_greeting(user_name: str) -> str:
    return SysConfigCRUD.get("boss_greeting_template", user_name=user_name) or ""


def _load_blacklists(user_name: str = "") -> tuple[list[str], list[str]]:
    """Load company/title blacklists from DB config."""
    raw_co = SysConfigCRUD.get("boss_blacklist_company", user_name=user_name) or ""
    raw_ti = SysConfigCRUD.get("boss_blacklist_title", user_name=user_name) or ""
    co_list = [w.strip() for w in raw_co.splitlines() if w.strip()]
    ti_list = [w.strip() for w in raw_ti.splitlines() if w.strip()]
    return co_list, ti_list


def _search_jobs(keyword, city, hr_filter, state):
    # 先 disable 两个投递按钮, 搜索完成再根据结果启用
    disabled_btns = (gr.update(interactive=False), gr.update(interactive=False))
    if not keyword or not keyword.strip():
        yield [], [], _status_html("请输入搜索关键词", "err"), *disabled_btns
        return
    c = get_crawler()
    if not c.is_running:
        yield [], [], _status_html("请先在「BOSS 账号」页面连接 BOSS 直聘", "err"), *disabled_btns
        return
    if not c.is_logged_in:
        yield [], [], _status_html("请先在「BOSS 账号」页面扫码登录", "err"), *disabled_btns
        return

    yield (
        gr.update(),
        gr.update(),
        _status_html(f"正在搜索「{keyword.strip()}」, 请稍候…", "info"),
        *disabled_btns,
    )

    try:
        jobs = c.search_jobs(keyword.strip(), city or "全国")
        if not jobs:
            yield [], [], _status_html("未搜索到岗位, 请调整关键词或检查登录状态", "warn"), *disabled_btns
            return

        if hr_filter and hr_filter != "不限":
            jobs = [j for j in jobs if hr_filter in j.get("hr_active", "")]

        user_name = state.get("user_name", "") if state else ""
        bl_co, bl_ti = _load_blacklists(user_name)
        if bl_co or bl_ti:
            before = len(jobs)
            jobs = [
                j for j in jobs
                if not any(kw in j.get("company", "") for kw in bl_co)
                and not any(kw in j.get("title", "") for kw in bl_ti)
            ]
            filtered = before - len(jobs)
            if filtered > 0:
                logger.info("黑名单过滤掉 %d 个岗位", filtered)

        table = [
            [
                i + 1,
                j["title"],
                j["company"],
                j["salary"],
                j["area"],
                j.get("hr_active", "") or "-",
                "✓" if j.get("applied") else "",
                j["tags"],
            ]
            for i, j in enumerate(jobs)
        ]
        has_jobs = len(jobs) > 0
        yield (
            table, jobs,
            _status_html(f"搜索完成, 找到 {len(jobs)} 个岗位", "ok"),
            gr.update(interactive=False),
            gr.update(interactive=has_jobs),
        )
    except Exception as e:
        logger.error("搜索岗位异常: %s", e)
        yield [], [], _status_html(f"搜索异常: {e}", "err"), *disabled_btns


def _on_job_select(evt: gr.SelectData, all_jobs):
    try:
        row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        if 0 <= row < len(all_jobs):
            job = all_jobs[row]
            c = get_crawler()
            # 只有在已登录且选中有效岗位时才启用 "发起沟通" 按钮
            enable = bool(c.is_logged_in)
            return str(row), _render_job_detail_html(job), gr.update(interactive=enable)
    except Exception:
        pass
    return "", _empty_detail_html(), gr.update(interactive=False)


def _view_detail(selected_idx, all_jobs):
    if not selected_idx:
        return _empty_detail_html()
    try:
        idx = int(selected_idx)
        if idx < 0 or idx >= len(all_jobs):
            return _render_job_detail_html({"title": "选择无效"})
        job = all_jobs[idx]
        c = get_crawler()
        if not c.is_running:
            return _render_job_detail_html(
                {"title": job.get("title", ""), "company": "浏览器未连接, 请先前往「BOSS 账号」"}
            )
        detail = c.get_job_detail(job["url"]) or {}
        return _render_job_detail_html(job, full_detail=detail)
    except Exception as e:
        return _render_job_detail_html({"title": "获取详情失败", "company": str(e)})


def _rebuild_table(all_jobs) -> list:
    """Rebuild the display table from all_jobs (reflects updated applied status)."""
    c = get_crawler()
    return [
        [
            i + 1,
            j["title"],
            j["company"],
            j["salary"],
            j["area"],
            j.get("hr_active", "") or "-",
            "✓" if j.get("applied") or c.is_applied(j.get("url", "")) else "",
            j["tags"],
        ]
        for i, j in enumerate(all_jobs)
    ]


def _apply_job(selected_idx, all_jobs, resume_choice, state):
    user_name = state.get("user_name", "") if state else ""
    if not selected_idx:
        yield _status_html("请先选中一个岗位", "err"), gr.update(), gr.update()
        return
    if not resume_choice:
        yield _status_html("请先选择要投递的简历", "err"), gr.update(), gr.update()
        return

    try:
        err = _preflight_check(user_name)
        if err:
            yield _status_html(err, "err"), gr.update(), gr.update()
            return

        idx = int(selected_idx)
        if idx < 0 or idx >= len(all_jobs):
            yield _status_html("选择无效", "err"), gr.update(), gr.update()
            return
        job = all_jobs[idx]

        c = get_crawler()
        if c.is_applied(job.get("url", "")):
            yield (
                _status_html("该岗位已沟通过, 无需重复投递", "warn"),
                gr.update(),
                gr.update(),
            )
            return

        # 进入耗时阶段, 推送 loading 状态条
        yield (
            _status_loading_html(f"正在向 {job.get('company','')} · {job.get('title','')} 发起沟通…"),
            gr.update(),
            gr.update(),
        )

        risk = risk_check_node({"user_name": user_name})
        if not risk.get("risk_passed", False):
            yield (
                _status_html(f"风控拦截: {risk.get('risk_message', '请稍后再试')}", "err"),
                gr.update(),
                gr.update(),
            )
            return

        try:
            resume_id = int(resume_choice.split(":")[0])
        except (ValueError, IndexError):
            yield (
                _status_html("简历选择格式错误，请重新选择", "err"),
                gr.update(),
                gr.update(),
            )
            return
        greeting = _get_greeting(user_name)
        result = c.start_chat(job["url"], greeting=greeting)

        status = "success" if "已发起" in result else "failed"
        kind = "ok" if status == "success" else "err"
        if "已发起" in result:
            job["applied"] = True
        try:
            DeliveryRecordCRUD.create(
                company=job.get("company", ""),
                position=job.get("title", ""),
                position_url=job.get("url", ""),
                resume_id=resume_id,
                status=status,
                user_name=user_name,
            )
        except Exception as db_err:
            logger.warning("投递记录写入失败: %s", db_err)

        yield _status_html(result, kind), _rebuild_table(all_jobs), all_jobs
    except Exception as e:
        yield _status_html(f"投递失败: {e}", "err"), gr.update(), gr.update()


def _batch_apply(all_jobs, resume_choice, batch_count, state):
    user_name = state.get("user_name", "") if state else ""
    if not all_jobs:
        yield "无搜索结果"
        return
    if not resume_choice:
        yield "请先选择简历"
        return

    try:
        err = _preflight_check(user_name)
        if err:
            yield err
            return

        c = get_crawler()
        settings = get_settings()
        today_count = DeliveryRecordCRUD.get_today_count(user_name=user_name)
        remaining = settings.MAX_DAILY_DELIVERY - today_count

        candidates = [j for j in all_jobs if not c.is_applied(j.get("url", ""))]
        if not candidates:
            yield "所有搜索结果均已沟通过, 请更换关键词搜索新岗位"
            return

        count = min(int(batch_count or 5), len(candidates), 10, remaining)
        try:
            resume_id = int(resume_choice.split(":")[0])
        except (ValueError, IndexError):
            yield "简历选择格式错误，请重新选择"
            return
        greeting = _get_greeting(user_name)

        if count <= 0:
            yield "今日投递额度已用完, 请明日再试"
            return

        results = []
        for i in range(count):
            yield f"正在投递第 {i + 1}/{count} 个岗位..."

            risk = risk_check_node({"user_name": user_name})
            if not risk.get("risk_passed", False):
                results.append(f"[{i+1}] 风控拦截, 停止投递")
                break

            job = candidates[i]
            msg = c.start_chat(job["url"], greeting=greeting)
            status = "success" if "已发起" in msg else "failed"
            try:
                DeliveryRecordCRUD.create(
                    company=job.get("company", ""),
                    position=job.get("title", ""),
                    position_url=job.get("url", ""),
                    resume_id=resume_id,
                    status=status,
                    user_name=user_name,
                )
            except Exception:
                pass
            results.append(f"[{i+1}] {job['title']} @ {job['company']} → {msg}")
            yield "\n".join(results)

            if i < count - 1:
                lo = min(settings.MIN_DELAY_SECONDS, settings.MAX_DELAY_SECONDS)
                hi = max(settings.MIN_DELAY_SECONDS, settings.MAX_DELAY_SECONDS)
                time.sleep(random.uniform(lo, hi))

        yield "\n".join(results) if results else "无结果"
    except Exception as e:
        logger.error("批量投递异常: %s", e)
        yield f"批量投递异常: {e}"


# ------------------------------------------------------------------
# Page builder
# ------------------------------------------------------------------

def create_delivery_page(login_state):
    """创建自动化投递页面 (Bento 玻璃风)"""
    gr.HTML(_DLV_STYLE)

    with gr.Column(elem_id="dlv-page-root", elem_classes=["dlv-scope"]):
        gr.HTML(_render_header_html())

        # ============ 连接状态 Banner 卡 ============
        conn_banner = gr.HTML(value=_connection_banner(), elem_id="dlv-conn-banner")

        # ============ 搜索卡 ============
        with gr.Column(elem_classes=["dlv-card", "dlv-card-search"]):
            gr.HTML(
                '<div class="dlv-card-head">'
                '  <div class="dlv-ch-icon dlv-ch-blue">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <circle cx="11" cy="11" r="8"></circle>'
                '      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>'
                '    </svg>'
                '  </div>'
                '  <div class="dlv-ch-title">搜索岗位</div>'
                '  <div class="dlv-ch-sub">关键词 · 城市 · HR 活跃度</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["dlv-search-row"]):
                keyword_input = gr.Textbox(
                    label="搜索关键词",
                    placeholder="如: Python工程师、前端开发、产品经理",
                    scale=5,
                    elem_classes=["dlv-input-field", "dlv-search-keyword"],
                )
                city_input = gr.Dropdown(
                    choices=CITY_LIST,
                    value="全国",
                    label="城市",
                    scale=2,
                    elem_classes=["dlv-input-field"],
                )
            with gr.Row(elem_classes=["dlv-search-row-2"]):
                hr_filter = gr.Dropdown(
                    choices=HR_ACTIVITY_OPTIONS,
                    value="不限",
                    label="HR 活跃度筛选",
                    scale=3,
                    elem_classes=["dlv-input-field"],
                )
                search_btn = gr.Button(
                    "搜索岗位",
                    variant="primary",
                    scale=3,
                    elem_classes=["dlv-btn", "dlv-btn-primary"],
                )
                refresh_conn_btn = gr.Button(
                    "刷新连接状态",
                    variant="secondary",
                    scale=2,
                    elem_classes=["dlv-btn", "dlv-btn-muted"],
                )

        # ============ 操作状态条 ============
        op_msg = gr.HTML(value="", elem_id="dlv-opmsg-slot")

        # ============ 结果表 + 详情/操作卡 (左 6 / 右 5) ============
        jobs_state = gr.State([])

        with gr.Column(elem_classes=["dlv-card", "dlv-card-results"]):
            gr.HTML(
                '<div class="dlv-card-head">'
                '  <div class="dlv-ch-icon dlv-ch-violet">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <line x1="8" y1="6" x2="21" y2="6"></line>'
                '      <line x1="8" y1="12" x2="21" y2="12"></line>'
                '      <line x1="8" y1="18" x2="21" y2="18"></line>'
                '      <line x1="3" y1="6" x2="3.01" y2="6"></line>'
                '      <line x1="3" y1="12" x2="3.01" y2="12"></line>'
                '      <line x1="3" y1="18" x2="3.01" y2="18"></line>'
                '    </svg>'
                '  </div>'
                '  <div class="dlv-ch-title">搜索结果 &amp; 投递</div>'
                '  <div class="dlv-ch-sub">点击行查看详情 · 单个 / 批量沟通</div>'
                '</div>'
                '<div class="dlv-table-hint" aria-hidden="true">'
                '  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
                '    <circle cx="11" cy="11" r="8"></circle>'
                '    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>'
                '  </svg>'
                '  <span>列表为空: 在上方输入关键词 → 点击「搜索」开始拉取岗位</span>'
                '</div>'
            )
            job_table = gr.Dataframe(
                headers=["序号", "岗位", "公司", "薪资", "地区", "HR活跃", "已投", "要求"],
                datatype=["number", "str", "str", "str", "str", "str", "str", "str"],
                value=[],
                interactive=False,
                elem_classes=["dlv-table"],
            )

            with gr.Row(elem_classes=["dlv-op-row"]):
                with gr.Column(scale=5, elem_classes=["dlv-op-col-left"]):
                    selected_idx = gr.Textbox(
                        label="已选岗位序号 (点击表格自动填入)",
                        placeholder="未选中: 请先在上方表格点击一行",
                        interactive=False,
                        elem_classes=["dlv-input-field", "dlv-selected-box"],
                    )
                    with gr.Row(elem_classes=["dlv-resume-row"]):
                        resume_dd = gr.Dropdown(
                            choices=[],
                            label="投递简历",
                            interactive=True,
                            scale=4,
                            elem_classes=["dlv-input-field"],
                        )
                        refresh_resume_btn = gr.Button(
                            "刷新",
                            size="sm",
                            scale=1,
                            elem_classes=["dlv-btn-mini", "dlv-btn-muted"],
                        )
                    with gr.Row(elem_classes=["dlv-action-row"]):
                        detail_btn = gr.Button(
                            "查看详情",
                            variant="secondary",
                            elem_classes=["dlv-btn", "dlv-btn-info"],
                        )
                        apply_btn = gr.Button(
                            "发起沟通 (单个)",
                            variant="primary",
                            interactive=False,
                            elem_classes=["dlv-btn", "dlv-btn-primary"],
                        )
                with gr.Column(scale=6, elem_classes=["dlv-op-col-right"]):
                    selected_detail = gr.HTML(
                        value=_empty_detail_html(),
                        elem_id="dlv-detail-slot",
                    )

        # ============ 批量沟通卡 ============
        with gr.Column(elem_classes=["dlv-card", "dlv-card-batch"]):
            gr.HTML(
                '<div class="dlv-card-head">'
                '  <div class="dlv-ch-icon dlv-ch-pink">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <polyline points="13 17 18 12 13 7"></polyline>'
                '      <polyline points="6 17 11 12 6 7"></polyline>'
                '    </svg>'
                '  </div>'
                '  <div class="dlv-ch-title">批量沟通</div>'
                '  <div class="dlv-ch-sub">对搜索结果前 N 个未投递岗位批量发起</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["dlv-batch-row"]):
                with gr.Column(scale=4, elem_classes=["dlv-batch-slider-col"]):
                    batch_count = gr.Slider(
                        1, 10, value=5, step=1,
                        label="批量沟通数量 (前 N 个)",
                        elem_classes=["dlv-slider", "dlv-slider-ticked"],
                    )
                    gr.HTML(
                        '<div class="dlv-slider-ticks">'
                        '  <span>1</span><span>·</span><span>3</span>'
                        '  <span>·</span><span>5</span><span>·</span>'
                        '  <span>7</span><span>·</span><span>10</span>'
                        '</div>'
                    )
                batch_btn = gr.Button(
                    "批量沟通",
                    variant="primary",
                    scale=1,
                    interactive=False,
                    elem_classes=["dlv-btn", "dlv-btn-primary"],
                )

            batch_result = gr.Textbox(
                label="批量投递结果",
                placeholder="点击「批量沟通」后, 这里会逐条显示每个岗位的投递结果与失败原因…",
                interactive=False,
                lines=6,
                elem_classes=["dlv-input-field", "dlv-batch-log"],
            )

    # ==================== Event bindings ====================

    def _refresh_resumes(state):
        user_name = state.get("user_name", "") if state else ""
        return gr.Dropdown(choices=_resume_choices(user_name))

    refresh_resume_btn.click(
        fn=_refresh_resumes,
        inputs=[login_state],
        outputs=[resume_dd],
    )

    def _refresh_conn_and_btns(jobs):
        banner = _connection_banner()
        has_jobs = bool(jobs)
        apply_upd, batch_upd = _btn_states(has_jobs=has_jobs)
        return banner, apply_upd, batch_upd

    refresh_conn_btn.click(
        fn=_refresh_conn_and_btns,
        inputs=[jobs_state],
        outputs=[conn_banner, apply_btn, batch_btn],
    )

    search_btn.click(
        fn=_search_jobs,
        inputs=[keyword_input, city_input, hr_filter, login_state],
        outputs=[job_table, jobs_state, op_msg, apply_btn, batch_btn],
    )

    job_table.select(
        fn=_on_job_select,
        inputs=[jobs_state],
        outputs=[selected_idx, selected_detail, apply_btn],
    )
    detail_btn.click(
        fn=_view_detail,
        inputs=[selected_idx, jobs_state],
        outputs=[selected_detail],
    )
    apply_btn.click(
        fn=_apply_job,
        inputs=[selected_idx, jobs_state, resume_dd, login_state],
        outputs=[op_msg, job_table, jobs_state],
    )
    batch_btn.click(
        fn=_batch_apply,
        inputs=[jobs_state, resume_dd, batch_count, login_state],
        outputs=[batch_result],
    )

    return conn_banner


# ================================================================
# 作用域 CSS (限定在 .dlv-scope / .dlv-root 下)
# ================================================================
# fmt: off
_DLV_STYLE = """
<style>
/* =========================================================
   Delivery Page — Bento 玻璃拟态风
   ========================================================= */
.dlv-scope { color: var(--c-text-1); }
.dlv-scope *, .dlv-root * { box-sizing: border-box; }
#dlv-page-root {
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 16px !important;
}
#dlv-page-root > .block:first-child,
#dlv-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* 页头 */
.dlv-root .dlv-head {
    display: flex; align-items: center; gap: 14px;
    margin: -10px 0 4px;
}
.dlv-root .dlv-head-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(244,114,182,0.28), rgba(79,139,255,0.22));
    border: 1px solid rgba(244,114,182,0.35);
    display: flex; align-items: center; justify-content: center;
    color: #F9A8D4;
    box-shadow: 0 8px 20px rgba(244,114,182,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.dlv-root .dlv-head-title { font-size: 22px; font-weight: 700; color: #F0F2FA; }
.dlv-root .dlv-head-sub { font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px; }

/* 通用卡片 */
.dlv-scope .dlv-card {
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
.dlv-scope .dlv-card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(255,255,255,0.16) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 22px 50px rgba(0,0,0,0.5),
        0 6px 18px rgba(52,211,153,0.14) !important;
}
.dlv-scope .dlv-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.dlv-scope .dlv-card > * { position: relative; z-index: 1; }

/* 卡头 */
.dlv-scope .dlv-card-head {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
}
/* 表格上方空态提示徽章 */
.dlv-scope .dlv-table-hint {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 12px 0 8px;
    padding: 6px 12px;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(79,139,255,0.14), rgba(167,139,250,0.10));
    border: 1px dashed rgba(141,187,255,0.32);
    color: rgba(220,228,255,0.82);
    font-size: 11.5px; font-weight: 500;
    width: fit-content;
}
.dlv-scope .dlv-table-hint svg { color: #AFC7FF; flex-shrink: 0; }
.dlv-scope .dlv-ch-icon {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.dlv-scope .dlv-ch-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.dlv-scope .dlv-ch-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(79,139,255,0.22));
    color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.35);
    box-shadow: 0 4px 14px rgba(167,139,250,0.22);
}
.dlv-scope .dlv-ch-pink {
    background: linear-gradient(135deg, rgba(244,114,182,0.28), rgba(251,146,60,0.22));
    color: #F9A8D4;
    border: 1px solid rgba(244,114,182,0.35);
    box-shadow: 0 4px 14px rgba(244,114,182,0.22);
}
.dlv-scope .dlv-ch-title { font-size: 16px; font-weight: 700; color: #F0F2FA; flex: 1; }
.dlv-scope .dlv-ch-sub { font-size: 12px; color: rgba(230,233,245,0.55); }

/* 输入字段 */
.dlv-scope .dlv-input-field textarea,
.dlv-scope .dlv-input-field input,
.dlv-scope .dlv-input-field .wrap-inner {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    border-radius: 12px !important;
}
.dlv-scope .dlv-input-field textarea:focus,
.dlv-scope .dlv-input-field input:focus {
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.12) !important;
}
.dlv-scope .dlv-search-keyword input {
    font-size: 14px !important;
    padding: 12px 14px !important;
}
.dlv-scope .dlv-selected-box input { font-size: 13px !important; }
.dlv-scope .dlv-batch-log textarea {
    min-height: 140px !important;
    font-family: 'JetBrains Mono', 'Consolas', monospace !important;
    font-size: 12.5px !important;
    line-height: 1.7 !important;
}

/* ---- 连接 Banner ---- */
.dlv-root .dcb-banner {
    display: grid;
    grid-template-columns: 40px 1fr auto;
    gap: 14px;
    align-items: center;
    padding: 14px 18px;
    border-radius: 14px;
    border: 1px solid transparent;
}
.dlv-root .dcb-ok {
    background: linear-gradient(135deg, rgba(52,211,153,0.12), rgba(79,139,255,0.08));
    border-color: rgba(52,211,153,0.28);
}
.dlv-root .dcb-warn {
    background: linear-gradient(135deg, rgba(251,146,60,0.12), rgba(244,114,182,0.08));
    border-color: rgba(251,146,60,0.28);
}
.dlv-root .dcb-icon {
    width: 38px; height: 38px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid transparent;
}
.dlv-root .dcb-icon-green {
    background: rgba(52,211,153,0.16);
    color: #6EE7B7;
    border-color: rgba(52,211,153,0.35);
    box-shadow: 0 4px 14px rgba(52,211,153,0.22);
}
.dlv-root .dcb-icon-orange {
    background: rgba(251,146,60,0.16);
    color: #FDBA74;
    border-color: rgba(251,146,60,0.35);
    box-shadow: 0 4px 14px rgba(251,146,60,0.22);
}
.dlv-root .dcb-text { min-width: 0; }
.dlv-root .dcb-title { font-size: 14.5px; font-weight: 700; color: #F0F2FA; }
.dlv-root .dcb-sub { font-size: 12.5px; color: rgba(230,233,245,0.6); margin-top: 2px; }
.dlv-root .dcb-chips { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.dlv-root .dcb-chip {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11.5px; font-weight: 600;
    border: 1px solid transparent;
}
.dlv-root .dcb-chip-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #34D399;
    box-shadow: 0 0 8px rgba(52,211,153,0.7);
    animation: dcbPulse 1.8s ease-in-out infinite;
}
.dlv-root .dcb-chip-dot-warn {
    background: #FB923C;
    box-shadow: 0 0 8px rgba(251,146,60,0.7);
}
@keyframes dcbPulse { 50% { opacity: 0.5; transform: scale(1.3); } }
.dlv-root .dcb-chip-green {
    background: rgba(52,211,153,0.14); color: #6EE7B7;
    border-color: rgba(52,211,153,0.30);
}
.dlv-root .dcb-chip-blue {
    background: rgba(79,139,255,0.14); color: #AFC7FF;
    border-color: rgba(79,139,255,0.28);
}
.dlv-root .dcb-chip-orange {
    background: rgba(251,146,60,0.14); color: #FDBA74;
    border-color: rgba(251,146,60,0.30);
}

/* ---- 搜索行 ---- */
.dlv-scope .dlv-search-row,
.dlv-scope .dlv-search-row-2 { gap: 12px !important; align-items: flex-end !important; }
.dlv-scope .dlv-resume-row { gap: 8px !important; align-items: flex-end !important; }

/* 按钮 */
.dlv-scope .dlv-btn,
.dlv-scope .dlv-btn button,
.dlv-scope .dlv-btn-mini,
.dlv-scope .dlv-btn-mini button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease, background 0.25s ease !important;
    letter-spacing: 0.3px !important;
}
.dlv-scope .dlv-btn button {
    padding: 12px 18px !important;
    font-size: 13.5px !important;
}
.dlv-scope .dlv-btn-mini button {
    padding: 8px 12px !important;
    font-size: 12.5px !important;
}
.dlv-scope .dlv-btn-primary,
.dlv-scope .dlv-btn-primary button {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 8px 20px rgba(79,139,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.dlv-scope .dlv-btn-primary:hover,
.dlv-scope .dlv-btn-primary button:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(79,139,255,0.45), inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.dlv-scope .dlv-btn-info,
.dlv-scope .dlv-btn-info button {
    background: rgba(56,189,248,0.12) !important;
    color: #7DD3FC !important;
    border: 1px solid rgba(56,189,248,0.30) !important;
}
.dlv-scope .dlv-btn-info:hover,
.dlv-scope .dlv-btn-info button:hover {
    background: rgba(56,189,248,0.18) !important;
    border-color: rgba(56,189,248,0.45) !important;
}
.dlv-scope .dlv-btn-muted,
.dlv-scope .dlv-btn-muted button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.75) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
}
.dlv-scope .dlv-btn-muted:hover,
.dlv-scope .dlv-btn-muted button:hover {
    background: rgba(79,139,255,0.12) !important;
    color: #AFC7FF !important;
    border-color: rgba(79,139,255,0.35) !important;
}
/* Disabled 态: 灰化 + 禁用手势, 覆盖所有变体 */
.dlv-scope .dlv-btn button:disabled,
.dlv-scope .dlv-btn button[disabled],
.dlv-scope .dlv-btn.disabled,
.dlv-scope .dlv-btn.disabled button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.32) !important;
    border: 1px dashed rgba(255,255,255,0.10) !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
    filter: grayscale(0.4) !important;
    opacity: 0.62 !important;
    transform: none !important;
}
.dlv-scope .dlv-btn button:disabled:hover,
.dlv-scope .dlv-btn button[disabled]:hover {
    background: rgba(255,255,255,0.04) !important;
    border-color: rgba(255,255,255,0.10) !important;
    transform: none !important;
}

/* ---- 操作区布局 ---- */
.dlv-scope .dlv-op-row { gap: 16px !important; align-items: stretch !important; }
.dlv-scope .dlv-op-col-left { gap: 10px !important; display: flex !important; flex-direction: column !important; }
.dlv-scope .dlv-op-col-right { display: flex !important; flex-direction: column !important; }
.dlv-scope .dlv-action-row { gap: 10px !important; margin-top: 4px; }
.dlv-scope .dlv-batch-row { gap: 14px !important; align-items: flex-end !important; }

/* ---- 岗位详情卡 ---- */
.dlv-root .dj-card {
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 14px;
    padding: 16px 18px;
    height: 100%;
    display: flex; flex-direction: column; gap: 10px;
}
.dlv-root .dj-head {
    display: flex; align-items: flex-start; justify-content: space-between; gap: 10px;
}
.dlv-root .dj-title {
    font-size: 16px; font-weight: 700; color: #F0F2FA;
    line-height: 1.4;
}
.dlv-root .dj-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 999px;
    font-size: 11.5px; font-weight: 700;
    flex-shrink: 0;
}
.dlv-root .dj-badge-green {
    background: rgba(52,211,153,0.15); color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.32);
}
.dlv-root .dj-company {
    font-size: 13px; color: rgba(230,233,245,0.8);
    font-weight: 500;
}
.dlv-root .dj-meta {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
    padding: 10px 0;
    border-top: 1px dashed rgba(255,255,255,0.06);
}
.dlv-root .dj-meta-row {
    display: flex; flex-direction: column;
    padding: 6px 10px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px;
}
.dlv-root .dj-meta-k {
    font-size: 11px; color: rgba(230,233,245,0.5);
    margin-bottom: 3px;
    font-weight: 600; letter-spacing: 0.3px;
}
.dlv-root .dj-meta-v {
    font-size: 13px; color: #F0F2FA; font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dlv-root .dj-tags {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding-top: 2px;
}
.dlv-root .dj-chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    border: 1px solid transparent;
}
.dlv-root .dj-chip-blue {
    background: rgba(79,139,255,0.14); color: #AFC7FF;
    border-color: rgba(79,139,255,0.28);
}
.dlv-root .dj-desc-title {
    font-size: 12px; font-weight: 600;
    color: rgba(230,233,245,0.5);
    letter-spacing: 0.8px; text-transform: uppercase;
    margin-top: 4px;
    padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.dlv-root .dj-desc-body {
    font-size: 12.5px; color: rgba(230,233,245,0.8);
    line-height: 1.75;
    max-height: 300px; overflow-y: auto;
    white-space: pre-wrap;
}

/* 空详情卡 */
.dlv-root .dj-empty {
    align-items: center; justify-content: center;
    text-align: center;
    border-style: dashed !important;
    border-color: rgba(255,255,255,0.1) !important;
    background: rgba(17,22,48,0.25) !important;
    min-height: 180px;
}
.dlv-root .dj-empty-icon {
    color: rgba(141,187,255,0.5);
    filter: drop-shadow(0 0 10px rgba(79,139,255,0.2));
    margin-bottom: 8px;
}
.dlv-root .dj-empty-title {
    font-size: 13.5px; font-weight: 600;
    color: rgba(230,233,245,0.75);
}
.dlv-root .dj-empty-sub {
    font-size: 12px; color: rgba(230,233,245,0.5);
    margin-top: 4px;
    max-width: 280px; line-height: 1.7;
}

/* 状态条 */
.dlv-root .dlv-status {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    font-size: 12.5px;
    color: rgba(230,233,245,0.85);
    backdrop-filter: blur(10px);
}
.dlv-root .dsi-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.dlv-root .dsi-blue   { background: #8DBBFF; box-shadow: 0 0 10px rgba(141,187,255,0.6); }
.dlv-root .dsi-green  { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.6); }
.dlv-root .dsi-red    { background: #F87171; box-shadow: 0 0 10px rgba(248,113,113,0.6); }
.dlv-root .dsi-orange { background: #FB923C; box-shadow: 0 0 10px rgba(251,146,60,0.6); }

/* 反馈图标 (✓ / ✗ / ⚠) + spinner */
.dlv-root .dsi-icon {
    width: 20px; height: 20px;
    flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%;
    border: 1px solid currentColor;
}
.dlv-root .dsi-icon-ok {
    color: #34D399;
    background: rgba(52,211,153,0.15);
    box-shadow: 0 0 12px rgba(52,211,153,0.45);
    animation: dlvPopIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.dlv-root .dsi-icon-err {
    color: #F87171;
    background: rgba(248,113,113,0.15);
    box-shadow: 0 0 12px rgba(248,113,113,0.45);
    animation: dlvShake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
.dlv-root .dsi-icon-warn {
    color: #FB923C;
    background: rgba(251,146,60,0.15);
    box-shadow: 0 0 12px rgba(251,146,60,0.42);
}
.dlv-root .dlv-status-ok   { border-color: rgba(52,211,153,0.32) !important; background: rgba(52,211,153,0.07) !important; }
.dlv-root .dlv-status-err  { border-color: rgba(248,113,113,0.32) !important; background: rgba(248,113,113,0.07) !important; }
.dlv-root .dlv-status-warn { border-color: rgba(251,146,60,0.32) !important; background: rgba(251,146,60,0.07) !important; }
.dlv-root .dlv-status-loading {
    border-color: rgba(141,187,255,0.30) !important;
    background: rgba(79,139,255,0.07) !important;
    color: #AFC7FF;
}
.dlv-root .dsi-spinner {
    width: 20px; height: 20px;
    flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%;
    color: #AFC7FF;
    background: rgba(79,139,255,0.18);
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 0 12px rgba(79,139,255,0.42);
}
.dlv-root .dsi-spinner svg { animation: dlvSpin 0.9s linear infinite; }
@keyframes dlvSpin { to { transform: rotate(360deg); } }
@keyframes dlvPopIn {
    0%   { opacity: 0; transform: scale(0.4); }
    60%  { opacity: 1; transform: scale(1.18); }
    100% { opacity: 1; transform: scale(1); }
}
@keyframes dlvShake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-3px); }
    40% { transform: translateX(3px); }
    60% { transform: translateX(-2px); }
    80% { transform: translateX(2px); }
}

/* 表格微调 (具体暗色样式由 DARK_OVERRIDE_CSS 兜底) */
.dlv-scope .dlv-table table { font-size: 13px !important; }
.dlv-scope .dlv-table thead th { font-weight: 700 !important; }

/* Slider tweaks */
.dlv-scope .dlv-slider .wrap { padding: 2px 0 !important; }

/* ---- 批量 slider: 刻度尺 + 紫色拇指 ---- */
.dlv-scope .dlv-batch-slider-col { display: flex !important; flex-direction: column !important; gap: 2px !important; }
.dlv-scope .dlv-slider-ticked { padding-bottom: 2px !important; }
.dlv-scope .dlv-slider-ticked input[type="range"] {
    accent-color: #795AFF !important;
}
/* 主轨道下叠加 9 等分细刻度 (利用 repeating-linear-gradient) */
.dlv-scope .dlv-slider-ticked input[type="range"] {
    background-image:
        linear-gradient(90deg, rgba(121,90,255,0.55), rgba(79,139,255,0.55)),
        repeating-linear-gradient(
            to right,
            rgba(255,255,255,0.22) 0 1px,
            transparent 1px calc(100% / 9)
        ) !important;
    background-size: var(--gr-slider-fill, 50%) 100%, 100% 100% !important;
    background-repeat: no-repeat, no-repeat !important;
    background-position: left center, left center !important;
}
.dlv-scope .dlv-slider-ticks {
    display: grid;
    grid-template-columns: repeat(9, 1fr);
    align-items: center;
    margin: 6px 12px 0 12px;
    color: rgba(230,233,245,0.55);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    user-select: none;
    line-height: 1;
}
.dlv-scope .dlv-slider-ticks span {
    text-align: center;
    font-variant-numeric: tabular-nums;
}
.dlv-scope .dlv-slider-ticks span:nth-child(odd) {
    color: rgba(230,233,245,0.85);
}
.dlv-scope .dlv-slider-ticks span:nth-child(even) {
    color: rgba(230,233,245,0.30);
    font-weight: 400;
}

/* 窄屏 */
@media (max-width: 1000px) {
    .dlv-scope .dlv-op-row { flex-direction: column !important; }
    .dlv-root .dj-meta { grid-template-columns: 1fr 1fr; }
    .dlv-scope .dlv-search-row,
    .dlv-scope .dlv-search-row-2 { flex-direction: column !important; align-items: stretch !important; }
    .dlv-root .dcb-banner { grid-template-columns: 40px 1fr; }
    .dlv-root .dcb-chips { grid-column: 1 / -1; justify-content: flex-start; }
}
</style>
"""
# fmt: on
