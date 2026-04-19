"""登录页面模块

双栏分屏登录页 — 左侧品牌展示 + 右侧登录表单。
参考 BOSS 直聘登录页设计, 适配项目蓝色主题。
LLM API Key 实时校验 + 姓名标识。
全局登录状态管理 + 退出登录。
用户名仅允许英文字母 (拼音格式), 用于数据隔离。
"""

from __future__ import annotations

import html as html_mod
import re

import gradio as gr

from app.core.config import get_settings, reload_settings, update_env_file
from app.core.logger import get_logger
from app.utils.auth_util import validate_api_key

logger = get_logger(__name__)

_USERNAME_RE = re.compile(r"^[a-zA-Z]+$")


# fmt: off
LOGIN_CSS = """
/* ============ Login Page — Split Layout ============ */

#login-panel {
    display: flex;
    align-items: center !important;
    justify-content: center !important;
    min-height: 100vh !important;
    background: linear-gradient(135deg, #0B1426 0%, #0F1E3D 30%, #162D58 60%, #1B3A6E 100%) !important;
    padding: 24px !important;
    position: relative !important;
    overflow: hidden !important;
}
#login-panel.hide {
    display: none !important;
}
#login-panel::before {
    content: '';
    position: absolute;
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(22,93,255,0.08), transparent 70%);
    border-radius: 50%;
    top: -150px; right: -100px;
    pointer-events: none;
}
#login-panel::after {
    content: '';
    position: absolute;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(71,133,255,0.06), transparent 70%);
    border-radius: 50%;
    bottom: -100px; left: -50px;
    pointer-events: none;
}

/* Split card container */
#login-container {
    max-width: 860px !important;
    width: 100% !important;
    border-radius: 20px !important;
    overflow: hidden !important;
    box-shadow: 0 24px 80px rgba(0,0,0,0.4),
                0 0 0 1px rgba(255,255,255,0.05) !important;
    gap: 0 !important;
    padding: 0 !important;
    background: #FFFFFF !important;
    border: none !important;
    animation: scaleIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    position: relative !important;
    z-index: 1 !important;
    align-items: stretch !important;
}

/* Left branding panel */
#login-left {
    background: linear-gradient(135deg, #165DFF 0%, #3575FF 50%, #5B93FF 100%) !important;
    padding: 52px 36px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    min-width: 340px !important;
    border: none !important;
    position: relative !important;
    overflow: hidden !important;
    align-self: stretch !important;
    border-radius: 0 !important;
}
#login-left > div { padding: 0 !important; }
#login-left::before {
    content: '';
    position: absolute;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(255,255,255,0.08), transparent 70%);
    border-radius: 50%;
    top: -40px; right: -40px;
    pointer-events: none;
}
#login-left::after {
    content: '';
    position: absolute;
    width: 160px; height: 160px;
    background: radial-gradient(circle, rgba(255,255,255,0.06), transparent 70%);
    border-radius: 50%;
    bottom: -30px; left: -30px;
    pointer-events: none;
}

/* Brand elements */
.login-brand { position: relative; z-index: 1; }
.brand-badge-row {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 12px;
}
.brand-badge {
    background: rgba(255,255,255,0.2);
    backdrop-filter: blur(10px);
    color: #fff;
    font-size: 15px; font-weight: 800;
    padding: 8px 14px;
    border-radius: 10px;
    letter-spacing: 1px;
    border: 1px solid rgba(255,255,255,0.15);
}
.brand-label {
    font-size: 22px; font-weight: 700;
    color: #fff; letter-spacing: 0.5px;
}
.brand-tagline {
    font-size: 14px;
    color: rgba(255,255,255,0.65);
    margin-bottom: 40px;
    letter-spacing: 0.5px;
}
.brand-features {
    display: flex; flex-direction: column; gap: 16px;
    perspective: 800px;
}
.feature-item {
    display: flex; align-items: center; gap: 14px;
    padding: 14px 16px;
    background: rgba(255,255,255,0.1);
    border-radius: 12px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.12);
    transition:
        transform 0.45s cubic-bezier(0.2, 0.8, 0.2, 1),
        background 0.3s ease,
        border-color 0.3s ease,
        box-shadow 0.35s ease;
    transform-style: preserve-3d;
    position: relative;
    cursor: default;
    will-change: transform;
}
.feature-item::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 12px;
    background: linear-gradient(135deg,
        rgba(255,255,255,0.18) 0%,
        rgba(255,255,255,0.0) 45%,
        rgba(255,255,255,0.0) 55%,
        rgba(255,255,255,0.12) 100%);
    opacity: 0;
    transition: opacity 0.35s ease;
    pointer-events: none;
}
.feature-item::after {
    content: '';
    position: absolute;
    left: -40%; top: -50%;
    width: 60%; height: 200%;
    background: linear-gradient(115deg,
        transparent 30%,
        rgba(255,255,255,0.18) 48%,
        rgba(255,255,255,0.32) 50%,
        rgba(255,255,255,0.18) 52%,
        transparent 70%);
    transform: skewX(-18deg);
    opacity: 0;
    pointer-events: none;
    transition: left 0.7s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.35s ease;
}
.feature-item:hover {
    background: rgba(255,255,255,0.18);
    border-color: rgba(255,255,255,0.3);
    transform:
        perspective(800px)
        translateY(-6px)
        translateZ(0)
        rotateX(4deg)
        rotateY(-3deg);
    box-shadow:
        0 18px 36px rgba(0,0,0,0.28),
        0 4px 12px rgba(22,93,255,0.18),
        inset 0 1px 0 rgba(255,255,255,0.22);
}
.feature-item:hover::before { opacity: 1; }
.feature-item:hover::after { opacity: 1; left: 110%; }
.feature-item:hover .feature-icon {
    transform: scale(1.18) rotate(-6deg);
    filter: drop-shadow(0 6px 14px rgba(255,255,255,0.32));
}
.feature-icon {
    font-size: 26px; flex-shrink: 0;
    width: 36px; text-align: center;
    transition: transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1),
                filter 0.35s ease;
    will-change: transform;
}
.feature-name {
    font-size: 15px; font-weight: 600;
    color: #fff; margin-bottom: 3px;
}
.feature-desc {
    font-size: 12px;
    color: rgba(255,255,255,0.6);
    line-height: 1.4;
}

/* Right form panel */
#login-card {
    background: #FFFFFF !important;
    padding: 48px 40px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    min-width: 360px !important;
    border: none !important;
    border-radius: 0 !important;
}
#login-card > div { padding: 0 !important; }
#login-card label span {
    color: #4E5969 !important;
    font-size: 13px !important;
    font-weight: 550 !important;
    background: none !important;
}
#login-card input {
    background: #F7F8FA !important;
    border: 1.5px solid #E5E6EB !important;
    color: #1D2129 !important;
    border-radius: 10px !important;
    height: 44px !important;
    transition: all 0.3s !important;
}
#login-card input::placeholder { color: #C9CDD4 !important; }
#login-card input:focus {
    border-color: #165DFF !important;
    box-shadow: 0 0 0 3px rgba(22,93,255,0.10) !important;
    background: #FFFFFF !important;
}

/* Login title and subtitle */
.login-title {
    text-align: center;
    font-size: 24px; font-weight: 700;
    color: #1D2129;
    margin-bottom: 6px;
    line-height: 1.5;
    background: none;
    -webkit-text-fill-color: #1D2129;
    background-clip: unset;
    -webkit-background-clip: unset;
}
.login-subtitle {
    text-align: center;
    font-size: 14px;
    color: #86909C;
    margin-bottom: 32px;
}

/* Login error */
#login-error { min-height: 24px !important; }
.login-error-text {
    color: #F53F3F;
    font-size: 13px;
    text-align: center;
    padding: 8px 12px;
    background: rgba(245,63,63,0.06);
    border-radius: 8px;
    border: 1px solid rgba(245,63,63,0.12);
}

/* Login button */
#login-btn {
    margin-top: 8px !important;
    background: linear-gradient(135deg, #165DFF, #4785FF) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    height: 46px !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 16px rgba(22,93,255,0.3) !important;
    transition: all 0.3s !important;
    letter-spacing: 0.5px !important;
}
#login-btn:hover {
    box-shadow: 0 8px 24px rgba(22,93,255,0.4) !important;
    transform: translateY(-1px) !important;
}
#login-btn:active { transform: translateY(0) !important; }

/* Login footer */
.login-footer {
    text-align: center;
    color: #C9CDD4;
    font-size: 12px;
    margin-top: 24px;
    letter-spacing: 0.3px;
}

/* ============ Logout Row (hidden, kept for Gradio event wiring) ============ */
#logout-row {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
}

/* ============ Header User Dropdown ============ */
.header-user-dropdown {
    position: relative;
    display: inline-flex;
    align-items: center;
}
.header-user-trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: #4E5969;
    font-weight: 500;
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 8px;
    transition: all 0.2s ease;
    user-select: none;
}
.header-user-trigger:hover {
    background: rgba(22,93,255,0.06);
    color: #165DFF;
}
.header-user-arrow {
    transition: transform 0.25s ease;
    color: #86909C;
    margin-left: 2px;
}
.header-user-dropdown:hover .header-user-arrow {
    transform: rotate(180deg);
    color: #165DFF;
}
.header-user-menu {
    position: absolute;
    top: 100%;
    right: 0;
    min-width: 160px;
    padding: 14px 6px 6px 6px;
    margin-top: -4px;
    background: transparent;
    opacity: 0;
    visibility: hidden;
    transform: translateY(-4px);
    transition: all 0.2s ease;
    z-index: 1000;
}
.header-user-menu > .header-user-menu-card {
    background: #FFFFFF;
    border-radius: 10px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.04);
    padding: 6px;
}
.header-user-dropdown:hover .header-user-menu {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
}
.header-user-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: #4E5969;
    border-radius: 6px;
    cursor: default;
    white-space: nowrap;
    transition: all 0.15s ease;
}
.header-user-info {
    font-weight: 500;
    color: #1D2129;
}
.header-user-menu-divider {
    height: 1px;
    background: #F2F3F5;
    margin: 4px 8px;
}
.header-logout-item {
    cursor: pointer !important;
    color: #F53F3F;
}
.header-logout-item:hover {
    background: rgba(245,63,63,0.06);
    color: #CB2634;
}

/* ============ Responsive Login ============ */
@media (max-width: 768px) {
    #login-container {
        flex-direction: column !important;
        max-width: 440px !important;
    }
    #login-left {
        min-width: 100% !important;
        padding: 32px 28px !important;
    }
    #login-left .brand-features { display: none !important; }
    #login-card {
        min-width: 100% !important;
        padding: 36px 28px !important;
    }
}
"""
# fmt: on


