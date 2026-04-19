"""Gradio UI 主入口

现代 SaaS 设计系统, 左侧固定导航 + 顶部通栏 + 右侧内容区。
设计规范: Glassmorphism + Gradient + Motion, 商务蓝 #165DFF。
对标 Linear / Vercel / Notion 现代 SaaS 设计语言。
"""

from __future__ import annotations

import gradio as gr

from app.core.config import get_settings
from app.core.logger import get_logger
from app.ui.pages.boss_account import create_boss_account_page
from app.ui.pages.dashboard import create_dashboard_page
from app.ui.pages.delivery import create_delivery_page
from app.ui.pages.jd_match import create_jd_match_page
from app.ui.pages.optimize import create_optimize_page
from app.ui.pages.records import create_records_page
from app.ui.pages.resume import create_resume_page
from app.ui.pages.settings import create_settings_page
from app.ui.login import (
    LOGIN_BRAND_HTML,
    LOGIN_CSS,
    build_header_html,
    handle_login,
    handle_logout,
    restore_session,
)
from app.ui.pages.dashboard import load_dashboard_data

logger = get_logger(__name__)

APP_THEME = gr.themes.Soft(
    primary_hue=gr.themes.Color(
        c50="#EBF1FF", c100="#D1E0FF", c200="#A3C2FF",
        c300="#75A4FF", c400="#4785FF", c500="#165DFF",
        c600="#124ED6", c700="#0E3FAD", c800="#0A3084",
        c900="#06215B", c950="#041640",
    ),
    neutral_hue=gr.themes.colors.gray,
)

