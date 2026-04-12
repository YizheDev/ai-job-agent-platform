"""BOSS 直聘账号管理页面

连接模式选择 (CDP/Playwright) / 扫码登录 / Cookie 管理 /
个人信息展示 / 打招呼话术模板 / 公司&岗位黑名单。
"""

from __future__ import annotations

import html as html_mod
import io
import threading

import gradio as gr
from PIL import Image

from app.core.logger import get_logger
from app.db.crud import SysConfigCRUD
from app.utils.boss_crawler import ConnectionMode, get_crawler
from app.utils.security_util import clear_cookie

logger = get_logger(__name__)

CFG_GREETING = "boss_greeting_template"
CFG_BLACKLIST_COMPANY = "boss_blacklist_company"
CFG_BLACKLIST_TITLE = "boss_blacklist_title"

DEFAULT_GREETING = "您好，我对贵公司的这个职位很感兴趣，希望能有机会进一步沟通。"

MODE_CDP_LABEL = "Chrome 真实浏览器 (推荐)"
MODE_PW_LABEL = "内置浏览器 (备用)"


def _mode_from_label(label: str) -> str:
    if "Chrome" in (label or ""):
        return ConnectionMode.CDP
    return ConnectionMode.PLAYWRIGHT


# ------------------------------------------------------------------
# Loading animation
# ------------------------------------------------------------------

_SPINNER_CSS = "@keyframes _bspin{to{transform:rotate(360deg)}}"

def _loading_html(msg: str) -> str:
    """带旋转动画的加载状态 HTML"""
    return (
        f'<style>{_SPINNER_CSS}</style>'
        '<div style="display:inline-flex;align-items:center;gap:10px;'
        'padding:6px 0;">'
        '<div style="width:16px;height:16px;border:2.5px solid #e0e7ff;'
        "border-top:2.5px solid #165DFF;border-radius:50%;"
        'animation:_bspin .8s linear infinite;flex-shrink:0;"></div>'
        f'<span style="color:#165DFF;font-weight:600;font-size:14px;">'
        f"{msg}</span>"
        "</div>"
    )


# ------------------------------------------------------------------
# Status helpers
# ------------------------------------------------------------------

def _status_text() -> str:
    c = get_crawler()
    if not c.is_running:
        return "未连接"
    return "已登录 ✓" if c.is_logged_in else "已连接 (未登录)"


def _status_html() -> str:
    c = get_crawler()
    text = _status_text()
    mode = c.mode_display
    cb = c.circuit_state

    if "已登录" in text:
        tag = f'<span class="status-tag tag-green">{text}</span>'
    elif "已连接" in text:
        tag = f'<span class="status-tag tag-orange">{text}</span>'
    else:
        tag = f'<span class="status-tag tag-gray">{text}</span>'

    if c.is_running:
        tag += (
            f' <span style="color:#666;font-size:13px;">| {mode}</span>'
        )
        if cb != "正常":
            tag += (
                f' <span style="color:#f60;font-size:13px;">'
                f'| 熔断: {cb}</span>'
            )
    return tag


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
        '<div style="font-size:15px;font-weight:600;color:#165DFF;'
        'margin-bottom:8px;">'
        "\U0001F464 BOSS 直聘 · 个人信息</div>"
        f'<div style="color:#333;font-size:14px;">{body}</div>'
        "</div>"
    )


# ------------------------------------------------------------------
# Connect / Login
# ------------------------------------------------------------------

