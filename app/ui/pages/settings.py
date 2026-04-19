"""系统设置页面 — Bento 玻璃拟态风

布局:
┌─ 页头: 图标 + 标题 + 副标题
├─ 操作结果状态条
├─ 分类 Tabs: 投递风控 / 大模型 API / 数据与隐私 / 用户协议 / 关于
│   每个 Tab 内容包在 Bento 卡片里, 配套图标 / 颜色 / 说明
└─ 底部: 操作按钮

对外接口保持: create_settings_page()
"""

from __future__ import annotations

import html as html_mod

import gradio as gr

from app.core.config import get_settings, reload_settings, update_env_file
from app.core.logger import get_logger
from app.utils.security_util import wipe_all_data

logger = get_logger(__name__)


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


_USER_AGREEMENT_MARKDOWN = """## 用户使用须知

1. 本工具仅为个人求职辅助工具, 不代表任何招聘平台官方。
2. 用户需严格遵守招聘平台用户协议, 不得违反平台规定。
3. 因用户操作不当、违反平台规则导致的任何损失, 本工具不承担责任。
4. 禁止用于商业代投、批量恶意投递。
5. 用户需自行保管个人简历、账号信息, 因用户自身泄露导致的风险自行承担。

## 免责声明

1. 本工具仅提供技术辅助, 不保证投递成功、不保证账号不被风控。
2. 因平台策略调整导致功能失效属正常现象, 本工具将逐步适配。
3. 本工具仅本地存储用户数据, 不保证数据绝对安全, 用户需定期备份。
4. 因设备故障、误操作导致的数据丢失, 本工具不承担责任。
5. 所有投递行为由用户发起并确认, 求职结果由用户自身条件和招聘方决定。
"""


# ------------------------------------------------------------------
# HTML renderers
# ------------------------------------------------------------------

