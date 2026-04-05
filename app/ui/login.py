"""登录页面模块

双栏分屏登录页 — 左侧品牌展示 + 右侧登录表单。
参考 BOSS 直聘登录页设计, 适配项目蓝色主题。
DeepSeek API Key 实时校验 + 姓名标识。
全局登录状态管理 + 退出登录。
用户名仅允许英文字母 (拼音格式), 用于数据隔离。
"""

from __future__ import annotations

import html as html_mod
import re

import gradio as gr

from app.core.config import get_settings, reload_settings, update_env_file
from app.core.logger import get_logger
from app.utils.auth_util import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    validate_deepseek_api_key,
)

logger = get_logger(__name__)

_USERNAME_RE = re.compile(r"^[a-zA-Z]+$")


# fmt: off
LOGIN_CSS = """
/* ============ Login Page — Split Layout ============ */

#login-panel {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 100vh !important;
    background: linear-gradient(135deg, #0B1426 0%, #0F1E3D 30%, #162D58 60%, #1B3A6E 100%) !important;
    padding: 24px !important;
    position: relative !important;
    overflow: hidden !important;
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
    background: transparent !important;
    border: none !important;
    animation: scaleIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    position: relative !important;
    z-index: 1 !important;
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
}
.feature-item {
    display: flex; align-items: center; gap: 14px;
    padding: 14px 16px;
    background: rgba(255,255,255,0.1);
    border-radius: 12px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.3s;
}
.feature-item:hover {
    background: rgba(255,255,255,0.18);
    transform: translateX(4px);
}
.feature-icon {
    font-size: 26px; flex-shrink: 0;
    width: 36px; text-align: center;
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

/* ============ Logout Row ============ */
#logout-row {
    background: linear-gradient(135deg, #FFFFFF 0%, #FAFBFC 100%) !important;
    border-bottom: 1px solid rgba(0,0,0,0.04) !important;
    padding: 0 28px !important;
    min-height: 40px !important;
    max-height: 40px !important;
    gap: 12px !important;
    align-items: center !important;
    justify-content: flex-end !important;
    margin: 0 !important;
    overflow: hidden !important;
}
#logout-row > div {
    flex: none !important;
    min-height: 0 !important;
    padding: 0 !important;
}
#logout-row .wrap[data-testid="status-tracker"] {
    display: none !important;
}
.logout-user-label {
    font-size: 13px; color: var(--c-text-3);
    text-align: right; line-height: 40px;
    font-weight: 450;
}
#logout-btn {
    height: 28px !important; min-height: 28px !important;
    line-height: 28px !important; padding: 0 16px !important;
    font-size: 12px !important; border-radius: 6px !important;
    min-width: auto !important; max-width: 80px !important;
    font-weight: 500 !important;
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


def build_header_html(user_name: str, version: str) -> str:
    """构建顶部通栏 HTML"""
    safe_name = html_mod.escape(user_name) if user_name else ""
    user_span = (
        f'<span style="font-size:13px;color:#4E5969;font-weight:500;">'
        f'\U0001F464 {safe_name}</span>'
        if safe_name
        else ""
    )
    return (
        '<div class="app-header-bar">'
        '<div class="hl">'
        '<span class="logo-text">AI求职智能管家</span>'
        '<span class="hd"></span>'
        '<span class="bc">智能求职辅助平台</span>'
        "</div>"
        '<div class="hr">'
        f'<span class="ver">V{version}</span>'
        f"{user_span}"
        "</div>"
        "</div>"
    )


def handle_login(user_name: str, api_key: str) -> tuple:
    """处理登录请求

    Returns:
        8-tuple matching _login_outputs:
            login_state, browser_state,
            login_panel, agreement_panel, main_panel,
            login_error, header_html, user_label_html
    """
    _keep = gr.skip()
    _empty_browser = {"logged_in": False, "user_name": "", "api_key": ""}

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

    result = validate_deepseek_api_key(api_key)

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
        update_env_file({
            "LLM_API_KEY": api_key,
            "LLM_BASE_URL": DEEPSEEK_BASE_URL,
            "LLM_MODEL": DEEPSEEK_MODEL,
        })
        reload_settings()
        logger.info("用户 [%s] 登录成功, DeepSeek 配置已更新", user_name)
    except Exception as e:
        logger.error("登录后保存配置失败: %s", e)

    state = {"logged_in": True, "user_name": user_name, "api_key": api_key}
    browser_data = {"logged_in": True, "user_name": user_name, "api_key": api_key}

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
            gr.Column(visible=False),
            gr.Column(visible=False),
            gr.Column(visible=True),
            "",
            header,
            user_label,
        )

    return (
        state, browser_data,
        gr.Column(visible=False),
        gr.Column(visible=True),
        gr.Column(visible=False),
        "",
        header,
        user_label,
    )


def handle_logout() -> tuple:
    """退出登录, 清空会话状态

    Returns:
        8-tuple matching logout outputs:
            login_state, browser_state,
            login_panel, agreement_panel, main_panel,
            login_name, login_key, login_error
    """
    logger.info("用户退出登录")
    empty = {"logged_in": False, "user_name": "", "api_key": ""}
    return (
        empty,
        empty,
        gr.Column(visible=True),
        gr.Column(visible=False),
        gr.Column(visible=False),
        "",
        "",
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
    empty_state = {"logged_in": False, "user_name": "", "api_key": ""}

    if not saved_state or not isinstance(saved_state, dict) or not saved_state.get("logged_in"):
        return (
            empty_state,
            gr.Column(visible=True),
            gr.Column(visible=False),
            gr.Column(visible=False),
            _keep, _keep,
        )

    user_name = saved_state.get("user_name", "")
    api_key = saved_state.get("api_key", "")

    if not user_name:
        return (
            empty_state,
            gr.Column(visible=True),
            gr.Column(visible=False),
            gr.Column(visible=False),
            _keep, _keep,
        )

    if api_key:
        try:
            update_env_file({"LLM_API_KEY": api_key})
            reload_settings()
        except Exception:
            pass

    state = {"logged_in": True, "user_name": user_name, "api_key": api_key}

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
            state,
            gr.Column(visible=False),
            gr.Column(visible=False),
            gr.Column(visible=True),
            header,
            user_label,
        )

    return (
        state,
        gr.Column(visible=False),
        gr.Column(visible=True),
        gr.Column(visible=False),
        header,
        user_label,
    )
