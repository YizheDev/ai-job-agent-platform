"""BOSS 直聘账号管理页面

连接 / 扫码登录 / Cookie 管理 / 个人信息展示 /
打招呼话术模板 / 公司&岗位黑名单。
"""

from __future__ import annotations

import html as html_mod
import io

import gradio as gr
from PIL import Image

from app.core.logger import get_logger
from app.db.crud import SysConfigCRUD
from app.utils.boss_crawler import get_crawler
from app.utils.security_util import clear_cookie

logger = get_logger(__name__)

CFG_GREETING = "boss_greeting_template"
CFG_BLACKLIST_COMPANY = "boss_blacklist_company"
CFG_BLACKLIST_TITLE = "boss_blacklist_title"

DEFAULT_GREETING = "您好，我对贵公司的这个职位很感兴趣，希望能有机会进一步沟通。"


# ------------------------------------------------------------------
# 辅助
# ------------------------------------------------------------------

def _status_text() -> str:
    c = get_crawler()
    if not c.is_running:
        return "未连接"
    return "已登录 ✓" if c.is_logged_in else "已连接 (未登录)"


def _status_html(text: str) -> str:
    if "已登录" in text:
        return f'<span class="status-tag tag-green">{text}</span>'
    if "已连接" in text:
        return f'<span class="status-tag tag-orange">{text}</span>'
    return f'<span class="status-tag tag-gray">{text}</span>'


def _build_profile_html(profile: dict) -> str:
    if not profile:
        return '<div class="alert-bar info">已登录, 但未能获取个人信息</div>'

    name = html_mod.escape(profile.get("name", ""))
    items = []
    if name:
        items.append(f"<strong>姓名</strong>: {name}")
    for key, label in [
        ("expect_position", "期望职位"),
        ("job_status", "求职状态"),
        ("basics", "基本信息"),
        ("advantage", "个人优势"),
    ]:
        val = profile.get(key, "")
        if val:
            safe = html_mod.escape(val[:200])
            items.append(f"<strong>{label}</strong>: {safe}")

    body = "<br>".join(items) if items else "已登录 BOSS 直聘"
    return (
        '<div style="background:linear-gradient(135deg,#f0f7ff,#e8f4fd);'
        "border:1px solid #d1e0ff;border-radius:12px;padding:20px 24px;"
        'margin:8px 0;line-height:1.8;">'
        '<div style="font-size:15px;font-weight:600;color:#165DFF;margin-bottom:8px;">'
        "\U0001F464 BOSS 直聘 · 个人信息</div>"
        f'<div style="color:#333;font-size:14px;">{body}</div>'
        "</div>"
    )


# ------------------------------------------------------------------
# 连接 / 登录
# ------------------------------------------------------------------

def _connect_and_show_qr():
    c = get_crawler()

    if not c.is_running:
        msg = c.launch(headless=True)
        if "失败" in msg:
            return (
                None, _status_html("连接失败"), f"浏览器启动失败: {msg}",
                "", gr.Column(visible=True), gr.Column(visible=False),
            )

    if c.is_logged_in:
        profile = c.get_user_profile()
        return (
            None, _status_html("已登录 ✓"),
            "已通过 Cookie 自动登录",
            _build_profile_html(profile),
            gr.Column(visible=False), gr.Column(visible=True),
        )

    login_msg = c.open_login_page()
    img_bytes = c.capture_login_screenshot()
    img = Image.open(io.BytesIO(img_bytes)) if img_bytes else None
    return (
        img, _status_html(_status_text()), login_msg,
        "", gr.Column(visible=True), gr.Column(visible=False),
    )


def _refresh_qr():
    c = get_crawler()
    if not c.is_running:
        return None, _status_html("未连接"), "请先点击「连接 BOSS 直聘」"

    c.open_login_page()
    img_bytes = c.capture_login_screenshot()
    img = Image.open(io.BytesIO(img_bytes)) if img_bytes else None
    return img, _status_html(_status_text()), "二维码已刷新, 请重新扫码"


def _check_login():
    c = get_crawler()
    if not c.is_running:
        return (
            _status_html("未连接"), "请先点击「连接 BOSS 直聘」",
            "", gr.Column(visible=True), gr.Column(visible=False),
        )

    msg = c.check_login()
    if c.is_logged_in:
        profile = c.get_user_profile()
        return (
            _status_html("已登录 ✓"), msg,
            _build_profile_html(profile),
            gr.Column(visible=False), gr.Column(visible=True),
        )
    return (
        _status_html(_status_text()), msg,
        "", gr.Column(visible=True), gr.Column(visible=False),
    )


def _disconnect():
    c = get_crawler()
    msg = c.close()
    return (
        None, _status_html("未连接"), msg,
        "", gr.Column(visible=True), gr.Column(visible=False),
    )


def _do_logout():
    c = get_crawler()
    if c.is_running:
        c.close()
    clear_cookie("boss_zhipin")
    return (
        None, _status_html("未连接"), "已退出登录, Cookie 已清除",
        "", gr.Column(visible=True), gr.Column(visible=False),
    )


# ------------------------------------------------------------------
# 配置读写
# ------------------------------------------------------------------

def _load_greeting(state) -> str:
    user_name = state.get("user_name", "") if state else ""
    val = SysConfigCRUD.get(CFG_GREETING, user_name=user_name)
    greeting = val if val else DEFAULT_GREETING
    get_crawler().greeting = greeting
    return greeting


def _save_greeting(text: str, state) -> str:
    user_name = state.get("user_name", "") if state else ""
    cleaned = text.strip()
    SysConfigCRUD.set(CFG_GREETING, cleaned, user_name=user_name)
    get_crawler().greeting = cleaned
    return "打招呼话术已保存"