def _render_header_html() -> str:
    return (
        '<div class="st-root">'
        '  <div class="st-head">'
        '    <div class="st-head-icon">'
        '      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <circle cx="12" cy="12" r="3"></circle>'
        '        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>'
        '      </svg>'
        '    </div>'
        '    <div class="st-head-text">'
        '      <div class="st-head-title">系统设置</div>'
        '      <div class="st-head-sub">风控参数 · 大模型配置 · 数据管理 · 用户协议</div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _status_html(msg: str, kind: str = "info") -> str:
    dot_cls = {"info": "sts-blue", "err": "sts-red", "ok": "sts-green", "warn": "sts-orange"}.get(kind, "sts-blue")
    icon_svg = ""
    extra_cls = ""
    if kind == "ok":
        extra_cls = " st-status-ok"
        icon_svg = (
            '<span class="sts-icon sts-icon-ok">'
            '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="20 6 9 17 4 12"></polyline>'
            '</svg></span>'
        )
    elif kind == "err":
        extra_cls = " st-status-err"
        icon_svg = (
            '<span class="sts-icon sts-icon-err">'
            '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
            '<line x1="6" y1="6" x2="18" y2="18"></line>'
            '<line x1="6" y1="18" x2="18" y2="6"></line>'
            '</svg></span>'
        )
    elif kind == "warn":
        extra_cls = " st-status-warn"
        icon_svg = (
            '<span class="sts-icon sts-icon-warn">'
            '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>'
            '<line x1="12" y1="9" x2="12" y2="13"></line>'
            '<line x1="12" y1="17" x2="12.01" y2="17"></line>'
            '</svg></span>'
        )
    return (
        '<div class="st-root">'
        f'  <div class="st-status{extra_cls}">'
        f'    {icon_svg if icon_svg else f"<span class=\"sts-dot {dot_cls}\"></span>"}'
        f'    <span class="sts-txt">{_safe(msg)}</span>'
        '  </div>'
        '</div>'
    )


def _status_loading_html(msg: str) -> str:
    """加载态: 旋转 spinner + 文案."""
    return (
        '<div class="st-root">'
        '  <div class="st-status st-status-loading">'
        '    <span class="sts-spinner" aria-label="loading">'
        '      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
        '        <path d="M21 12a9 9 0 1 1-9-9" stroke-dasharray="40" stroke-dashoffset="0"></path>'
        '      </svg>'
        '    </span>'
        f'    <span class="sts-txt">{_safe(msg)}</span>'
        '  </div>'
        '</div>'
    )


def _empty_status_html() -> str:
    """初始隐藏状态条, 不显示空圈; 实际操作后再显示反馈."""
    return '<div class="st-root st-status-hidden" aria-hidden="true"></div>'


def _render_card_head(icon_cls: str, icon_svg: str, title: str, sub: str) -> str:
    return (
        '<div class="st-card-head" style="position:relative;z-index:3;">'
        f'  <div class="st-ch-icon {icon_cls}">{icon_svg}</div>'
        f'  <div class="st-ch-title" style="font-size:16px;font-weight:700;color:#F0F2FA;flex:1;line-height:1.4;">{_safe(title)}</div>'
        f'  <div class="st-ch-sub" style="font-size:12px;color:rgba(230,233,245,0.7);line-height:1.4;">{_safe(sub)}</div>'
        '</div>'
    )


def _render_tip_html(kind: str, title: str, body: str) -> str:
    palette = {
        "info": "st-tip-blue",
        "ok": "st-tip-green",
        "warn": "st-tip-orange",
        "err": "st-tip-red",
    }
    cls = palette.get(kind, "st-tip-blue")
    return (
        '<div class="st-root">'
        f'  <div class="st-tip {cls}">'
        f'    <div class="st-tip-title">{_safe(title)}</div>'
        f'    <div class="st-tip-body">{body}</div>'
        '  </div>'
        '</div>'
    )


def _render_danger_html() -> str:
    return (
        '<div class="st-root">'
        '  <div class="st-danger">'
        '    <div class="st-danger-icon">'
        '      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>'
        '        <line x1="12" y1="9" x2="12" y2="13"></line>'
        '        <line x1="12" y1="17" x2="12.01" y2="17"></line>'
        '      </svg>'
        '    </div>'
        '    <div class="st-danger-text">'
        '      <div class="st-danger-title">一键清理所有本地数据</div>'
        '      <div class="st-danger-body">'
        '        该操作将删除所有简历、投递记录、Cookie, <b>不可恢复</b>. '
        '        操作前建议先导出重要数据.'
        '      </div>'
        '    </div>'
        '  </div>'
        '</div>'
    )


def _render_about_html(app_name: str, app_version: str) -> str:
    chips_html = (
        '<span class="st-chip st-chip-blue">Python 3.11</span>'
        '<span class="st-chip st-chip-violet">LangGraph</span>'
        '<span class="st-chip st-chip-green">Playwright</span>'
        '<span class="st-chip st-chip-pink">Gradio</span>'
    )
    features = [
        ("安全合规", "严格遵守平台规则, 不触发账号风控"),
        ("AI 智能优化", "多智能体协作, 简历 JD 智能匹配"),
        ("全流程可控", "从搜索到投递每一步用户确认"),
        ("隐私本地化", "所有数据本地存储, 零云端依赖"),
    ]
    feat_html = "".join(
        '<div class="st-feat-row">'
        f'  <div class="st-feat-dot"></div>'
        f'  <div class="st-feat-k">{_safe(k)}</div>'
        f'  <div class="st-feat-v">{_safe(v)}</div>'
        '</div>'
        for k, v in features
    )
    return (
        '<div class="st-root">'
        '  <div class="st-about">'
        '    <div class="st-about-hero">'
        '      <div class="st-about-logo">'
        '        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>'
        '          <path d="M7 8h.01"></path>'
        '          <path d="M11 8h6"></path>'
        '          <path d="M7 12h.01"></path>'
        '          <path d="M11 12h6"></path>'
        '          <path d="M7 16h.01"></path>'
        '          <path d="M11 16h6"></path>'
        '        </svg>'
        '      </div>'
        '      <div class="st-about-meta">'
        f'        <div class="st-about-name">{_safe(app_name)}</div>'
        f'        <div class="st-about-ver">Version {_safe(app_version)}</div>'
        f'        <div class="st-about-chips">{chips_html}</div>'
        '      </div>'
        '    </div>'
        '    <div class="st-about-tagline">'
        '      AI 求职管家 · 安全不封号, 精准拿面试'
        '    </div>'
        f'    <div class="st-about-feats">{feat_html}</div>'
        '  </div>'
        '</div>'
    )


# ------------------------------------------------------------------
# Business logic (签名保持)
# ------------------------------------------------------------------

def _load_settings():
    """加载当前设置"""
    try:
        settings = get_settings()
        return (
            settings.MAX_DAILY_DELIVERY,
            settings.MIN_DELAY_SECONDS,
            settings.MAX_DELAY_SECONDS,
            settings.DELIVERY_START_HOUR,
            settings.DELIVERY_END_HOUR,
            settings.MATCH_THRESHOLD,
            settings.LLM_API_KEY[:8] + "..." if len(settings.LLM_API_KEY) > 8 else settings.LLM_API_KEY,
            settings.LLM_BASE_URL,
            settings.LLM_MODEL,
        )
    except Exception:
        return 20, 2, 4, 9, 18, 70, "", "", ""


def _save_risk_settings(max_daily, min_delay, max_delay, start_hour, end_hour, threshold):
    """保存风控设置到 .env 并热更新"""
    try:
        min_delay, max_delay = int(min_delay), int(max_delay)
        start_hour, end_hour = int(start_hour), int(end_hour)
        if min_delay > max_delay:
            yield _status_html(
                f"保存失败: 最小延时 ({min_delay}s) 不能大于最大延时 ({max_delay}s)",
                "err",
            )
            return
        if start_hour >= end_hour:
            yield _status_html(
                f"保存失败: 开始时段 ({start_hour}:00) 必须早于结束时段 ({end_hour}:00)",
                "err",
            )
            return
        yield _status_loading_html("正在写入 .env 并热更新风控参数…")
        update_env_file({
            "MAX_DAILY_DELIVERY": str(int(max_daily)),
            "MIN_DELAY_SECONDS": str(int(min_delay)),
            "MAX_DELAY_SECONDS": str(int(max_delay)),
            "DELIVERY_START_HOUR": str(int(start_hour)),
            "DELIVERY_END_HOUR": str(int(end_hour)),
            "MATCH_THRESHOLD": str(int(threshold)),
        })
        reload_settings()
        logger.info("风控设置已保存")
        yield _status_html("风控设置保存成功", "ok")
    except Exception as e:
        yield _status_html(f"保存失败: {e}", "err")


def _save_api_settings(api_key, base_url, model):
    """保存 API 设置到 .env 并热更新 (含 API Key 校验)

    使用 generator 提供 "校验中…" loading 态, 然后给出最终成功 ✓ / 失败 ✗ 反馈.
    UI 端将自动展示 saving 时按钮 disabled + 顶部 spinner.
    """
    if not api_key or not api_key.strip():
        yield _status_html("保存失败: API Key 不能为空", "err"), gr.update(interactive=True)
        return
    yield _status_loading_html(f"正在校验 API Key 并保存配置… (model={model})"), gr.update(interactive=False)
    try:
        from app.utils.auth_util import validate_api_key
        result = validate_api_key(api_key.strip(), base_url=base_url, model=model)
        if not result.success:
            yield _status_html(f"保存失败: {result.message}", "err"), gr.update(interactive=True)
            return
        update_env_file({
            "LLM_API_KEY": api_key.strip(),
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model,
        })
        reload_settings()
        logger.info("API 设置已保存 (校验通过)")
        yield _status_html("API 配置校验通过并保存成功, 已立即生效", "ok"), gr.update(interactive=True)
    except Exception as e:
        yield _status_html(f"保存失败: {e}", "err"), gr.update(interactive=True)


def _do_wipe(confirm_text: str, confirm_check: bool):
    """清除所有数据 — 双重确认 (勾选 + 输入验证文本)."""
    expected = "DELETE"
    if not confirm_check:
        yield _status_html(
            "请先勾选 \"我已了解清除数据不可恢复\" 再操作",
            "warn",
        )
        return
    if (confirm_text or "").strip() != expected:
        yield _status_html(
            f"二次确认失败: 请在输入框中输入 {expected} (区分大小写) 以确认",
            "warn",
        )
        return
    yield _status_loading_html("正在清除本地数据 (数据库、Cookie、日志)…")
    try:
        ok = wipe_all_data()
        if ok:
            yield _status_html("所有本地数据已清除 (不可恢复)", "ok")
            return
        yield _status_html("数据清除失败", "err")
    except Exception as e:
        logger.error("数据清除异常: %s", e)
        yield _status_html(f"数据清除失败: {e}", "err")


# ------------------------------------------------------------------
# Page builder
# ------------------------------------------------------------------

def create_settings_page():
    """创建系统设置页面 (Bento 玻璃风)"""
    settings = get_settings()
    gr.HTML(_ST_STYLE)

    with gr.Column(elem_id="st-page-root", elem_classes=["st-scope"]):
        gr.HTML(_render_header_html())

        settings_msg = gr.HTML(value=_empty_status_html(), elem_id="st-status-slot")

        with gr.Tabs(elem_id="settings-tabs", elem_classes=["st-tabs"]):

            # ============ 投递风控 ============
            with gr.Tab("投递风控"):
                with gr.Column(elem_classes=["st-card", "st-card-risk"]):
                    gr.HTML(_render_card_head(
                        "st-ch-blue",
                        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>'
                        '</svg>',
                        "投递风控参数",
                        "日投递上限 · 延时抖动 · 时段 · 匹配阈值",
                    ))
                    gr.HTML(_render_tip_html(
                        "info",
                        "为什么要做风控?",
                        "招聘平台会针对短时间密集投递触发风控. "
                        "下列参数共同组成 <b>拟人节奏</b>, 可显著降低封号概率.",
                    ))

                    max_daily = gr.Slider(
                        1, 50, value=settings.MAX_DAILY_DELIVERY,
                        step=1, label="每日最大投递量",
                        elem_classes=["st-slider"],
                    )
                    with gr.Row(elem_classes=["st-slider-row"]):
                        min_delay = gr.Slider(
                            1, 10, value=settings.MIN_DELAY_SECONDS,
                            step=1, label="最小延时 (秒)",
                            elem_classes=["st-slider", "st-slider-half"],
                        )
                        gr.HTML(
                            '<div class="st-slider-spacer" aria-hidden="true"></div>',
                            elem_classes=["st-slider-gap"],
                        )
                        max_delay = gr.Slider(
                            1, 10, value=settings.MAX_DELAY_SECONDS,
                            step=1, label="最大延时 (秒)",
                            elem_classes=["st-slider", "st-slider-half"],
                        )
                    with gr.Row(elem_classes=["st-slider-row"]):
                        start_hour = gr.Slider(
                            0, 23, value=settings.DELIVERY_START_HOUR,
                            step=1, label="投递开始时段",
                            elem_classes=["st-slider", "st-slider-half"],
                        )
                        gr.HTML(
                            '<div class="st-slider-spacer" aria-hidden="true"></div>',
                            elem_classes=["st-slider-gap"],
                        )
                        end_hour = gr.Slider(
                            1, 24, value=settings.DELIVERY_END_HOUR,
                            step=1, label="投递结束时段",
                            elem_classes=["st-slider", "st-slider-half"],
                        )
                    threshold = gr.Slider(
                        0, 100, value=settings.MATCH_THRESHOLD,
                        step=5, label="最低匹配分数阈值",
                        elem_classes=["st-slider"],
                    )

                    save_risk_btn = gr.Button(
                        "保存风控设置", variant="primary",
                        elem_classes=["st-btn", "st-btn-primary"],
                    )
                    save_risk_btn.click(
                        fn=_save_risk_settings,
                        inputs=[max_daily, min_delay, max_delay, start_hour, end_hour, threshold],
                        outputs=[settings_msg],
                    )

            # ============ 大模型 API ============
            with gr.Tab("大模型 API"):
                with gr.Column(elem_classes=["st-card", "st-card-api"]):
                    gr.HTML(_render_card_head(
                        "st-ch-violet",
                        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>'
                        '<line x1="3" y1="9" x2="21" y2="9"></line>'
                        '<line x1="9" y1="21" x2="9" y2="9"></line>'
                        '</svg>',
                        "大模型配置",
                        "支持 OpenAI / DeepSeek / 通义千问 等兼容 OpenAI 格式的服务",
                    ))

                    api_key = gr.Textbox(
                        label="API Key",
                        type="password",
                        value=settings.LLM_API_KEY,
                        placeholder="sk-...",
                        elem_classes=["st-input-field"],
                    )
                    base_url = gr.Textbox(
                        label="API Base URL",
                        value=settings.LLM_BASE_URL,
                        placeholder="https://api.openai.com/v1",
                        elem_classes=["st-input-field"],
                    )
                    model = gr.Dropdown(
                        label="模型名称",
                        choices=[
                            "deepseek-chat", "deepseek-reasoner",
                            "gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo",
                            "qwen-plus", "qwen-turbo", "qwen-max",
                            "glm-4", "glm-4-flash",
                        ],
                        value=settings.LLM_MODEL,
                        allow_custom_value=True,
                        elem_classes=["st-input-field"],
                    )
                    save_api_btn = gr.Button(
                        "保存 API 配置 (含校验)", variant="primary",
                        elem_classes=["st-btn", "st-btn-primary", "st-btn-api-save"],
                    )
                    save_api_btn.click(
                        fn=_save_api_settings,
                        inputs=[api_key, base_url, model],
                        outputs=[settings_msg, save_api_btn],
                    )
                    gr.HTML(_render_tip_html(
                        "ok",
                        "API 密钥安全",
                        "密钥仅保存在本地 <code>.env</code> 文件, "
                        "不上传任何云端. 保存前会发请求做 1 次连通性校验.",
                    ))

            # ============ 数据与隐私 ============
            with gr.Tab("数据与隐私"):
                with gr.Column(elem_classes=["st-card", "st-card-privacy"]):
                    gr.HTML(_render_card_head(
                        "st-ch-green",
                        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>'
                        '<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>'
                        '</svg>',
                        "数据与隐私",
                        "所有数据仅本地存储 · 零云端依赖",
                    ))

                    gr.HTML(_render_tip_html(
                        "ok",
                        "本地优先",
                        "简历、投递记录、Cookie 均保存在本机 <code>data/</code> 目录, "
                        "不会上传任何云端服务器.",
                    ))

                    gr.HTML(_render_danger_html())
                    with gr.Column(elem_classes=["st-confirm-block"]):
                        wipe_check = gr.Checkbox(
                            label="我已了解: 清除后所有简历 / 投递记录 / Cookie 不可恢复",
                            value=False,
                            elem_classes=["st-confirm-check"],
                        )
                        wipe_text = gr.Textbox(
                            label="二次确认: 请输入 DELETE (区分大小写) 以解锁清除按钮",
                            placeholder="DELETE",
                            value="",
                            elem_classes=["st-input-field", "st-confirm-text"],
                        )
                        wipe_btn = gr.Button(
                            "一键清理所有数据", variant="stop",
                            elem_classes=["st-btn", "st-btn-danger"],
                            interactive=False,
                        )

                        def _toggle_wipe(text: str, checked: bool):
                            ok = bool(checked) and (text or "").strip() == "DELETE"
                            return gr.update(interactive=ok)

                        wipe_check.change(fn=_toggle_wipe, inputs=[wipe_text, wipe_check], outputs=[wipe_btn])
                        wipe_text.change(fn=_toggle_wipe, inputs=[wipe_text, wipe_check], outputs=[wipe_btn])
                        wipe_btn.click(
                            fn=_do_wipe,
                            inputs=[wipe_text, wipe_check],
                            outputs=[settings_msg],
                        )

            # ============ 用户协议 ============
            with gr.Tab("用户协议"):
                with gr.Column(elem_classes=["st-card", "st-card-agreement"]):
                    gr.HTML(_render_card_head(
                        "st-ch-pink",
                        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>'
                        '<polyline points="14 2 14 8 20 8"></polyline>'
                        '</svg>',
                        "用户使用须知 & 免责声明",
                        "使用前请仔细阅读",
                    ))
                    gr.Markdown(_USER_AGREEMENT_MARKDOWN, elem_classes=["st-agreement-md"])

            # ============ 关于 ============
            with gr.Tab("关于"):
                with gr.Column(elem_classes=["st-card", "st-card-about"]):
                    gr.HTML(_render_card_head(
                        "st-ch-orange",
                        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                        '<circle cx="12" cy="12" r="10"></circle>'
                        '<line x1="12" y1="16" x2="12" y2="12"></line>'
                        '<line x1="12" y1="8" x2="12.01" y2="8"></line>'
                        '</svg>',
                        "关于本应用",
                        f"{settings.APP_NAME} · v{settings.APP_VERSION}",
                    ))
                    gr.HTML(_render_about_html(settings.APP_NAME, settings.APP_VERSION))


# ================================================================
# 作用域 CSS (限定在 .st-scope / .st-root 下)
# ================================================================
# fmt: off
_ST_STYLE = """
<style>
/* =========================================================
   Settings Page — Bento 玻璃拟态风
   ========================================================= */
.st-scope { color: var(--c-text-1); }
.st-scope *, .st-root * { box-sizing: border-box; }
#st-page-root {
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 16px !important;
}
#st-page-root > .block:first-child,
#st-page-root > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }

/* 页头 */
.st-root .st-head {
    display: flex; align-items: center; gap: 14px;
    margin: -10px 0 4px;
}
.st-root .st-head-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(56,189,248,0.28), rgba(79,139,255,0.22));
    border: 1px solid rgba(56,189,248,0.35);
    display: flex; align-items: center; justify-content: center;
    color: #7DD3FC;
    box-shadow: 0 8px 20px rgba(56,189,248,0.22), inset 0 1px 0 rgba(255,255,255,0.08);
}
.st-root .st-head-title { font-size: 22px; font-weight: 700; color: #F0F2FA; }
.st-root .st-head-sub { font-size: 13px; color: rgba(230,233,245,0.6); margin-top: 2px; }

/* Tabs 样式 */
.st-scope .st-tabs {
    position: relative;
    background: transparent !important;
    padding: 0 !important;
}
.st-scope .st-tabs .tab-nav {
    background: rgba(17,22,48,0.35) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important;
    padding: 6px !important;
    gap: 4px !important;
    margin-bottom: 14px !important;
    display: flex !important; flex-wrap: wrap !important;
    backdrop-filter: blur(16px) saturate(130%);
}
.st-scope .st-tabs .tab-nav > button {
    background: transparent !important;
    color: rgba(230,233,245,0.65) !important;
    border: 1px solid transparent !important;
    padding: 9px 16px !important;
    border-radius: 10px !important;
    font-size: 13px !important; font-weight: 600 !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.3px;
}
.st-scope .st-tabs .tab-nav > button:hover {
    background: rgba(79,139,255,0.10) !important;
    color: #AFC7FF !important;
}
.st-scope .st-tabs .tab-nav > button.selected {
    background: linear-gradient(135deg, rgba(79,139,255,0.24), rgba(121,90,255,0.18)) !important;
    color: #F0F2FA !important;
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 4px 14px rgba(79,139,255,0.22), inset 0 1px 0 rgba(255,255,255,0.12) !important;
}
.st-scope .st-tabs > .tabitem {
    padding: 0 !important;
    background: transparent !important;
}

/* 通用卡片 */
.st-scope .st-card {
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
    gap: 14px !important;
    display: flex !important;
    flex-direction: column !important;
    transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease,
                border-color 0.28s ease !important;
    will-change: transform;
}
.st-scope .st-card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(255,255,255,0.16) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 22px 50px rgba(0,0,0,0.5),
        0 6px 18px rgba(79,139,255,0.12) !important;
}
.st-scope .st-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
    pointer-events: none;
}
.st-scope .st-card > * { position: relative; z-index: 1; }

/* 卡头 */
.st-root .st-card-head {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
    position: relative;
    z-index: 2;
}
.st-root .st-ch-icon {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.st-root .st-ch-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.28), rgba(121,90,255,0.20));
    color: #AFC7FF;
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 4px 14px rgba(79,139,255,0.22);
}
.st-root .st-ch-violet {
    background: linear-gradient(135deg, rgba(167,139,250,0.28), rgba(244,114,182,0.22));
    color: #DDD6FE;
    border: 1px solid rgba(167,139,250,0.35);
    box-shadow: 0 4px 14px rgba(167,139,250,0.22);
}
.st-root .st-ch-green {
    background: linear-gradient(135deg, rgba(52,211,153,0.28), rgba(79,139,255,0.22));
    color: #6EE7B7;
    border: 1px solid rgba(52,211,153,0.35);
    box-shadow: 0 4px 14px rgba(52,211,153,0.22);
}
.st-root .st-ch-pink {
    background: linear-gradient(135deg, rgba(244,114,182,0.28), rgba(251,146,60,0.22));
    color: #F9A8D4;
    border: 1px solid rgba(244,114,182,0.35);
    box-shadow: 0 4px 14px rgba(244,114,182,0.22);
}
.st-root .st-ch-orange {
    background: linear-gradient(135deg, rgba(251,146,60,0.28), rgba(253,224,71,0.22));
    color: #FDBA74;
    border: 1px solid rgba(251,146,60,0.35);
    box-shadow: 0 4px 14px rgba(251,146,60,0.22);
}
.st-root .st-ch-title { font-size: 16px; font-weight: 700; color: #F0F2FA !important; flex: 1; text-shadow: 0 1px 2px rgba(0,0,0,0.4); }
.st-root .st-ch-sub { font-size: 12px; color: rgba(230,233,245,0.65) !important; }

/* 输入字段 */
.st-scope .st-input-field textarea,
.st-scope .st-input-field input,
.st-scope .st-input-field .wrap-inner {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F0F2FA !important;
    border-radius: 12px !important;
}
.st-scope .st-input-field textarea:focus,
.st-scope .st-input-field input:focus {
    border-color: rgba(79,139,255,0.45) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.12) !important;
}

/* Sliders: darker track + gradient bar */
.st-scope .st-slider {
    padding: 10px 2px !important;
    margin-bottom: 6px !important;
}
/* 间距 spacer: 在两个 slider 中插入一个固定宽度的空白列, 强制视觉分隔 */
.st-scope .st-slider-gap {
    flex: 0 0 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    padding: 0 !important;
    margin: 0 !important;
    background: transparent !important;
    border: none !important;
}
.st-scope .st-slider-spacer {
    width: 32px;
    height: 100%;
    pointer-events: none;
}
/* 行内的每个 slider 加 padding + 玻璃背景, 柄和数字不会重叠 */
.st-scope .st-slider-half {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    padding: 12px 22px !important;
    background: rgba(17,22,48,0.30) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 14px !important;
    margin-bottom: 0 !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}
.st-scope .st-slider-half:hover {
    background: rgba(17,22,48,0.42) !important;
    border-color: rgba(79,139,255,0.30) !important;
}
.st-scope .st-slider-row {
    align-items: stretch !important;
    padding: 4px 0 12px !important;
}
/* 强制每个 slider 的 min/max 端点数字与 track 之间留出气口 */
.st-scope .st-slider .min,
.st-scope .st-slider .max {
    padding: 0 6px !important;
    color: rgba(230,233,245,0.55) !important;
    font-size: 11px !important;
    font-variant-numeric: tabular-nums;
}
.st-scope .st-slider input[type="range"] {
    accent-color: #4F8BFF !important;
}
/* Slider 标签更大更清晰 */
.st-scope .st-slider label,
.st-scope .st-slider .block-label {
    font-size: 12.5px !important;
    font-weight: 600 !important;
    color: rgba(230,233,245,0.85) !important;
    margin-bottom: 6px !important;
    letter-spacing: 0.3px !important;
}

/* 按钮 */
.st-scope .st-btn,
.st-scope .st-btn button {
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: transform 0.2s ease, box-shadow 0.3s ease, background 0.25s ease !important;
    letter-spacing: 0.3px !important;
    padding: 12px 18px !important;
    font-size: 13.5px !important;
}
.st-scope .st-btn-primary,
.st-scope .st-btn-primary button {
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 100%) !important;
    color: #FFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 8px 20px rgba(79,139,255,0.32), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.st-scope .st-btn-primary:hover,
.st-scope .st-btn-primary button:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(79,139,255,0.45), inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.st-scope .st-btn-danger,
.st-scope .st-btn-danger button {
    background: linear-gradient(135deg, #F87171 0%, #FB923C 100%) !important;
    color: #FFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 8px 20px rgba(248,113,113,0.32), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.st-scope .st-btn-danger:hover,
.st-scope .st-btn-danger button:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(248,113,113,0.45), inset 0 1px 0 rgba(255,255,255,0.22) !important;
}

/* 状态条 */
.st-root .st-status {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    font-size: 12.5px;
    color: rgba(230,233,245,0.85);
    backdrop-filter: blur(10px);
}
.st-root .st-status-empty { color: rgba(230,233,245,0.45); font-style: italic; }
/* 初始未操作状态: 完全收起, 不在视觉上出现空圈 */
.st-root.st-status-hidden { display: none !important; }
#st-status-slot:has(> .st-status-hidden) { display: none !important; }
.st-root .sts-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.st-root .sts-blue   { background: #8DBBFF; box-shadow: 0 0 10px rgba(141,187,255,0.6); }
.st-root .sts-green  { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.6); }
.st-root .sts-red    { background: #F87171; box-shadow: 0 0 10px rgba(248,113,113,0.6); }
.st-root .sts-orange { background: #FB923C; box-shadow: 0 0 10px rgba(251,146,60,0.6); }
.st-root .sts-gray   { background: rgba(200,200,220,0.35); }

/* 反馈图标 (✓ / ✗ / ⚠) */
.st-root .sts-icon {
    width: 22px; height: 22px;
    flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%;
    border: 1px solid currentColor;
}
.st-root .sts-icon-ok {
    color: #34D399;
    background: rgba(52,211,153,0.15);
    box-shadow: 0 0 14px rgba(52,211,153,0.45), inset 0 1px 0 rgba(255,255,255,0.18);
    animation: stsPopIn 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.st-root .sts-icon-err {
    color: #F87171;
    background: rgba(248,113,113,0.15);
    box-shadow: 0 0 14px rgba(248,113,113,0.45), inset 0 1px 0 rgba(255,255,255,0.18);
    animation: stsShake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
.st-root .sts-icon-warn {
    color: #FB923C;
    background: rgba(251,146,60,0.15);
    box-shadow: 0 0 14px rgba(251,146,60,0.42), inset 0 1px 0 rgba(255,255,255,0.18);
}
.st-root .st-status-ok   { border-color: rgba(52,211,153,0.32) !important; background: rgba(52,211,153,0.07) !important; }
.st-root .st-status-err  { border-color: rgba(248,113,113,0.32) !important; background: rgba(248,113,113,0.07) !important; }
.st-root .st-status-warn { border-color: rgba(251,146,60,0.32) !important; background: rgba(251,146,60,0.07) !important; }
.st-root .st-status-loading {
    border-color: rgba(141,187,255,0.30) !important;
    background: rgba(79,139,255,0.07) !important;
    color: #AFC7FF;
}
.st-root .sts-spinner {
    width: 22px; height: 22px;
    flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%;
    color: #AFC7FF;
    background: rgba(79,139,255,0.18);
    border: 1px solid rgba(79,139,255,0.35);
    box-shadow: 0 0 14px rgba(79,139,255,0.42);
}
.st-root .sts-spinner svg { animation: stsSpin 0.9s linear infinite; }
@keyframes stsSpin {
    to { transform: rotate(360deg); }
}
@keyframes stsPopIn {
    0%   { opacity: 0; transform: scale(0.4); }
    60%  { opacity: 1; transform: scale(1.18); }
    100% { opacity: 1; transform: scale(1); }
}
@keyframes stsShake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-3px); }
    40% { transform: translateX(3px); }
    60% { transform: translateX(-2px); }
    80% { transform: translateX(2px); }
}

/* Tip 信息块 */
.st-root .st-tip {
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.7;
}
.st-root .st-tip-title {
    font-weight: 700; font-size: 13.5px; margin-bottom: 4px;
    display: flex; align-items: center; gap: 6px;
}
.st-root .st-tip-body {
    color: rgba(230,233,245,0.85);
    font-size: 12.5px;
}
.st-root .st-tip-body b,
.st-root .st-tip-body strong {
    color: #FFFFFF !important;
    background: linear-gradient(135deg, rgba(79,139,255,0.30), rgba(168,115,245,0.22));
    border: 1px solid rgba(141,187,255,0.40);
    padding: 1px 8px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 12px;
    margin: 0 2px;
    letter-spacing: 0.3px;
    box-shadow: 0 1px 6px rgba(79,139,255,0.22), inset 0 1px 0 rgba(255,255,255,0.10);
    white-space: nowrap;
    display: inline-block;
    vertical-align: 1px;
}
.st-root .st-tip-body code {
    background: rgba(79,139,255,0.14);
    color: #AFC7FF;
    padding: 1px 6px;
    border-radius: 5px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11.5px;
}
.st-root .st-tip-blue {
    background: linear-gradient(135deg, rgba(79,139,255,0.12), rgba(121,90,255,0.08));
    border: 1px solid rgba(79,139,255,0.28);
}
.st-root .st-tip-blue .st-tip-title { color: #AFC7FF; }
.st-root .st-tip-green {
    background: linear-gradient(135deg, rgba(52,211,153,0.12), rgba(79,139,255,0.08));
    border: 1px solid rgba(52,211,153,0.28);
}
.st-root .st-tip-green .st-tip-title { color: #6EE7B7; }
.st-root .st-tip-orange {
    background: linear-gradient(135deg, rgba(251,146,60,0.12), rgba(244,114,182,0.08));
    border: 1px solid rgba(251,146,60,0.28);
}
.st-root .st-tip-orange .st-tip-title { color: #FDBA74; }
.st-root .st-tip-red {
    background: linear-gradient(135deg, rgba(248,113,113,0.14), rgba(244,114,182,0.08));
    border: 1px solid rgba(248,113,113,0.32);
}
.st-root .st-tip-red .st-tip-title { color: #FCA5A5; }

/* Danger 警告块 */
.st-root .st-danger {
    display: grid;
    grid-template-columns: 48px 1fr;
    gap: 14px;
    align-items: flex-start;
    padding: 16px 18px;
    background: linear-gradient(135deg, rgba(248,113,113,0.10), rgba(251,146,60,0.06));
    border: 1px solid rgba(248,113,113,0.30);
    border-radius: 14px;
}
.st-root .st-danger-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: rgba(248,113,113,0.18);
    color: #FCA5A5;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid rgba(248,113,113,0.32);
    box-shadow: 0 4px 14px rgba(248,113,113,0.22);
}
.st-root .st-danger-title {
    font-size: 14px; font-weight: 700; color: #FCA5A5;
    margin-bottom: 4px;
}
.st-root .st-danger-body {
    font-size: 12.5px; color: rgba(230,233,245,0.75);
    line-height: 1.7;
}
.st-root .st-danger-body b { color: #FCA5A5; font-weight: 700; }

/* 双重确认块: 包裹 checkbox + 输入 + 危险按钮, 显示 "高警觉" 红色边框 */
.st-scope .st-confirm-block {
    margin-top: 14px !important;
    padding: 16px 18px !important;
    border: 1px dashed rgba(248,113,113,0.36) !important;
    border-radius: 14px !important;
    background: rgba(248,113,113,0.05) !important;
    display: flex !important; flex-direction: column !important; gap: 12px !important;
}
.st-scope .st-confirm-block .st-confirm-check label {
    color: #FED4D4 !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
}
.st-scope .st-confirm-block .st-confirm-text input {
    border: 1px solid rgba(248,113,113,0.32) !important;
    background: rgba(248,113,113,0.08) !important;
    color: #FFE4E4 !important;
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase;
}
.st-scope .st-confirm-block .st-confirm-text input::placeholder {
    color: rgba(252,164,164,0.45) !important;
}
.st-scope .st-confirm-block .st-confirm-text input:focus {
    border-color: #F87171 !important;
    box-shadow: 0 0 0 3px rgba(248,113,113,0.18) !important;
}
.st-scope .st-confirm-block .st-btn-danger[disabled],
.st-scope .st-confirm-block .st-btn-danger button[disabled] {
    opacity: 0.4 !important;
    cursor: not-allowed !important;
    filter: grayscale(0.4);
}

/* 用户协议 Markdown 美化 */
.st-scope .st-agreement-md {
    padding: 8px 4px;
}
.st-scope .st-agreement-md h2 {
    color: #F0F2FA !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    margin: 18px 0 10px 0 !important;
    padding: 0 0 6px 0 !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    display: flex; align-items: center; gap: 8px;
}
.st-scope .st-agreement-md h2::before {
    content: ''; width: 3px; height: 14px;
    background: linear-gradient(180deg, #4F8BFF, #795AFF);
    border-radius: 2px;
}
.st-scope .st-agreement-md ol,
.st-scope .st-agreement-md ul {
    padding-left: 22px !important;
    margin: 6px 0 !important;
}
.st-scope .st-agreement-md li {
    font-size: 13px !important;
    color: rgba(230,233,245,0.75) !important;
    line-height: 1.85 !important;
    margin-bottom: 4px !important;
}

/* 关于页 */
.st-root .st-about {
    display: flex; flex-direction: column; gap: 16px;
}
.st-root .st-about-hero {
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 16px; align-items: center;
    padding: 14px;
    background: rgba(17,22,48,0.35);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
}
.st-root .st-about-logo {
    width: 64px; height: 64px; border-radius: 16px;
    background: linear-gradient(135deg, #4F8BFF 0%, #795AFF 50%, #F472B6 100%);
    color: #FFF;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 10px 24px rgba(79,139,255,0.32), inset 0 1px 0 rgba(255,255,255,0.22);
}
.st-root .st-about-name {
    font-size: 18px; font-weight: 800; color: #F0F2FA;
    letter-spacing: -0.3px;
}
.st-root .st-about-ver {
    font-size: 12.5px; color: rgba(230,233,245,0.55);
    margin-top: 2px;
}
.st-root .st-about-chips {
    display: flex; gap: 6px; flex-wrap: wrap;
    margin-top: 8px;
}
.st-root .st-chip {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid transparent;
}
.st-root .st-chip-blue {
    background: rgba(79,139,255,0.14); color: #AFC7FF;
    border-color: rgba(79,139,255,0.28);
}
.st-root .st-chip-violet {
    background: rgba(167,139,250,0.14); color: #DDD6FE;
    border-color: rgba(167,139,250,0.28);
}
.st-root .st-chip-green {
    background: rgba(52,211,153,0.14); color: #6EE7B7;
    border-color: rgba(52,211,153,0.28);
}
.st-root .st-chip-pink {
    background: rgba(244,114,182,0.14); color: #F9A8D4;
    border-color: rgba(244,114,182,0.28);
}
.st-root .st-about-tagline {
    padding: 12px 16px;
    text-align: center;
    background: linear-gradient(135deg, rgba(79,139,255,0.12), rgba(121,90,255,0.08));
    border: 1px solid rgba(79,139,255,0.25);
    border-radius: 12px;
    color: #AFC7FF;
    font-size: 14px; font-weight: 600;
    letter-spacing: 0.5px;
}
.st-root .st-about-feats {
    display: flex; flex-direction: column; gap: 8px;
}
.st-root .st-feat-row {
    display: grid;
    grid-template-columns: 14px 120px 1fr;
    gap: 10px;
    align-items: center;
    padding: 8px 12px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 10px;
}
.st-root .st-feat-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #4F8BFF;
    box-shadow: 0 0 10px rgba(79,139,255,0.6);
}
.st-root .st-feat-k {
    font-size: 13px; font-weight: 700; color: #F0F2FA;
}
.st-root .st-feat-v {
    font-size: 12px; color: rgba(230,233,245,0.7);
    line-height: 1.5;
}

/* ================================================================
   响应式 — 多档断点
   ================================================================ */
@media (max-width: 1199px) {
    .st-root .st-feat-row { gap: 8px; }
}
@media (max-width: 900px) {
    .st-scope .st-card { padding: 18px !important; }
    .st-scope .st-slider-spacer { width: 16px !important; }
    .st-scope .st-slider-gap {
        flex: 0 0 16px !important;
        min-width: 16px !important;
        max-width: 16px !important;
    }
}
@media (max-width: 720px) {
    .st-scope .st-slider-row {
        flex-direction: column !important;
        gap: 12px !important;
    }
    .st-scope .st-slider-spacer { display: none !important; }
    .st-scope .st-slider-gap { display: none !important; }
    .st-scope .st-slider-half { padding: 0 !important; max-width: 100% !important; }
    .st-root .st-about-hero { grid-template-columns: 1fr; }
    .st-root .st-feat-row { grid-template-columns: 14px 1fr; }
    .st-root .st-feat-v { grid-column: 1 / -1; padding-left: 24px; }
    .st-scope .st-card:hover { transform: none !important; }
}
@media (max-width: 480px) {
    .st-scope .st-card {
        padding: 14px !important;
        border-radius: 14px !important;
    }
    .st-root .st-card-head { gap: 8px !important; padding-bottom: 10px !important; }
}
</style>
"""
# fmt: on
