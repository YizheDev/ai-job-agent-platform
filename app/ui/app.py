"""Gradio UI 主入口

整合所有页面, 商务简约风格, 全局导航与状态管理。
严格遵循 UI 设计规范: 商务蓝 #165DFF, 极简白, 专业克制。
"""

from __future__ import annotations

import gradio as gr

from app.core.config import get_settings
from app.core.logger import get_logger
from app.ui.pages.dashboard import create_dashboard_page
from app.ui.pages.delivery import create_delivery_page
from app.ui.pages.jd_match import create_jd_match_page
from app.ui.pages.optimize import create_optimize_page
from app.ui.pages.records import create_records_page
from app.ui.pages.resume import create_resume_page
from app.ui.pages.settings import create_settings_page

logger = get_logger(__name__)

# 商务简约主题 CSS
_CUSTOM_CSS = """
/* 全局样式 */
.gradio-container {
    max-width: 1200px !important;
    margin: 0 auto !important;
    font-family: 'Microsoft YaHei', 'PingFang SC', 'Inter', sans-serif !important;
}

/* 主色调: 商务蓝 #165DFF */
.primary-btn { background-color: #165DFF !important; }

/* 卡片阴影 */
.gr-box { box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important; }

/* 表头 */
.gr-dataframe th {
    background-color: #F7F8FA !important;
    font-weight: 600 !important;
}

/* 标签页 */
.tabs > .tab-nav > button.selected {
    border-bottom-color: #165DFF !important;
    color: #165DFF !important;
}

/* 顶部标题栏 */
.app-header {
    background: linear-gradient(135deg, #165DFF 0%, #1E80FF 100%);
    color: white;
    padding: 16px 24px;
    border-radius: 6px;
    margin-bottom: 16px;
}
"""

# 用户协议弹窗内容
_DISCLAIMER = (
    "使用本工具即表示您已阅读并同意以下条款：\n"
    "1. 本工具仅为个人求职辅助, 不代表任何招聘平台官方\n"
    "2. 用户需遵守招聘平台用户协议, 账号风险自行承担\n"
    "3. 数据仅本地存储, 不上传云端\n"
    "4. 禁止用于商业代投或恶意投递"
)


def _accept_agreement():
    """用户同意协议"""
    from app.db.crud import SysConfigCRUD
    SysConfigCRUD.set("agreement_accepted", "true")
    return gr.update(visible=False), gr.update(visible=True)


def _check_agreement() -> bool:
    """检查用户是否已同意协议"""
    try:
        from app.db.crud import SysConfigCRUD
        return SysConfigCRUD.get("agreement_accepted") == "true"
    except Exception:
        return False


def create_app() -> gr.Blocks:
    """创建 Gradio 应用主界面"""
    settings = get_settings()

    theme = gr.themes.Soft(
        primary_hue=gr.themes.Color(
            c50="#EBF1FF", c100="#D1E0FF", c200="#A3C2FF",
            c300="#75A4FF", c400="#4785FF", c500="#165DFF",
            c600="#124ED6", c700="#0E3FAD", c800="#0A3084",
            c900="#06215B", c950="#041640",
        ),
        neutral_hue=gr.themes.colors.gray,
        font=[gr.themes.GoogleFont("Inter"), "Microsoft YaHei", "PingFang SC", "sans-serif"],
    )

    with gr.Blocks(
        title=settings.APP_NAME,
        theme=theme,
        css=_CUSTOM_CSS,
    ) as app:

        # ========== 用户协议弹窗 ==========
        agreed = _check_agreement()

        with gr.Column(visible=not agreed) as agreement_panel:
            gr.Markdown(f"# {settings.APP_NAME}")
            gr.Markdown("### 用户使用须知与免责声明")
            gr.Markdown(_DISCLAIMER)
            agree_btn = gr.Button("已阅读并同意, 开始使用", variant="primary", size="lg")

        # ========== 主界面 ==========
        with gr.Column(visible=agreed) as main_panel:
            # 顶部标题
            gr.Markdown(
                f"""<div style="background: linear-gradient(135deg, #165DFF, #1E80FF);
                color: white; padding: 16px 24px; border-radius: 6px; margin-bottom: 8px;">
                <h2 style="margin:0; color:white;">{settings.APP_NAME}</h2>
                <p style="margin:4px 0 0; opacity:0.9; color:#E0E8FF;">
                安全不封号, 精准拿面试 | V{settings.APP_VERSION}</p></div>"""
            )

            # Tab 导航
            with gr.Tabs():
                with gr.Tab("工作台"):
                    create_dashboard_page()

                with gr.Tab("简历管理"):
                    create_resume_page()

                with gr.Tab("JD 匹配"):
                    create_jd_match_page()

                with gr.Tab("简历优化"):
                    create_optimize_page()

                with gr.Tab("自动投递"):
                    create_delivery_page()

                with gr.Tab("投递记录"):
                    create_records_page()

                with gr.Tab("系统设置"):
                    create_settings_page()

        # 协议确认事件
        agree_btn.click(
            fn=_accept_agreement,
            outputs=[agreement_panel, main_panel],
        )

    logger.info("Gradio UI 构建完成")
    return app