# fmt: off
APP_CSS = """
/* ================================================================
   AI求职智能管家 — 现代设计系统 V2.0
   Glassmorphism · Gradient · Motion · Depth
   Web Fonts: Inter / Noto Sans SC / JetBrains Mono
       (通过 <link> 由 _render_font_links_html 注入,
        因 Gradio constructed-stylesheets 不支持 @import)
   ================================================================ */

/* --- Design Tokens --- */
:root {
    --c-primary: #165DFF;
    --c-primary-light: #4785FF;
    --c-primary-lighter: #6AA1FF;
    --c-primary-dark: #0E42D2;
    --c-primary-bg: rgba(22,93,255,0.06);
    --c-success: #00B42A;
    --c-success-bg: rgba(0,180,42,0.08);
    --c-warning: #FF7D00;
    --c-warning-bg: rgba(255,125,0,0.08);
    --c-danger: #F53F3F;
    --c-danger-bg: rgba(245,63,63,0.08);
    --c-text-1: #1D2129;
    --c-text-2: #4E5969;
    --c-text-3: #86909C;
    --c-text-4: #C9CDD4;
    --c-bg-page: #F0F2F5;
    --c-bg-card: #FFFFFF;
    --c-border: #E5E6EB;
    --c-border-light: #F2F3F5;
    --shadow-s: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-m: 0 4px 12px rgba(0,0,0,0.05), 0 2px 6px rgba(0,0,0,0.04);
    --shadow-l: 0 8px 24px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.04);
    --shadow-xl: 0 16px 48px rgba(0,0,0,0.08), 0 6px 18px rgba(0,0,0,0.04);
    --r-s: 8px;
    --r-m: 12px;
    --r-l: 16px;
    --r-xl: 20px;
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
    --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* --- Animations --- */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
@keyframes slideRight {
    from { opacity: 0; transform: translateX(-16px); }
    to   { opacity: 1; transform: translateX(0); }
}
@keyframes scaleIn {
    from { opacity: 0; transform: scale(0.92); }
    to   { opacity: 1; transform: scale(1); }
}
@keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes ringDraw {
    from { stroke-dashoffset: 340; }
}
@keyframes barGrow {
    from { transform: scaleY(0); }
    to   { transform: scaleY(1); }
}
@keyframes float {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-8px); }
}
@keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(22,93,255,0.3); }
    50%      { box-shadow: 0 0 0 8px rgba(22,93,255,0); }
}
@keyframes slideDown {
    from { opacity: 0; transform: translateY(-8px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* --- Global Base --- */
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }

body, .gradio-container {
    /*
       字体栈说明 (从左到右优先级):
         1. Inter / Noto Sans SC: 网络下载, 最佳形态
         2. system-ui + -apple-system + Segoe UI: 现代 OS 默认 UI 字体
         3. PingFang SC / Microsoft YaHei / Hiragino Sans GB / Source Han Sans SC / Noto Sans CJK SC:
            macOS / Windows / iOS / 思源 / Linux 中文回退
         4. Apple Color Emoji / Segoe UI Emoji / Noto Color Emoji: 保证 emoji 不变方块
         5. Helvetica Neue / Arial / sans-serif: 最终西文兜底
    */
    font-family:
        'Inter',
        'Noto Sans SC',
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        'PingFang SC',
        'Hiragino Sans GB',
        'Microsoft YaHei',
        'Source Han Sans SC',
        'Noto Sans CJK SC',
        'WenQuanYi Micro Hei',
        'Helvetica Neue',
        Helvetica,
        Arial,
        'Apple Color Emoji',
        'Segoe UI Emoji',
        'Noto Color Emoji',
        sans-serif !important;
    background: linear-gradient(160deg, #F0F2F5 0%, #E8ECF2 40%, #EDF0F5 100%) !important;
    color: var(--c-text-2) !important;
    font-size: 14px !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
    font-feature-settings:
        "cv11" on,    /* Inter 单层 a */
        "ss01" on,    /* Inter 替换字形 (开启更和谐的拉丁数字) */
        "ss03" on,    /* 简化 g */
        "tnum" on,    /* 表格数字 (等宽数字, 适合数据统计场景) */
        "calt" on;    /* 上下文字形 */
    font-variant-numeric: tabular-nums;
    text-rendering: optimizeLegibility !important;
    letter-spacing: 0.01em;
}
/* 数字 / 代码块 单独使用 Mono 字体, 提高数据感 */
.gradio-container code, .gradio-container pre,
.gradio-container .num-mono, .gradio-container [data-mono] {
    font-family:
        'JetBrains Mono',
        'Fira Code',
        'Cascadia Code',
        'Source Code Pro',
        'Inter',
        ui-monospace,
        SFMono-Regular,
        Menlo,
        Consolas,
        'Liberation Mono',
        'Courier New',
        monospace !important;
    font-feature-settings: "tnum" on, "zero" on;
}
.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}
footer { display: none !important; }

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: var(--c-text-4); border-radius: 3px;
    transition: background 0.2s;
}
::-webkit-scrollbar-thumb:hover { background: var(--c-text-3); }

/* --- 顶部通栏 (52px, gradient accent) --- */
.app-header-bar {
    position: relative;
    background: linear-gradient(135deg, #FFFFFF 0%, #F9FAFC 100%);
    padding: 0 28px;
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 10;
    animation: slideDown 0.4s var(--ease);
}
.app-header-bar::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--c-primary), var(--c-primary-light), transparent 70%);
    opacity: 0.7;
}
.app-header-bar .hl { display: flex; align-items: center; gap: 14px; }
.app-header-bar .logo-text {
    font-size: 16px; font-weight: 700; color: var(--c-primary);
    letter-spacing: 0.5px;
    background: linear-gradient(135deg, #165DFF, #4785FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.app-header-bar .hd {
    width: 1px; height: 18px;
    background: linear-gradient(180deg, transparent, var(--c-border), transparent);
}
.app-header-bar .bc { font-size: 13px; color: var(--c-text-3); font-weight: 400; }
.app-header-bar .hr {
    display: flex; align-items: center; gap: 16px;
    font-size: 13px; color: var(--c-text-2);
}
.app-header-bar .ver {
    font-size: 11px; color: var(--c-primary); font-weight: 600;
    background: var(--c-primary-bg); padding: 3px 10px;
    border-radius: 20px; letter-spacing: 0.3px;
    border: 1px solid rgba(22,93,255,0.12);
}

/* --- 主布局: 左侧导航 + 右侧内容 --- */
#main-tabs {
    display: flex !important;
    flex-direction: row !important;
    min-height: calc(100vh - 60px) !important;
    gap: 0 !important;
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}

/* 左侧导航栏 */
#main-tabs > .tab-wrapper {
    display: flex !important;
    flex-direction: column !important;
    width: 200px !important;
    min-width: 200px !important;
    max-width: 200px !important;
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    background: linear-gradient(180deg, #FFFFFF 0%, #FAFBFD 100%) !important;
    border-right: 1px solid var(--c-border) !important;
    border-bottom: none !important;
    padding: 24px 0 !important;
    gap: 0 !important;
    flex-shrink: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    align-self: stretch !important;
    box-shadow: 2px 0 12px rgba(0,0,0,0.02) !important;
}
#main-tabs > .tab-wrapper::before {
    content: '\\1F916  智能管家';
    display: block;
    font-size: 15px;
    font-weight: 700;
    color: var(--c-text-1);
    padding: 4px 24px 20px;
    border-bottom: 1px solid var(--c-border-light);
    margin-bottom: 16px;
    letter-spacing: 0.5px;
}
#main-tabs > .tab-wrapper .tab-container.visually-hidden {
    display: none !important;
}
#main-tabs > .tab-wrapper .tab-container {
    display: flex !important;
    flex-direction: column !important;
    gap: 4px !important;
    border: none !important;
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    flex: 1 !important;
    padding: 0 8px !important;
}
#main-tabs > .tab-wrapper .overflow-menu {
    display: none !important;
}
#main-tabs > .tab-wrapper .tab-container button {
    text-align: left !important;
    justify-content: flex-start !important;
    border: none !important;
    border-radius: var(--r-s) !important;
    padding: 0 16px !important;
    height: 42px !important;
    min-height: 42px !important;
    font-size: 14px !important;
    color: var(--c-text-2) !important;
    background: transparent !important;
    border-left: none !important;
    border-bottom: none !important;
    transition: all 0.25s var(--ease) !important;
    font-weight: 450 !important;
    width: 100% !important;
    cursor: pointer !important;
    margin: 0 !important;
    white-space: nowrap !important;
    line-height: 42px !important;
    position: relative !important;
}
#main-tabs > .tab-wrapper .tab-container button:hover {
    background: var(--c-primary-bg) !important;
    color: var(--c-primary) !important;
    transform: translateX(2px) !important;
}
#main-tabs > .tab-wrapper .tab-container button.selected {
    background: linear-gradient(135deg, rgba(22,93,255,0.10), rgba(71,133,255,0.08)) !important;
    color: var(--c-primary) !important;
    font-weight: 600 !important;
    border-bottom: none !important;
    box-shadow: 0 2px 8px rgba(22,93,255,0.08) !important;
}
#main-tabs > .tab-wrapper .tab-container button.selected::before {
    content: '';
    position: absolute;
    left: 0; top: 50%;
    transform: translateY(-50%);
    width: 3px; height: 20px;
    background: linear-gradient(180deg, var(--c-primary), var(--c-primary-light));
    border-radius: 0 3px 3px 0;
}

/* 右侧内容区 */
#main-tabs > .tabitem {
    flex: 1 !important;
    padding: 10px 28px 28px 28px !important;
    background: transparent !important;
    min-height: calc(100vh - 60px) !important;
    overflow-y: auto !important;
    animation: fadeIn 0.35s var(--ease) !important;
}

/* --- 卡片通用 --- */
.card {
    background: var(--c-bg-card);
    border-radius: var(--r-m);
    box-shadow: var(--shadow-s);
    padding: 24px;
    margin-bottom: 20px;
    transition: all 0.3s var(--ease);
    border: 1px solid rgba(0,0,0,0.04);
    animation: fadeInUp 0.5s var(--ease);
}
.card:hover {
    box-shadow: var(--shadow-m);
    transform: translateY(-2px);
}

/* --- 数据概览卡片 (Dashboard) --- */
.data-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-bottom: 28px;
}
.data-card {
    background: var(--c-bg-card);
    border-radius: var(--r-m);
    box-shadow: var(--shadow-s);
    padding: 24px;
    transition: all 0.35s var(--ease);
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(0,0,0,0.03);
    animation: fadeInUp 0.5s var(--ease) backwards;
}
.data-card:nth-child(1) { animation-delay: 0.05s; }
.data-card:nth-child(2) { animation-delay: 0.1s; }
.data-card:nth-child(3) { animation-delay: 0.15s; }
.data-card:nth-child(4) { animation-delay: 0.2s; }
.data-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: var(--r-m) var(--r-m) 0 0;
    background: linear-gradient(90deg, var(--c-primary), var(--c-primary-light));
    opacity: 0;
    transition: opacity 0.3s;
}
.data-card:hover::before { opacity: 1; }
.data-card:hover {
    box-shadow: var(--shadow-l);
    transform: translateY(-4px);
}
.data-card .dc-icon {
    width: 40px; height: 40px; border-radius: var(--r-s);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; margin-bottom: 14px;
}
.data-card .dc-icon.blue   { background: var(--c-primary-bg); }
.data-card .dc-icon.green  { background: var(--c-success-bg); }
.data-card .dc-icon.orange { background: var(--c-warning-bg); }
.data-card .dc-icon.gray   { background: rgba(134,144,156,0.08); }
.data-card .dc-label {
    font-size: 13px; color: var(--c-text-3);
    margin-bottom: 10px; font-weight: 450;
}
.data-card .dc-value {
    font-size: 32px; font-weight: 700; color: var(--c-text-1);
    line-height: 1.1; letter-spacing: -0.5px;
}
.data-card .dc-value.blue  { color: var(--c-primary); }
.data-card .dc-value.green { color: var(--c-success); }
.data-card .dc-value.orange { color: var(--c-warning); }

/* --- 风险提示条 --- */
.alert-bar {
    background: var(--c-warning-bg);
    border-left: 4px solid var(--c-warning);
    padding: 14px 20px;
    border-radius: 0 var(--r-s) var(--r-s) 0;
    margin-bottom: 20px;
    font-size: 14px;
    color: var(--c-text-2);
    animation: slideRight 0.4s var(--ease);
    backdrop-filter: blur(8px);
    line-height: 1.6;
}
.alert-bar.success { background: var(--c-success-bg); border-left-color: var(--c-success); }
.alert-bar.error   { background: var(--c-danger-bg);  border-left-color: var(--c-danger); }
.alert-bar.info    { background: var(--c-primary-bg);  border-left-color: var(--c-primary); }

/* --- 状态标签 --- */
.status-tag {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 550;
    line-height: 1.6;
    transition: all 0.2s var(--ease);
    gap: 4px;
}
.tag-blue   { background: var(--c-primary-bg); color: var(--c-primary); }
.tag-green  { background: var(--c-success-bg); color: var(--c-success); }
.tag-orange { background: var(--c-warning-bg); color: var(--c-warning); }
.tag-red    { background: var(--c-danger-bg);  color: var(--c-danger); }
.tag-gray   { background: rgba(134,144,156,0.08); color: var(--c-text-3); }

/* --- 表格 --- */
.custom-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 13px;
    border-radius: var(--r-m);
    overflow: hidden;
    box-shadow: var(--shadow-s);
    border: 1px solid var(--c-border-light);
}
.custom-table th {
    background: linear-gradient(180deg, #F7F8FA, #F2F3F5);
    color: var(--c-text-2);
    font-weight: 600;
    text-align: left;
    padding: 0 20px;
    height: 48px;
    border-bottom: 1px solid var(--c-border);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.custom-table td {
    padding: 0 20px;
    height: 52px;
    border-bottom: 1px solid var(--c-border-light);
    color: var(--c-text-2);
    transition: all 0.2s var(--ease);
}
.custom-table tr:last-child td { border-bottom: none; }
.custom-table tr:hover td {
    background: rgba(22,93,255,0.02);
}
.custom-table tbody tr {
    transition: all 0.2s var(--ease);
}
.custom-table tbody tr:hover {
    transform: scale(1.002);
}

/* --- Gradio 按钮覆盖 --- */
button.primary, .gr-button-primary {
    background: linear-gradient(135deg, var(--c-primary), var(--c-primary-light)) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: var(--r-s) !important;
    font-weight: 600 !important;
    transition: all 0.3s var(--ease) !important;
    box-shadow: 0 2px 8px rgba(22,93,255,0.25) !important;
    position: relative !important;
    overflow: hidden !important;
    letter-spacing: 0.3px !important;
}
button.primary:hover, .gr-button-primary:hover {
    background: linear-gradient(135deg, var(--c-primary-dark), var(--c-primary)) !important;
    box-shadow: 0 4px 16px rgba(22,93,255,0.35) !important;
    transform: translateY(-1px) !important;
}
button.primary:active, .gr-button-primary:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 6px rgba(22,93,255,0.2) !important;
}
button.secondary, .gr-button-secondary {
    background: var(--c-bg-card) !important;
    color: var(--c-text-2) !important;
    border: 1px solid var(--c-border) !important;
    border-radius: var(--r-s) !important;
    font-weight: 500 !important;
    transition: all 0.3s var(--ease) !important;
    box-shadow: var(--shadow-s) !important;
}
button.secondary:hover, .gr-button-secondary:hover {
    border-color: var(--c-primary) !important;
    color: var(--c-primary) !important;
    box-shadow: var(--shadow-m) !important;
    transform: translateY(-1px) !important;
    background: rgba(22,93,255,0.02) !important;
}
button.stop, .gr-button-stop {
    background: var(--c-bg-card) !important;
    color: var(--c-danger) !important;
    border: 1px solid rgba(245,63,63,0.3) !important;
    border-radius: var(--r-s) !important;
    font-weight: 500 !important;
    transition: all 0.3s var(--ease) !important;
}
button.stop:hover, .gr-button-stop:hover {
    background: var(--c-danger-bg) !important;
    border-color: var(--c-danger) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(245,63,63,0.15) !important;
}

/* --- Gradio Dataframe 覆盖 --- */
.gr-dataframe, .dataframe, .gradio-dataframe {
    border-radius: var(--r-m) !important;
    overflow: hidden !important;
    box-shadow: var(--shadow-s) !important;
    border: 1px solid var(--c-border-light) !important;
}
.gr-dataframe th, .dataframe th, table thead th {
    background: linear-gradient(180deg, #F7F8FA, #F2F3F5) !important;
    color: var(--c-text-2) !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    height: 46px !important;
    border-bottom: 1px solid var(--c-border) !important;
    text-align: left !important;
    letter-spacing: 0.3px !important;
}
.gr-dataframe td, .dataframe td, table tbody td {
    height: 48px !important;
    border-bottom: 1px solid var(--c-border-light) !important;
    font-size: 13px !important;
    color: var(--c-text-2) !important;
    transition: background 0.2s !important;
}
table tbody tr:hover td { background: rgba(22,93,255,0.02) !important; }

/* --- 输入框 / 下拉框 --- */
input[type="text"], input[type="password"], input[type="number"],
textarea, select, .gr-text-input {
    border: 1.5px solid var(--c-border) !important;
    border-radius: var(--r-s) !important;
    font-size: 14px !important;
    color: var(--c-text-2) !important;
    transition: all 0.3s var(--ease) !important;
    background: var(--c-bg-card) !important;
}
input:focus, textarea:focus, select:focus {
    border-color: var(--c-primary) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(22,93,255,0.10),
                0 2px 8px rgba(22,93,255,0.06) !important;
}
label span {
    font-size: 13px !important;
    font-weight: 550 !important;
    color: var(--c-text-2) !important;
    background: none !important;
}

/* --- 标题 --- */
.section-title {
    font-size: 17px; font-weight: 700; color: var(--c-text-1);
    margin-bottom: 20px; padding-bottom: 14px;
    border-bottom: 2px solid var(--c-border-light);
    position: relative;
}
.section-title::after {
    content: '';
    position: absolute;
    bottom: -2px; left: 0;
    width: 40px; height: 2px;
    background: linear-gradient(90deg, var(--c-primary), var(--c-primary-light));
    border-radius: 1px;
}

/* --- 环形图 --- */
.ring-chart-wrap {
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
}
.ring-chart {
    position: relative; width: 160px; height: 160px;
}
.ring-chart svg circle[stroke-dashoffset] {
    transition: stroke-dashoffset 1.2s var(--ease);
}
.ring-chart .animated-ring {
    animation: ringDraw 1.2s var(--ease) forwards;
}
.ring-chart .rt {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%); text-align: center;
}
.ring-chart .rs {
    font-size: 36px; font-weight: 700; color: var(--c-text-1);
    line-height: 1; letter-spacing: -1px;
}
.ring-chart .rl {
    font-size: 12px; color: var(--c-text-3); margin-top: 6px;
    font-weight: 500;
}

/* --- 柱状图 --- */
.bar-chart {
    display: flex; align-items: flex-end; gap: 14px;
    height: 200px; padding: 20px 12px 0;
    background: linear-gradient(180deg, transparent, rgba(22,93,255,0.02));
    border-radius: var(--r-m);
}
.bar-item {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; height: 100%; justify-content: flex-end;
}
.bar-item .bar {
    width: 100%; max-width: 40px;
    background: linear-gradient(180deg, var(--c-primary), var(--c-primary-light));
    border-radius: 6px 6px 0 0;
    min-height: 3px;
    transition: all 0.3s var(--ease);
    transform-origin: bottom;
    animation: barGrow 0.8s var(--ease) backwards;
}
.bar-item:nth-child(1) .bar { animation-delay: 0.05s; }
.bar-item:nth-child(2) .bar { animation-delay: 0.1s; }
.bar-item:nth-child(3) .bar { animation-delay: 0.15s; }
.bar-item:nth-child(4) .bar { animation-delay: 0.2s; }
.bar-item:nth-child(5) .bar { animation-delay: 0.25s; }
.bar-item:nth-child(6) .bar { animation-delay: 0.3s; }
.bar-item:nth-child(7) .bar { animation-delay: 0.35s; }
.bar-item .bar:hover {
    background: linear-gradient(180deg, var(--c-primary-dark), var(--c-primary));
    transform: scaleY(1.05);
    box-shadow: 0 -4px 12px rgba(22,93,255,0.2);
}
.bar-item .bv {
    font-size: 12px; color: var(--c-primary); font-weight: 700;
    margin-bottom: 6px;
    opacity: 0;
    animation: fadeIn 0.4s var(--ease) 0.6s forwards;
}
.bar-item .bl {
    font-size: 11px; color: var(--c-text-3); margin-top: 10px;
    white-space: nowrap; font-weight: 450;
}

/* --- 进度步骤 --- */
.progress-steps {
    display: flex; align-items: center; padding: 24px 0;
}
.step-node {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.step-dot {
    width: 32px; height: 32px; border-radius: 50%;
    border: 2px solid var(--c-border); background: var(--c-bg-card);
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; color: var(--c-text-3);
    transition: all 0.3s var(--ease);
    font-weight: 600;
}
.step-dot.active {
    border-color: var(--c-primary);
    background: linear-gradient(135deg, var(--c-primary), var(--c-primary-light));
    color: #FFF;
    box-shadow: 0 4px 12px rgba(22,93,255,0.3);
    animation: pulseGlow 2s ease-in-out infinite;
}
.step-dot.done {
    border-color: var(--c-success);
    background: linear-gradient(135deg, #00B42A, #34D058);
    color: #FFF;
}
.step-name {
    font-size: 12px; color: var(--c-text-3); font-weight: 450;
}
.step-name.active { color: var(--c-primary); font-weight: 600; }
.step-name.done   { color: var(--c-success); font-weight: 500; }
.step-line {
    flex: 1; height: 2px; background: var(--c-border);
    margin: 0 10px; align-self: flex-start;
    margin-top: 16px; border-radius: 1px;
    position: relative;
    overflow: hidden;
}
.step-line.done {
    background: var(--c-success);
}

/* --- 进度条 --- */
.progress-bar-bg {
    background: var(--c-border-light);
    border-radius: 6px;
    height: 8px;
    overflow: hidden;
    margin: 14px 0;
}
.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--c-primary), var(--c-primary-light), var(--c-primary));
    background-size: 200% 100%;
    border-radius: 6px;
    transition: width 0.6s var(--ease);
    animation: shimmer 2s linear infinite;
}

/* --- 设置页子 Tabs --- */
#settings-tabs > .tab-wrapper {
    border-bottom: 2px solid var(--c-border-light) !important;
    gap: 0 !important; padding: 0 !important; margin-bottom: 24px !important;
    flex-direction: row !important;
}
#settings-tabs > .tab-wrapper .tab-container.visually-hidden {
    display: none !important;
}
#settings-tabs > .tab-wrapper .tab-container {
    display: flex !important;
    flex-direction: row !important;
    gap: 4px !important;
}
#settings-tabs > .tab-wrapper .tab-container button {
    height: 44px !important; font-size: 14px !important;
    color: var(--c-text-3) !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important; padding: 0 20px !important;
    font-weight: 450 !important;
    transition: all 0.25s var(--ease) !important;
    border-radius: var(--r-s) var(--r-s) 0 0 !important;
}
#settings-tabs > .tab-wrapper .tab-container button:hover {
    color: var(--c-primary) !important;
    background: rgba(22,93,255,0.03) !important;
}
#settings-tabs > .tab-wrapper .tab-container button.selected {
    color: var(--c-primary) !important;
    border-bottom-color: var(--c-primary) !important;
    font-weight: 600 !important;
    background: rgba(22,93,255,0.04) !important;
}

/* --- Loading overlay (suppress for quick-action buttons & tab switches) --- */
.app-header-bar ~ .wrap[data-testid="status-tracker"],
#logout-row .wrap[data-testid="status-tracker"],
.app-header-bar + .wrap[data-testid="status-tracker"],
#main-tabs > .wrap[data-testid="status-tracker"],
#main-tabs .wrap[data-testid="status-tracker"],
#main-panel > .wrap[data-testid="status-tracker"] {
    display: none !important;
}
.wrap[data-testid="status-tracker"].translucent {
    background: transparent !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* --- 协议页 --- */
#agreement-panel {
    max-width: 560px !important;
    margin: 60px auto !important;
    background: rgba(255,255,255,0.9);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: var(--r-xl);
    box-shadow: var(--shadow-xl);
    padding: 48px !important;
    border: 1px solid rgba(255,255,255,0.5);
    animation: scaleIn 0.5s var(--ease-spring);
}
#agreement-panel h1 { color: var(--c-text-1) !important; text-align: center; }

/* --- 分隔线 --- */
.divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--c-border), transparent);
    margin: 24px 0;
}

/* --- Markdown 微调 --- */
.prose h2 {
    font-size: 20px !important; font-weight: 700 !important;
    color: var(--c-text-1) !important; margin-bottom: 20px !important;
    letter-spacing: -0.3px !important;
}
.prose h3 {
    font-size: 16px !important; font-weight: 600 !important;
    color: var(--c-text-1) !important; margin-bottom: 14px !important;
}

/* --- Gradio 容器微调 --- */
.block { border: none !important; }
.gr-group {
    border-radius: var(--r-m) !important;
    border: 1px solid var(--c-border-light) !important;
}
.gr-box {
    border-radius: var(--r-m) !important;
    box-shadow: var(--shadow-s) !important;
}
.contain { gap: 14px !important; }

/* --- 匹配结果标签 --- */
.match-tags {
    display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0;
}
.match-tag {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 14px; border-radius: 20px; font-size: 13px;
    font-weight: 550;
    transition: all 0.25s var(--ease);
    cursor: default;
}
.match-tag:hover { transform: translateY(-1px); }
.match-tag.hit  {
    background: var(--c-success-bg); color: var(--c-success);
    border: 1px solid rgba(0,180,42,0.15);
}
.match-tag.miss {
    background: var(--c-danger-bg); color: var(--c-danger);
    border: 1px solid rgba(245,63,63,0.15);
}
.match-tag.weak {
    background: var(--c-warning-bg); color: var(--c-warning);
    border: 1px solid rgba(255,125,0,0.15);
}

/* --- 信息卡片 --- */
.info-card {
    background: var(--c-bg-card);
    border-radius: var(--r-m);
    border: 1px solid var(--c-border-light);
    padding: 20px 24px;
    margin-bottom: 16px;
    transition: all 0.3s var(--ease);
    box-shadow: var(--shadow-s);
}
.info-card:hover { box-shadow: var(--shadow-m); }
.info-card .ic-row {
    display: flex; align-items: center; padding: 8px 0;
    font-size: 14px; color: var(--c-text-2);
}
.info-card .ic-label {
    width: 84px; color: var(--c-text-3);
    font-size: 13px; flex-shrink: 0; font-weight: 450;
}
.info-card .ic-value { color: var(--c-text-1); font-weight: 600; }

/* --- 分布图例 --- */
.legend-row {
    display: flex; align-items: center; gap: 10px;
    padding: 7px 0; font-size: 13px; color: var(--c-text-2);
}
.legend-dot {
    width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0;
}

/* --- Gradio Slider --- */
input[type="range"] {
    accent-color: var(--c-primary) !important;
}

/* --- Gradio File Upload --- */
.upload-container {
    border-radius: var(--r-m) !important;
    border: 2px dashed var(--c-border) !important;
    transition: all 0.3s var(--ease) !important;
}
.upload-container:hover {
    border-color: var(--c-primary) !important;
    background: var(--c-primary-bg) !important;
}

/* --- Form & Page Alignment Fixes --- */

/* Row items align at bottom so inputs and buttons line up */
#main-tabs .row {
    align-items: flex-end !important;
}

/* Consistent section heading spacing */
#main-tabs .prose h2 {
    margin-top: 0 !important;
    margin-bottom: 20px !important;
    padding-top: 4px !important;
}
#main-tabs .prose h3 {
    margin-top: 24px !important;
    margin-bottom: 12px !important;
}

/* Non-interactive textbox polish */
.gr-textbox textarea[disabled],
.gr-textbox input[disabled],
input[readonly], textarea[readonly] {
    background: #F7F8FA !important;
    cursor: default !important;
    border-color: var(--c-border-light) !important;
}

/* Dataframe polish */
.gr-dataframe {
    margin: 4px 0 8px !important;
}

/* Slider track 顶部留白 — 实际外观由后续 #main-tabs 美化块控制 */
.gr-slider input[type="range"] {
    margin-top: 4px !important;
    background: transparent !important;
}

/* Button row consistent sizing */
#main-tabs .row button {
    min-height: 42px !important;
}

/* Alert bar first-child no top margin */
.alert-bar:first-child {
    margin-top: 0;
}

/* Fix Gradio block internal padding consistency */
#main-tabs > .tabitem .block {
    padding: 0 !important;
}

/* --- 响应式 --- */
/* 1024–1199: 顶栏副标题先收起, 留白给版本/铃铛/用户菜单 */
@media (max-width: 1199px) {
    .app-header-bar { padding: 0 18px !important; }
    .app-header-bar .bc { display: none !important; }
    .app-header-bar .hd { display: none !important; }
    .app-header-bar .hr { gap: 12px !important; }
}
/* 900px: 侧栏图标化 (保留原 60px 折叠) */
@media (max-width: 900px) {
    #main-tabs > .tab-wrapper {
        width: 60px !important; min-width: 60px !important; max-width: 60px !important;
        overflow: hidden !important;
    }
    #main-tabs > .tab-wrapper::before {
        content: '\\1F916'; font-size: 18px;
        padding: 0 12px 14px; text-align: center;
    }
    #main-tabs > .tab-wrapper .tab-container button {
        font-size: 0 !important; padding: 0 !important;
        text-indent: -9999px !important;
        justify-content: center !important;
    }
    .data-cards { grid-template-columns: repeat(2, 1fr); }
    /* 顶栏 logo 缩短 */
    .app-header-bar .logo-text { font-size: 14px !important; }
}
/* 720px (大手机): 侧栏默认完全收起, 通过 .haju-nav-open 滑出抽屉 */
@media (max-width: 720px) {
    /* 1) 默认整条侧栏滑出屏幕外, 用 transform 而非 display, 保留状态 + 流畅过渡 */
    #main-tabs > .tab-wrapper {
        position: fixed !important;
        z-index: 1000 !important;
        top: 48px !important; left: 0 !important;
        bottom: 0 !important; height: calc(100vh - 48px) !important;
        width: 240px !important; min-width: 240px !important; max-width: 240px !important;
        overflow-y: auto !important;
        transform: translateX(-100%) !important;
        transition: transform 0.28s cubic-bezier(.4,0,.2,1) !important;
        background: linear-gradient(180deg,
            rgba(18,16,46,0.96) 0%,
            rgba(13,11,36,0.96) 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
        box-shadow: 8px 0 32px rgba(0,0,0,0.55) !important;
    }
    /* 2) 标签文本恢复显示 (drawer 模式下要看得到名字) */
    #main-tabs > .tab-wrapper .tab-container button {
        font-size: 14px !important; padding: 0 16px !important;
        text-indent: 0 !important; justify-content: flex-start !important;
        color: rgba(230,233,245,0.85) !important;
    }
    #main-tabs > .tab-wrapper .tab-container button:hover {
        color: #FFFFFF !important;
        background: rgba(79,139,255,0.15) !important;
    }
    #main-tabs > .tab-wrapper .tab-container button.selected {
        color: #FFFFFF !important;
    }
    #main-tabs > .tab-wrapper::before {
        content: '\\1F916  智能管家' !important; font-size: 14px !important;
        text-align: left !important; padding: 16px 20px 14px !important;
        color: rgba(230,233,245,0.95) !important;
        border-bottom: 1px solid rgba(255,255,255,0.07) !important;
    }
    /* 3) 打开态 — 必须放在 #main-tabs 上, 因为 Gradio 的 CSS 作用域会
        给所有规则前置 ".gradio-container .contain", 而 body 不在该祖先链
        内, 所以 body.haju-nav-open 永远不会匹配. */
    #main-tabs.haju-nav-open > .tab-wrapper { transform: translateX(0) !important; }
    /* 4) 半透明遮罩, 点击关闭 (挂在 #main-tabs::after) */
    #main-tabs.haju-nav-open::after {
        content: '';
        position: fixed; inset: 48px 0 0 0;
        background: rgba(0,0,0,0.42);
        backdrop-filter: blur(2px);
        z-index: 999;
    }
    /* 5) 内容区不受遮罩影响 (避免水平滚动) */
    #main-tabs > .tabitem { width: 100% !important; padding: 16px !important; }
    /* 6) 汉堡按钮: 通过 ::before 注入到顶栏左侧 */
    .app-header-bar .hl::before {
        content: '';
        display: inline-block;
        width: 22px; height: 18px;
        margin-right: 10px;
        background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>');
        background-size: contain; background-repeat: no-repeat;
        background-position: center;
        cursor: pointer;
    }
    .app-header-bar .hl { cursor: pointer; }
}
/* 768px: 顶栏更紧凑, 可选隐藏文字 logo (改为符号), 用户名只留 avatar */
@media (max-width: 768px) {
    .app-header-bar {
        padding: 0 12px !important;
        height: 48px !important;
    }
    .app-header-bar .logo-text {
        max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        font-size: 13px !important;
    }
    .app-header-bar .ver { padding: 2px 7px !important; font-size: 10px !important; }
    .app-header-bar .header-user-name { display: none !important; }
    .app-header-bar .header-user-arrow { display: none !important; }
    .app-header-bar .header-user-trigger { padding: 6px !important; }
    .app-header-bar .header-bell-trigger { padding: 6px !important; }
}
/* 540px (手机): 进一步收缩, 只留 logo + bell + avatar */
@media (max-width: 540px) {
    .app-header-bar { padding: 0 8px !important; height: 44px !important; }
    .app-header-bar .logo-text { font-size: 12px !important; max-width: 80px; }
    .app-header-bar .ver { display: none !important; }
}
"""
# fmt: on