def _connect_boss(mode_label, cdp_port):
    mode = _mode_from_label(mode_label)
    c = get_crawler()

    _UP = gr.update()

    if c.is_running:
        if c.is_logged_in:
            try:
                profile = c.get_user_profile()
            except Exception as pe:
                logger.warning("获取个人信息失败 (不影响连接): %s", pe)
                profile = {}
            yield (
                None, _status_html(), "已处于连接状态",
                _build_profile_html(profile),
                gr.update(visible=False), gr.update(visible=True),
                gr.Timer(active=False),
            )
            return
        if c._is_cdp:
            yield (
                None, _status_html(),
                "已连接, 请在 Chrome 浏览器窗口中完成登录, 然后点击「检查登录状态」",
                "", gr.update(visible=True), gr.update(visible=False),
                gr.Timer(active=False),
            )
        else:
            img_bytes = c.capture_login_screenshot()
            img = Image.open(io.BytesIO(img_bytes)) if img_bytes else None
            yield (
                img, _status_html(), "已连接, 等待登录中...",
                "", gr.update(visible=True), gr.update(visible=False),
                gr.Timer(active=True),
            )
        return

    if mode == ConnectionMode.CDP:
        loading_msg = "正在启动 Chrome 并连接 BOSS 直聘..."
    else:
        loading_msg = "正在启动内置浏览器..."

    yield (_UP, _loading_html(loading_msg), loading_msg, _UP, _UP, _UP, _UP)

    try:
        if mode == ConnectionMode.CDP:
            port = int(cdp_port) if cdp_port else 9222
            msg = c.launch_cdp(port)

            if "失败" in msg or "超时" in msg:
                yield (
                    None, _status_html(), msg,
                    "", gr.update(visible=True), gr.update(visible=False),
                    gr.Timer(active=False),
                )
                return

            if c.is_logged_in:
                yield (
                    _UP,
                    _loading_html("连接成功, 正在获取个人信息..."),
                    "连接成功, 正在获取个人信息...",
                    _UP, _UP, _UP, _UP,
                )
                try:
                    profile = c.get_user_profile()
                except Exception as pe:
                    logger.warning("获取个人信息失败 (不影响连接): %s", pe)
                    profile = {}
                yield (
                    None, _status_html(), msg,
                    _build_profile_html(profile),
                    gr.update(visible=False), gr.update(visible=True),
                    gr.Timer(active=False),
                )
                return

            yield (
                None, _status_html(), msg,
                "", gr.update(visible=True), gr.update(visible=False),
                gr.Timer(active=False),
            )
            return

        # Playwright mode
        msg = c.launch_playwright(headless=True)
        if "失败" in msg:
            yield (
                None, _status_html(), msg,
                "", gr.update(visible=True), gr.update(visible=False),
                gr.Timer(active=False),
            )
            return

        if c.is_logged_in:
            yield (
                _UP,
                _loading_html("连接成功, 正在获取个人信息..."),
                "连接成功, 正在获取个人信息...",
                _UP, _UP, _UP, _UP,
            )
            try:
                profile = c.get_user_profile()
            except Exception as pe:
                logger.warning("获取个人信息失败 (不影响连接): %s", pe)
                profile = {}
            yield (
                None, _status_html(), msg,
                _build_profile_html(profile),
                gr.update(visible=False), gr.update(visible=True),
                gr.Timer(active=False),
            )
            return

        yield (_UP, _loading_html("正在打开登录页面..."),
               "正在打开登录页面...", _UP, _UP, _UP, _UP)
        login_msg = c.open_login_page()
        img_bytes = c.capture_login_screenshot()
        img = Image.open(io.BytesIO(img_bytes)) if img_bytes else None
        yield (
            img, _status_html(), login_msg,
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=True),
        )

    except Exception as e:
        logger.error("连接过程中出现异常: %s", e)
        yield (
            None, _status_html(), f"连接异常: {e}",
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )


def _refresh_qr():
    c = get_crawler()
    if not c.is_running:
        return None, _status_html(), "请先点击「连接 BOSS 直聘」"
    if c._is_cdp:
        return (
            None, _status_html(),
            "Chrome 模式下请直接在浏览器窗口中操作, 登录后点击「检查登录状态」",
        )
    c.open_login_page()
    img_bytes = c.capture_login_screenshot()
    img = Image.open(io.BytesIO(img_bytes)) if img_bytes else None
    return img, _status_html(), "二维码已刷新, 请重新扫码"


def _check_login():
    c = get_crawler()
    _UP = gr.update()
    if not c.is_running:
        yield (
            _status_html(), "请先点击「连接 BOSS 直聘」",
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )
        return

    yield (_loading_html("正在检查登录状态..."),
           "正在检查登录状态...", _UP, _UP, _UP, _UP)

    enable_timer = not c._is_cdp

    try:
        msg = c.check_login()
        if c.is_logged_in:
            yield (_loading_html("登录成功, 正在获取个人信息..."),
                   "正在获取个人信息...", _UP, _UP, _UP, _UP)
            try:
                profile = c.get_user_profile()
            except Exception as pe:
                logger.warning("获取个人信息失败 (不影响登录): %s", pe)
                profile = {}
            yield (
                _status_html(), msg,
                _build_profile_html(profile),
                gr.update(visible=False), gr.update(visible=True),
                gr.Timer(active=False),
            )
            return

        yield (
            _status_html(), msg,
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=enable_timer),
        )
    except Exception as e:
        logger.error("检查登录状态异常: %s", e)
        yield (
            _status_html(), f"检查登录异常: {e}",
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )


def _disconnect():
    _UP = gr.update()
    yield (_UP, _loading_html("正在断开连接..."),
           "正在断开连接...", _UP, _UP, _UP, _UP)
    try:
        c = get_crawler()
        msg = c.close()
        yield (
            None, _status_html(), msg,
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )
    except Exception as e:
        logger.error("断开连接异常: %s", e)
        yield (
            None, _status_html(), f"断开连接异常: {e}",
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )


