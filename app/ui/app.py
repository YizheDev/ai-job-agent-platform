"""Gradio UI 主入口

企业级SaaS商务极简风格, 左侧固定导航 + 顶部通栏 + 右侧内容区。
设计规范: 商务蓝 #165DFF, 极简白, 专业克制, 纯CSS零图片。
对标飞书管理后台 / Notion / Salesforce 设计语言。
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

APP_THEME = gr.themes.Soft(
    primary_hue=gr.themes.Color(
        c50="#EBF1FF", c100="#D1E0FF", c200="#A3C2FF",
        c300="#75A4FF", c400="#4785FF", c500="#165DFF",
        c600="#124ED6", c700="#0E3FAD", c800="#0A3084",
        c900="#06215B", c950="#041640",
    ),
    neutral_hue=gr.themes.colors.gray,
    font=["Inter", "PingFang SC", "Microsoft YaHei", "sans-serif"],
)

# fmt: off
APP_CSS = """
/* ================================================================
   AI求职智能管家 — 全局设计系统 (纯CSS, 零图片)
   对标: 飞书/Notion/Salesforce 企业级SaaS商务极简
   ================================================================ */

/* --- 全局基础 --- */
* { box-sizing: border-box; }

body, .gradio-container {
    font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    background: #F5F7FA !important;
    color: #4E5969 !important;
    font-size: 14px !important;
}
.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}
footer { display: none !important; }

/* --- 顶部通栏 (48px) --- */
.app-header-bar {
    background: #FFFFFF;
    border-bottom: 1px solid #E5E6EB;
    padding: 0 24px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.app-header-bar .hl { display: flex; align-items: center; gap: 12px; }
.app-header-bar .logo-text {
    font-size: 15px; font-weight: 600; color: #165DFF;
    letter-spacing: 0.5px;
}
.app-header-bar .hd { width: 1px; height: 16px; background: #E5E6EB; }
.app-header-bar .bc { font-size: 13px; color: #86909C; }
.app-header-bar .hr { display: flex; align-items: center; gap: 16px; font-size: 13px; color: #4E5969; }
.app-header-bar .ver {
    font-size: 11px; color: #86909C; background: #F2F3F5;
    padding: 2px 8px; border-radius: 10px; font-weight: 500;
}

/* --- 主布局: gr.Tabs → 左侧导航栏 + 右侧内容区 --- */
#main-tabs {
    display: flex !important;
    flex-direction: row !important;
    min-height: calc(100vh - 56px) !important;
    gap: 0 !important;
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}

/* 左侧导航栏 */
#main-tabs > .tab-nav {
    display: flex !important;
    flex-direction: column !important;
    width: 180px !important;
    min-width: 180px !important;
    max-width: 180px !important;
    background: #FFFFFF !important;
    border-right: 1px solid #E5E6EB !important;
    border-bottom: none !important;
    padding: 20px 0 !important;
    gap: 2px !important;
    flex-shrink: 0 !important;
    overflow-y: auto !important;
    align-self: stretch !important;
}
#main-tabs > .tab-nav::before {
    content: 'AI求职智能管家';
    display: block;
    font-size: 15px;
    font-weight: 600;
    color: #1D2129;
    padding: 0 20px 18px;
    border-bottom: 1px solid #E5E6EB;
    margin-bottom: 12px;
    letter-spacing: 0.5px;
}
#main-tabs > .tab-nav button {
    text-align: left !important;
    justify-content: flex-start !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 20px !important;
    height: 40px !important;
    min-height: 40px !important;
    font-size: 14px !important;
    color: #4E5969 !important;
    background: transparent !important;
    border-left: 3px solid transparent !important;
    border-bottom: none !important;
    transition: all 0.15s ease !important;
    font-weight: 400 !important;
    width: 100% !important;
    cursor: pointer !important;
    margin: 0 !important;
    white-space: nowrap !important;
    line-height: 40px !important;
}
#main-tabs > .tab-nav button:hover {
    background: #E8F3FF !important;
    color: #165DFF !important;
}
#main-tabs > .tab-nav button.selected {
    background: #E8F3FF !important;
    color: #165DFF !important;
    border-left-color: #165DFF !important;
    font-weight: 500 !important;
    border-bottom: none !important;
}

/* 右侧内容区 */
#main-tabs > .tabitem {
    flex: 1 !important;
    padding: 24px !important;
    background: #F5F7FA !important;
    min-height: calc(100vh - 56px) !important;
    overflow-y: auto !important;
}