def _load_blacklists(state) -> tuple[str, str]:
    user_name = state.get("user_name", "") if state else ""
    companies = SysConfigCRUD.get(CFG_BLACKLIST_COMPANY, user_name=user_name) or ""
    titles = SysConfigCRUD.get(CFG_BLACKLIST_TITLE, user_name=user_name) or ""
    return companies, titles


def _save_blacklists(companies: str, titles: str, state) -> str:
    user_name = state.get("user_name", "") if state else ""
    SysConfigCRUD.set(CFG_BLACKLIST_COMPANY, companies.strip(), user_name=user_name)
    SysConfigCRUD.set(CFG_BLACKLIST_TITLE, titles.strip(), user_name=user_name)
    return "黑名单已保存"


# ------------------------------------------------------------------
# 页面
# ------------------------------------------------------------------

def create_boss_account_page(login_state):
    """创建 BOSS 直聘账号管理页面"""

    gr.Markdown("## BOSS 直聘 · 账号管理")
    gr.HTML(
        '<div class="alert-bar info">'
        "在此页面连接并登录 BOSS 直聘, 管理账号状态和投递偏好。"
        " 登录成功后即可在「自动投递」页面搜索和投递岗位。"
        "</div>"
    )

    op_msg = gr.Textbox(label="操作状态", interactive=False, max_lines=2)

    # ==================== 连接与登录 ====================
    gr.Markdown("### 连接与登录")

    with gr.Row():
        conn_status = gr.HTML(value=_status_html(_status_text()))

    with gr.Row():
        connect_btn = gr.Button("连接 BOSS 直聘", variant="primary", scale=2)
        check_login_btn = gr.Button("检查登录状态", variant="secondary", scale=2)
        disconnect_btn = gr.Button("断开连接", variant="stop", scale=1)
        logout_boss_btn = gr.Button("退出登录 (清除 Cookie)", variant="stop", scale=1)

    with gr.Column(visible=False) as profile_section:
        profile_html = gr.HTML("")

    with gr.Column(visible=True) as login_section:
        with gr.Row():
            with gr.Column(scale=1):
                qr_image = gr.Image(
                    label="BOSS 直聘登录页 (请用 APP 扫码)",
                    type="pil",
                    interactive=False,
                    height=400,
                )
            with gr.Column(scale=1):
                gr.Markdown(
                    "**扫码登录指引**\n\n"
                    "1. 点击「连接 BOSS 直聘」\n"
                    "2. 左侧将显示登录页截图 (含二维码)\n"
                    "3. 打开 **BOSS 直聘 APP** → 扫一扫\n"
                    "4. 手机确认登录后, 点击「检查登录状态」\n"
                    "5. 状态变为 **已登录 ✓** 即可前往自动投递页面\n\n"
                    "> 如二维码过期, 点击「连接 BOSS 直聘」重新获取\n\n"
                    "> 已有登录记录时会自动通过 Cookie 登录"
                )

    # ==================== 打招呼话术 ====================
    gr.Markdown("### 打招呼话术模板")
    gr.HTML(
        '<div class="alert-bar info">'
        "自定义发起沟通时的招呼语, 留空则使用默认话术。"
        "</div>"
    )
    greeting_input = gr.Textbox(
        label="话术模板",
        placeholder="您好，我对贵公司的这个职位很感兴趣...",
        lines=3,
        value="",
    )
    greeting_msg = gr.Textbox(label="", interactive=False, max_lines=1, visible=False)
    with gr.Row():
        load_greeting_btn = gr.Button("加载已保存话术", variant="secondary", size="sm")
        save_greeting_btn = gr.Button("保存话术", variant="primary", size="sm")

    # ==================== 黑名单 ====================
    gr.Markdown("### 公司 & 岗位黑名单")
    gr.HTML(
        '<div class="alert-bar info">'
        "搜索结果中匹配黑名单的岗位将被自动过滤, 每行一个关键词。"
        "</div>"
    )
    with gr.Row():
        blacklist_company = gr.Textbox(
            label="公司黑名单 (每行一个)",
            placeholder="例:\n某某外包公司\n某某中介",
            lines=5,
        )
        blacklist_title = gr.Textbox(
            label="岗位名称黑名单 (每行一个)",
            placeholder="例:\n电话销售\n保险代理",
            lines=5,
        )
    blacklist_msg = gr.Textbox(label="", interactive=False, max_lines=1, visible=False)
    with gr.Row():
        load_bl_btn = gr.Button("加载已保存黑名单", variant="secondary", size="sm")
        save_bl_btn = gr.Button("保存黑名单", variant="primary", size="sm")

    # ==================== 事件绑定 ====================

    _connect_outputs = [
        qr_image, conn_status, op_msg,
        profile_html, login_section, profile_section,
    ]

    connect_btn.click(fn=_connect_and_show_qr, outputs=_connect_outputs)

    _check_outputs = [
        conn_status, op_msg,
        profile_html, login_section, profile_section,
    ]
    check_login_btn.click(fn=_check_login, outputs=_check_outputs)

    disconnect_btn.click(fn=_disconnect, outputs=_connect_outputs)
    logout_boss_btn.click(fn=_do_logout, outputs=_connect_outputs)

    load_greeting_btn.click(
        fn=_load_greeting, inputs=[login_state], outputs=[greeting_input],
    )
    save_greeting_btn.click(
        fn=_save_greeting, inputs=[greeting_input, login_state], outputs=[op_msg],
    )

    def _load_bl(state):
        return _load_blacklists(state)

    load_bl_btn.click(
        fn=_load_bl, inputs=[login_state],
        outputs=[blacklist_company, blacklist_title],
    )
    save_bl_btn.click(
        fn=_save_blacklists,
        inputs=[blacklist_company, blacklist_title, login_state],
        outputs=[op_msg],
    )