def _do_logout():
    _UP = gr.update()
    yield (_UP, _loading_html("正在退出登录并清理数据..."),
           "正在退出登录...", _UP, _UP, _UP, _UP)
    try:
        c = get_crawler()
        if c.is_running:
            c.close()
        clear_cookie("boss_zhipin")
        yield (
            None, _status_html(), "已退出登录, Cookie 已清除",
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )
    except Exception as e:
        logger.error("退出登录异常: %s", e)
        yield (
            None, _status_html(), f"退出登录异常: {e}",
            "", gr.update(visible=True), gr.update(visible=False),
            gr.Timer(active=False),
        )


# ------------------------------------------------------------------
# Auto-poll login status (Timer callback)
# ------------------------------------------------------------------

_auto_check_lock = threading.Lock()


def _auto_check_login():
    """Timer callback: login status polling for Playwright headless mode only.

    CDP mode MUST NOT auto-poll — any Playwright command (locator, inner_text,
    even URL reads via CDP protocol) can cause visible page flickering and
    prevent the user from logging in. In CDP mode the user interacts with
    Chrome directly and clicks "检查登录状态" manually.
    """
    c = get_crawler()
    _UP = gr.update()

    if not c.is_running or c.is_logged_in:
        return (_status_html(), _UP, _UP, _UP, _UP, gr.Timer(active=False))

    if c._is_cdp:
        return (_status_html(), _UP, _UP, _UP, _UP, gr.Timer(active=False))

    if not _auto_check_lock.acquire(blocking=False):
        return (_UP, _UP, _UP, _UP, _UP, gr.Timer(active=True))

    try:
        if not c.quick_check_login():
            return (_UP, _UP, _UP, _UP, _UP, gr.Timer(active=True))

        if c.confirm_login_no_navigate():
            try:
                profile = c.get_user_profile()
            except Exception:
                profile = {}
            return (
                _status_html(),
                "✓ 登录成功, Cookie 已保存 (自动检测到登录)",
                _build_profile_html(profile),
                gr.update(visible=False), gr.update(visible=True),
                gr.Timer(active=False),
            )
        return (_status_html(), _UP, _UP, _UP, _UP, gr.Timer(active=True))
    except Exception:
        return (_UP, _UP, _UP, _UP, _UP, gr.Timer(active=True))
    finally:
        _auto_check_lock.release()


# ------------------------------------------------------------------
# Config read/write
# ------------------------------------------------------------------

def _load_greeting(state) -> str:
    try:
        user_name = state.get("user_name", "") if state else ""
        val = SysConfigCRUD.get(CFG_GREETING, user_name=user_name)
        greeting = val if val else DEFAULT_GREETING
        get_crawler().greeting = greeting
        return greeting
    except Exception as e:
        logger.error("加载打招呼话术失败: %s", e)
        return DEFAULT_GREETING


def _save_greeting(text: str, state) -> str:
    try:
        user_name = state.get("user_name", "") if state else ""
        cleaned = text.strip()
        SysConfigCRUD.set(CFG_GREETING, cleaned, user_name=user_name)
        get_crawler().greeting = cleaned
        return "打招呼话术已保存"
    except Exception as e:
        logger.error("保存打招呼话术失败: %s", e)
        return f"保存失败: {e}"


def _load_blacklists(state) -> tuple[str, str]:
    try:
        user_name = state.get("user_name", "") if state else ""
        companies = (
            SysConfigCRUD.get(CFG_BLACKLIST_COMPANY, user_name=user_name) or ""
        )
        titles = (
            SysConfigCRUD.get(CFG_BLACKLIST_TITLE, user_name=user_name) or ""
        )
        return companies, titles
    except Exception as e:
        logger.error("加载黑名单失败: %s", e)
        return "", ""


def _save_blacklists(companies: str, titles: str, state) -> str:
    try:
        user_name = state.get("user_name", "") if state else ""
        SysConfigCRUD.set(
            CFG_BLACKLIST_COMPANY, companies.strip(), user_name=user_name,
        )
        SysConfigCRUD.set(
            CFG_BLACKLIST_TITLE, titles.strip(), user_name=user_name,
        )
        return "黑名单已保存"
    except Exception as e:
        logger.error("保存黑名单失败: %s", e)
        return f"保存失败: {e}"