LOGIN_BRAND_HTML = """<div class="login-brand">
    <div class="brand-badge-row">
        <span class="brand-badge">AI</span>
        <span class="brand-label">求职智能管家</span>
    </div>
    <div class="brand-tagline">智能求职 · 精准匹配 · 高效投递</div>
    <div class="brand-features">
        <div class="feature-item">
            <div class="feature-icon">🤖</div>
            <div>
                <div class="feature-name">AI 智能匹配</div>
                <div class="feature-desc">智能解析 JD 岗位描述，与简历精准匹配分析</div>
            </div>
        </div>
        <div class="feature-item">
            <div class="feature-icon">📝</div>
            <div>
                <div class="feature-name">简历优化</div>
                <div class="feature-desc">AI 驱动针对性优化，提升面试邀约率</div>
            </div>
        </div>
        <div class="feature-item">
            <div class="feature-icon">🚀</div>
            <div>
                <div class="feature-name">自动投递</div>
                <div class="feature-desc">智能批量投递，全流程自动化管理</div>
            </div>
        </div>
    </div>
</div>"""


def _get_failed_count(user_name: str) -> int:
    """获取当前用户最近 24h 失败投递数（用于 header 通知铃铛角标）。失败时返回 0。"""
    if not user_name:
        return 0
    try:
        from app.db.crud import DeliveryRecordCRUD
        recs = DeliveryRecordCRUD.list_records(
            user_name=user_name,
            status="failed",
            limit=200,
            offset=0,
        )
        return len(recs) if recs else 0
    except Exception:
        return 0


