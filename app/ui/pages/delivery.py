"""自动化投递页面

搜索岗位 → 查看详情 → 一键沟通 / 批量投递。
BOSS 直聘的连接和登录在「BOSS 账号」页面完成。
集成 HR 活跃度筛选、去重检测、每日额度控制。
"""

from __future__ import annotations

import random
import time

import gradio as gr

from datetime import datetime

from app.agents.risk_agent import risk_check_node
from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD, ResumeCRUD, SysConfigCRUD
from app.utils.boss_crawler import CITY_LIST, HR_ACTIVITY_OPTIONS, get_crawler

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resume_choices(user_name: str = "") -> list[str]:
    try:
        resumes = ResumeCRUD.get_all(user_name=user_name)
        return [f"{r['id']}:{r['file_name']}" for r in resumes]
    except Exception:
        return []


def _connection_banner() -> str:
    c = get_crawler()
    if c.is_running and c.is_logged_in:
        return (
            '<div class="alert-bar success">'
            "✓ BOSS 直聘已连接并登录, 可以开始搜索和投递。"
            "</div>"
        )
    return (
        '<div class="alert-bar">'
        "⚠ 请先前往「BOSS 账号」页面连接并登录 BOSS 直聘, 然后再进行搜索和投递。"
        "</div>"
    )


# ------------------------------------------------------------------
# Search
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
    if not keyword or not keyword.strip():
        return [], [], "请输入搜索关键词"
    c = get_crawler()
    if not c.is_running:
        return [], [], "请先在「BOSS 账号」页面连接 BOSS 直聘"
    if not c.is_logged_in:
        return [], [], "请先在「BOSS 账号」页面扫码登录"

    jobs = c.search_jobs(keyword.strip(), city or "全国")
    if not jobs:
        return [], [], "未搜索到岗位, 请调整关键词或检查登录状态"

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
    return table, jobs, f"搜索完成, 找到 {len(jobs)} 个岗位"


def _on_job_select(evt: gr.SelectData, all_jobs):
    try:
        row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        if 0 <= row < len(all_jobs):
            job = all_jobs[row]
            applied_mark = " **(已沟通)**" if job.get("applied") else ""
            detail = (
                f"**岗位**: {job['title']}{applied_mark}\n"
                f"**公司**: {job['company']}\n"
                f"**薪资**: {job['salary']}\n"
                f"**地区**: {job['area']}\n"
                f"**HR 活跃**: {job.get('hr_active', '未知')}\n"
                f"**要求**: {job['tags']}"
            )
            return str(row), detail
    except Exception:
        pass
    return "", ""


# ------------------------------------------------------------------
# Detail / Apply
# ------------------------------------------------------------------

def _view_detail(selected_idx, all_jobs):
    if not selected_idx:
        return "请先在搜索结果中点击选中一个岗位"
    try:
        idx = int(selected_idx)
        if idx < 0 or idx >= len(all_jobs):
            return "选择无效"
        job = all_jobs[idx]
        c = get_crawler()
        if not c.is_running:
            return "浏览器未连接, 请前往「BOSS 账号」页面连接"
        detail = c.get_job_detail(job["url"])
        if not detail:
            return "获取详情失败"
        desc = detail.get("description", "")
        if len(desc) > 1000:
            desc = desc[:1000] + "..."
        return (
            f"### {detail.get('title', job['title'])}\n"
            f"**公司**: {detail.get('company', job['company'])}\n"
            f"**薪资**: {detail.get('salary', job['salary'])}\n\n"
            f"**岗位描述**:\n\n{desc}"
        )
    except Exception as e:
        return f"获取详情失败: {e}"


def _apply_job(selected_idx, all_jobs, resume_choice, state):
    user_name = state.get("user_name", "") if state else ""
    if not selected_idx:
        return "请先选中一个岗位"
    if not resume_choice:
        return "请先选择要投递的简历"

    err = _preflight_check(user_name)
    if err:
        return err

    try:
        idx = int(selected_idx)
        if idx < 0 or idx >= len(all_jobs):
            return "选择无效"
        job = all_jobs[idx]

        c = get_crawler()
        if c.is_applied(job.get("url", "")):
            return "该岗位已沟通过, 无需重复投递"

        risk = risk_check_node({})
        if not risk.get("risk_passed", False):
            return f"风控拦截: {risk.get('risk_message', '请稍后再试')}"

        resume_id = int(resume_choice.split(":")[0])
        greeting = _get_greeting(user_name)
        result = c.start_chat(job["url"], greeting=greeting)

        status = "success" if "已发起" in result or "已点击" in result else "failed"
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

        return result
    except Exception as e:
        return f"投递失败: {e}"


