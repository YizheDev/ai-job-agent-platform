"""BOSS 直聘账号管理页面 — Bento 玻璃拟态风

布局:
┌─ 页头: 图标 + 标题 + 说明
├─ 状态 Hero 卡: 连接状态徽章 + 模式 + 熔断 + 4 按钮 (连接/检查/断开/退出)
├─ 连接模式卡: Chrome ↔ 内置浏览器 单选 + 模式说明
├─ 个人信息卡 / 扫码卡 (互斥显示)
├─ 打招呼话术卡
└─ 公司 & 岗位黑名单卡 (2 列)

对外接口保持: create_boss_account_page(login_state)
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


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


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
        f"<style>{_SPINNER_CSS}</style>"
        '<div style="display:inline-flex;align-items:center;gap:10px;'
        'padding:6px 0;">'
        '<div style="width:16px;height:16px;'
        "border:2.5px solid rgba(255,255,255,0.12);"
        "border-top:2.5px solid #8DBBFF;border-radius:50%;"
        'animation:_bspin .8s linear infinite;flex-shrink:0;"></div>'
        '<span style="color:#8DBBFF;font-weight:600;font-size:14px;">'
        f"{_safe(msg)}</span>"
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
    """连接状态 pill + 模式/熔断 副信息 (嵌入到 Hero 卡)."""
    c = get_crawler()
    text = _status_text()
    mode = c.mode_display if c.is_running else ""
    cb = c.circuit_state if c.is_running else ""

    if "已登录" in text:
        cls, icon = "bst-green", (
            '<svg viewBox="0 0 16 16" width="11" height="11" fill="none" '
            'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" '
            'stroke-linejoin="round"><polyline points="3 8 7 12 13 4"></polyline></svg>'
        )
    elif "已连接" in text:
        cls, icon = "bst-orange", (
            '<svg viewBox="0 0 16 16" width="11" height="11" fill="none" '
            'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
            'stroke-linejoin="round"><circle cx="8" cy="8" r="3"></circle></svg>'
        )
    else:
        cls, icon = "bst-gray", (
            '<svg viewBox="0 0 16 16" width="11" height="11" fill="none" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round"><circle cx="8" cy="8" r="3"></circle></svg>'
        )

    extras: list[str] = []
    if mode:
        extras.append(f'<span class="bs-meta"><span class="bs-meta-k">模式</span>{_safe(mode)}</span>')
    if cb and cb != "正常":
        extras.append(f'<span class="bs-meta bs-meta-warn"><span class="bs-meta-k">熔断</span>{_safe(cb)}</span>')

    return (
        '<div class="bs-root">'
        f'  <span class="bst {cls}">{icon}<span class="bst-txt">{_safe(text)}</span></span>'
        + "".join(extras)
        + "</div>"
    )


def _build_profile_html(profile: dict) -> str:
    if not profile:
        return (
            '<div class="bs-root">'
            '  <div class="bs-profile-empty">已登录, 但未能获取个人信息</div>'
            "</div>"
        )

    name = _safe(profile.get("name", ""))
    expect = _safe(profile.get("expect_position", ""))
    status = _safe(profile.get("job_status", ""))
    basics = _safe(profile.get("basics", ""))
    advantage = _safe(profile.get("advantage", ""))[:300]

    chips = []
    if status:
        chips.append(f'<span class="bs-chip bs-chip-green">{status}</span>')
    if expect:
        chips.append(f'<span class="bs-chip bs-chip-blue">{expect}</span>')

    rows = []
    if basics:
        rows.append(
            '<div class="bs-pinfo-row">'
            '  <div class="bs-pinfo-k">基本信息</div>'
            f'  <div class="bs-pinfo-v">{basics}</div>'
            "</div>"
        )
    if advantage:
        rows.append(
            '<div class="bs-pinfo-row">'
            '  <div class="bs-pinfo-k">个人优势</div>'
            f'  <div class="bs-pinfo-v">{advantage}</div>'
            "</div>"
        )

    avatar_letter = name[:1] if name else "B"
    chips_html = "".join(chips) or "&nbsp;"
    pinfo_body = (
        "".join(rows)
        if rows
        else '<div class="bs-pinfo-empty">未能获取更多信息</div>'
    )
    display_name = name or "BOSS 用户"

    return (
        '<div class="bs-root">'
        '  <div class="bs-profile-card">'
        '    <div class="bs-profile-head">'
        f'      <div class="bs-avatar">{avatar_letter}</div>'
        '      <div class="bs-profile-ident">'
        f'        <div class="bs-profile-name">{display_name}</div>'
        f'        <div class="bs-profile-chips">{chips_html}</div>'
        "      </div>"
        '      <div class="bs-profile-tag">'
        '        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <polyline points="20 6 9 17 4 12"></polyline>'
        "        </svg>"
        "        已登录"
        "      </div>"
        "    </div>"
        f'    <div class="bs-pinfo">{pinfo_body}</div>'
        "  </div>"
        "</div>"
    )


def _render_header_html() -> str:
    return (
        '<div class="bs-root">'
        '  <div class="bs-head">'
        '    <div class="bs-head-icon">'
        '      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>'
        '        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>'
        "      </svg>"
        "    </div>"
        '    <div class="bs-head-text">'
        '      <div class="bs-head-title">BOSS 直聘 · 账号管理</div>'
        '      <div class="bs-head-sub">连接并登录 BOSS 直聘 · 管理账号状态 · 配置投递偏好</div>'
        "    </div>"
        "  </div>"
        "</div>"
    )


def _render_tip_html(kind: str, title: str, body: str) -> str:
    palette = {
        "info": ("bs-tip-blue", "rgba(79,139,255,0.22)", "#AFC7FF"),
        "chrome": ("bs-tip-green", "rgba(52,211,153,0.22)", "#6EE7B7"),
        "pw": ("bs-tip-orange", "rgba(251,146,60,0.22)", "#FDBA74"),
    }
    cls, _, _ = palette.get(kind, palette["info"])
    return (
        '<div class="bs-root">'
        f'  <div class="bs-tip {cls}">'
        f'    <div class="bs-tip-title">{_safe(title)}</div>'
        f'    <div class="bs-tip-body">{body}</div>'
        "  </div>"
        "</div>"
    )


def _render_help_html() -> str:
    return (
        '<div class="bs-root">'
        '  <div class="bs-help-card">'
        '    <div class="bs-help-title">'
        '      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <circle cx="12" cy="12" r="10"></circle>'
        '        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>'
        '        <line x1="12" y1="17" x2="12.01" y2="17"></line>'
        "      </svg>"
        "      使用说明"
        "    </div>"
        '    <div class="bs-help-section">'
        '      <div class="bs-help-h">Chrome 模式 (推荐)</div>'
        '      <ol class="bs-help-ol">'
        "        <li>点击「连接 BOSS 直聘」, Chrome 会自动启动</li>"
        "        <li>在弹出的 <b>Chrome 浏览器窗口</b> 中登录 BOSS 直聘</li>"
        "        <li>登录后点击「检查登录状态」或等待自动检测</li>"
        "        <li>后续使用会自动记住登录态</li>"
        "      </ol>"
        "    </div>"
        '    <div class="bs-help-section">'
        '      <div class="bs-help-h">内置浏览器模式 (备用)</div>'
        '      <ol class="bs-help-ol">'
        "        <li>点击「连接 BOSS 直聘」</li>"
        "        <li>左侧显示二维码, 用 BOSS 直聘 APP 扫码</li>"
        "        <li>系统自动检测登录状态</li>"
        "      </ol>"
        "    </div>"
        '    <div class="bs-help-note">登录成功后可前往「自动投递」搜索和投递岗位</div>'
        "  </div>"
        "</div>"
    )


# ------------------------------------------------------------------
# Connect / Login (回调签名不变)
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
    """Timer callback: login status polling for Playwright headless mode only."""
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
        companies = SysConfigCRUD.get(CFG_BLACKLIST_COMPANY, user_name=user_name) or ""
        titles = SysConfigCRUD.get(CFG_BLACKLIST_TITLE, user_name=user_name) or ""
        return companies, titles
    except Exception as e:
        logger.error("加载黑名单失败: %s", e)
        return "", ""


def _save_blacklists(companies: str, titles: str, state) -> str:
    try:
        user_name = state.get("user_name", "") if state else ""
        SysConfigCRUD.set(CFG_BLACKLIST_COMPANY, companies.strip(), user_name=user_name)
        SysConfigCRUD.set(CFG_BLACKLIST_TITLE, titles.strip(), user_name=user_name)
        return "黑名单已保存"
    except Exception as e:
        logger.error("保存黑名单失败: %s", e)
        return f"保存失败: {e}"


# ------------------------------------------------------------------
# Page builder
# ------------------------------------------------------------------

def create_boss_account_page(login_state):
    """创建 BOSS 直聘账号管理页面 (Bento 玻璃风)"""
    gr.HTML(_BS_STYLE)

    with gr.Column(elem_id="boss-page-root", elem_classes=["bs-scope"]):
        gr.HTML(_render_header_html())

        # ============ 状态 Hero 卡 ============
        with gr.Column(elem_classes=["bs-card", "bs-card-status"]):
            gr.HTML(
                '<div class="bs-card-head">'
                '  <div class="bs-ch-icon bs-ch-blue">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <circle cx="12" cy="12" r="3"></circle>'
                '      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>'
                '    </svg>'
                '  </div>'
                '  <div class="bs-ch-title">连接状态</div>'
                '  <div class="bs-ch-sub">登录后即可前往「自动投递」使用</div>'
                '</div>'
            )
            op_msg = gr.Textbox(
                label="操作状态",
                interactive=False,
                max_lines=3,
                elem_classes=["bs-input-field", "bs-opmsg-box"],
            )
            conn_status = gr.HTML(value=_status_html(), elem_id="bs-status-slot")

            with gr.Row(elem_classes=["bs-action-row"]):
                connect_btn = gr.Button(
                    "连接 BOSS 直聘",
                    variant="primary",
                    elem_classes=["bs-btn", "bs-btn-primary"],
                )
                check_login_btn = gr.Button(
                    "检查登录状态",
                    variant="secondary",
                    elem_classes=["bs-btn", "bs-btn-secondary"],
                )
                disconnect_btn = gr.Button(
                    "断开连接",
                    variant="stop",
                    elem_classes=["bs-btn", "bs-btn-warn"],
                )
                logout_boss_btn = gr.Button(
                    "退出登录 (清除 Cookie)",
                    variant="stop",
                    elem_classes=["bs-btn", "bs-btn-danger"],
                )

        # ============ 连接模式卡 ============
        with gr.Column(elem_classes=["bs-card", "bs-card-mode"]):
            gr.HTML(
                '<div class="bs-card-head">'
                '  <div class="bs-ch-icon bs-ch-green">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>'
                '      <line x1="8" y1="21" x2="16" y2="21"></line>'
                '      <line x1="12" y1="17" x2="12" y2="21"></line>'
                '    </svg>'
                '  </div>'
                '  <div class="bs-ch-title">连接模式</div>'
                '  <div class="bs-ch-sub">推荐 Chrome · 备用内置浏览器</div>'
                '</div>'
            )
            mode_radio = gr.Radio(
                choices=[MODE_CDP_LABEL, MODE_PW_LABEL],
                value=MODE_CDP_LABEL,
                label="选择连接方式",
                elem_classes=["bs-mode-radio"],
            )

            with gr.Column(visible=True) as cdp_section:
                gr.HTML(
                    _render_tip_html(
                        "chrome",
                        "Chrome 真实浏览器模式 (推荐)",
                        "点击「连接 BOSS 直聘」后系统会启动 Chrome 浏览器, "
                        "首次使用请在弹出的 Chrome 中登录 BOSS 直聘, "
                        "后续会自动记住登录状态。",
                    )
                )
                cdp_port_input = gr.Textbox(
                    label="调试端口 (一般无需修改)",
                    value="9222",
                    max_lines=1,
                    visible=False,
                    elem_classes=["bs-input-field"],
                )

            with gr.Column(visible=False) as pw_section:
                gr.HTML(
                    _render_tip_html(
                        "pw",
                        "内置浏览器模式 (备用)",
                        "使用内置浏览器, 通过 Cookie 或扫码登录。"
                        " Chrome 不可用时系统会自动降级到此模式。",
                    )
                )

        def _toggle_mode(label):
            is_cdp = "Chrome" in (label or "")
            return gr.update(visible=is_cdp), gr.update(visible=not is_cdp)

        mode_radio.change(
            fn=_toggle_mode,
            inputs=[mode_radio],
            outputs=[cdp_section, pw_section],
        )

        # ============ 个人信息 (已登录) ============
        with gr.Column(visible=False, elem_classes=["bs-card", "bs-card-profile"]) as profile_section:
            gr.HTML(
                '<div class="bs-card-head">'
                '  <div class="bs-ch-icon bs-ch-teal">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>'
                '      <circle cx="12" cy="7" r="4"></circle>'
                '    </svg>'
                '  </div>'
                '  <div class="bs-ch-title">个人信息</div>'
                '  <div class="bs-ch-sub">从 BOSS 直聘账号实时拉取</div>'
                '</div>'
            )
            profile_html = gr.HTML("")

        # ============ 登录/扫码 (未登录) ============
        with gr.Column(visible=True, elem_classes=["bs-card", "bs-card-login"]) as login_section:
            gr.HTML(
                '<div class="bs-card-head">'
                '  <div class="bs-ch-icon bs-ch-violet">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <rect x="3" y="3" width="7" height="7" rx="1"></rect>'
                '      <rect x="14" y="3" width="7" height="7" rx="1"></rect>'
                '      <rect x="3" y="14" width="7" height="7" rx="1"></rect>'
                '      <path d="M14 14h2v2h-2z"></path>'
                '      <path d="M18 14h2v2h-2z"></path>'
                '      <path d="M14 18h2v2h-2z"></path>'
                '      <path d="M18 18h2v2h-2z"></path>'
                '    </svg>'
                '  </div>'
                '  <div class="bs-ch-title">登录 / 扫码</div>'
                '  <div class="bs-ch-sub">Chrome 模式下截图仅供参考</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["bs-login-row"]):
                with gr.Column(scale=1, elem_classes=["bs-login-col"]):
                    qr_image = gr.Image(
                        label="登录页截图 / 二维码",
                        type="pil",
                        interactive=False,
                        height=400,
                        elem_classes=["bs-qr-image"],
                    )
                with gr.Column(scale=1, elem_classes=["bs-login-col"]):
                    gr.HTML(_render_help_html())

        # ============ 打招呼话术卡 ============
        with gr.Column(elem_classes=["bs-card", "bs-card-greeting"]):
            gr.HTML(
                '<div class="bs-card-head">'
                '  <div class="bs-ch-icon bs-ch-pink">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>'
                '    </svg>'
                '  </div>'
                '  <div class="bs-ch-title">打招呼话术模板</div>'
                '  <div class="bs-ch-sub">发起沟通时的默认招呼语</div>'
                '</div>'
            )
            greeting_input = gr.Textbox(
                label="话术模板",
                placeholder="您好，我对贵公司的这个职位很感兴趣...",
                lines=3,
                value="",
                elem_classes=["bs-input-field", "bs-greeting-ta"],
            )
            greeting_msg = gr.Textbox(
                label="", interactive=False, max_lines=1, visible=False,
            )
            with gr.Row(elem_classes=["bs-action-row-mini"]):
                load_greeting_btn = gr.Button(
                    "加载已保存话术",
                    variant="secondary",
                    size="sm",
                    elem_classes=["bs-btn-mini", "bs-btn-muted"],
                )
                save_greeting_btn = gr.Button(
                    "保存话术",
                    variant="primary",
                    size="sm",
                    elem_classes=["bs-btn-mini", "bs-btn-primary"],
                )

        # ============ 黑名单卡 ============
        with gr.Column(elem_classes=["bs-card", "bs-card-blacklist"]):
            gr.HTML(
                '<div class="bs-card-head">'
                '  <div class="bs-ch-icon bs-ch-red">'
                '    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '      <circle cx="12" cy="12" r="10"></circle>'
                '      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>'
                '    </svg>'
                '  </div>'
                '  <div class="bs-ch-title">公司 &amp; 岗位黑名单</div>'
                '  <div class="bs-ch-sub">每行一个关键词, 搜索时自动过滤</div>'
                '</div>'
            )
            with gr.Row(elem_classes=["bs-bl-row"]):
                blacklist_company = gr.Textbox(
                    label="公司黑名单 (每行一个)",
                    placeholder="例:\n某某外包公司\n某某中介",
                    lines=5,
                    elem_classes=["bs-input-field", "bs-bl-ta"],
                )
                blacklist_title = gr.Textbox(
                    label="岗位名称黑名单 (每行一个)",
                    placeholder="例:\n电话销售\n保险代理",
                    lines=5,
                    elem_classes=["bs-input-field", "bs-bl-ta"],
                )
            blacklist_msg = gr.Textbox(
                label="", interactive=False, max_lines=1, visible=False,
            )
            with gr.Row(elem_classes=["bs-action-row-mini"]):
                load_bl_btn = gr.Button(
                    "加载已保存黑名单",
                    variant="secondary",
                    size="sm",
                    elem_classes=["bs-btn-mini", "bs-btn-muted"],
                )
                save_bl_btn = gr.Button(
                    "保存黑名单",
                    variant="primary",
                    size="sm",
                    elem_classes=["bs-btn-mini", "bs-btn-primary"],
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


# ================================================================
# 作用域 CSS (限定在 .bs-scope / .bs-root 下)
# ================================================================
# fmt: off
_BS_STYLE = """
<style>
/* =========================================================
   BOSS Account Page — Bento 玻璃拟态风
   作用域: .bs-scope (Gradio 组件根) / .bs-root (HTML 注入根)
   ========================================================= */