def _build_notification_html(user_name: str) -> str:
    """构建通知铃铛 + 下拉面板 HTML。"""
    failed = _get_failed_count(user_name)
    badge = (
        f'<span class="header-bell-badge" aria-label="{failed} 条失败投递">'
        f'{failed if failed < 99 else "99+"}</span>'
    ) if failed > 0 else ""
    panel_body = (
        f'<div class="header-bell-panel-row header-bell-row-warn">'
        f'<span class="hbell-row-dot"></span>'
        f'<div class="hbell-row-text">'
        f'<div class="hbell-row-title">最近 24h 投递失败</div>'
        f'<div class="hbell-row-sub">共 {failed} 条记录, 点击查看 →</div>'
        f'</div></div>'
        if failed > 0 else
        '<div class="header-bell-panel-empty">'
        '<div class="hbell-empty-ico">\U0001F389</div>'
        '<div class="hbell-empty-title">暂无失败通知</div>'
        '<div class="hbell-empty-sub">投递任务运行正常</div>'
        '</div>'
    )
    return (
        '<div class="header-bell-wrap" role="button" tabindex="0" '
        'aria-haspopup="menu" aria-expanded="false" '
        'aria-label="通知中心" data-haju-menu="bell" '
        'onmouseenter="this.setAttribute(\'aria-expanded\',\'true\')" '
        'onmouseleave="if(!this.classList.contains(\'open\'))'
        '{this.setAttribute(\'aria-expanded\',\'false\');}" '
        'onkeydown="if(event.key===\'Enter\'||event.key===\' \')'
        '{event.preventDefault();this.classList.toggle(\'open\');'
        'this.setAttribute(\'aria-expanded\',this.classList.contains(\'open\'));}'
        'else if(event.key===\'Escape\')'
        '{this.classList.remove(\'open\');this.setAttribute(\'aria-expanded\',\'false\');this.blur();}">'
        '<span class="header-bell-trigger" '
        'onclick="(function(t){const w=t.closest(\'.header-bell-wrap\');'
        'if(w){w.classList.toggle(\'open\');'
        'w.setAttribute(\'aria-expanded\',w.classList.contains(\'open\'));}})(this);">'
        '<svg class="header-bell-ico" viewBox="0 0 24 24" width="18" height="18" '
        'fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'aria-hidden="true" role="img">'
        '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/>'
        '<path d="M13.73 21a2 2 0 0 1-3.46 0"/>'
        '</svg>'
        f'{badge}'
        '</span>'
        '<div class="header-bell-panel" role="menu" aria-label="通知列表">'
        '<div class="header-bell-panel-card">'
        '<div class="header-bell-panel-head">'
        '<span class="hbell-head-title">通知中心</span>'
        '<span class="hbell-head-link" '
        'onclick="(function(){const t=document.querySelectorAll(\'#main-tabs '
        '.tab-wrapper button\');for(const b of t){if(b.textContent.includes(\'投递记录\'))'
        '{b.click();break;}}})();">查看全部</span>'
        '</div>'
        f'{panel_body}'
        '</div>'
        '</div>'
        '</div>'
    )