/* --- 卡片通用 --- */
.card {
    background: #FFFFFF;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    padding: 20px;
    margin-bottom: 20px;
    transition: box-shadow 0.2s;
}
.card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.10); }

/* --- 数据概览卡片 (Dashboard 四宫格) --- */
.data-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-bottom: 24px;
}
.data-card {
    background: #FFFFFF;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    padding: 20px 24px;
    transition: box-shadow 0.2s;
}
.data-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.10); }
.data-card .dc-label {
    font-size: 13px; color: #86909C; margin-bottom: 10px; font-weight: 400;
}
.data-card .dc-value {
    font-size: 28px; font-weight: 600; color: #1D2129; line-height: 1.2;
}
.data-card .dc-value.blue  { color: #165DFF; }
.data-card .dc-value.green { color: #00B42A; }
.data-card .dc-value.orange { color: #FF7D00; }

/* --- 风险提示条 --- */
.alert-bar {
    background: #FFF7E8; border-left: 4px solid #FF7D00;
    padding: 12px 16px; border-radius: 0 4px 4px 0;
    margin-bottom: 20px; font-size: 14px; color: #4E5969;
}
.alert-bar.success { background: #E8FFEA; border-left-color: #00B42A; }
.alert-bar.error   { background: #FFECE8; border-left-color: #F53F3F; }
.alert-bar.info    { background: #E8F3FF; border-left-color: #165DFF; }

/* --- 状态标签 --- */
.status-tag {
    display: inline-block; padding: 2px 8px; border-radius: 2px;
    font-size: 12px; font-weight: 500; line-height: 1.8;
}
.tag-blue   { background: #E8F3FF; color: #165DFF; }
.tag-green  { background: #E8FFEA; color: #00B42A; }
.tag-orange { background: #FFF7E8; color: #FF7D00; }
.tag-red    { background: #FFECE8; color: #F53F3F; }
.tag-gray   { background: #F2F3F5; color: #86909C; }

/* --- 自定义 HTML 表格 --- */
.custom-table {
    width: 100%; border-collapse: collapse; font-size: 13px;
}
.custom-table th {
    background: #F7F8FA; color: #4E5969; font-weight: 500;
    text-align: left; padding: 0 16px; height: 48px;
    border-bottom: 1px solid #E5E6EB;
}
.custom-table td {
    padding: 0 16px; height: 48px; border-bottom: 1px solid #F2F3F5; color: #4E5969;
}
.custom-table tr:hover td { background: #FAFBFC; }
.custom-table tbody tr:nth-child(even) td { background: #FAFBFC; }
.custom-table tbody tr:nth-child(even):hover td { background: #F5F7FA; }

/* --- Gradio 按钮覆盖 --- */
button.primary, .gr-button-primary {
    background: #165DFF !important; color: #FFFFFF !important;
    border: none !important; border-radius: 4px !important;
    font-weight: 500 !important;
}
button.primary:hover, .gr-button-primary:hover { background: #0E42D2 !important; }
button.secondary, .gr-button-secondary {
    background: #FFFFFF !important; color: #4E5969 !important;
    border: 1px solid #E5E6EB !important; border-radius: 4px !important;
}
button.secondary:hover, .gr-button-secondary:hover {
    border-color: #165DFF !important; color: #165DFF !important;
}
button.stop, .gr-button-stop {
    background: #FFFFFF !important; color: #F53F3F !important;
    border: 1px solid #FFCDC8 !important; border-radius: 4px !important;
}
button.stop:hover, .gr-button-stop:hover {
    background: #FFF0ED !important; border-color: #F53F3F !important;
}

/* --- Gradio Dataframe 覆盖 --- */
.gr-dataframe th, .dataframe th, table thead th {
    background: #F7F8FA !important; color: #4E5969 !important;
    font-weight: 500 !important; font-size: 13px !important;
    height: 44px !important; border-bottom: 1px solid #E5E6EB !important;
    text-align: left !important;
}
.gr-dataframe td, .dataframe td, table tbody td {
    height: 44px !important; border-bottom: 1px solid #F2F3F5 !important;
    font-size: 13px !important; color: #4E5969 !important;
}
table tbody tr:hover td { background: #FAFBFC !important; }

/* --- 输入框 / 下拉框 --- */
input[type="text"], input[type="password"], input[type="number"],
textarea, select, .gr-text-input {
    border: 1px solid #E5E6EB !important; border-radius: 4px !important;
    font-size: 14px !important; color: #4E5969 !important;
}
input:focus, textarea:focus, select:focus {
    border-color: #165DFF !important; outline: none !important;
    box-shadow: 0 0 0 2px rgba(22,93,255,0.08) !important;
}
label span {
    font-size: 13px !important; font-weight: 500 !important; color: #4E5969 !important;
}

/* --- 标题 --- */
.section-title {
    font-size: 16px; font-weight: 600; color: #1D2129;
    margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #E5E6EB;
}

/* --- 纯CSS环形图 --- */
.ring-chart-wrap {
    display: flex; align-items: center; justify-content: center; padding: 20px;
}
.ring-chart {
    position: relative; width: 140px; height: 140px;
}
.ring-chart svg { transform: rotate(-90deg); }
.ring-chart .rt {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%); text-align: center;
}
.ring-chart .rs {
    font-size: 32px; font-weight: 600; color: #1D2129; line-height: 1;
}
.ring-chart .rl {
    font-size: 12px; color: #86909C; margin-top: 4px;
}

/* --- 纯CSS柱状图 --- */
.bar-chart {
    display: flex; align-items: flex-end; gap: 12px;
    height: 180px; padding: 16px 8px 0;
}
.bar-item {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; height: 100%; justify-content: flex-end;
}
.bar-item .bar {
    width: 100%; max-width: 36px; background: #165DFF;
    border-radius: 3px 3px 0 0; min-height: 2px;
    transition: background 0.2s;
}
.bar-item .bar:hover { background: #0E42D2; }
.bar-item .bv {
    font-size: 11px; color: #165DFF; font-weight: 500; margin-bottom: 4px;
}
.bar-item .bl {
    font-size: 11px; color: #86909C; margin-top: 8px; white-space: nowrap;
}

/* --- 进度步骤 --- */
.progress-steps {
    display: flex; align-items: center; padding: 20px 0;
}
.step-node {
    display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.step-dot {
    width: 28px; height: 28px; border-radius: 50%;
    border: 2px solid #E5E6EB; background: #FFFFFF;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #86909C;
}
.step-dot.active  { border-color: #165DFF; background: #165DFF; color: #FFF; }
.step-dot.done    { border-color: #00B42A; background: #00B42A; color: #FFF; }
.step-name { font-size: 12px; color: #86909C; }
.step-name.active { color: #165DFF; font-weight: 500; }
.step-name.done   { color: #00B42A; }
.step-line {
    flex: 1; height: 2px; background: #E5E6EB; margin: 0 8px; align-self: flex-start;
    margin-top: 14px;
}
.step-line.done { background: #00B42A; }

/* --- 进度条 --- */
.progress-bar-bg {
    background: #F2F3F5; border-radius: 4px; height: 8px; overflow: hidden; margin: 12px 0;
}
.progress-bar-fill {
    height: 100%; background: linear-gradient(90deg, #165DFF, #4785FF);
    border-radius: 4px; transition: width 0.5s ease;
}

/* --- 设置页子 Tabs --- */
#settings-tabs > .tab-nav {
    border-bottom: 1px solid #E5E6EB !important;
    gap: 0 !important; padding: 0 !important; margin-bottom: 20px !important;
    flex-direction: row !important;
}
#settings-tabs > .tab-nav button {
    height: 40px !important; font-size: 14px !important;
    color: #86909C !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important; padding: 0 16px !important;
    font-weight: 400 !important;
}
#settings-tabs > .tab-nav button:hover { color: #165DFF !important; }
#settings-tabs > .tab-nav button.selected {
    color: #165DFF !important; border-bottom-color: #165DFF !important;
    font-weight: 500 !important; background: transparent !important;
}

/* --- 协议页 --- */
#agreement-panel {
    max-width: 560px !important; margin: 60px auto !important;
    background: #FFFFFF; border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08); padding: 40px !important;
}
#agreement-panel h1 { color: #1D2129 !important; text-align: center; }

/* --- 分隔线 --- */
.divider { height: 1px; background: #E5E6EB; margin: 20px 0; }

/* --- Markdown 微调 --- */
.prose h2 {
    font-size: 18px !important; font-weight: 600 !important;
    color: #1D2129 !important; margin-bottom: 16px !important;
}
.prose h3 {
    font-size: 15px !important; font-weight: 600 !important;
    color: #1D2129 !important; margin-bottom: 12px !important;
}

/* --- Gradio 容器微调 --- */
.block { border: none !important; }
.gr-group { border-radius: 4px !important; }
.gr-box {
    border-radius: 4px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}
.contain { gap: 12px !important; }

/* --- 匹配结果标签 --- */
.match-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.match-tag {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 3px; font-size: 13px;
}
.match-tag.hit  { background: #E8FFEA; color: #00B42A; }
.match-tag.miss { background: #FFECE8; color: #F53F3F; }
.match-tag.weak { background: #FFF7E8; color: #FF7D00; }

/* --- 信息卡片 (投递任务等) --- */
.info-card {
    background: #FFFFFF; border-radius: 4px; border: 1px solid #E5E6EB;
    padding: 16px 20px; margin-bottom: 16px;
}
.info-card .ic-row {
    display: flex; align-items: center; padding: 6px 0;
    font-size: 14px; color: #4E5969;
}
.info-card .ic-label {
    width: 80px; color: #86909C; font-size: 13px; flex-shrink: 0;
}
.info-card .ic-value { color: #1D2129; font-weight: 500; }

/* --- 分布图例 --- */
.legend-row {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 0; font-size: 13px; color: #4E5969;
}
.legend-dot {
    width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
}

/* --- 响应式 (平板折叠侧栏) --- */
@media (max-width: 900px) {
    #main-tabs > .tab-nav {
        width: 56px !important; min-width: 56px !important; max-width: 56px !important;
        overflow: hidden !important;
    }
    #main-tabs > .tab-nav::before {
        content: '管家'; font-size: 12px; padding: 0 8px 12px;
    }
    #main-tabs > .tab-nav button {
        font-size: 0 !important; padding: 0 !important;
        text-indent: -9999px !important;
    }
    .data-cards { grid-template-columns: repeat(2, 1fr); }
}
"""
# fmt: on

_DISCLAIMER = (
    "使用本工具即表示您已阅读并同意以下条款：\n\n"
    "1. 本工具仅为个人求职辅助, 不代表任何招聘平台官方\n\n"
    "2. 用户需遵守招聘平台用户协议, 账号风险自行承担\n\n"
    "3. 数据仅本地存储, 不上传云端\n\n"
    "4. 禁止用于商业代投或恶意投递"
)


def _accept_agreement():
    """用户同意协议"""
    from app.db.crud import SysConfigCRUD
    SysConfigCRUD.set("agreement_accepted", "true")
    return gr.Column(visible=False), gr.Column(visible=True)


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

    with gr.Blocks(
        title=settings.APP_NAME,
        theme=APP_THEME,
        css=APP_CSS,
    ) as app:

        agreed = _check_agreement()

        # ---- 协议面板 ----
        with gr.Column(visible=not agreed, elem_id="agreement-panel") as agreement_panel:
            gr.Markdown(f"# {settings.APP_NAME}")
            gr.Markdown("### 用户使用须知与免责声明")
            gr.Markdown(_DISCLAIMER)
            agree_btn = gr.Button("已阅读并同意, 开始使用", variant="primary", size="lg")

        # ---- 主面板 ----
        with gr.Column(visible=agreed) as main_panel:

            # 顶部通栏
            gr.HTML(
                f'<div class="app-header-bar">'
                f'<div class="hl">'
                f'<span class="logo-text">AI求职智能管家</span>'
                f'<span class="hd"></span>'
                f'<span class="bc">智能求职辅助平台</span>'
                f'</div>'
                f'<div class="hr">'
                f'<span class="ver">V{settings.APP_VERSION}</span>'
                f'<span style="cursor:pointer" title="帮助">❓</span>'
                f'<span style="cursor:pointer" title="设置">⚙️</span>'
                f'</div>'
                f'</div>'
            )

            # 左侧导航 + 右侧内容 (通过CSS将Tabs转为侧栏)
            with gr.Tabs(elem_id="main-tabs"):
                with gr.Tab("📊 工作台"):
                    create_dashboard_page()
                with gr.Tab("📄 简历管理"):
                    create_resume_page()
                with gr.Tab("🔍 JD匹配"):
                    create_jd_match_page()
                with gr.Tab("✨ 简历优化"):
                    create_optimize_page()
                with gr.Tab("🚀 自动投递"):
                    create_delivery_page()
                with gr.Tab("📋 投递记录"):
                    create_records_page()
                with gr.Tab("⚙ 系统设置"):
                    create_settings_page()

        agree_btn.click(
            fn=_accept_agreement,
            outputs=[agreement_panel, main_panel],
        )

    logger.info("Gradio UI 构建完成")
    return app