# fmt: off
DARK_OVERRIDE_CSS = """
/* ================================================================
   DARK THEME OVERRIDE V1 — Raycast-inspired 统一暗色主题
   以 !important + 级联后置 双重保险覆盖原浅色主题。
   保留所有原 class 名 / elem_id, 7 个页面的 Python 代码零改动。
   ================================================================ */

/* --- Design Tokens 重定义 --- */
:root {
    --c-primary: #4F8BFF;
    --c-primary-light: #6AA1FF;
    --c-primary-lighter: #8DBBFF;
    --c-primary-dark: #2763EA;
    --c-primary-bg: rgba(79,139,255,0.14);

    --c-success: #34D399;
    --c-success-bg: rgba(52,211,153,0.14);
    --c-warning: #FB923C;
    --c-warning-bg: rgba(251,146,60,0.14);
    --c-danger: #F87171;
    --c-danger-bg: rgba(248,113,113,0.14);

    --c-text-1: #F0F2FA;
    --c-text-2: rgba(230,233,245,0.85);
    --c-text-3: rgba(230,233,245,0.55);
    --c-text-4: rgba(230,233,245,0.35);
    --c-bg-page: #141838;
    --c-bg-card: rgba(255,255,255,0.045);
    --c-border: rgba(255,255,255,0.08);
    --c-border-light: rgba(255,255,255,0.05);
    --shadow-s: 0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);
    --shadow-m: 0 4px 12px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3);
    --shadow-l: 0 8px 24px rgba(0,0,0,0.55), 0 4px 12px rgba(0,0,0,0.35);
    --shadow-xl: 0 16px 48px rgba(0,0,0,0.6), 0 6px 18px rgba(0,0,0,0.4);
}

/* --- 全局背景 (淡化基调 + 把星云全权交给 .bg-fx) --- */
html, body {
    background: transparent !important;
    color: var(--c-text-2) !important;
    min-height: 100vh;
}
body {
    /* 基调: 不带任何颜色层, 让 .bg-fx 的 aurora 直接发色 */
    background: linear-gradient(160deg, #1E2359 0%, #251C64 50%, #2F1872 100%) !important;
}
gradio-app, .gradio-container, .main, main, .app {
    background: transparent !important;
    color: var(--c-text-2) !important;
}
.gradio-container {
    position: relative !important;
    z-index: 1 !important;
}
/* 内容层永远在粒子层之上 */
.gradio-container > *,
#app-container,
#login-panel,
#agreement-panel,
#main-panel,
#main-tabs {
    position: relative !important;
    z-index: 2 !important;
}
/* 顶部通栏: 必须在所有内容之上, 这样下拉菜单/通知面板才不会被 Bento 卡盖住 */
.app-header-bar {
    position: relative !important;
    z-index: 60 !important;
}

/* 禁掉原来那个静态点阵 (交给 .bg-fx 动态层) */
body::before { display: none !important; }

/* =========================================================
   动态粒子背景层 (.bg-fx)
   ---------------------------------------------------------
   结构:
     .bg-fx           外壳, position:fixed, 覆盖全屏
       .aurora        3 束星云 (慢速漂浮 + 呼吸)
       .grid-fade     淡点阵 (带 radial mask)
       .pt * N        50 颗闪烁星点 (twinkle + drift)
       .comet * 3     3 条流星拖尾 (periodic sweep)
   ========================================================= */
.bg-fx {
    position: fixed !important;
    inset: 0 !important;
    z-index: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
}

/* --- 星云漂浮 (普通 alpha 合成 + 低饱和柔色 + 中等模糊) --- */
.bg-fx .aurora {
    position: absolute;
    border-radius: 50%;
    filter: blur(64px) saturate(60%);
    opacity: 0.78;
    will-change: transform;
}
.bg-fx .a1 {
    width: 720px; height: 720px;
    top: -6%; left: -8%;
    background: radial-gradient(closest-side,
        rgba(167,139,250,1) 0%,
        rgba(167,139,250,0.55) 40%,
        rgba(167,139,250,0.12) 70%,
        transparent 85%);
    animation: auroraFloat1 26s ease-in-out infinite alternate;
}
.bg-fx .a2 {
    width: 660px; height: 660px;
    top: 8%; right: -8%;
    background: radial-gradient(closest-side,
        rgba(79,139,255,1) 0%,
        rgba(79,139,255,0.55) 40%,
        rgba(79,139,255,0.12) 70%,
        transparent 85%);
    animation: auroraFloat2 22s ease-in-out infinite alternate;
}
.bg-fx .a3 {
    width: 600px; height: 600px;
    bottom: -120px; left: 28%;
    background: radial-gradient(closest-side,
        rgba(52,211,153,1) 0%,
        rgba(52,211,153,0.52) 40%,
        rgba(52,211,153,0.10) 70%,
        transparent 85%);
    animation: auroraFloat3 30s ease-in-out infinite alternate;
}
.bg-fx .a4 {
    width: 540px; height: 540px;
    top: 48%; left: 4%;
    background: radial-gradient(closest-side,
        rgba(244,114,182,1) 0%,
        rgba(244,114,182,0.50) 40%,
        rgba(244,114,182,0.10) 70%,
        transparent 85%);
    animation: auroraFloat4 28s ease-in-out infinite alternate;
}
@keyframes auroraFloat1 {
    0%   { transform: translate(0,0) scale(1); }
    50%  { transform: translate(-8vw, 12vh) scale(1.12); }
    100% { transform: translate(12vw, -6vh) scale(0.94); }
}
@keyframes auroraFloat2 {
    0%   { transform: translate(0,0) scale(1); }
    50%  { transform: translate(8vw, -8vh) scale(1.08); }
    100% { transform: translate(-10vw, 10vh) scale(1.16); }
}
@keyframes auroraFloat3 {
    0%   { transform: translate(0,0) scale(1); }
    50%  { transform: translate(-6vw, -10vh) scale(1.10); }
    100% { transform: translate(14vw, 4vh) scale(0.96); }
}
@keyframes auroraFloat4 {
    0%   { transform: translate(0,0) scale(1); }
    50%  { transform: translate(10vw, 6vh) scale(1.12); }
    100% { transform: translate(-6vw, -8vh) scale(0.92); }
}

/* --- 淡点阵 (用 radial mask 做顶部渐隐) --- */
.bg-fx .grid-fade {
    position: absolute; inset: 0;
    background-image: radial-gradient(rgba(255,255,255,0.055) 1px, transparent 1px);
    background-size: 26px 26px;
    mask-image: radial-gradient(ellipse at 50% 35%, black 0%, transparent 85%);
    -webkit-mask-image: radial-gradient(ellipse at 50% 35%, black 0%, transparent 85%);
    opacity: 0.55;
}

/* --- 闪烁星点 (twinkle + slow drift) --- */
.bg-fx .pt {
    position: absolute;
    border-radius: 50%;
    opacity: 0;
    will-change: opacity, transform;
    animation-name: ptTwinkle;
    animation-timing-function: ease-in-out;
    animation-iteration-count: infinite;
}
@keyframes ptTwinkle {
    0%   { opacity: 0;   transform: scale(0.5) translateY(0); }
    20%  { opacity: 0.95; transform: scale(1.2) translateY(-4px); }
    50%  { opacity: 0.35; transform: scale(1)   translateY(-2px); }
    78%  { opacity: 1;   transform: scale(1.15) translateY(-6px); }
    100% { opacity: 0;   transform: scale(0.5) translateY(0); }
}

/* --- 流星拖尾 (长斜扫过 + 头部光点)
   ---------------------------------------------------------
   关键: 拖尾方向 = 运动方向
     * --cang: 拖尾旋转角 (正 = 顺时针, 在屏幕上表现为向右下倾斜)
     * --cdx:  水平位移 (100vw + padding)
     * --cdy:  垂直位移 = cdx * tan(cang), 使终点向量 == 拖尾方向
   这样流星头部的运动矢量和拖尾线条始终共线.
   ========================================================= */
.bg-fx .comet {
    position: absolute;
    left: -220px;
    width: 200px; height: 1.8px;
    --cdx: calc(100vw + 320px);
    --cdy: calc(var(--cdx) * tan(var(--cang, 6deg)));
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(141,187,255,0.55) 25%,
        rgba(221,214,254,0.85) 70%,
        rgba(255,255,255,1) 95%,
        rgba(255,255,255,0.98) 100%);
    border-radius: 2px;
    filter: drop-shadow(0 0 6px rgba(141,187,255,0.9));
    opacity: 0;
    transform: rotate(var(--cang, 6deg));
    animation-name: cometTravel;
    animation-duration: var(--cdur, 18s);
    animation-delay: var(--cdelay, 0s);
    animation-iteration-count: infinite;
    animation-timing-function: linear;
    transform-origin: 0% 50%;
}
.bg-fx .comet::after {
    content: '';
    position: absolute; right: -3px; top: -3.6px;
    width: 8px; height: 8px; border-radius: 50%;
    background: radial-gradient(circle, #fff 0%, rgba(221,214,254,0.9) 40%, transparent 80%);
    filter: drop-shadow(0 0 8px #fff) drop-shadow(0 0 14px rgba(141,187,255,0.9));
}
@keyframes cometTravel {
    0%   { transform: translate(0, 0) rotate(var(--cang, 6deg)); opacity: 0; }
    3%   { opacity: 1; }
    26%  { opacity: 1; }
    42%  { transform: translate(var(--cdx), var(--cdy)) rotate(var(--cang, 6deg)); opacity: 0; }
    100% { transform: translate(var(--cdx), var(--cdy)) rotate(var(--cang, 6deg)); opacity: 0; }
}

/* ---------- 粒子性能降级矩阵 ----------
   1. 中屏 (≤1280): 隐藏 1/3 粒子, 流星减半
   2. 移动端 (≤720): 隐藏 1/2 粒子 + 流星完全关闭
   3. 极小屏 (≤480): 关掉所有 .pt + 流星, 只保留 aurora
   4. body.haju-low-fx (JS 自动加): 整张 .bg-fx 直接 hide 动画, 仅留淡淡 aurora
   5. prefers-reduced-motion: 全部静止 + 降透明度
*/
@media (max-width: 1280px) {
    .bg-fx .pt:nth-child(3n) { display: none; }
    .bg-fx .comet:nth-child(odd) { display: none; }
    .bg-fx .aurora { filter: blur(58px) saturate(60%); opacity: 0.7; }
}
@media (max-width: 720px) {
    .bg-fx .pt:nth-child(2n) { display: none; }
    .bg-fx .comet { display: none !important; }
    .bg-fx .aurora { filter: blur(54px) saturate(55%); opacity: 0.62; }
}
@media (max-width: 480px) {
    .bg-fx .pt { display: none !important; }
    .bg-fx .grid-fade { opacity: 0.3; }
    .bg-fx .aurora { filter: blur(48px) saturate(50%); opacity: 0.55; }
}
/* JS 检测到弱设备 / 后台 / electron 卡顿时挂上 .haju-low-fx */
/* 注意: 由于 Gradio 把所有规则前置 .gradio-container .contain,
   而 body 不在该祖先链内, 所以 body.* 类名无法选中 .bg-fx.
   这里同时支持 body 和 #bg-fx-slot (它本身在 .contain 内). */
body.haju-low-fx .bg-fx .pt,
body.haju-low-fx .bg-fx .comet,
#bg-fx-slot.haju-low-fx .bg-fx .pt,
#bg-fx-slot.haju-low-fx .bg-fx .comet { display: none !important; }
body.haju-low-fx .bg-fx .aurora,
#bg-fx-slot.haju-low-fx .bg-fx .aurora {
    animation: none !important; filter: blur(40px) saturate(50%) !important;
    opacity: 0.45 !important;
}
body.haju-low-fx .bg-fx .grid-fade,
#bg-fx-slot.haju-low-fx .bg-fx .grid-fade { opacity: 0.25 !important; }
/* 后台标签页时直接停止动画 (节能 + 防 GPU 撞墙) */
body.haju-bg-pause .bg-fx .pt,
body.haju-bg-pause .bg-fx .comet,
body.haju-bg-pause .bg-fx .aurora,
#bg-fx-slot.haju-bg-pause .bg-fx .pt,
#bg-fx-slot.haju-bg-pause .bg-fx .comet,
#bg-fx-slot.haju-bg-pause .bg-fx .aurora { animation-play-state: paused !important; }
/* 尊重减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
    .bg-fx .aurora,
    .bg-fx .pt,
    .bg-fx .comet { animation: none !important; opacity: 0.3 !important; }
}

/* --- 顶部通栏 --- */
.app-header-bar {
    background: linear-gradient(135deg, rgba(18,14,48,0.7) 0%, rgba(12,10,34,0.55) 100%) !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    backdrop-filter: blur(20px) saturate(130%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(130%) !important;
}
.app-header-bar::after {
    background: linear-gradient(90deg, var(--c-primary), #A873F5, transparent 70%) !important;
    opacity: 0.55 !important;
}
.app-header-bar .logo-text {
    background: linear-gradient(135deg, #8DBBFF, #FFD1E4) !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}
.app-header-bar .hd {
    background: linear-gradient(180deg, transparent, rgba(255,255,255,0.14), transparent) !important;
}
.app-header-bar .bc { color: var(--c-text-3) !important; }
.app-header-bar .hr { color: var(--c-text-2) !important; }
.app-header-bar .ver {
    background: rgba(79,139,255,0.15) !important;
    color: var(--c-primary-light) !important;
    border: 1px solid rgba(79,139,255,0.3) !important;
}

/* --- 左侧导航 --- */
#main-tabs > .tab-wrapper {
    background: linear-gradient(180deg, rgba(12,10,34,0.75) 0%, rgba(18,14,48,0.55) 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    border-bottom: none !important;
    border-top: none !important;
    border-left: none !important;
    backdrop-filter: blur(20px) saturate(130%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(130%) !important;
    box-shadow: 4px 0 16px rgba(0,0,0,0.3) !important;
    --block-border-color: transparent !important;
    --border-color-primary: transparent !important;
}
#main-tabs > .tab-wrapper > .tab-container {
    border: none !important;
    --block-border-color: transparent !important;
    --border-color-primary: transparent !important;
}
#main-tabs > .tab-wrapper,
#main-tabs > .tab-wrapper > .tab-container,
#main-tabs > .tab-wrapper > .tab-container > * {
    border-bottom-color: transparent !important;
    border-top-color: transparent !important;
}
#main-tabs.tabs {
    border: none !important;
    --block-border-color: transparent !important;
}
#main-tabs > .tab-wrapper::before {
    color: var(--c-text-1) !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
}
#main-tabs > .tab-wrapper .tab-container button {
    color: var(--c-text-3) !important;
    position: relative !important;
    transition: background 0.22s ease, color 0.22s ease,
                transform 0.22s cubic-bezier(0.2,0.8,0.2,1),
                box-shadow 0.22s ease, padding-left 0.22s ease !important;
    overflow: hidden !important;
}
/* hover 累积态: 半透明渐变 + 左侧 accent bar 滑入 */
#main-tabs > .tab-wrapper .tab-container button::before {
    content: '';
    position: absolute;
    left: 0; top: 50%;
    width: 3px; height: 0;
    background: linear-gradient(180deg, rgba(79,139,255,0.55),
                                       rgba(168,115,245,0.55));
    border-radius: 0 3px 3px 0;
    transform: translateY(-50%);
    transition: height 0.28s cubic-bezier(0.2,0.8,0.2,1),
                background 0.22s ease, box-shadow 0.22s ease;
    z-index: 1;
    pointer-events: none;
}
#main-tabs > .tab-wrapper .tab-container button:hover {
    background: linear-gradient(90deg, rgba(79,139,255,0.10),
                                      rgba(255,255,255,0.04) 60%,
                                      transparent) !important;
    color: var(--c-text-1) !important;
    padding-left: 18px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04) !important;
}
#main-tabs > .tab-wrapper .tab-container button:hover::before {
    height: 22px;
    background: linear-gradient(180deg, var(--c-primary-light),
                                       #C7AEFF) !important;
    box-shadow: 0 0 8px rgba(79,139,255,0.38);
}
#main-tabs > .tab-wrapper .tab-container button.selected {
    background: linear-gradient(135deg, rgba(79,139,255,0.22),
                                       rgba(168,115,245,0.16)) !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 12px rgba(79,139,255,0.25),
                0 1px 0 rgba(255,255,255,0.08) inset !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}
#main-tabs > .tab-wrapper .tab-container button.selected::before {
    height: 22px;
    background: linear-gradient(180deg, var(--c-primary-light), #FFD1E4) !important;
    box-shadow: 0 0 10px rgba(79,139,255,0.55) !important;
}

/* --- Cards 通用 (card / info-card / data-card 统一玻璃) --- */
.card, .info-card {
    background: rgba(255,255,255,0.045) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    backdrop-filter: blur(20px) saturate(130%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(130%) !important;
    box-shadow: 0 1px 0 rgba(255,255,255,0.06) inset, 0 8px 24px rgba(0,0,0,0.3) !important;
    transition: transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 0.32s ease,
                background 0.28s ease,
                border-color 0.28s ease !important;
    will-change: transform;
}
.card:hover, .info-card:hover {
    background: rgba(255,255,255,0.07) !important;
    border-color: rgba(255,255,255,0.18) !important;
    transform: translateY(-3px) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.10) inset,
        0 18px 48px rgba(0,0,0,0.55),
        0 6px 18px rgba(79,139,255,0.12) !important;
}
.info-card .ic-row { color: var(--c-text-2) !important; }
.info-card .ic-label { color: var(--c-text-3) !important; }
.info-card .ic-value { color: var(--c-text-1) !important; }

/* --- Alert bars --- */
.alert-bar {
    background: rgba(251,146,60,0.12) !important;
    border: 1px solid rgba(251,146,60,0.32) !important;
    border-left: 4px solid #FB923C !important;
    color: #FDBA74 !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
}
.alert-bar.success {
    background: rgba(52,211,153,0.12) !important;
    border-color: rgba(52,211,153,0.32) !important;
    border-left-color: #34D399 !important;
    color: #6EE7B7 !important;
}
.alert-bar.info {
    background: rgba(79,139,255,0.12) !important;
    border-color: rgba(79,139,255,0.32) !important;
    border-left-color: #4F8BFF !important;
    color: #93C5FD !important;
}
.alert-bar.error {
    background: rgba(248,113,113,0.12) !important;
    border-color: rgba(248,113,113,0.32) !important;
    border-left-color: #F87171 !important;
    color: #FCA5A5 !important;
}
.alert-bar strong { color: #FFFFFF !important; }

/* --- Status tags --- */
.status-tag { border: 1px solid transparent !important; }
.tag-blue   { background: rgba(96,165,250,0.16) !important; color: #93C5FD !important; border-color: rgba(96,165,250,0.32) !important; }
.tag-green  { background: rgba(52,211,153,0.16) !important; color: #6EE7B7 !important; border-color: rgba(52,211,153,0.32) !important; }
.tag-orange { background: rgba(251,146,60,0.16) !important; color: #FDBA74 !important; border-color: rgba(251,146,60,0.32) !important; }
.tag-red    { background: rgba(248,113,113,0.16) !important; color: #FCA5A5 !important; border-color: rgba(248,113,113,0.32) !important; }
.tag-gray   { background: rgba(148,163,184,0.16) !important; color: #CBD5E1 !important; border-color: rgba(148,163,184,0.32) !important; }

/* --- Match tags --- */
.match-tag.hit  {
    background: rgba(52,211,153,0.14) !important;
    color: #6EE7B7 !important;
    border-color: rgba(52,211,153,0.32) !important;
}
.match-tag.miss {
    background: rgba(248,113,113,0.14) !important;
    color: #FCA5A5 !important;
    border-color: rgba(248,113,113,0.32) !important;
}
.match-tag.weak {
    background: rgba(251,146,60,0.14) !important;
    color: #FDBA74 !important;
    border-color: rgba(251,146,60,0.32) !important;
}

/* --- Inputs / Textarea / Select --- */
input[type="text"], input[type="password"], input[type="number"], input[type="email"],
textarea, select, .gr-text-input {
    background: rgba(255,255,255,0.045) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: var(--c-text-1) !important;
    caret-color: var(--c-primary-light) !important;
}
input::placeholder, textarea::placeholder {
    color: rgba(230,233,245,0.32) !important;
}
input:focus, textarea:focus, select:focus {
    background: rgba(255,255,255,0.065) !important;
    border-color: var(--c-primary) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.18),
                0 2px 8px rgba(79,139,255,0.08) !important;
}
input[readonly], textarea[readonly],
.gr-textbox input[disabled], .gr-textbox textarea[disabled] {
    background: rgba(255,255,255,0.025) !important;
    color: rgba(230,233,245,0.55) !important;
    border-color: rgba(255,255,255,0.06) !important;
}
label span {
    color: var(--c-text-2) !important;
    background: none !important;
}

/* --- Dropdown (Gradio) — 暗色高对比, 防止白底 + 白字不可读 --- */
.gr-dropdown,
[data-testid*="dropdown"] ul,
[data-testid="dropdown"] [role="listbox"],
[data-testid="dropdown"] .options,
.gradio-container .gradio-dropdown ul {
    background: rgba(22,18,52,0.98) !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    color: var(--c-text-1) !important;
    backdrop-filter: blur(20px) saturate(140%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(140%) !important;
    box-shadow: 0 18px 48px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06) inset !important;
    border-radius: 12px !important;
    padding: 4px !important;
    max-height: 360px !important;
    overflow-y: auto !important;
}
[role="listbox"] li,
[role="option"],
[data-testid="dropdown"] li,
[data-testid="dropdown"] .item,
ul[role="listbox"] > li {
    color: var(--c-text-2) !important;
    background: transparent !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    transition: background 0.15s ease, color 0.15s ease;
    cursor: pointer;
}
[role="listbox"] li:hover,
[role="option"]:hover,
[role="option"][aria-selected="true"],
[data-testid="dropdown"] li:hover,
[data-testid="dropdown"] .item:hover,
[data-testid="dropdown"] .item.selected {
    background: linear-gradient(135deg, rgba(79,139,255,0.25), rgba(167,139,250,0.18)) !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 0 rgba(255,255,255,0.08) inset;
}
/* Dropdown 触发输入框: 显示当前值 — 必须可读 (常见 bug: 暗背景 + 黑字) */
[data-testid="dropdown"] input,
[data-testid="dropdown"] .wrap-inner input,
.gr-dropdown input,
.gradio-dropdown input {
    color: var(--c-text-1) !important;
    background: rgba(17,22,48,0.5) !important;
    border-color: rgba(255,255,255,0.10) !important;
    caret-color: var(--c-primary-light) !important;
}
[data-testid="dropdown"] input::placeholder,
.gr-dropdown input::placeholder {
    color: rgba(230,233,245,0.40) !important;
    opacity: 1 !important;
}
/* Dropdown 内的 单 item / token (单选 chip) */
[data-testid="dropdown"] .single-select,
[data-testid="dropdown"] .token,
[data-testid="dropdown"] .selected-text {
    color: var(--c-text-1) !important;
}
/* 箭头颜色 */
[data-testid="dropdown"] svg,
.gr-dropdown svg.dropdown-arrow,
.dropdown-arrow {
    color: var(--c-text-3) !important;
    fill: currentColor !important;
}

/* =================================================================
   Dropdown 触发器美化 (默认 Gradio 触发样式过于扁平)
   关键: 让闭合态像 "玻璃 pill" — 渐变背景 / 柔和 border / 自定义 caret
   ================================================================= */
#main-tabs .gradio-dropdown,
#main-tabs [data-testid="dropdown"],
#login-card .gradio-dropdown,
#login-card [data-testid="dropdown"] {
    border-radius: 12px !important;
}
#main-tabs .gradio-dropdown .wrap,
#main-tabs [data-testid="dropdown"] .wrap,
#main-tabs .wrap:has(> .wrap-inner),
#login-card .gradio-dropdown .wrap,
#login-card [data-testid="dropdown"] .wrap,
#login-card .wrap:has(> .wrap-inner) {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01)),
        rgba(17,22,48,0.55) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 12px !important;
    min-height: 44px !important;
    padding: 0 !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 1px 3px rgba(0,0,0,0.18) !important;
    transition: border-color 0.2s ease, box-shadow 0.25s ease,
                background 0.25s ease, transform 0.18s ease !important;
}
#main-tabs .gradio-dropdown .wrap:hover,
#main-tabs [data-testid="dropdown"] .wrap:hover,
#main-tabs .wrap:has(> .wrap-inner):hover {
    border-color: rgba(141,187,255,0.45) !important;
    background:
        linear-gradient(180deg, rgba(79,139,255,0.10), rgba(168,115,245,0.05)),
        rgba(17,22,48,0.65) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.08),
        0 4px 14px rgba(79,139,255,0.18) !important;
}
#main-tabs .gradio-dropdown .wrap:focus-within,
#main-tabs [data-testid="dropdown"] .wrap:focus-within,
#main-tabs .wrap:has(> .wrap-inner):focus-within,
#login-card .gradio-dropdown .wrap:focus-within {
    border-color: rgba(141,187,255,0.85) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.12),
        0 0 0 3px rgba(79,139,255,0.20),
        0 6px 18px rgba(79,139,255,0.25) !important;
    background:
        linear-gradient(180deg, rgba(79,139,255,0.14), rgba(168,115,245,0.08)),
        rgba(17,22,48,0.7) !important;
}
#main-tabs .gradio-dropdown .wrap-inner,
#main-tabs [data-testid="dropdown"] .wrap-inner,
#main-tabs .wrap > .wrap-inner,
#login-card .gradio-dropdown .wrap-inner,
#login-card [data-testid="dropdown"] .wrap-inner {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 8px 38px 8px 14px !important;
    min-height: 44px !important;
    border-radius: 12px !important;
}
#main-tabs .gradio-dropdown input,
#main-tabs [data-testid="dropdown"] input,
#main-tabs .wrap-inner input,
#login-card .gradio-dropdown input,
#login-card [data-testid="dropdown"] input {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: #F0F2FA !important;
    line-height: 1.4 !important;
}
/* 自定义下拉箭头: 用 SVG mask 覆盖 Gradio 默认 SVG */
#main-tabs .gradio-dropdown .wrap-inner::after,
#main-tabs [data-testid="dropdown"] .wrap-inner::after,
#main-tabs .wrap > .wrap-inner::after,
#login-card .gradio-dropdown .wrap-inner::after {
    content: '';
    position: absolute;
    right: 14px; top: 50%;
    transform: translateY(-50%) rotate(0deg);
    width: 14px; height: 14px;
    background: linear-gradient(135deg, #8DBBFF 0%, #C7B8FF 100%);
    -webkit-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>") center/contain no-repeat;
            mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>") center/contain no-repeat;
    transition: transform 0.25s cubic-bezier(0.2,0.8,0.2,1), background 0.2s ease;
    pointer-events: none;
    z-index: 2;
}
#main-tabs .gradio-dropdown .wrap-inner:focus-within::after,
#main-tabs [data-testid="dropdown"] .wrap-inner:focus-within::after,
#main-tabs .wrap > .wrap-inner:focus-within::after,
#login-card .gradio-dropdown .wrap-inner:focus-within::after,
#main-tabs [data-testid="dropdown"]:has(ul[role="listbox"]) .wrap-inner::after {
    transform: translateY(-50%) rotate(180deg);
    background: linear-gradient(135deg, #C7B8FF 0%, #8DBBFF 100%);
}
#main-tabs .gradio-dropdown .wrap-inner { position: relative !important; }
#main-tabs [data-testid="dropdown"] .wrap-inner { position: relative !important; }
#main-tabs .wrap > .wrap-inner { position: relative !important; }
#login-card .gradio-dropdown .wrap-inner { position: relative !important; }
/* 隐藏 Gradio 自带的箭头 svg, 让我们的 ::after 接管 */
#main-tabs .gradio-dropdown svg.dropdown-arrow,
#main-tabs [data-testid="dropdown"] .icon-wrap svg,
#main-tabs [data-testid="dropdown"] .wrap-inner > svg,
#main-tabs .wrap > .wrap-inner > svg,
#main-tabs .wrap-inner > .icon-wrap,
#login-card .gradio-dropdown svg.dropdown-arrow,
#login-card [data-testid="dropdown"] .icon-wrap svg {
    display: none !important;
}
/* 选项面板: 圆角更大, 阴影更深, hover 渐变更明显 */
[role="listbox"],
[data-testid="dropdown"] [role="listbox"],
[data-testid="dropdown"] .options,
.gradio-container .gradio-dropdown ul {
    background: rgba(20,16,46,0.97) !important;
    border: 1px solid rgba(141,187,255,0.22) !important;
    border-radius: 14px !important;
    padding: 6px !important;
    margin-top: 6px !important;
    box-shadow:
        0 24px 60px rgba(0,0,0,0.6),
        0 0 0 1px rgba(255,255,255,0.04) inset,
        0 2px 0 rgba(141,187,255,0.10) inset !important;
    backdrop-filter: blur(24px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
    animation: ddPanelEnter 0.18s cubic-bezier(0.2,0.8,0.2,1);
}
@keyframes ddPanelEnter {
    from { opacity: 0; transform: translateY(-4px) scale(0.98); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
[role="listbox"] li,
[role="option"],
[data-testid="dropdown"] li,
[data-testid="dropdown"] .item {
    color: rgba(230,233,245,0.88) !important;
    background: transparent !important;
    padding: 10px 12px !important;
    border-radius: 9px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    transition: background 0.15s ease, color 0.15s ease, transform 0.12s ease, padding-left 0.15s ease !important;
    cursor: pointer;
    position: relative;
}
[role="listbox"] li:hover,
[role="option"]:hover,
[data-testid="dropdown"] li:hover,
[data-testid="dropdown"] .item:hover {
    background: linear-gradient(135deg, rgba(79,139,255,0.20), rgba(168,115,245,0.14)) !important;
    color: #FFFFFF !important;
    padding-left: 16px !important;
}
[role="option"][aria-selected="true"],
[data-testid="dropdown"] .item.selected,
[data-testid="dropdown"] li[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(79,139,255,0.30), rgba(168,115,245,0.20)) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
[role="option"][aria-selected="true"]::before,
[data-testid="dropdown"] .item.selected::before,
[data-testid="dropdown"] li[aria-selected="true"]::before {
    content: '';
    position: absolute;
    left: 4px; top: 50%; transform: translateY(-50%);
    width: 3px; height: 60%;
    background: linear-gradient(180deg, #4F8BFF, #A873F5);
    border-radius: 2px;
}

/* --- Buttons --- */
button.primary, .gr-button-primary {
    background: linear-gradient(135deg, #4F8BFF 0%, #2763EA 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.15) inset,
        0 6px 20px rgba(79,139,255,0.35) !important;
}
button.primary:hover, .gr-button-primary:hover {
    background: linear-gradient(135deg, #6AA1FF 0%, #4785FF 100%) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.18) inset,
        0 10px 28px rgba(79,139,255,0.5) !important;
}
button.secondary, .gr-button-secondary {
    background: rgba(255,255,255,0.06) !important;
    color: var(--c-text-2) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    box-shadow: 0 1px 0 rgba(255,255,255,0.06) inset !important;
}
button.secondary:hover, .gr-button-secondary:hover {
    background: rgba(255,255,255,0.1) !important;
    color: var(--c-text-1) !important;
    border-color: rgba(255,255,255,0.2) !important;
    box-shadow: 0 1px 0 rgba(255,255,255,0.08) inset, 0 6px 20px rgba(0,0,0,0.35) !important;
}
button.stop, .gr-button-stop {
    background: rgba(248,113,113,0.12) !important;
    color: #FCA5A5 !important;
    border: 1px solid rgba(248,113,113,0.32) !important;
}
button.stop:hover, .gr-button-stop:hover {
    background: rgba(248,113,113,0.2) !important;
    color: #FFB4B4 !important;
    border-color: rgba(248,113,113,0.5) !important;
    box-shadow: 0 6px 20px rgba(248,113,113,0.25) !important;
}

/* --- Dataframe --- */
.gr-dataframe, .dataframe, .gradio-dataframe {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
}
.gr-dataframe th, .dataframe th, table thead th {
    background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.03)) !important;
    color: rgba(230,233,245,0.7) !important;
    border-bottom: 1px solid rgba(255,255,255,0.12) !important;
    font-size: 11.5px !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
}
.gr-dataframe td, .dataframe td, table tbody td {
    background: transparent !important;
    color: var(--c-text-2) !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}
table tbody tr:hover td {
    background: rgba(255,255,255,0.04) !important;
}

/* --- Custom-table (dashboard 原版旧表格) --- */
.custom-table { background: transparent !important; border: none !important; }
.custom-table th {
    background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.03)) !important;
    color: rgba(230,233,245,0.7) !important;
    border-bottom: 1px solid rgba(255,255,255,0.12) !important;
}
.custom-table td {
    color: var(--c-text-2) !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}
.custom-table tr:hover td { background: rgba(255,255,255,0.03) !important; }

/* --- Markdown 文字 --- */
.prose, .prose p, .prose li, .prose span:not([class]), .prose strong, .prose em {
    color: var(--c-text-2) !important;
}
.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6 {
    color: var(--c-text-1) !important;
}
.prose code {
    background: rgba(255,255,255,0.08) !important;
    color: #FFD1E4 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
}
.prose a { color: var(--c-primary-light) !important; }
.prose hr {
    border-top: 1px solid rgba(255,255,255,0.08) !important;
    background: transparent !important;
}
.prose blockquote {
    border-left: 3px solid var(--c-primary) !important;
    color: var(--c-text-2) !important;
    background: rgba(79,139,255,0.05) !important;
}

/* --- Gradio 容器透明化 --- */
.gr-group, .gr-box, .block, .form {
    background: transparent !important;
    border: none !important;
}
.gr-block-info, .gr-block-label { color: var(--c-text-3) !important; }
.gr-panel { background: transparent !important; }

/* --- Bar chart (records 页纯CSS柱状图) --- */
.bar-chart {
    background: linear-gradient(180deg, transparent, rgba(168,115,245,0.06)) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: var(--r-m) !important;
}
.bar-item .bar {
    background: linear-gradient(180deg, #A873F5 0%, #6E43D8 100%) !important;
    box-shadow:
        0 0 18px rgba(168,115,245,0.35),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.bar-item .bar:hover {
    background: linear-gradient(180deg, #C4B5FF 0%, #8B5FFF 100%) !important;
    box-shadow: 0 0 28px rgba(168,115,245,0.55) !important;
}
.bar-item .bv { color: var(--c-primary-light) !important; }
.bar-item .bl { color: var(--c-text-3) !important; }

/* --- Ring chart (jd_match + records 环形图) --- */
.ring-chart svg > circle:first-child {
    stroke: rgba(255,255,255,0.08) !important;
}
.ring-chart .rs { color: var(--c-text-1) !important; }
.ring-chart .rl { color: var(--c-text-3) !important; }

/* --- Step progress --- */
.step-dot {
    background: rgba(255,255,255,0.04) !important;
    border-color: rgba(255,255,255,0.1) !important;
    color: var(--c-text-3) !important;
}
.step-name { color: var(--c-text-3) !important; }
.step-line { background: rgba(255,255,255,0.08) !important; }

/* --- Progress bar --- */
.progress-bar-bg { background: rgba(255,255,255,0.08) !important; }

/* --- Legend (分布图例) --- */
.legend-row { color: var(--c-text-2) !important; }
.legend-row strong { color: var(--c-text-1) !important; }

/* --- Data-cards (Dashboard 旧四格, Bento 已替代, 但保险起见) --- */
.data-card {
    background: rgba(255,255,255,0.045) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    backdrop-filter: blur(20px) !important;
}
.data-card .dc-icon.blue   { background: rgba(79,139,255,0.15) !important; }
.data-card .dc-icon.green  { background: rgba(52,211,153,0.15) !important; }
.data-card .dc-icon.orange { background: rgba(251,146,60,0.15) !important; }
.data-card .dc-icon.gray   { background: rgba(148,163,184,0.15) !important; }
.data-card .dc-label { color: var(--c-text-3) !important; }
.data-card .dc-value { color: var(--c-text-1) !important; }
.data-card .dc-value.blue   { color: var(--c-primary-light) !important; }
.data-card .dc-value.green  { color: #6EE7B7 !important; }
.data-card .dc-value.orange { color: #FDBA74 !important; }

/* --- Settings 子 Tabs --- */
#settings-tabs > .tab-wrapper {
    border-bottom: 2px solid rgba(255,255,255,0.08) !important;
}
#settings-tabs > .tab-wrapper .tab-container button {
    color: var(--c-text-3) !important;
}
#settings-tabs > .tab-wrapper .tab-container button:hover {
    color: var(--c-primary-light) !important;
    background: rgba(79,139,255,0.06) !important;
}
#settings-tabs > .tab-wrapper .tab-container button.selected {
    color: var(--c-primary-light) !important;
    border-bottom-color: var(--c-primary-light) !important;
    background: rgba(79,139,255,0.08) !important;
}

/* --- 协议面板 --- */
#agreement-panel {
    background: rgba(255,255,255,0.05) !important;
    backdrop-filter: blur(20px) saturate(130%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(130%) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: 0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04) !important;
}
#agreement-panel h1, #agreement-panel h2, #agreement-panel h3 {
    color: var(--c-text-1) !important;
}

/* --- Divider --- */
.divider {
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent) !important;
}

/* --- Slider 兼容兜底 (实际外观见后续美化块) --- */
input[type="range"] {
    accent-color: var(--c-primary-light) !important;
}

/* --- Radio / Checkbox --- */
.gr-radio, .gr-checkbox {
    background: transparent !important;
}
.gr-radio label, .gr-checkbox label {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: var(--c-text-2) !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    transition: all 0.2s ease !important;
}
.gr-radio label:hover, .gr-checkbox label:hover {
    background: rgba(255,255,255,0.07) !important;
    border-color: rgba(255,255,255,0.14) !important;
}
.gr-radio input:checked + label,
.gr-radio label[data-selected="true"],
.gr-radio label.selected,
.gr-checkbox input:checked + label {
    background: linear-gradient(135deg, rgba(79,139,255,0.22), rgba(168,115,245,0.16)) !important;
    border-color: rgba(79,139,255,0.4) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(79,139,255,0.25), 0 1px 0 rgba(255,255,255,0.08) inset !important;
}

/* --- File Upload --- */
.upload-container, [data-testid="file-upload"], .file-preview-holder {
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(255,255,255,0.18) !important;
    color: var(--c-text-2) !important;
    border-radius: var(--r-m) !important;
}
.upload-container:hover {
    border-color: var(--c-primary) !important;
    background: rgba(79,139,255,0.08) !important;
}

/* --- Image block (boss 二维码) --- */
.gr-image, [data-testid="image"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: var(--r-m) !important;
}

/* ================================================================
   Scrollbar — 暗色玻璃 + 渐变拇指 (Webkit / Firefox)
   ----------------------------------------------------------------
   * Firefox 仅支持 scrollbar-width / scrollbar-color, 不支持 ::pseudo
     所以为它单独设一组高对比的 thumb / track 色, 再 hover 时切色.
   * Webkit (Chrome / Edge / Safari) 用渐变 thumb, hover 加亮.
   ================================================================ */

/* ---- 1) Firefox / 标准 — scrollbar-color 接收 "thumb track" ---- */
* {
    scrollbar-width: thin;
    scrollbar-color: rgba(168,115,245,0.55) rgba(255,255,255,0.04);
}
*:hover { scrollbar-color: rgba(168,115,245,0.85) rgba(255,255,255,0.06); }
/* 表格 / 代码块 等深色容器, 使用更亮的 thumb */
.dataframe, .gradio-dataframe, .gr-dataframe,
.svelte-virtual-table-viewport,
pre, code, textarea {
    scrollbar-width: thin;
    scrollbar-color: rgba(141,187,255,0.7) rgba(0,0,0,0.18);
}
/* Firefox 专属: 让 body / html 的滚动条变细 */
html, body { scrollbar-width: thin; }

/* ---- 2) Webkit — 渐变拇指, hover 加亮 ---- */
::-webkit-scrollbar {
    width: 10px !important;
    height: 10px !important;
    background: transparent !important;
}
::-webkit-scrollbar-track {
    background: transparent !important;
    margin: 4px;
}
::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg,
        rgba(79,139,255,0.45),
        rgba(168,115,245,0.45)) !important;
    border-radius: 999px !important;
    border: 2px solid transparent !important;
    background-clip: padding-box !important;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
    transition: background 0.2s ease;
}
::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg,
        rgba(79,139,255,0.7),
        rgba(168,115,245,0.7)) !important;
    background-clip: padding-box !important;
    border: 2px solid transparent !important;
}
::-webkit-scrollbar-thumb:active {
    background: linear-gradient(180deg, #4F8BFF, #A873F5) !important;
    background-clip: padding-box !important;
    border: 2px solid transparent !important;
}
::-webkit-scrollbar-corner { background: transparent !important; }

/* --- Logout row + button --- */
#logout-row {
    padding: 8px 28px !important;
    justify-content: flex-end !important;
}
#logout-btn {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: var(--c-text-3) !important;
    box-shadow: none !important;
}
#logout-btn:hover {
    background: rgba(248,113,113,0.12) !important;
    border-color: rgba(248,113,113,0.35) !important;
    color: #FCA5A5 !important;
}

/* --- Section title (h2/h3 增强) --- */
.section-title {
    color: var(--c-text-1) !important;
    border-bottom-color: rgba(255,255,255,0.08) !important;
}

/* --- Tab 内容区 --- */
#main-tabs > .tabitem {
    background: transparent !important;
    color: var(--c-text-2) !important;
}

/* --- 登录页覆盖 (login.py 定义了自己的 LOGIN_CSS) --- */
/* 让 body + .bg-fx 的星云穿透显示 */
#login-panel {
    background: transparent !important;
}
#login-container {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    backdrop-filter: blur(20px) saturate(130%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(130%) !important;
    box-shadow: 0 28px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04) !important;
}
#login-card {
    background: rgba(18,14,48,0.45) !important;
    color: var(--c-text-2) !important;
}
#login-card label span {
    color: rgba(230,233,245,0.8) !important;
}
#login-card input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: var(--c-text-1) !important;
}
#login-card input::placeholder {
    color: rgba(230,233,245,0.32) !important;
}
#login-card input:focus {
    background: rgba(255,255,255,0.065) !important;
    border-color: var(--c-primary) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.18) !important;
}
#login-card .login-title {
    color: var(--c-text-1) !important;
    -webkit-text-fill-color: var(--c-text-1) !important;
}
#login-card .login-subtitle {
    color: var(--c-text-3) !important;
}
#login-card .login-footer {
    color: var(--c-text-4) !important;
}
.login-error-text {
    color: #FCA5A5 !important;
    background: rgba(248,113,113,0.1) !important;
    border: 1px solid rgba(248,113,113,0.25) !important;
}
#login-btn {
    background: linear-gradient(135deg, #4F8BFF, #2763EA) !important;
    box-shadow: 0 6px 20px rgba(79,139,255,0.4),
                0 1px 0 rgba(255,255,255,0.15) inset !important;
}
#login-btn:hover {
    background: linear-gradient(135deg, #6AA1FF, #4785FF) !important;
    box-shadow: 0 10px 28px rgba(79,139,255,0.5),
                0 1px 0 rgba(255,255,255,0.18) inset !important;
}
/* ================================================================
   Header 用户下拉 + 通知铃铛 (升级版)
   ================================================================ */

/* 整体右侧栏 spacing */
.app-header-bar .hr { gap: 14px !important; }

/* ---- 用户头像 / 触发按钮 ---- */
.header-user-dropdown {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    user-select: none;
}
.header-user-trigger {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    padding: 5px 10px 5px 5px !important;
    border-radius: 999px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    background: rgba(255,255,255,0.04) !important;
    color: var(--c-text-2) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    line-height: 1 !important;
    transition: background 0.2s ease, border-color 0.2s ease,
                box-shadow 0.2s ease, transform 0.2s ease !important;
}
.header-user-trigger:hover {
    background: linear-gradient(135deg, rgba(79,139,255,0.18),
                                       rgba(168,115,245,0.14)) !important;
    border-color: rgba(79,139,255,0.35) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(79,139,255,0.22) !important;
    transform: translateY(-1px) !important;
}
.header-user-avatar {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 26px; height: 26px;
    border-radius: 999px;
    background: linear-gradient(135deg, #4F8BFF, #A873F5);
    color: #FFFFFF !important;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0;
    box-shadow: 0 2px 8px rgba(79,139,255,0.32),
                inset 0 1px 0 rgba(255,255,255,0.18);
    flex-shrink: 0;
    text-transform: uppercase;
}
.header-user-avatar-lg {
    width: 36px; height: 36px;
    font-size: 15px;
}
.header-user-name {
    color: inherit !important;
    font-weight: 600;
    letter-spacing: 0.2px;
    max-width: 96px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.header-user-arrow {
    color: rgba(255,255,255,0.55) !important;
    transition: transform 0.25s ease, color 0.2s ease;
}
.header-user-dropdown:hover .header-user-arrow {
    color: #FFFFFF !important;
    transform: rotate(180deg);
}

/* ---- 用户下拉菜单 ----
   关键: 菜单顶部用 14px 透明 padding 替代 top: calc(100% + 10px) 的 gap,
   让 trigger 与菜单视觉间距保持 10px, 但实际 hover 区连续, 不再断开. */
.header-user-menu {
    position: absolute !important;
    top: 100%;
    right: 0;
    min-width: 220px;
    padding: 14px 6px 6px 6px;
    margin-top: -4px;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    opacity: 0;
    pointer-events: none;
    transform: translateY(-6px) scale(0.98);
    transition: opacity 0.18s ease, transform 0.22s cubic-bezier(0.2,0.8,0.2,1);
    transform-origin: top right;
    z-index: 999;
}
/* 内部包裹容器才是真正的视觉卡片 */
.header-user-menu > .header-user-menu-card {
    position: relative;
    background: rgba(20,16,46,0.96);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    box-shadow: 0 18px 48px rgba(0,0,0,0.55),
                0 0 0 1px rgba(255,255,255,0.04),
                inset 0 1px 0 rgba(255,255,255,0.06);
    backdrop-filter: blur(22px) saturate(140%);
    -webkit-backdrop-filter: blur(22px) saturate(140%);
    padding: 6px;
}
.header-user-dropdown:hover .header-user-menu,
.header-user-dropdown:focus-within .header-user-menu,
.header-user-dropdown.open .header-user-menu {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0) scale(1);
}
.header-user-menu > .header-user-menu-card::before {
    content: '';
    position: absolute;
    top: -8px; right: 18px;
    width: 0; height: 0;
    border-left: 7px solid transparent;
    border-right: 7px solid transparent;
    border-bottom: 8px solid rgba(20,16,46,0.96);
    filter: drop-shadow(0 -1px 0 rgba(255,255,255,0.06));
}
.header-user-menu-item {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 10px 12px !important;
    border-radius: 8px;
    color: var(--c-text-2) !important;
    font-size: 13px !important;
    cursor: pointer;
    transition: background 0.18s ease, color 0.18s ease, transform 0.15s ease;
}
.header-user-menu-item:hover {
    background: rgba(79,139,255,0.14) !important;
    color: #FFFFFF !important;
    transform: translateX(2px);
}
.header-user-menu-item svg { flex-shrink: 0; opacity: 0.85; }
.header-user-menu-item:hover svg { opacity: 1; color: var(--c-primary-light); }
.header-user-info {
    color: var(--c-text-1) !important;
    cursor: default;
    background: rgba(255,255,255,0.04);
    padding: 12px !important;
    margin-bottom: 2px;
}
.header-user-info:hover {
    background: rgba(255,255,255,0.04) !important;
    color: var(--c-text-1) !important;
    transform: none;
}
.header-user-info-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.header-user-info-name {
    font-size: 13px; font-weight: 700;
    color: #FFFFFF !important;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 130px;
}
.header-user-info-sub {
    font-size: 11px; color: rgba(167,139,250,0.85) !important;
    letter-spacing: 0.3px;
}
.header-user-menu-divider {
    height: 1px;
    margin: 4px 0;
    background: rgba(255,255,255,0.08) !important;
}
.header-logout-item { color: #FCA5A5 !important; }
.header-logout-item:hover {
    background: rgba(248,113,113,0.14) !important;
    color: #FFB4B4 !important;
}
.header-logout-item:hover svg { color: #FCA5A5 !important; }

/* ---- 通知铃铛 ---- */
.header-bell-wrap {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    user-select: none;
}
.header-bell-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px; height: 34px;
    border-radius: 999px;
    color: rgba(230,233,245,0.95);
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    transition: background 0.2s ease, color 0.2s ease,
                border-color 0.2s ease, box-shadow 0.2s ease,
                transform 0.2s ease;
    position: relative;
}
/* SVG 子图形 (path/line/polyline/circle) 在头部 / 下拉菜单 / 通知面板内.
   Gradio 内置 CSS 会把 path 的 stroke 写死成 #1F2937 (深灰),
   通过 [class] 属性选择器再次叠加, 避免被覆盖. */
.app-header-bar [class*="header-bell-ico"],
.app-header-bar [class*="header-bell-ico"] path,
.app-header-bar [class*="header-bell-ico"] line,
.app-header-bar [class*="header-bell-ico"] polyline,
.app-header-bar [class*="header-bell-ico"] circle,
.app-header-bar [class*="header-user-arrow"],
.app-header-bar [class*="header-user-arrow"] path {
    stroke: #FFFFFF !important;
    fill: none !important;
}
.header-user-menu [class*="header-user-menu-item"] svg,
.header-user-menu [class*="header-user-menu-item"] svg path,
.header-user-menu [class*="header-user-menu-item"] svg line,
.header-user-menu [class*="header-user-menu-item"] svg polyline,
.header-user-menu [class*="header-user-menu-item"] svg circle {
    stroke: rgba(255,255,255,0.92) !important;
    fill: none !important;
}
.header-user-menu [class*="header-logout-item"] svg,
.header-user-menu [class*="header-logout-item"] svg path,
.header-user-menu [class*="header-logout-item"] svg line,
.header-user-menu [class*="header-logout-item"] svg polyline {
    stroke: #FCA5A5 !important;
}
.header-bell-panel [class*="header-bell-panel"] svg,
.header-bell-panel [class*="header-bell-panel"] svg path {
    stroke: rgba(255,255,255,0.92) !important;
    fill: none !important;
}
.app-header-bar .header-bell-trigger .header-bell-ico { opacity: 0.96; }
.app-header-bar .header-user-trigger .header-user-arrow {
    stroke: rgba(255,255,255,0.78) !important;
}
.header-bell-trigger:hover {
    background: rgba(79,139,255,0.16);
    color: #FFFFFF;
    border-color: rgba(79,139,255,0.38);
    box-shadow: 0 4px 14px rgba(79,139,255,0.24);
    transform: translateY(-1px);
}
.header-bell-ico { display: block; }
.header-bell-wrap:hover .header-bell-ico {
    animation: hbellShake 0.6s ease;
}
@keyframes hbellShake {
    0%,100% { transform: rotate(0); }
    20% { transform: rotate(12deg); }
    40% { transform: rotate(-10deg); }
    60% { transform: rotate(6deg); }
    80% { transform: rotate(-3deg); }
}
.header-bell-badge {
    position: absolute;
    top: -2px; right: -2px;
    min-width: 16px; height: 16px;
    padding: 0 4px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 800;
    line-height: 16px;
    text-align: center;
    color: #FFFFFF;
    background: linear-gradient(135deg, #FF5F8F, #C73075);
    border: 1.5px solid rgba(20,16,46,1);
    box-shadow: 0 2px 6px rgba(199,48,117,0.45);
    animation: hbellPulse 2.4s ease-in-out infinite;
}
@keyframes hbellPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.08); }
}

/* ---- 通知面板 ---- */
.header-bell-panel {
    position: absolute !important;
    top: 100%;
    right: 0;
    min-width: 280px;
    padding: 14px 6px 6px 6px;
    margin-top: -4px;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    opacity: 0;
    pointer-events: none;
    transform: translateY(-6px) scale(0.98);
    transition: opacity 0.18s ease, transform 0.22s cubic-bezier(0.2,0.8,0.2,1);
    transform-origin: top right;
    z-index: 999;
}
.header-bell-panel > .header-bell-panel-card {
    position: relative;
    background: rgba(20,16,46,0.96);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    box-shadow: 0 18px 48px rgba(0,0,0,0.55),
                0 0 0 1px rgba(255,255,255,0.04),
                inset 0 1px 0 rgba(255,255,255,0.06);
    backdrop-filter: blur(22px) saturate(140%);
    -webkit-backdrop-filter: blur(22px) saturate(140%);
    padding: 6px;
}
.header-bell-wrap:hover .header-bell-panel,
.header-bell-wrap:focus-within .header-bell-panel,
.header-bell-wrap.open .header-bell-panel {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0) scale(1);
}
.header-bell-panel > .header-bell-panel-card::before {
    content: '';
    position: absolute;
    top: -8px; right: 14px;
    width: 0; height: 0;
    border-left: 7px solid transparent;
    border-right: 7px solid transparent;
    border-bottom: 8px solid rgba(20,16,46,0.96);
}
.header-bell-panel-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 12px 8px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.hbell-head-title { color: #FFFFFF; font-weight: 700; font-size: 13px; letter-spacing: 0.3px; }
.hbell-head-link {
    color: var(--c-primary-light);
    font-size: 12px; font-weight: 600;
    cursor: pointer;
    padding: 2px 8px;
    border-radius: 6px;
    transition: background 0.18s ease, color 0.18s ease;
}
.hbell-head-link:hover {
    background: rgba(79,139,255,0.14);
    color: #FFFFFF;
}
.header-bell-panel-row {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    margin-top: 4px;
    cursor: pointer;
    transition: background 0.18s ease;
}
.header-bell-panel-row:hover { background: rgba(255,255,255,0.05); }
.header-bell-row-warn .hbell-row-dot {
    width: 8px; height: 8px;
    border-radius: 999px;
    background: #FCA5A5;
    box-shadow: 0 0 8px rgba(252,165,165,0.55);
    margin-top: 6px;
    flex-shrink: 0;
}
.hbell-row-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.hbell-row-title { color: #FFFFFF; font-size: 13px; font-weight: 600; }
.hbell-row-sub { color: rgba(230,233,245,0.6); font-size: 11px; letter-spacing: 0.2px; }
.header-bell-panel-empty {
    display: flex; flex-direction: column;
    align-items: center;
    padding: 22px 14px 18px 14px;
    text-align: center;
}
.hbell-empty-ico { font-size: 26px; line-height: 1; margin-bottom: 6px; opacity: 0.85; }
.hbell-empty-title { color: #FFFFFF; font-size: 13px; font-weight: 600; }
.hbell-empty-sub { color: rgba(230,233,245,0.55); font-size: 11px; margin-top: 2px; }

/* --- Timer (boss_account) --- */
[data-testid="timer"] { display: none !important; }

/* --- Forced text color for stubborn Gradio children --- */
#main-tabs p, #main-tabs span:not([class]), #main-tabs div:not([class]):not([id]) {
    color: var(--c-text-2);
}

/* ================================================================
   PATCH v2 — 修截图里发现的 3 类细节瑕疵
   - Gradio form label 的"紫色药丸"底
   - Dataframe 表头文字太淡几乎看不见
   - 还有白底的 Dropdown / File Upload 按钮
   ================================================================ */

/* --- Gradio 表单 label: 去掉任何色块, 变成纯文字标题 --- */
#main-tabs label,
#main-tabs .label-wrap,
#main-tabs .label-wrap > span,
#main-tabs .block > label > span,
#main-tabs .form label,
#main-tabs label[data-testid="block-label"],
#main-tabs [data-testid="block-label"],
#login-panel label,
#login-panel .label-wrap,
#login-panel .label-wrap > span,
#agreement-panel label {
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
    color: var(--c-text-2) !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 0 6px 0 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-shadow: none !important;
    border-radius: 0 !important;
}
/* label 内 svg / 小图标保持原色 */
#main-tabs label svg,
#login-panel label svg {
    background: transparent !important;
}

/* --- Dropdown / 单选等组合控件的外壳统一暗色 --- */
#main-tabs .secondary-wrap,
#main-tabs .gr-dropdown,
#main-tabs .gr-dropdown input,
#main-tabs .dropdown-arrow {
    background: rgba(17,22,48,0.65) !important;
    color: var(--c-text-1) !important;
    border-color: rgba(255,255,255,0.1) !important;
}
#main-tabs .container:not(.gradio-container) {
    background: transparent !important;
    border: none !important;
}
/* Dropdown 外层 .block 容器: 去掉 Gradio 默认的灰色边框 */
#main-tabs .gradio-dropdown,
#main-tabs [data-testid="dropdown"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    --block-border-color: transparent !important;
    --block-background-fill: transparent !important;
    --input-border-color: transparent !important;
}
#main-tabs .gradio-dropdown.block,
#main-tabs [data-testid="dropdown"].block,
#main-tabs .block:has(> .gradio-dropdown),
#main-tabs .block:has(> [data-testid="dropdown"]),
#main-tabs .block:has(.gradio-dropdown),
#main-tabs .block:has([data-testid="dropdown"]) {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    --block-border-color: transparent !important;
    --block-background-fill: transparent !important;
}
#main-tabs .token,
#main-tabs .dropdown-option {
    background: rgba(79,139,255,0.15) !important;
    color: var(--c-text-1) !important;
    border: 1px solid rgba(79,139,255,0.3) !important;
}

/* --- File Upload "选择文件" 按钮: 去掉紫色药丸, 变成淡描边 chip --- */
#main-tabs .file-upload,
#main-tabs .gr-file,
#main-tabs [data-testid="upload-button"],
#main-tabs .upload-button,
#main-tabs .wrap.svelte-xwlu1w .wrap-inner {
    background: rgba(17,22,48,0.4) !important;
    border: 1px dashed rgba(255,255,255,0.18) !important;
    color: var(--c-text-2) !important;
}
#main-tabs .file-preview,
#main-tabs .file-preview-holder {
    background: rgba(17,22,48,0.4) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: var(--c-text-2) !important;
}

/* --- Dataframe 表头: 更亮的文字 + 更明显的分隔 --- */
#main-tabs table.dataframe thead th,
#main-tabs .table thead th,
#main-tabs [data-testid="dataframe"] thead th,
#main-tabs .cell-wrap.header,
#main-tabs .svelte-p5q82i thead th,
#main-tabs .gr-dataframe thead th {
    background: rgba(79,139,255,0.14) !important;
    color: var(--c-text-1) !important;
    font-weight: 600 !important;
    border-bottom: 1px solid rgba(79,139,255,0.3) !important;
    text-transform: none !important;
    letter-spacing: 0.2px !important;
}
#main-tabs table.dataframe tbody td,
#main-tabs [data-testid="dataframe"] tbody td {
    color: var(--c-text-2) !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}
#main-tabs [data-testid="dataframe"] .cell-wrap,
#main-tabs .cell-wrap {
    color: var(--c-text-1) !important;
}

/* --- Dataframe: 针对 Gradio 6.9 真实 DOM class (.table-wrap / .svelte-1fq485w) --- */
#main-tabs .table-wrap,
#main-tabs .table-wrap.svelte-4x7jh,
#main-tabs [data-testid="dataframe"],
#main-tabs [data-testid="dataframe"] > div,
#main-tabs .dataframe,
#main-tabs .gr-dataframe {
    background: rgba(17,22,48,0.45) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    color: var(--c-text-2) !important;
    overflow: hidden !important;
}
/* 所有 dataframe <table> 去掉默认白底 */
#main-tabs .table-wrap table,
#main-tabs table.svelte-u825rv,
#main-tabs table.svelte-4x7jh,
#main-tabs .dataframe table {
    background: transparent !important;
    color: var(--c-text-2) !important;
}
/* thead / th 暗色 */
#main-tabs .table-wrap thead,
#main-tabs .table-wrap thead tr,
#main-tabs table thead,
#main-tabs thead.thead {
    background: transparent !important;
}
#main-tabs .table-wrap thead th,
#main-tabs thead th,
#main-tabs th.svelte-1fq485w,
#main-tabs [role="columnheader"] {
    background: linear-gradient(180deg, rgba(79,139,255,0.22), rgba(79,139,255,0.10)) !important;
    color: var(--c-text-1) !important;
    font-weight: 600 !important;
    border-bottom: 1px solid rgba(79,139,255,0.3) !important;
    border-top: none !important;
    border-left: none !important;
    border-right: none !important;
    padding: 10px 12px !important;
}
/* 表头里每个 cell-wrap/header-content/button/span 都强制白字 */
#main-tabs th .cell-wrap,
#main-tabs th .header-content,
#main-tabs th .header-button,
#main-tabs th span,
#main-tabs th button,
#main-tabs [role="columnheader"] * {
    background: transparent !important;
    color: var(--c-text-1) !important;
    font-weight: 600 !important;
}
/* 表头右侧的 cell-menu-button "⋮" 淡化 */
#main-tabs .cell-menu-button,
#main-tabs .cell-menu-button.svelte-pgxclp {
    color: var(--c-text-3) !important;
    background: transparent !important;
}
/* tbody td 文字 + 分隔线 */
#main-tabs .table-wrap tbody td,
#main-tabs tbody td,
#main-tabs td.svelte-1fq485w {
    background: transparent !important;
    color: var(--c-text-2) !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
    border-left: none !important;
    border-right: none !important;
    padding: 10px 12px !important;
}
/* 交替行 + hover */
#main-tabs .table-wrap tbody tr:nth-child(even) td,
#main-tabs tbody tr:nth-child(even) td {
    background: rgba(255,255,255,0.02) !important;
}
#main-tabs .table-wrap tbody tr:hover td,
#main-tabs tbody tr:hover td {
    background: rgba(79,139,255,0.06) !important;
}
/* Drag drop 提示 overlay: "将 CSV 或 TSV 文件拖放到此处" 覆盖层透明化 */
#main-tabs .svelte-1o7nwih.disable_click {
    background: transparent !important;
}

/* --- 状态 textbox (只读显示框) 去掉白底 --- */
#main-tabs textarea[readonly],
#main-tabs input[readonly] {
    background: rgba(17,22,48,0.4) !important;
    color: var(--c-text-2) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}

/* =================================================================
   Number Input + Slider Reset Button — 玻璃 pill 风格美化
   ----------------------------------------------------------------
   Gradio 6.x slider DOM:
   .block.gradio-slider > .wrap > .head > .tab-like-container
       > input[type=number] (data-testid=number-input)
       + button.reset-button (data-testid=reset-button)  ↺
   .wrap > .slider_input_container > span.min_value + input[type=range]
       + span.max_value
   ================================================================= */

/* 容器: 数字输入 + 还原按钮 合并成 pill */
#main-tabs .tab-like-container,
#login-card .tab-like-container {
    background: rgba(17,22,48,0.55) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 10px !important;
    padding: 0 !important;
    overflow: hidden !important;
    display: inline-flex !important;
    align-items: stretch !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.04),
        0 1px 3px rgba(0,0,0,0.18) !important;
    transition: border-color 0.18s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
#main-tabs .tab-like-container:hover,
#login-card .tab-like-container:hover {
    border-color: rgba(141,187,255,0.45) !important;
    background: rgba(17,22,48,0.7) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.08),
        0 4px 12px rgba(79,139,255,0.18) !important;
}
#main-tabs .tab-like-container:focus-within,
#login-card .tab-like-container:focus-within {
    border-color: rgba(141,187,255,0.85) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.10),
        0 0 0 3px rgba(79,139,255,0.20),
        0 4px 14px rgba(79,139,255,0.25) !important;
}

/* 数字输入框 */
#main-tabs .tab-like-container input[type="number"],
#main-tabs input[data-testid="number-input"],
#login-card input[data-testid="number-input"],
#main-tabs .gr-slider input[type="number"],
#main-tabs input[type="number"] {
    background: transparent !important;
    color: #F0F2FA !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 6px 10px !important;
    font-size: 13.5px !important;
    font-weight: 600 !important;
    line-height: 1.4 !important;
    font-variant-numeric: tabular-nums !important;
    box-shadow: none !important;
    outline: none !important;
    min-width: 56px !important;
    text-align: center !important;
    -moz-appearance: textfield !important;
}
/* 隐藏浏览器默认上下箭头 */
#main-tabs .tab-like-container input[type="number"]::-webkit-outer-spin-button,
#main-tabs .tab-like-container input[type="number"]::-webkit-inner-spin-button,
#main-tabs input[type="number"]::-webkit-outer-spin-button,
#main-tabs input[type="number"]::-webkit-inner-spin-button {
    -webkit-appearance: none !important;
    margin: 0 !important;
}

/* Slider 内部 .head 容器: 强制顶端对齐, 防止 reset 按钮偏移 */
#main-tabs .gradio-slider .head,
#main-tabs .block:has(input[type="range"]) .head {
    display: flex !important;
    align-items: flex-start !important;
    gap: 8px !important;
    margin-bottom: 2px !important;
}
/* 还原按钮 ↺ — 圆形玻璃按钮, hover 旋转 + 高亮 */
#main-tabs .reset-button,
#main-tabs button[data-testid="reset-button"],
#login-card button[data-testid="reset-button"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02)) !important;
    color: rgba(230,233,245,0.85) !important;
    border: none !important;
    border-left: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 0 !important;
    padding: 0 10px !important;
    min-width: 32px !important;
    height: auto !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    line-height: 1 !important;
    cursor: pointer !important;
    box-shadow: none !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background 0.18s ease, color 0.18s ease, transform 0.4s cubic-bezier(0.2,0.8,0.2,1) !important;
}
#main-tabs .reset-button:hover,
#main-tabs button[data-testid="reset-button"]:hover {
    background: linear-gradient(180deg, rgba(79,139,255,0.32), rgba(168,115,245,0.20)) !important;
    color: #FFFFFF !important;
    transform: rotate(-180deg) !important;
}
#main-tabs .reset-button:active,
#main-tabs button[data-testid="reset-button"]:active {
    transform: rotate(-180deg) scale(0.92) !important;
}

/* =================================================================
   Slider Track + Thumb — 蓝紫渐变 + 发光圆球
   ================================================================= */
/* 已填充区域 (左侧) + 未填充区域 (右侧) 双层背景 */
#main-tabs input[type="range"],
#login-card input[type="range"] {
    -webkit-appearance: none !important;
    appearance: none !important;
    height: 8px !important;
    width: 100% !important;
    border-radius: 999px !important;
    background:
        linear-gradient(90deg, #4F8BFF 0%, #A873F5 100%) 0 0 / var(--gr-slider-fill, var(--range_progress, 0%)) 100% no-repeat,
        rgba(255,255,255,0.10) !important;
    box-shadow:
        0 0 0 1px rgba(255,255,255,0.05) inset,
        0 1px 2px rgba(0,0,0,0.25) inset !important;
    outline: none !important;
    cursor: pointer !important;
    transition: box-shadow 0.2s ease !important;
}
#main-tabs input[type="range"]:hover,
#login-card input[type="range"]:hover {
    box-shadow:
        0 0 0 1px rgba(141,187,255,0.30) inset,
        0 0 12px rgba(79,139,255,0.30) !important;
}
/* 轨道层 (Webkit) */
#main-tabs input[type="range"]::-webkit-slider-runnable-track,
#login-card input[type="range"]::-webkit-slider-runnable-track {
    background: transparent !important;
    height: 8px !important;
    border-radius: 999px !important;
    border: none !important;
}
#main-tabs input[type="range"]::-moz-range-track {
    background: rgba(255,255,255,0.10) !important;
    height: 8px !important;
    border-radius: 999px !important;
    border: none !important;
}
#main-tabs input[type="range"]::-moz-range-progress {
    background: linear-gradient(90deg, #4F8BFF 0%, #A873F5 100%) !important;
    height: 8px !important;
    border-radius: 999px !important;
}
/* Thumb 圆球 */
#main-tabs input[type="range"]::-webkit-slider-thumb,
#login-card input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none !important;
    appearance: none !important;
    width: 20px !important; height: 20px !important;
    border-radius: 50% !important;
    background: radial-gradient(circle at 35% 30%, #FFFFFF 0%, #C7B8FF 60%, #8DBBFF 100%) !important;
    border: 2px solid rgba(255,255,255,0.85) !important;
    box-shadow:
        0 0 0 4px rgba(79,139,255,0.18),
        0 4px 12px rgba(79,139,255,0.45),
        inset 0 -1px 1px rgba(0,0,0,0.18) !important;
    cursor: grab !important;
    margin-top: -6px !important;
    transition: transform 0.18s ease, box-shadow 0.2s ease !important;
}
#main-tabs input[type="range"]::-webkit-slider-thumb:hover,
#login-card input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.15) !important;
    box-shadow:
        0 0 0 6px rgba(79,139,255,0.25),
        0 6px 18px rgba(79,139,255,0.6) !important;
}
#main-tabs input[type="range"]::-webkit-slider-thumb:active,
#login-card input[type="range"]::-webkit-slider-thumb:active {
    cursor: grabbing !important;
    transform: scale(1.08) !important;
}
#main-tabs input[type="range"]::-moz-range-thumb {
    width: 20px !important; height: 20px !important;
    border-radius: 50% !important;
    background: radial-gradient(circle at 35% 30%, #FFFFFF 0%, #C7B8FF 60%, #8DBBFF 100%) !important;
    border: 2px solid rgba(255,255,255,0.85) !important;
    box-shadow:
        0 0 0 4px rgba(79,139,255,0.18),
        0 4px 12px rgba(79,139,255,0.45) !important;
    cursor: grab !important;
}
/* min/max 标签 */
#main-tabs .slider_input_container .min_value,
#main-tabs .slider_input_container .max_value,
#login-card .slider_input_container .min_value,
#login-card .slider_input_container .max_value {
    color: rgba(230,233,245,0.55) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    font-variant-numeric: tabular-nums !important;
    letter-spacing: 0.3px !important;
    padding: 0 6px !important;
}
/* slider 容器对齐 */
#main-tabs .slider_input_container,
#login-card .slider_input_container {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 6px 4px 4px 4px !important;
}

/* --- 登录页标签特别处理: LOGIN_CSS 有 '#login-card label span' 浅色规则,
   这里用更高 specificity 覆盖 --- */
#login-card label span,
#login-card .label-wrap span,
#login-card .label-wrap > span,
#login-panel #login-card label span,
#login-panel #login-card .label-wrap span {
    background: transparent !important;
    background-image: none !important;
    color: var(--c-text-2) !important;
    padding: 0 0 4px 0 !important;
    font-weight: 500 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    text-shadow: none !important;
}
/* 登录卡 input 强制暗色 */
#login-panel #login-card input,
#login-card input {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: var(--c-text-1) !important;
}
#login-panel #login-card input::placeholder,
#login-card input::placeholder {
    color: var(--c-text-4) !important;
}
#login-panel #login-card input:focus,
#login-card input:focus {
    border-color: var(--c-primary) !important;
    background: rgba(17,22,48,0.65) !important;
    box-shadow: 0 0 0 3px rgba(79,139,255,0.15) !important;
}
/* 登录卡 Dropdown 的可视输入区 & 下拉项 */
#login-panel #login-card .wrap-inner,
#login-panel #login-card .container,
#login-panel #login-card [data-testid="dropdown"] .wrap-inner,
#login-panel #login-card [data-testid="dropdown"] input {
    background: rgba(17,22,48,0.5) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: var(--c-text-1) !important;
}
#login-card .dropdown-arrow { color: var(--c-text-3) !important; }

/* --- 最后保险: 任何 label 内带背景色的 svelte class 都清掉 --- */
#main-tabs label span[class*="svelte-"],
#login-card label span[class*="svelte-"],
#main-tabs .label-wrap > span[class*="svelte-"] {
    background: transparent !important;
    background-image: none !important;
    color: var(--c-text-2) !important;
    padding: 0 0 4px 0 !important;
    border-radius: 0 !important;
}

/* --- KEY FIX: Gradio block-info 药丸就是这俩 data-testid 选择器 --- */
[data-testid="block-info"],
[data-testid="block-info"].has-info,
span[data-testid="block-info"] {
    background: transparent !important;
    background-image: none !important;
    background-color: transparent !important;
    color: var(--c-text-2) !important;
    padding: 0 0 6px 0 !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    text-shadow: none !important;
    letter-spacing: 0 !important;
}
/* block-info 后面的说明文字（"可下拉选择..."）也统一 --- */
.svelte-1xfsv4t .info,
.svelte-1hguek3 .info,
.block .info,
[data-testid="block-info"] + .info,
.has-info + .info {
    color: var(--c-text-3) !important;
    background: transparent !important;
    font-size: 12px !important;
}

/* ================================================================
   A11y — :focus-visible 键盘导航高亮
   仅当用户使用键盘 (Tab) 时显示, 不影响鼠标点击
   ================================================================ */
button:focus-visible,
.gr-button:focus-visible,
[role="button"]:focus-visible,
[role="menuitem"]:focus-visible,
[role="tab"]:focus-visible,
.tab-wrapper button:focus-visible,
a:focus-visible,
.header-bell-trigger:focus-visible,
.header-user-trigger:focus-visible,
.feature-item:focus-visible {
    outline: 2px solid var(--c-primary-light, #4F8BFF) !important;
    outline-offset: 3px !important;
    box-shadow:
        0 0 0 4px rgba(79,139,255,0.22),
        0 0 0 1px rgba(255,255,255,0.18) inset !important;
    border-radius: 8px !important;
    transition: box-shadow 0.18s ease, outline-offset 0.18s ease;
    z-index: 5;
}
input:focus-visible,
textarea:focus-visible,
select:focus-visible {
    outline: 2px solid var(--c-primary-light, #4F8BFF) !important;
    outline-offset: 1px !important;
}
/* 鼠标点击时不显示焦点环 (现代浏览器 :focus-visible polyfill) */
button:focus:not(:focus-visible),
[role="button"]:focus:not(:focus-visible),
[role="tab"]:focus:not(:focus-visible),
a:focus:not(:focus-visible) {
    outline: none !important;
    box-shadow: inherit !important;
}

/* 跳过到主内容链接 (skip link) — 隐藏直至键盘聚焦 */
.skip-to-content {
    position: absolute !important;
    top: -100px;
    left: 12px;
    z-index: 10000;
    padding: 10px 18px;
    background: linear-gradient(135deg, var(--c-primary, #165DFF), #4F8BFF);
    color: #FFFFFF !important;
    border-radius: 8px;
    font-weight: 700;
    font-size: 13px;
    text-decoration: none;
    box-shadow: 0 8px 24px rgba(22,93,255,0.42);
    transition: top 0.2s ease;
}
.skip-to-content:focus,
.skip-to-content:focus-visible {
    top: 12px;
    outline: 2px solid #FFFFFF !important;
    outline-offset: 3px !important;
}

/* prefers-reduced-motion: 减弱大幅动画 */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
        scroll-behavior: auto !important;
    }
    .b-tile:hover,
    .card:hover, .info-card:hover,
    .res-scope .res-card:hover,
    .rc-scope .rc-card:hover,
    .st-scope .st-card:hover,
    .op-scope .op-card:hover,
    .dlv-scope .dlv-card:hover,
    .bs-scope .bs-card:hover,
    .feature-item:hover {
        transform: none !important;
    }
}
"""
# fmt: on


