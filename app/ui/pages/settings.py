"""系统设置页面

风控参数、大模型 API 配置、数据隐私、用户协议。
使用标签页子导航, 商务极简表单。
"""

from __future__ import annotations

import gradio as gr

from app.core.config import get_settings, reload_settings, update_env_file
from app.core.logger import get_logger
from app.utils.security_util import wipe_all_data

logger = get_logger(__name__)

_USER_AGREEMENT = """## 用户使用须知

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
            return f"保存失败: 最小延时 ({min_delay}s) 不能大于最大延时 ({max_delay}s)"
        if start_hour >= end_hour:
            return f"保存失败: 开始时段 ({start_hour}:00) 必须早于结束时段 ({end_hour}:00)"
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
        return "✓ 风控设置保存成功"
    except Exception as e:
        return f"保存失败: {e}"


def _save_api_settings(api_key, base_url, model):
    """保存 API 设置到 .env 并热更新 (含 API Key 校验)"""
    if not api_key or not api_key.strip():
        return "保存失败: API Key 不能为空"
    try:
        from app.utils.auth_util import validate_api_key
        result = validate_api_key(api_key.strip(), base_url=base_url, model=model)
        if not result.success:
            return f"保存失败: {result.message}"
        update_env_file({
            "LLM_API_KEY": api_key.strip(),
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model,
        })
        reload_settings()
        logger.info("API 设置已保存 (校验通过)")
        return "✓ API 配置校验通过并保存成功, 已立即生效"
    except Exception as e:
        return f"保存失败: {e}"


def _do_wipe():
    """清除所有数据"""
    try:
        ok = wipe_all_data()
        if ok:
            return "✓ 所有本地数据已清除 (不可恢复)"
        return "数据清除失败"
    except Exception as e:
        logger.error("数据清除异常: %s", e)
        return f"数据清除失败: {e}"


def create_settings_page():
    """创建系统设置页面"""
    settings = get_settings()

    gr.Markdown("## 系统设置")
    settings_msg = gr.Textbox(label="操作结果", interactive=False, max_lines=1)

    with gr.Tabs(elem_id="settings-tabs"):

        with gr.Tab("投递风控"):
            gr.Markdown("### 风控参数设置")
            max_daily = gr.Slider(
                1, 50, value=settings.MAX_DAILY_DELIVERY,
                step=1, label="每日最大投递量",
            )
            with gr.Row():
                min_delay = gr.Slider(
                    1, 10, value=settings.MIN_DELAY_SECONDS,
                    step=1, label="最小延时 (秒)",
                )
                max_delay = gr.Slider(
                    1, 10, value=settings.MAX_DELAY_SECONDS,
                    step=1, label="最大延时 (秒)",
                )
            with gr.Row():
                start_hour = gr.Slider(
                    0, 23, value=settings.DELIVERY_START_HOUR,
                    step=1, label="投递开始时段",
                )
                end_hour = gr.Slider(
                    1, 24, value=settings.DELIVERY_END_HOUR,
                    step=1, label="投递结束时段",
                )
            threshold = gr.Slider(
                0, 100, value=settings.MATCH_THRESHOLD,
                step=5, label="最低匹配分数阈值",
            )
            gr.Button("保存风控设置", variant="primary").click(
                fn=_save_risk_settings,
                inputs=[max_daily, min_delay, max_delay, start_hour, end_hour, threshold],
                outputs=[settings_msg],
            )

        with gr.Tab("大模型 API"):
            gr.Markdown("### 大模型配置")
            gr.Markdown(
                "支持 OpenAI / DeepSeek / 通义千问 等兼容 OpenAI API 格式的大模型服务"
            )
            api_key = gr.Textbox(
                label="API Key",
                type="password",
                value=settings.LLM_API_KEY,
                placeholder="sk-...",
            )
            base_url = gr.Textbox(
                label="API Base URL",
                value=settings.LLM_BASE_URL,
                placeholder="https://api.openai.com/v1",
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
            )
            gr.Button("保存 API 配置", variant="primary").click(
                fn=_save_api_settings,
                inputs=[api_key, base_url, model],
                outputs=[settings_msg],
            )
            gr.HTML(
                '<div class="alert-bar info" style="margin-top:12px;">'
                "API 密钥仅保存在本地 .env 文件, 不上传云端"
                "</div>"
            )

        with gr.Tab("数据与隐私"):
            gr.Markdown("### 数据管理")
            gr.Markdown("所有数据仅存储在本地设备, 不上传任何云端服务器。")
            gr.HTML('<div class="divider"></div>')
            gr.HTML(
                '<div class="alert-bar error">'
                "⚠ 一键清理: 将删除所有本地数据 (简历、投递记录、Cookie), 不可恢复!"
                "</div>"
            )
            gr.Button("一键清理所有数据", variant="stop").click(
                fn=_do_wipe, outputs=[settings_msg]
            )

        with gr.Tab("用户协议"):
            gr.Markdown(_USER_AGREEMENT)

        with gr.Tab("关于"):
            gr.Markdown(
                f"### {settings.APP_NAME}\n"
                f"- **版本**: V{settings.APP_VERSION}\n"
                f"- **技术栈**: Python 3.11 + LangGraph + Playwright + Gradio\n"
                f"- **定位**: 企业级 AI 多智能体求职辅助工具\n"
                f"- **核心优势**: 安全合规、AI 智能优化、全流程可控、隐私本地化\n\n"
                f"---\n"
                f"*AI 求职管家: 安全不封号, 精准拿面试*"
            )