.bs-scope { color: var(--c-text-1); }
.bs-scope *, .bs-root * { box-sizing: border-box; }
#boss-page-root {
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 16px !important;
}
#boss-page-root > .block:first-child,
#boss-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* 页头 */
.bs-root .bs-head {
    display: flex; align-items: center; gap: 14px;
    margin: -8px 0 6px;
}
.bs-root .bs-head-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(52,211,153,0.22));
    border: 1px solid rgba(79,139,255,0.35);
    display: flex; align-items: center; justify-content: center;
    color: #AFC7FF;
    box-shadow: 0 8px 20px rgba(79,139,255,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.bs-root .bs-head-title { font-size: 22px; font-weight: 700; color: #F0F2FA; }
.bs-root .bs-head-sub { font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px; }

/* 通用卡片 */
.bs-scope .bs-card {
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
.bs-scope .bs-card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(255,255,255,0.16) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 22px 50px rgba(0,0,0,0.5),
        0 6px 18px rgba(168,115,245,0.14) !important;
}
.bs-scope .bs-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.bs-scope .bs-card > * { position: relative; z-index: 1; }

/* 卡头 */
.bs-scope .bs-card-head {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
}
.bs-scope .bs-ch-icon {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.bs-scope .bs-ch-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.bs-scope .bs-ch-green {
    background: linear-gradient(135deg, rgba(52,211,153,0.28), rgba(79,139,255,0.22));
    color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.35);
    box-shadow: 0 4px 14px rgba(52,211,153,0.22);
}
.bs-scope .bs-ch-teal {
    background: linear-gradient(135deg, rgba(56,189,248,0.28), rgba(52,211,153,0.22));
    color: #7DD3FC;
    border: 1px solid rgba(56,189,248,0.35);
    box-shadow: 0 4px 14px rgba(56,189,248,0.22);
}
.bs-scope .bs-ch-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(244,114,182,0.22));
    color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.35);
    box-shadow: 0 4px 14px rgba(167,139,250,0.22);
}
.bs-scope .bs-ch-pink {
    background: linear-gradient(135deg, rgba(244,114,182,0.28), rgba(251,146,60,0.22));
    color: #F9A8D4;
    border: 1px solid rgba(244,114,182,0.35);
    box-shadow: 0 4px 14px rgba(244,114,182,0.22);
}
.bs-scope .bs-ch-red {
    background: linear-gradient(135deg, rgba(248,113,113,0.28), rgba(244,114,182,0.22));
    color: #FCA5A5;
    border: 1px solid rgba(248,113,113,0.35);
    box-shadow: 0 4px 14px rgba(248,113,113,0.22);
}
.bs-scope .bs-ch-title { font-size: 16px; font-weight: 700; color: #F0F2FA; flex: 1; }
.bs-scope .bs-ch-sub { font-size: 12px; color: rgba(230,233,245,0.55); }

/* 输入字段 */
.bs-scope .bs-input-field textarea,
.bs-scope .bs-input-field input,
.bs-scope .bs-input-field .wrap-inner {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    border-radius: 12px !important;
}
.bs-scope .bs-input-field textarea:focus,
.bs-scope .bs-input-field input:focus {
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.12) !important;
}
.bs-scope .bs-opmsg-box textarea { min-height: 60px !important; font-size: 13px !important; }
.bs-scope .bs-greeting-ta textarea { min-height: 100px !important; font-size: 14px !important; line-height: 1.8 !important; }
.bs-scope .bs-bl-ta textarea { min-height: 140px !important; font-size: 13px !important; line-height: 1.7 !important; font-family: 'JetBrains Mono', 'Consolas', monospace !important; }