APP_CSS += LOGIN_CSS
APP_CSS += DARK_OVERRIDE_CSS

_DISCLAIMER = (
    "使用本工具即表示您已阅读并同意以下条款：\n\n"
    "1. 本工具仅为个人求职辅助, 不代表任何招聘平台官方\n\n"
    "2. 用户需遵守招聘平台用户协议, 账号风险自行承担\n\n"
    "3. 数据仅本地存储, 不上传云端\n\n"
    "4. 禁止用于商业代投或恶意投递"
)


def _accept_agreement(state):
    """用户同意协议"""
    try:
        user_name = state.get("user_name", "") if state else ""
        from app.db.crud import SysConfigCRUD
        SysConfigCRUD.set("agreement_accepted", "true", user_name=user_name)
        return gr.update(visible=False), gr.update(visible=True)
    except Exception as e:
        logger.error("保存协议状态失败: %s", e)
        return gr.update(visible=False), gr.update(visible=True)


def _check_agreement(user_name: str = "") -> bool:
    """检查用户是否已同意协议"""
    try:
        from app.db.crud import SysConfigCRUD
        return SysConfigCRUD.get("agreement_accepted", user_name=user_name) == "true"
    except Exception:
        return False


def _render_particles_bg_html() -> str:
    """生成 100 颗闪烁星点 + 3 条流星 + 4 束星云的 HTML 片段.

    使用固定随机种子, 保证每次渲染位置一致 (避免刷新抖动).
    流星的拖尾角度与运动向量通过 CSS tan() 自动匹配.
    """
    import random as _r

    _r.seed(20260418)
    palette = [
        "rgba(255,255,255,0.95)",
        "rgba(141,187,255,0.90)",
        "rgba(196,181,253,0.88)",
        "rgba(249,168,212,0.85)",
        "rgba(110,231,183,0.82)",
        "rgba(253,224,71,0.78)",
    ]
    parts: list[str] = []
    for _ in range(100):
        top = _r.uniform(0, 100)
        left = _r.uniform(0, 100)
        size = _r.uniform(1.0, 3.2)
        delay = _r.uniform(0, 20)
        duration = _r.uniform(6, 20)
        col = _r.choice(palette)
        parts.append(
            f'<span class="pt" style="top:{top:.1f}%;left:{left:.1f}%;'
            f"width:{size:.1f}px;height:{size:.1f}px;background:{col};"
            f"box-shadow:0 0 {size * 4:.1f}px {col};"
            f"animation-delay:-{delay:.1f}s;animation-duration:{duration:.1f}s;"
            f'"></span>'
        )
    comets: list[str] = []
    angle_pool = [4, 6, 8, 10, 12]
    for i in range(3):
        top = _r.uniform(5, 55)
        delay = _r.uniform(0, 18)
        duration = _r.uniform(14, 22)
        angle = angle_pool[i % len(angle_pool)]
        comets.append(
            f'<span class="comet" style="top:{top:.1f}%;--cdelay:-{delay:.1f}s;'
            f'--cdur:{duration:.1f}s;--cang:{angle}deg;"></span>'
        )
    return (
        '<div class="bg-fx" aria-hidden="true">'
        '  <div class="aurora a1"></div>'
        '  <div class="aurora a2"></div>'
        '  <div class="aurora a3"></div>'
        '  <div class="aurora a4"></div>'
        '  <div class="grid-fade"></div>'
        + "".join(parts)
        + "".join(comets)
        + "</div>"
    )


