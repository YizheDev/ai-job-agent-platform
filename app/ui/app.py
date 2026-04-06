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
    font-family: 'Inter', 'SF Pro Display', 'PingFang SC', 'Microsoft YaHei',
                 -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: linear-gradient(160deg, #F0F2F5 0%, #E8ECF2 40%, #EDF0F5 100%) !important;
    color: var(--c-text-2) !important;
    font-size: 14px !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
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
    padding: 28px !important;
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

/* --- Loading overlay --- */
.app-header-bar ~ .wrap[data-testid="status-tracker"],
#logout-row .wrap[data-testid="status-tracker"],
.app-header-bar + .wrap[data-testid="status-tracker"] {
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

/* Slider track fix */
.gr-slider input[type="range"] {
    margin-top: 4px !important;
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
}
"""
# fmt: on

APP_CSS += LOGIN_CSS

_DISCLAIMER = (
    "使用本工具即表示您已阅读并同意以下条款：\n\n"
    "1. 本工具仅为个人求职辅助, 不代表任何招聘平台官方\n\n"
    "2. 用户需遵守招聘平台用户协议, 账号风险自行承担\n\n"
    "3. 数据仅本地存储, 不上传云端\n\n"
    "4. 禁止用于商业代投或恶意投递"
)


def _accept_agreement(state):
    """用户同意协议"""
    user_name = state.get("user_name", "") if state else ""
    from app.db.crud import SysConfigCRUD
    SysConfigCRUD.set("agreement_accepted", "true", user_name=user_name)
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

    with gr.Blocks(title=settings.APP_NAME) as app:

        login_state = gr.State(
            {"logged_in": False, "user_name": "", "api_key": ""}
        )
        browser_state = gr.BrowserState(
            {"logged_in": False, "user_name": "", "api_key": ""},
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
                        label="DeepSeek API Key",
                        placeholder="请输入 API Key (sk-...)",
                        type="password",
                        max_lines=1,
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

            btn_upload.click(fn=lambda: gr.Tabs(selected=1), outputs=[main_tabs])
            btn_delivery.click(fn=lambda: gr.Tabs(selected=5), outputs=[main_tabs])
            btn_records.click(fn=lambda: gr.Tabs(selected=6), outputs=[main_tabs])

            # Auto-refresh delivery page connection banner when tab is selected
            from app.ui.pages.delivery import _connection_banner
            delivery_tab.select(
                fn=lambda: _connection_banner(),
                outputs=[delivery_conn_banner],
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
                inputs=[login_name, login_key],
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
                login_name, login_key, login_error,
            ],
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

    logger.info("Gradio UI 构建完成")
    return app