/* 状态 pill */
.bs-root .bst {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: 999px;
    font-size: 13px; font-weight: 700;
    letter-spacing: 0.3px;
    border: 1px solid;
}
.bs-root .bst-green {
    background: rgba(52,211,153,0.15);
    color: #6EE7B7;
    border-color: rgba(52,211,153,0.35);
    box-shadow: 0 0 16px rgba(52,211,153,0.22);
}
.bs-root .bst-orange {
    background: rgba(251,146,60,0.15);
    color: #FDBA74;
    border-color: rgba(251,146,60,0.35);
    box-shadow: 0 0 16px rgba(251,146,60,0.18);
}
.bs-root .bst-gray {
    background: rgba(148,163,184,0.14);
    color: rgba(226,232,240,0.85);
    border-color: rgba(148,163,184,0.28);
}
.bs-root .bs-meta {
    display: inline-flex; align-items: center; gap: 6px;
    margin-left: 10px;
    padding: 5px 10px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    font-size: 12px; color: rgba(230,233,245,0.75);
}
.bs-root .bs-meta-k {
    color: rgba(230,233,245,0.5);
    margin-right: 2px;
}
.bs-root .bs-meta-warn { color: #FDBA74; border-color: rgba(251,146,60,0.25); background: rgba(251,146,60,0.08); }

/* 动作按钮行 */
.bs-scope .bs-action-row { gap: 10px !important; margin-top: 6px; }
.bs-scope .bs-action-row-mini { gap: 8px !important; }

.bs-scope .bs-btn,
.bs-scope .bs-btn button,
.bs-scope .bs-btn-mini,
.bs-scope .bs-btn-mini button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease, background 0.25s ease !important;
    letter-spacing: 0.3px !important;
}
.bs-scope .bs-btn button {
    padding: 12px 16px !important;
    font-size: 13.5px !important;
}
.bs-scope .bs-btn-mini button {
    padding: 8px 14px !important;
    font-size: 12.5px !important;
}
.bs-scope .bs-btn-primary,
.bs-scope .bs-btn-primary button {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 8px 20px rgba(79,139,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.bs-scope .bs-btn-primary:hover,
.bs-scope .bs-btn-primary button:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(79,139,255,0.45), inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.bs-scope .bs-btn-secondary,
.bs-scope .bs-btn-secondary button {
    background: rgba(52,211,153,0.12) !important;
    color: #6EE7B7 !important;
    border: 1px solid rgba(52,211,153,0.30) !important;
    box-shadow: 0 4px 14px rgba(52,211,153,0.18) !important;
}
.bs-scope .bs-btn-secondary:hover,
.bs-scope .bs-btn-secondary button:hover {
    background: rgba(52,211,153,0.18) !important;
    border-color: rgba(52,211,153,0.45) !important;
}
.bs-scope .bs-btn-warn,
.bs-scope .bs-btn-warn button {
    background: rgba(251,146,60,0.12) !important;
    color: #FDBA74 !important;
    border: 1px solid rgba(251,146,60,0.30) !important;
}
.bs-scope .bs-btn-warn:hover,
.bs-scope .bs-btn-warn button:hover {
    background: rgba(251,146,60,0.18) !important;
    border-color: rgba(251,146,60,0.45) !important;
}
.bs-scope .bs-btn-danger,
.bs-scope .bs-btn-danger button {
    background: rgba(248,113,113,0.12) !important;
    color: #FCA5A5 !important;
    border: 1px solid rgba(248,113,113,0.30) !important;
}
.bs-scope .bs-btn-danger:hover,
.bs-scope .bs-btn-danger button:hover {
    background: rgba(248,113,113,0.18) !important;
    border-color: rgba(248,113,113,0.45) !important;
}
.bs-scope .bs-btn-muted,
.bs-scope .bs-btn-muted button {
    background: rgba(255,255,255,0.04) !important;
    color: rgba(230,233,245,0.75) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
}
.bs-scope .bs-btn-muted:hover,
.bs-scope .bs-btn-muted button:hover {
    background: rgba(79,139,255,0.12) !important;
    color: #AFC7FF !important;
    border-color: rgba(79,139,255,0.35) !important;
}

/* Mode radio: segmented 风格 — 两个对等 pill, 左右等分 */
.bs-scope .bs-mode-radio .wrap {
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
    gap: 12px !important;
    padding: 6px 2px !important;
    background: rgba(17,22,48,0.35) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important;
    padding: 6px !important;
}
.bs-scope .bs-mode-radio label {
    position: relative;
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 10px !important;
    padding: 14px 36px 14px 46px !important;
    cursor: pointer;
    transition: background 0.22s ease, border-color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease !important;
    margin: 0 !important;
    color: rgba(230,233,245,0.78) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: 0.2px !important;
    min-height: 56px !important;
    display: flex !important;
    align-items: center !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.bs-scope .bs-mode-radio label input[type="radio"] {
    position: absolute; opacity: 0; pointer-events: none;
}
/* 左侧图标 (伪元素) */
.bs-scope .bs-mode-radio label::before {
    content: '';
    position: absolute;
    left: 14px; top: 50%;
    transform: translateY(-50%);
    width: 22px; height: 22px;
    background-repeat: no-repeat; background-position: center; background-size: contain;
    opacity: 0.85;
    transition: opacity 0.22s ease, transform 0.22s ease;
}
/* 第一个 Chrome, 第二个 内置浏览器 */
.bs-scope .bs-mode-radio label:nth-child(1)::before {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='22' height='22' fill='none' stroke='%238DBBFF' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'/><circle cx='12' cy='12' r='4'/><line x1='21.17' y1='8' x2='12' y2='8'/><line x1='3.95' y1='6.06' x2='8.54' y2='14'/><line x1='10.88' y1='21.94' x2='15.46' y2='14'/></svg>");
}
.bs-scope .bs-mode-radio label:nth-child(2)::before {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='22' height='22' fill='none' stroke='%23DDD6FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='2' y='3' width='20' height='14' rx='2' ry='2'/><line x1='8' y1='21' x2='16' y2='21'/><line x1='12' y1='17' x2='12' y2='21'/></svg>");
}
.bs-scope .bs-mode-radio label:hover {
    background: rgba(255,255,255,0.04) !important;
    border-color: rgba(255,255,255,0.10) !important;
    color: #F0F2FA !important;
}
.bs-scope .bs-mode-radio label:has(input:checked) {
    background: linear-gradient(135deg, rgba(79,139,255,0.22), rgba(121,90,255,0.14)) !important;
    border-color: rgba(79,139,255,0.50) !important;
    box-shadow: 0 6px 18px rgba(79,139,255,0.28), inset 0 1px 0 rgba(255,255,255,0.12) !important;
    color: #F0F2FA !important;
}
.bs-scope .bs-mode-radio label:has(input:checked)::before {
    opacity: 1;
    transform: translateY(-50%) scale(1.08);
}
/* 选中时添加右上角对勾徽章 */
.bs-scope .bs-mode-radio label:has(input:checked)::after {
    content: '';
    position: absolute;
    top: 10px; right: 10px;
    width: 16px; height: 16px;
    border-radius: 50%;
    background: #4F8BFF;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.22), 0 4px 10px rgba(79,139,255,0.45);
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' width='16' height='16' fill='none' stroke='white' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'><polyline points='3 8 7 12 13 4'/></svg>");
    background-repeat: no-repeat; background-position: center; background-size: 10px;
}
/* 顶层 label 文本 "选择连接方式" 淡化 */
.bs-scope .bs-mode-radio > label.block,
.bs-scope .bs-mode-radio > .block-label {
    color: rgba(230,233,245,0.55) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    margin-bottom: 6px !important;
}

/* 中窄屏 (1100-1300px): 两 pill 各自加 ellipsis, 缩小字体 */
@media (max-width: 1300px) {
    .bs-scope .bs-mode-radio label {
        font-size: 12.5px !important;
        padding: 12px 36px 12px 42px !important;
        letter-spacing: 0.1px !important;
    }
}
/* 窄屏 (≤1100px): 两个 segmented pill 改为上下堆叠 */
@media (max-width: 1100px) {
    .bs-scope .bs-mode-radio .wrap {
        grid-template-columns: 1fr !important;
        gap: 8px !important;
    }
    .bs-scope .bs-mode-radio label {
        min-height: 52px !important;
        padding: 14px 38px 14px 48px !important;
        font-size: 13.5px !important;
        white-space: normal !important;
        overflow: visible !important;
    }
}
@media (max-width: 600px) {
    .bs-scope .bs-mode-radio label {
        font-size: 13px !important;
        padding: 12px 36px 12px 42px !important;
        min-height: 48px !important;
    }
    .bs-scope .bs-mode-radio label::before {
        width: 18px; height: 18px;
        left: 12px;
    }
}

/* Tip 信息块 */
.bs-root .bs-tip {
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.75;
    margin-top: 6px;
}
.bs-root .bs-tip-title {
    font-weight: 700; font-size: 13.5px; margin-bottom: 6px;
    display: flex; align-items: center; gap: 6px;
}
.bs-root .bs-tip-body { color: rgba(230,233,245,0.75); font-size: 12.5px; }
.bs-root .bs-tip-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.12), rgba(121,90,255,0.08));
    border: 1px solid rgba(79,139,255,0.28);
}
.bs-root .bs-tip-blue .bs-tip-title { color: #AFC7FF; }
.bs-root .bs-tip-green {
    background: linear-gradient(135deg, rgba(52,211,153,0.12), rgba(79,139,255,0.08));
    border: 1px solid rgba(52,211,153,0.28);
}
.bs-root .bs-tip-green .bs-tip-title { color: #6EE7B7; }
.bs-root .bs-tip-orange {
    background: linear-gradient(135deg, rgba(251,146,60,0.12), rgba(244,114,182,0.08));
    border: 1px solid rgba(251,146,60,0.28);
}
.bs-root .bs-tip-orange .bs-tip-title { color: #FDBA74; }

/* Login/QR 栏 */
.bs-scope .bs-login-row { gap: 16px !important; }
.bs-scope .bs-qr-image {
    border-radius: 14px !important;
    overflow: hidden !important;
    background: rgba(17,22,48,0.35) !important;
    border: 1px dashed rgba(255,255,255,0.1) !important;
}
.bs-scope .bs-qr-image img {
    border-radius: 10px !important;
}

/* Help 面板 */
.bs-root .bs-help-card {
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 14px;
    padding: 18px;
    height: 100%;
}
.bs-root .bs-help-title {
    font-size: 14px; font-weight: 700; color: #F0F2FA;
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 12px;
    color: #8DBBFF;
}
.bs-root .bs-help-section { margin-bottom: 14px; }
.bs-root .bs-help-h {
    font-size: 13px; font-weight: 700; color: rgba(230,233,245,0.85);
    margin-bottom: 6px;
    padding-left: 8px; border-left: 3px solid #4F8BFF;
}
.bs-root .bs-help-ol {
    margin: 0; padding-left: 22px;
    color: rgba(230,233,245,0.75); font-size: 12.5px; line-height: 1.8;
}
.bs-root .bs-help-ol li { margin-bottom: 2px; }
.bs-root .bs-help-note {
    margin-top: 10px;
    padding: 8px 12px;
    background: rgba(52,211,153,0.08);
    border: 1px solid rgba(52,211,153,0.22);
    border-radius: 8px;
    color: #6EE7B7;
    font-size: 12px;
}

/* Profile 个人信息卡 */
.bs-root .bs-profile-card { }
.bs-root .bs-profile-empty {
    padding: 20px; text-align: center;
    color: rgba(230,233,245,0.55); font-size: 13px;
    background: rgba(17,22,48,0.3);
    border: 1px dashed rgba(255,255,255,0.1);
    border-radius: 12px;
}
.bs-root .bs-profile-head {
    display: flex; align-items: center; gap: 14px;
    padding: 8px 0 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 12px;
}
.bs-root .bs-avatar {
    width: 52px; height: 52px; border-radius: 14px;
    background: linear-gradient(135deg, #4F8BFF, #795AFF);
    color: #FFF;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 800;
    box-shadow: 0 8px 18px rgba(79,139,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18);
    flex-shrink: 0;
}
.bs-root .bs-profile-ident { flex: 1; min-width: 0; }
.bs-root .bs-profile-name {
    font-size: 16px; font-weight: 700; color: #F0F2FA;
    margin-bottom: 6px;
}
.bs-root .bs-profile-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.bs-root .bs-chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    border: 1px solid transparent;
}
.bs-root .bs-chip-green {
    background: rgba(52,211,153,0.14); color: #6EE7B7;
    border-color: rgba(52,211,153,0.28);
}
.bs-root .bs-chip-blue {
    background: rgba(79,139,255,0.14); color: #AFC7FF;
    border-color: rgba(79,139,255,0.28);
}
.bs-root .bs-profile-tag {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 12px; border-radius: 999px;
    background: rgba(52,211,153,0.14);
    color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.30);
    font-size: 12px; font-weight: 700;
    flex-shrink: 0;
}
.bs-root .bs-pinfo { display: flex; flex-direction: column; gap: 10px; }
.bs-root .bs-pinfo-row {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 10px;
    padding: 10px 14px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 10px;
}
.bs-root .bs-pinfo-k {
    font-size: 12px; color: rgba(230,233,245,0.5);
    padding-top: 2px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
.bs-root .bs-pinfo-v {
    font-size: 13px; color: #F0F2FA; line-height: 1.75;
}
.bs-root .bs-pinfo-empty {
    padding: 14px; text-align: center;
    color: rgba(230,233,245,0.5); font-size: 12.5px;
    background: rgba(255,255,255,0.02);
    border-radius: 10px;
}

/* Blacklist 布局 */
.bs-scope .bs-bl-row { gap: 14px !important; }

/* 窄屏 */
@media (max-width: 900px) {
    .bs-scope .bs-login-row { flex-direction: column !important; }
    .bs-scope .bs-bl-row { flex-direction: column !important; }
    .bs-scope .bs-action-row { flex-wrap: wrap !important; }
}
</style>
"""
# fmt: on