APP_BOOT_JS = r"""
() => {
    /* ==========================================================
       页面加载后一次性初始化 (Gradio 6.x app.load(js=) 入口)
       三段逻辑:
         1. SVG 无障碍标记 (aria-label / role="img")
         2. 粒子背景性能降级 (haju-low-fx) + 后台暂停 (haju-bg-pause)
         3. 移动端侧栏抽屉 (haju-nav-open) + 事件委托
       ========================================================== */

    /* ---------- 1) SVG 无障碍标记 ---------- */
    function tagSvgs(root) {
        try {
            var svgs = (root || document).querySelectorAll('svg:not([data-a11y])');
            for (var i = 0; i < svgs.length; i++) {
                var s = svgs[i];
                s.setAttribute('data-a11y', '1');
                if (s.getAttribute('aria-label') || s.getAttribute('aria-labelledby')) {
                    s.setAttribute('role', 'img');
                    s.setAttribute('focusable', 'false');
                    continue;
                }
                var title = s.querySelector('title');
                if (title && title.textContent && title.textContent.trim()) {
                    s.setAttribute('role', 'img');
                    s.setAttribute('aria-label', title.textContent.trim());
                    s.setAttribute('focusable', 'false');
                    continue;
                }
                s.setAttribute('aria-hidden', 'true');
                s.setAttribute('focusable', 'false');
                s.setAttribute('role', 'presentation');
            }
            var ems = (root || document).querySelectorAll(
                '.feature-icon, .kpi-icon, .hbell-empty-ico, [data-decorative-emoji]'
            );
            for (var j = 0; j < ems.length; j++) {
                if (!ems[j].hasAttribute('aria-hidden')) {
                    ems[j].setAttribute('aria-hidden', 'true');
                }
            }
        } catch (e) {}
    }
    tagSvgs(document);
    try {
        var mo = new MutationObserver(function(muts) {
            for (var k = 0; k < muts.length; k++) {
                var m = muts[k];
                if (m.addedNodes && m.addedNodes.length) {
                    for (var n = 0; n < m.addedNodes.length; n++) {
                        var node = m.addedNodes[n];
                        if (node.nodeType === 1) tagSvgs(node);
                    }
                }
            }
        });
        mo.observe(document.body, { childList: true, subtree: true });
    } catch (e) {}

    /* ---------- 2) 粒子背景性能降级 + 后台暂停 ----------
       同样受 Gradio scope 影响 — body 类不命中 .bg-fx, 必须把镜像
       类挂到 #bg-fx-slot (它在 .contain 内). */
    function _fxTargets() {
        var arr = [];
        var slot = document.getElementById('bg-fx-slot');
        if (slot) arr.push(slot);
        if (document.body) arr.push(document.body);
        return arr;
    }
    function applyLowFx() {
        try {
            var memOk = !('deviceMemory' in navigator) || navigator.deviceMemory >= 4;
            var cpuOk = !('hardwareConcurrency' in navigator) || navigator.hardwareConcurrency >= 4;
            var w = window.innerWidth || document.documentElement.clientWidth || 1280;
            var motion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            var coarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
            var weak = (!memOk) || (!cpuOk) || w < 720 || motion || (coarse && w < 1024);
            _fxTargets().forEach(function (el) {
                el.classList.toggle('haju-low-fx', !!weak);
            });
        } catch (e) {}
    }
    function bgPause() {
        try {
            var pause = document.hidden;
            _fxTargets().forEach(function (el) {
                el.classList.toggle('haju-bg-pause', !!pause);
            });
        } catch (e) {}
    }
    applyLowFx();
    bgPause();
    try {
        window.addEventListener('resize', applyLowFx, { passive: true });
        document.addEventListener('visibilitychange', bgPause);
    } catch (e) {}

    /* ---------- 3) 移动端侧栏抽屉 ----------
       注意: Gradio 6 会把所有 CSS 选择器前置 ".gradio-container .contain",
       而 <body> 不在该祖先链内, 所以 body.haju-nav-open ... 永远不命中.
       修复: 把 toggle 类挂到 #main-tabs (它在 .contain 内). 同时为了
       JS 内部统计 / 兼容旧引用, 也在 body 上保留同名类作为镜像. */
    var NAV_MQ = '(max-width: 720px)';
    function _navTargets() {
        var arr = [];
        var mt = document.getElementById('main-tabs');
        if (mt) arr.push(mt);
        if (document.body) arr.push(document.body);
        return arr;
    }
    function navIsMobile() {
        try { return window.matchMedia && window.matchMedia(NAV_MQ).matches; }
        catch (e) { return false; }
    }
    function navIsOpen() {
        var mt = document.getElementById('main-tabs');
        if (mt) return mt.classList.contains('haju-nav-open');
        return document.body && document.body.classList.contains('haju-nav-open');
    }
    function navClose() {
        _navTargets().forEach(function (el) {
            el.classList.remove('haju-nav-open');
        });
    }
    function navOpen() {
        if (!navIsMobile()) return;
        _navTargets().forEach(function (el) {
            el.classList.add('haju-nav-open');
        });
    }
    function navToggle() {
        if (!navIsMobile()) { navClose(); return; }
        var open = navIsOpen();
        _navTargets().forEach(function (el) {
            el.classList.toggle('haju-nav-open', !open);
        });
    }
    function onAnyClick(e) {
        try {
            var t = e.target;
            if (navIsOpen() && t.closest('#main-tabs > .tab-wrapper .tab-container button')) {
                setTimeout(navClose, 140);
                return;
            }
            if (navIsMobile() && t.closest('.app-header-bar .hl')) {
                if (t.closest('.header-user-dropdown, .header-bell-wrap, .header-user-menu, .header-bell-pop')) return;
                e.preventDefault();
                e.stopPropagation();
                navToggle();
                return;
            }
            if (navIsOpen() && navIsMobile()) {
                if (t.closest('#main-tabs > .tab-wrapper, .app-header-bar')) return;
                navClose();
            }
        } catch (e2) {}
    }
    function onNavResize() { if (!navIsMobile()) navClose(); }
    function onNavKey(e) { if (e.key === 'Escape') navClose(); }
    try {
        document.addEventListener('click', onAnyClick, true);
        window.addEventListener('resize', onNavResize, { passive: true });
        document.addEventListener('keydown', onNavKey);
    } catch (e) {}
    window.__hajuNav = {
        open: navOpen, close: navClose, toggle: navToggle,
        isMobile: navIsMobile, isOpen: navIsOpen,
    };
}
"""