def _batch_apply(all_jobs, resume_choice, batch_count, state):
    user_name = state.get("user_name", "") if state else ""
    if not all_jobs:
        return "无搜索结果"
    if not resume_choice:
        return "请先选择简历"

    err = _preflight_check(user_name)
    if err:
        return err

    c = get_crawler()
    settings = get_settings()
    today_count = DeliveryRecordCRUD.get_today_count(user_name=user_name)
    remaining = settings.MAX_DAILY_DELIVERY - today_count

    candidates = [j for j in all_jobs if not c.is_applied(j.get("url", ""))]
    if not candidates:
        return "所有搜索结果均已沟通过, 请更换关键词搜索新岗位"

    count = min(int(batch_count or 5), len(candidates), 10, remaining)
    resume_id = int(resume_choice.split(":")[0])
    greeting = _get_greeting(user_name)

    results = []
    for i in range(count):
        risk = risk_check_node({})
        if not risk.get("risk_passed", False):
            results.append(f"[{i+1}] 风控拦截, 停止投递")
            break

        job = candidates[i]
        msg = c.start_chat(job["url"], greeting=greeting)
        status = "success" if "已发起" in msg or "已点击" in msg else "failed"
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

        if i < count - 1:
            time.sleep(random.uniform(
                settings.MIN_DELAY_SECONDS, settings.MAX_DELAY_SECONDS,
            ))

    return "\n".join(results) if results else "无结果"


# ------------------------------------------------------------------
# Page builder
# ------------------------------------------------------------------

def create_delivery_page(login_state):
    """创建自动化投递页面 — 搜索岗位 → 一键投递"""

    gr.Markdown("## 自动化投递")
    conn_banner = gr.HTML(value=_connection_banner())
    op_msg = gr.Textbox(label="操作状态", interactive=False, max_lines=2)

    # ==================== Search ====================
    gr.Markdown("### 搜索岗位")
    with gr.Row():
        keyword_input = gr.Textbox(
            label="搜索关键词",
            placeholder="如: Python工程师、前端开发、产品经理",
            scale=3,
        )
        city_input = gr.Dropdown(
            choices=CITY_LIST, value="全国", label="城市", scale=1,
        )
    with gr.Row():
        hr_filter = gr.Dropdown(
            choices=HR_ACTIVITY_OPTIONS,
            value="不限",
            label="HR 活跃度筛选",
            scale=2,
        )
        search_btn = gr.Button("搜索岗位", variant="primary", scale=2)
        refresh_conn_btn = gr.Button("刷新连接状态", variant="secondary", scale=1)

    # ==================== Results & Apply ====================
    gr.Markdown("### 搜索结果 & 投递")
    jobs_state = gr.State([])
    job_table = gr.Dataframe(
        headers=["序号", "岗位", "公司", "薪资", "地区", "HR活跃", "已投", "要求"],
        datatype=["number", "str", "str", "str", "str", "str", "str", "str"],
        value=[],
        interactive=False,
    )

    with gr.Row():
        selected_idx = gr.Textbox(
            label="已选岗位序号 (点击表格自动填入)", interactive=False, scale=1,
        )
        resume_dd = gr.Dropdown(
            choices=[], label="投递简历", interactive=True, scale=2,
        )

        def _refresh_resumes(state):
            user_name = state.get("user_name", "") if state else ""
            return gr.Dropdown(choices=_resume_choices(user_name))

        gr.Button("刷新简历", size="sm", scale=0).click(
            fn=_refresh_resumes,
            inputs=[login_state],
            outputs=[resume_dd],
        )

    selected_detail = gr.Markdown(value="")

    with gr.Row():
        detail_btn = gr.Button("查看详情", variant="secondary", scale=1)
        apply_btn = gr.Button("发起沟通 (单个)", variant="primary", scale=1)
    with gr.Row():
        batch_count = gr.Slider(
            1, 10, value=5, step=1, label="批量沟通数量 (前 N 个)", scale=3,
        )
        batch_btn = gr.Button("批量沟通", variant="primary", scale=1)

    batch_result = gr.Textbox(label="批量投递结果", interactive=False, lines=6)

    # ==================== Event bindings ====================

    refresh_conn_btn.click(
        fn=lambda: _connection_banner(),
        outputs=[conn_banner],
    )

    search_btn.click(
        fn=_search_jobs,
        inputs=[keyword_input, city_input, hr_filter, login_state],
        outputs=[job_table, jobs_state, op_msg],
    )

    job_table.select(
        fn=_on_job_select,
        inputs=[jobs_state],
        outputs=[selected_idx, selected_detail],
    )
    detail_btn.click(
        fn=_view_detail,
        inputs=[selected_idx, jobs_state],
        outputs=[selected_detail],
    )
    apply_btn.click(
        fn=_apply_job,
        inputs=[selected_idx, jobs_state, resume_dd, login_state],
        outputs=[op_msg],
    )
    batch_btn.click(
        fn=_batch_apply,
        inputs=[jobs_state, resume_dd, batch_count, login_state],
        outputs=[batch_result],
    )

    return conn_banner