def build_header_html(user_name: str, version: str) -> str:
    """构建顶部通栏 HTML（含 logo / 通知铃铛 / 用户下拉菜单）。"""
    safe_name = html_mod.escape(user_name) if user_name else ""
    if safe_name:
        bell_block = _build_notification_html(user_name)
        avatar_letter = safe_name[0].upper() if safe_name else "?"
        user_block = (
            f'<div class="header-user-dropdown" role="button" tabindex="0" '
            f'aria-haspopup="menu" aria-expanded="false" aria-label="用户菜单" '
            f'data-haju-menu="user" '
            f'onmouseenter="this.setAttribute(\'aria-expanded\',\'true\')" '
            f'onmouseleave="this.setAttribute(\'aria-expanded\',\'false\')" '
            f'onfocus="this.setAttribute(\'aria-expanded\',\'true\')" '
            f'onblur="this.setAttribute(\'aria-expanded\',\'false\')" '
            f'onkeydown="if(event.key===\'Enter\'||event.key===\' \')'
            f'{{event.preventDefault();this.classList.toggle(\'open\');'
            f'this.setAttribute(\'aria-expanded\',this.classList.contains(\'open\'));}}'
            f'else if(event.key===\'Escape\')'
            f'{{this.classList.remove(\'open\');this.setAttribute(\'aria-expanded\',\'false\');this.blur();}}">'
            f'<span class="header-user-trigger">'
            f'<span class="header-user-avatar" aria-hidden="true">{avatar_letter}</span>'
            f'<span class="header-user-name">{safe_name}</span>'
            f'<svg class="header-user-arrow" viewBox="0 0 12 12" '
            f'width="12" height="12" aria-hidden="true" role="img">'
            f'<path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="currentColor" '
            f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>'
            f'</span>'
            f'<div class="header-user-menu" role="menu">'
            f'<div class="header-user-menu-card">'
            f'<div class="header-user-menu-item header-user-info">'
            f'<span class="header-user-avatar header-user-avatar-lg" '
            f'aria-hidden="true">{avatar_letter}</span>'
            f'<div class="header-user-info-text">'
            f'<div class="header-user-info-name">{safe_name}</div>'
            f'<div class="header-user-info-sub">已登录</div>'
            f'</div>'
            f'</div>'
            f'<div class="header-user-menu-divider"></div>'
            f'<div class="header-user-menu-item" role="menuitem" '
            f'onclick="(function(){{const t=document.querySelectorAll('
            f'\'#main-tabs .tab-wrapper button\');'
            f'for(const b of t){{if(b.textContent.includes(\'系统设置\'))'
            f'{{b.click();break;}}}}}})();">'
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" role="img">'
            f'<circle cx="12" cy="12" r="3"/>'
            f'<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 '
            f'2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 '
            f'2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l'
            f'-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 '
            f'1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 '
            f'1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 '
            f'0 0 0 1.82.33h.0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 '
            f'1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 '
            f'2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.0a1.65 1.65 0 0 0 1.51 1H21'
            f'a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
            f'</svg>'
            f'<span>系统设置</span>'
            f'</div>'
            f'<div class="header-user-menu-divider"></div>'
            f'<div class="header-user-menu-item header-logout-item" role="menuitem" '
            f'onclick="document.querySelector(\'#logout-btn\').click()">'
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" role="img">'
            f'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
            f'<polyline points="16 17 21 12 16 7"/>'
            f'<line x1="21" y1="12" x2="9" y2="12"/>'
            f'</svg>'
            f'<span>退出登录</span>'
            f'</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
    else:
        bell_block = ""
        user_block = ""
    return (
        '<div class="app-header-bar">'
        '<div class="hl">'
        '<span class="logo-text">AI求职智能管家</span>'
        '<span class="hd"></span>'
        '<span class="bc">智能求职辅助平台</span>'
        "</div>"
        '<div class="hr">'
        f'<span class="ver">V{version}</span>'
        f"{bell_block}"
        f"{user_block}"
        "</div>"
        "</div>"
    )


def handle_login(user_name: str, api_key: str, base_url: str, model: str) -> tuple:
    """处理登录请求

    Returns:
        8-tuple matching _login_outputs:
            login_state, browser_state,
            login_panel, agreement_panel, main_panel,
            login_error, header_html, user_label_html
    """
    _keep = gr.skip()

    if not user_name or not user_name.strip():
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            '<div class="login-error-text">请输入用户名</div>',
            _keep, _keep,
        )

    user_name = user_name.strip()

    if not _USERNAME_RE.match(user_name):
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            '<div class="login-error-text">用户名仅支持英文字母 (拼音格式, 如 zhangsan)</div>',
            _keep, _keep,
        )

    if not api_key or not api_key.strip():
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            '<div class="login-error-text">请输入 API Key</div>',
            _keep, _keep,
        )

    if not base_url or not base_url.strip():
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            '<div class="login-error-text">请输入 API Base URL</div>',
            _keep, _keep,
        )

    if not model or not str(model).strip():
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            '<div class="login-error-text">请输入模型名称</div>',
            _keep, _keep,
        )

    base_url = base_url.strip().rstrip("/")
    model = str(model).strip()

    try:
        result = validate_api_key(
            api_key,
            base_url=base_url,
            model=model,
        )
    except Exception as e:
        logger.error("API Key 校验过程异常: %s", e)
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            '<div class="login-error-text">API 校验服务异常, 请稍后重试</div>',
            _keep, _keep,
        )

    if not result.success:
        safe_msg = html_mod.escape(result.message)
        return (
            {"logged_in": False}, _keep,
            _keep, _keep, _keep,
            f'<div class="login-error-text">{safe_msg}</div>',
            _keep, _keep,
        )

    # ---- 校验通过 ----
    user_name = user_name.lower()
    api_key = api_key.strip()

    try:
        update_env_file(
            {
                "LLM_API_KEY": api_key,
                "LLM_BASE_URL": base_url,
                "LLM_MODEL": model,
            }
        )
        reload_settings()
        logger.info(
            "用户 [%s] 登录成功, API 配置已同步 (base_url=%s, model=%s)",
            user_name,
            base_url,
            model,
        )
    except Exception as e:
        logger.error("登录后保存配置失败: %s", e)

    state = {
        "logged_in": True,
        "user_name": user_name,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }
    browser_data = {
        "logged_in": True,
        "user_name": user_name,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }

    from app.db.crud import SysConfigCRUD

    try:
        agreed = SysConfigCRUD.get("agreement_accepted", user_name=user_name) == "true"
    except Exception:
        agreed = False

    settings = get_settings()
    header = build_header_html(user_name, settings.APP_VERSION)
    safe_name = html_mod.escape(user_name)
    user_label = f'<span class="logout-user-label">当前用户: {safe_name}</span>'

    if agreed:
        return (
            state, browser_data,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            "",
            header,
            user_label,
        )

    return (
        state, browser_data,
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(visible=False),
        "",
        header,
        user_label,
    )