def create_app() -> gr.Blocks:
    """创建 Gradio 应用主界面"""
    settings = get_settings()

    base_model_map = {
        "https://api.openai.com/v1": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3", "o4-mini"],
        "https://api.deepseek.com": ["deepseek-chat", "deepseek-reasoner"],
        "https://dashscope.aliyuncs.com/compatible-mode/v1": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "https://open.bigmodel.cn/api/paas/v4": ["glm-4", "glm-4-flash"],
        "https://api.moonshot.cn/v1": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "https://api.minimax.chat/v1": ["abab6.5s-chat", "abab6.5-chat", "abab5.5-chat"],
        "https://api.lingyiwanwu.com/v1": ["yi-lightning", "yi-large", "yi-medium"],
        "https://api.anthropic.com/v1": ["claude-3-5-sonnet", "claude-3-5-haiku"],
        "https://api.groq.com/openai/v1": ["llama-3.1-70b-instruct", "mixtral-8x7b-instruct"],
        "https://api.together.xyz/v1": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
    }

    common_model_choices = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "o3",
        "o4-mini",
        "deepseek-chat",
        "deepseek-reasoner",
        "qwen-plus",
        "qwen-max",
        "qwen-turbo",
        "glm-4",
        "glm-4-flash",
        "moonshot-v1-8k",
        "abab6.5s-chat",
        "yi-lightning",
        "llama-3.1-70b-instruct",
        "mixtral-8x7b-instruct",
        "claude-3-5-sonnet",
        "gemini-1.5-pro",
    ]

    def _recommend_models_by_base_url(base_url: str, current_model: str):
        key = (base_url or "").strip().rstrip("/")
        preferred = base_model_map.get(key, [])
        merged = preferred + [m for m in common_model_choices if m not in preferred]
        chosen = (current_model or "").strip()
        if not chosen:
            chosen = preferred[0] if preferred else settings.LLM_MODEL
        return gr.update(choices=merged, value=chosen)

    with gr.Blocks(title=settings.APP_NAME) as app:

        gr.HTML(_render_particles_bg_html(), elem_id="bg-fx-slot")

        gr.HTML(
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" '
            'href="https://fonts.googleapis.com/css2?'
            'family=Inter:wght@400;500;600;700;800'
            '&family=Noto+Sans+SC:wght@400;500;600;700'
            '&family=JetBrains+Mono:wght@400;500'
            '&display=swap">',
            elem_id="font-loader",
        )

        # 三段 JS 已挪到 app.load(js=APP_BOOT_JS) 里执行
        # (Gradio 6.x 不会执行 gr.HTML 内联 <script>, 必须用 load(js=))

        login_state = gr.State(
            {
                "logged_in": False,
                "user_name": "",
                "api_key": "",
                "base_url": "",
                "model": "",
            }
        )
        browser_state = gr.BrowserState(
            {
                "logged_in": False,
                "user_name": "",
                "api_key": "",
                "base_url": "",
                "model": "",
            },
            storage_key="ai_job_agent_session",
            secret="ai_job_agent_2026_persistent_key",
        )

        # ---- 登录面板 (首屏: 左品牌 + 右表单) ----
        with gr.Column(visible=True, elem_id="login-panel") as login_panel:
            with gr.Row(elem_id="login-container"):
                with gr.Column(elem_id="login-left", min_width=340):
                    gr.HTML(LOGIN_BRAND_HTML)
                with gr.Column(elem_id="login-card", min_width=360):
                    gr.HTML(
                        '<div class="login-title">欢迎登录</div>'
                        '<div class="login-subtitle">输入您的信息，开始智能求职之旅</div>'
                    )
                    login_name = gr.Textbox(
                        label="用户名",
                        placeholder="请输入英文姓名拼音 (如 zhangsan)",
                        max_lines=1,
                    )
                    login_key = gr.Textbox(
                        label="API Key",
                        placeholder="请输入 API Key",
                        type="password",
                        max_lines=1,
                    )
                    login_base_url = gr.Dropdown(
                        label="API Base URL",
                        choices=[
                            "https://api.openai.com/v1",
                            "https://api.deepseek.com",
                            "https://dashscope.aliyuncs.com/compatible-mode/v1",
                            "https://open.bigmodel.cn/api/paas/v4",
                            "https://api.moonshot.cn/v1",
                            "https://api.minimax.chat/v1",
                            "https://api.lingyiwanwu.com/v1",
                            "https://api.siliconflow.cn/v1",
                            "https://api.baichuan-ai.com/v1",
                            "https://api.together.xyz/v1",
                            "https://api.groq.com/openai/v1",
                            "https://openrouter.ai/api/v1",
                            "https://api.anthropic.com/v1",
                        ],
                        value=settings.LLM_BASE_URL,
                        allow_custom_value=True,
                        filterable=True,
                        info="可下拉选择常用服务地址，也可手动输入自定义地址",
                    )
                    login_model = gr.Dropdown(
                        label="模型名称",
                        choices=[
                            "gpt-4o",
                            "gpt-4o-mini",
                            "gpt-4.1",
                            "gpt-4.1-mini",
                            "o3",
                            "o4-mini",
                            "deepseek-chat",
                            "deepseek-reasoner",
                            "qwen-plus",
                            "qwen-max",
                            "qwen-turbo",
                            "glm-4",
                            "glm-4-flash",
                            "moonshot-v1-8k",
                            "abab6.5s-chat",
                            "yi-lightning",
                            "llama-3.1-70b-instruct",
                            "mixtral-8x7b-instruct",
                            "claude-3-5-sonnet",
                            "gemini-1.5-pro",
                        ],
                        value=settings.LLM_MODEL,
                        allow_custom_value=True,
                        filterable=True,
                        info="可下拉选择常见模型，也可手动输入自定义模型名",
                    )
                    login_error = gr.HTML("", elem_id="login-error")
                    login_btn = gr.Button(
                        "登录", variant="primary", size="lg", elem_id="login-btn",
                    )
                    gr.HTML(
                        '<div class="login-footer">'
                        "🔒 API Key 仅本地校验使用，不会上传云端"
                        "</div>"
                    )

        # ---- 协议面板 ----
        with gr.Column(visible=False, elem_id="agreement-panel") as agreement_panel:
            gr.Markdown(f"# {settings.APP_NAME}")
            gr.Markdown("### 用户使用须知与免责声明")
            gr.Markdown(_DISCLAIMER)
            agree_btn = gr.Button(
                "已阅读并同意, 开始使用", variant="primary", size="lg",
            )

        # ---- 主面板 ----
        with gr.Column(visible=False, elem_id="main-panel") as main_panel:

            header_html = gr.HTML(
                build_header_html("", settings.APP_VERSION)
            )

            with gr.Row(elem_id="logout-row"):
                user_label_html = gr.HTML("")
                logout_btn = gr.Button(
                    "退出登录", size="sm", variant="secondary",
                    elem_id="logout-btn", min_width=80, scale=0,
                )

            with gr.Tabs(elem_id="main-tabs") as main_tabs:
                with gr.Tab("📊 工作台", id=0):
                    (btn_upload, btn_delivery, btn_records,
                     dash_cards, dash_risk, dash_recent) = create_dashboard_page(login_state)
                with gr.Tab("📄 简历管理", id=1):
                    create_resume_page(login_state)
                with gr.Tab("🔍 JD匹配", id=2):
                    create_jd_match_page(login_state)
                with gr.Tab("✨ 简历优化", id=3):
                    create_optimize_page(login_state)
                with gr.Tab("🔗 BOSS账号", id=4):
                    create_boss_account_page(login_state)
                with gr.Tab("🚀 自动投递", id=5) as delivery_tab:
                    delivery_conn_banner = create_delivery_page(login_state)
                with gr.Tab("📋 投递记录", id=6):
                    create_records_page(login_state)
                with gr.Tab("⚙ 系统设置", id=7):
                    create_settings_page()

            def _click_tab_js(tab_text: str) -> str:
                """生成按文本匹配点击 tab 按钮的 JS（兼容 Gradio 6 overflow 结构）"""
                return (
                    "() => {"
                    "  const mt = document.querySelector('#main-tabs');"
                    "  if (!mt) return;"
                    "  const btns = mt.querySelectorAll('.tab-wrapper button');"
                    "  for (const b of btns) {"
                    f"    if (b.textContent.includes('{tab_text}')) "
                    "      { b.click(); return; }"
                    "  }"
                    "}"
                )

            btn_upload.click(
                fn=lambda: gr.Tabs(selected=1), outputs=[main_tabs],
                js=_click_tab_js("简历管理"),
            )
            btn_delivery.click(
                fn=lambda: gr.Tabs(selected=5), outputs=[main_tabs],
                js=_click_tab_js("自动投递"),
            )
            btn_records.click(
                fn=lambda: gr.Tabs(selected=6), outputs=[main_tabs],
                js=_click_tab_js("投递记录"),
            )

            from app.ui.pages.delivery import _connection_banner

            def _safe_connection_banner():
                try:
                    return _connection_banner()
                except Exception:
                    return (
                        '<div class="alert-bar">'
                        "⚠ 请先前往「BOSS 账号」页面连接并登录 BOSS 直聘"
                        "</div>"
                    )

            delivery_tab.select(
                fn=_safe_connection_banner,
                outputs=[delivery_conn_banner],
            )

        login_base_url.change(
            fn=_recommend_models_by_base_url,
            inputs=[login_base_url, login_model],
            outputs=[login_model],
        )

        # ---- 辅助: 刷新工作台数据 ----
        _dash_outputs = [dash_cards, dash_risk, dash_recent]

        def _refresh_dashboard(state):
            user_name = state.get("user_name", "") if state else ""
            if not user_name:
                return (gr.skip(),) * 3
            return load_dashboard_data(user_name)

        # ---- 事件: 登录 (按钮点击 + 回车提交) ----
        _login_outputs = [
            login_state, browser_state,
            login_panel, agreement_panel, main_panel,
            login_error, header_html, user_label_html,
        ]

        for trigger in (login_btn.click, login_name.submit, login_key.submit):
            trigger(
                fn=handle_login,
                inputs=[login_name, login_key, login_base_url, login_model],
                outputs=_login_outputs,
            ).then(
                fn=_refresh_dashboard,
                inputs=[login_state],
                outputs=_dash_outputs,
            )

        # ---- 事件: 同意协议 ----
        agree_btn.click(
            fn=_accept_agreement,
            inputs=[login_state],
            outputs=[agreement_panel, main_panel],
        ).then(
            fn=_refresh_dashboard,
            inputs=[login_state],
            outputs=_dash_outputs,
        )

        # ---- 事件: 退出登录 ----
        logout_btn.click(
            fn=handle_logout,
            outputs=[
                login_state, browser_state,
                login_panel, agreement_panel, main_panel,
                login_name, login_key, login_base_url, login_model, login_error,
            ],
        ).then(
            fn=lambda _: load_dashboard_data(""),
            inputs=[login_state],
            outputs=_dash_outputs,
        )

        # ---- 事件: 页面加载 → 从 BrowserState 恢复会话 ----
        app.load(
            fn=restore_session,
            inputs=[browser_state],
            outputs=[
                login_state,
                login_panel, agreement_panel, main_panel,
                header_html, user_label_html,
            ],
        ).then(
            fn=_refresh_dashboard,
            inputs=[login_state],
            outputs=_dash_outputs,
        )

        # ---- 事件: 页面加载 → 注入前端 JS (a11y + 性能 + 移动端抽屉) ----
        # Gradio 6.x 不会执行 gr.HTML 内联 <script>, 必须用 load(js=)
        app.load(fn=None, js=APP_BOOT_JS)

    logger.info("Gradio UI 构建完成")
    return app