# ------------------------------------------------------------------
# Page
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

    op_msg = gr.Textbox(label="操作状态", interactive=False, max_lines=3)

    # ==================== 连接模式选择 ====================
    gr.Markdown("### 连接模式")

    mode_radio = gr.Radio(
        choices=[MODE_CDP_LABEL, MODE_PW_LABEL],
        value=MODE_CDP_LABEL,
        label="选择连接方式",
    )

    with gr.Column(visible=True) as cdp_section:
        gr.HTML(
            '<div class="alert-bar info">'
            "<strong>Chrome 真实浏览器模式 (推荐)</strong><br>"
            "点击「连接 BOSS 直聘」后系统将自动启动 Chrome 浏览器。<br>"
            "首次使用请在弹出的 Chrome 中登录 BOSS 直聘, "
            "后续会自动记住登录状态。"
            "</div>"
        )
        cdp_port_input = gr.Textbox(
            label="调试端口 (一般无需修改)",
            value="9222",
            max_lines=1,
            visible=False,
        )

    with gr.Column(visible=False) as pw_section:
        gr.HTML(
            '<div class="alert-bar info">'
            "<strong>内置浏览器模式 (备用)</strong><br>"
            "使用内置浏览器, 通过 Cookie 或扫码登录。"
            " Chrome 不可用时系统会自动降级到此模式。"
            "</div>"
        )

    def _toggle_mode(label):
        is_cdp = "Chrome" in (label or "")
        return gr.update(visible=is_cdp), gr.update(visible=not is_cdp)

    mode_radio.change(
        fn=_toggle_mode,
        inputs=[mode_radio],
        outputs=[cdp_section, pw_section],
    )

    # ==================== 连接与登录 ====================
    gr.Markdown("### 连接与登录")

    with gr.Row():
        conn_status = gr.HTML(value=_status_html())

    with gr.Row():
        connect_btn = gr.Button(
            "连接 BOSS 直聘", variant="primary", scale=1,
        )
        check_login_btn = gr.Button(
            "检查登录状态", variant="secondary", scale=1,
        )
        disconnect_btn = gr.Button("断开连接", variant="stop", scale=1)
        logout_boss_btn = gr.Button(
            "退出登录 (清除 Cookie)", variant="stop", scale=1,
        )

    with gr.Column(visible=False) as profile_section:
        profile_html = gr.HTML("")

    with gr.Column(visible=True) as login_section:
        with gr.Row():
            with gr.Column(scale=1):
                qr_image = gr.Image(
                    label="登录页截图 / 二维码",
                    type="pil",
                    interactive=False,
                    height=400,
                )
            with gr.Column(scale=1):
                gr.Markdown(
                    "**使用说明**\n\n"
                    "**Chrome 模式 (推荐):**\n"
                    "1. 点击「连接 BOSS 直聘」→ Chrome 自动启动\n"
                    "2. **在弹出的 Chrome 窗口中**登录 BOSS 直聘\n"
                    "3. 登录后点击「检查登录状态」或等待自动检测\n"
                    "4. 后续使用会自动记住登录\n\n"
                    "**内置浏览器模式 (备用):**\n"
                    "1. 点击「连接 BOSS 直聘」\n"
                    "2. 左侧显示二维码, 用 BOSS 直聘 APP 扫码\n"
                    "3. 系统自动检测登录状态\n\n"
                    "> **注意**: Chrome 模式下请直接在 Chrome 浏览器中操作, "
                    "左侧会显示 Chrome 页面截图供参考\n\n"
                    "> 登录成功后即可前往「自动投递」页面搜索和投递岗位"
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
    greeting_msg = gr.Textbox(
        label="", interactive=False, max_lines=1, visible=False,
    )
    with gr.Row():
        load_greeting_btn = gr.Button(
            "加载已保存话术", variant="secondary", size="sm",
        )
        save_greeting_btn = gr.Button(
            "保存话术", variant="primary", size="sm",
        )

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
    blacklist_msg = gr.Textbox(
        label="", interactive=False, max_lines=1, visible=False,
    )
    with gr.Row():
        load_bl_btn = gr.Button(
            "加载已保存黑名单", variant="secondary", size="sm",
        )
        save_bl_btn = gr.Button(
            "保存黑名单", variant="primary", size="sm",
        )

    # ==================== Event bindings ====================

    auto_poll_timer = gr.Timer(value=8, active=False)

    _connect_outputs = [
        qr_image, conn_status, op_msg,
        profile_html, login_section, profile_section,
        auto_poll_timer,
    ]

    connect_btn.click(
        fn=_connect_boss,
        inputs=[mode_radio, cdp_port_input],
        outputs=_connect_outputs,
    )

    _check_outputs = [
        conn_status, op_msg,
        profile_html, login_section, profile_section,
        auto_poll_timer,
    ]
    check_login_btn.click(fn=_check_login, outputs=_check_outputs)

    disconnect_btn.click(fn=_disconnect, outputs=_connect_outputs)
    logout_boss_btn.click(fn=_do_logout, outputs=_connect_outputs)

    auto_poll_timer.tick(fn=_auto_check_login, outputs=_check_outputs)

    load_greeting_btn.click(
        fn=_load_greeting, inputs=[login_state], outputs=[greeting_input],
    )
    save_greeting_btn.click(
        fn=_save_greeting, inputs=[greeting_input, login_state],
        outputs=[op_msg],
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