def handle_logout() -> tuple:
    """退出登录, 清空会话状态

    Returns:
        10-tuple matching logout outputs:
            login_state, browser_state,
            login_panel, agreement_panel, main_panel,
            login_name, login_key, login_base_url, login_model, login_error
    """
    logger.info("用户退出登录")
    settings = get_settings()
    empty = {
        "logged_in": False,
        "user_name": "",
        "api_key": "",
        "base_url": "",
        "model": "",
    }
    return (
        empty,
        empty,
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        "",
        settings.LLM_BASE_URL,
        settings.LLM_MODEL,
        "",
    )


def restore_session(saved_state) -> tuple:
    """从 BrowserState 恢复会话 (页面加载时自动调用)

    Returns:
        6-tuple: (login_state,
                  login_vis, agree_vis, main_vis,
                  header, user_label)
    """
    _keep = gr.skip()
    empty_state = {
        "logged_in": False,
        "user_name": "",
        "api_key": "",
        "base_url": "",
        "model": "",
    }
    _show_login = (
        empty_state,
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        _keep, _keep,
    )

    try:
        if not saved_state or not isinstance(saved_state, dict) or not saved_state.get("logged_in"):
            return _show_login

        user_name = saved_state.get("user_name", "")
        api_key = saved_state.get("api_key", "")
        base_url = (saved_state.get("base_url") or "").strip().rstrip("/")
        model = str(saved_state.get("model") or "").strip()

        if not user_name:
            return _show_login

        updates: dict[str, str] = {}
        if api_key:
            updates["LLM_API_KEY"] = api_key
        if base_url:
            updates["LLM_BASE_URL"] = base_url
        if model:
            updates["LLM_MODEL"] = model

        if updates:
            try:
                update_env_file(updates)
                reload_settings()
            except Exception:
                pass

        state = {
            "logged_in": True,
            "user_name": user_name,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }

        from app.db.crud import SysConfigCRUD

        try:
            agreed = SysConfigCRUD.get("agreement_accepted", user_name=user_name) == "true"
        except Exception:
            agreed = False

        settings = get_settings()
        header = build_header_html(user_name, settings.APP_VERSION)
        safe_name = html_mod.escape(user_name)
        user_label = f'<span class="logout-user-label">当前用户: {safe_name}</span>'

        logger.info("会话恢复: user=%s, agreed=%s", user_name, agreed)

        if agreed:
            return (
                state,
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
                header,
                user_label,
            )

        return (
            state,
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            header,
            user_label,
        )
    except Exception as e:
        logger.error("会话恢复失败: %s", e)
        return _show_login
