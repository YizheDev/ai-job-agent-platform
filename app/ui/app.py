"""Gradio UI entrypoint."""

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
from app.ui.view_model import get_ui_snapshot

logger = get_logger(__name__)

APP_THEME = gr.themes.Soft(
    primary_hue=gr.themes.Color(
        c50="#F0F9FF",
        c100="#E0F2FE",
        c200="#BAE6FD",
        c300="#7DD3FC",
        c400="#38BDF8",
        c500="#0EA5E9",
        c600="#0284C7",
        c700="#0369A1",
        c800="#075985",
        c900="#0C4A6E",
        c950="#082F49",
    ),
    neutral_hue=gr.themes.colors.slate,
)

# fmt: off
APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');

:root {
    --surface: #f0f9ff;
    --surface-low: #e0f2fe;
    --surface-high: #bae6fd;
    --surface-card: rgba(255, 255, 255, 0.78);
    --surface-solid: #ffffff;
    --text: #0f172a;
    --text-soft: #334155;
    --text-muted: #64748b;
    --outline: rgba(148, 163, 184, 0.22);
    --primary: #0EA5E9;
    --primary-strong: #0369A1;
    --secondary: #38BDF8;
    --accent: #7DD3FC;
    --tertiary: #BAE6FD;
    --success: #10B981;
    --warning: #F59E0B;
    --danger: #EF4444;
    --shadow-lg: 0 24px 60px rgba(14, 165, 233, 0.15);
    --shadow-md: 0 18px 40px rgba(15, 23, 42, 0.10);
    --radius-xl: 28px;
    --radius-lg: 22px;
    --radius-md: 18px;
    --radius-sm: 14px;
}

* { box-sizing: border-box; }

html, body {
    min-height: 100%;
}

body, .gradio-container {
    margin: 0 !important;
    font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    color: var(--text) !important;
    background:
        radial-gradient(circle at top right, rgba(30, 144, 255, 0.18), transparent 28%),
        radial-gradient(circle at bottom left, rgba(79, 166, 255, 0.10), transparent 30%),
        linear-gradient(180deg, #fdfefe 0%, #f2f8ff 100%) !important;
}

.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
}

footer { display: none !important; }

#agreement-panel {
    min-height: 100vh;
    display: flex !important;
    align-items: center;
    justify-content: center;
    padding: 40px;
}

#agreement-panel > .form {
    width: min(720px, 100%);
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border: 1px solid rgba(255, 255, 255, 0.68);
    border-radius: 32px;
    box-shadow: var(--shadow-lg);
    padding: 32px !important;
}

#agreement-panel h1,
#agreement-panel h3 {
    font-family: 'Manrope', 'PingFang SC', sans-serif !important;
}

.app-topbar {
    min-height: 74px;
    padding: 0 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 22px;
    position: sticky;
    top: 0;
    z-index: 20;
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(22px);
    -webkit-backdrop-filter: blur(22px);
    border-bottom: 1px solid rgba(135, 146, 162, 0.16);
    pointer-events: none;
}

.app-topbar .brand {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 260px;
    position: relative;
    z-index: 3;
    pointer-events: auto;
}

.app-topbar .brand-mark {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%);
    box-shadow: 0 12px 24px rgba(30, 144, 255, 0.20);
}

.app-topbar .brand-copy {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.app-nav {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    pointer-events: auto;
}

.app-nav-btn {
    height: 42px;
    padding: 0 16px;
    border-radius: 999px;
    border: 1px solid rgba(30, 144, 255, 0.12);
    background: rgba(255, 255, 255, 0.74);
    color: var(--text-soft);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 15px;
    font-weight: 800;
    cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
    white-space: nowrap;
}

.app-nav-btn:hover {
    transform: translateY(-1px);
    background: rgba(255, 255, 255, 0.92);
    border-color: rgba(30, 144, 255, 0.30);
    box-shadow: 0 14px 28px rgba(30, 144, 255, 0.12);
}

.app-nav-btn.active {
    color: var(--primary);
    background: linear-gradient(135deg, rgba(103, 184, 255, 0.24), rgba(30, 144, 255, 0.14));
    border-color: rgba(30, 144, 255, 0.30);
    box-shadow: 0 16px 30px rgba(30, 144, 255, 0.14);
}

.app-topbar .brand-title {
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--primary-strong);
}

.app-topbar .brand-meta {
    margin-top: 3px;
    color: var(--text-muted);
    font-size: 12px;
}

.topbar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: nowrap;
    margin-left: auto;
    position: relative;
    z-index: 3;
    pointer-events: auto;
}

.status-pill {
    padding: 10px 16px;
    border-radius: 999px;
    color: white;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    background: linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%);
    box-shadow: 0 12px 24px rgba(0, 88, 190, 0.18);
}

.icon-pill, .version-pill {
    min-width: 42px;
    height: 42px;
    padding: 0 14px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(135, 146, 162, 0.12);
    color: var(--text-soft);
    font-weight: 700;
}

.icon-pill {
    cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.icon-pill:hover {
    transform: translateY(-1px);
    border-color: rgba(30, 144, 255, 0.32);
    box-shadow: 0 12px 24px rgba(30, 144, 255, 0.14);
}

.version-pill {
    min-width: unset;
    font-size: 13px;
    color: var(--text-muted);
}

#main-tabs.tabs {
    display: flex !important;
    flex-direction: column !important;
    min-height: calc(100vh - 74px) !important;
    border: none !important;
    background: transparent !important;
    gap: 0 !important;
    position: relative !important;
    pointer-events: auto !important;
}

#main-tabs > .tab-wrapper {
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    pointer-events: none !important;
}

#main-tabs > .tab-wrapper > .tab-container[role="tablist"] {
    display: flex !important;
    width: 100% !important;
}

#main-tabs > .tab-wrapper > .tab-container.visually-hidden,
#main-tabs > .tab-wrapper::before,
#main-tabs > .tab-wrapper::after {
    display: none !important;
    content: none !important;
}

#main-tabs > .tab-wrapper > .tab-container[role="tablist"] button { display: none !important; }

#main-tabs > .tabitem {
    flex: 1 !important;
    padding: 8px 32px 36px !important;
    background: transparent !important;
    overflow-y: auto !important;
    position: relative !important;
    z-index: 1 !important;
    min-width: 0 !important;
    pointer-events: auto !important;
}


#main-tabs > .tabitem {
    flex: 1 1 auto !important;
    width: 100% !important;
    padding: 8px 32px 36px !important;
}

.page-shell {
    max-width: 1540px;
    width: 100%;
    margin: 0 auto;
    position: relative;
    z-index: 1;
}

.page-shell::before {
    content: "";
    position: absolute;
    top: 24px;
    right: 40px;
    width: 360px;
    height: 360px;
    background: radial-gradient(circle, rgba(87, 223, 254, 0.15) 0%, transparent 68%);
    pointer-events: none;
    filter: blur(6px);
    z-index: -1;
}

.page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 8px;
}

.page-subtitle {
    margin-top: 0;
    color: var(--text-soft);
    font-size: 17px;
    line-height: 1.65;
    max-width: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.section-title {
    margin: 0 0 16px;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.eyebrow {
    margin-bottom: 14px;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.glass-card {
    background: var(--surface-card);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border: 1px solid rgba(255, 255, 255, 0.68);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-md);
}

.glass-card,
.stitch-card,
.metric-pill-soft,
.dock-pill,
.list-card,
.risk-item,
.hero-metric,
.pending-item,
.kv-row,
.ic-row,
.table-shell {
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.glass-card:hover,
.metric-pill-soft:hover,
.dock-pill:hover,
.list-card:hover,
.pending-item:hover,
.kv-row:hover,
.ic-row:hover {
    transform: translateY(-2px);
    box-shadow: 0 18px 34px rgba(17, 24, 39, 0.08);
}

.card {
    background: rgba(255, 255, 255, 0.86);
    border: 1px solid rgba(135, 146, 162, 0.14);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    padding: 24px;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: 1.8fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
}

.dashboard-bottom {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 24px;
}

.hero-card {
    padding: 28px;
    display: grid;
    grid-template-columns: 168px 1fr;
    gap: 22px;
    align-items: center;
    overflow: hidden;
    position: relative;
}

.hero-card::after {
    content: "";
    position: absolute;
    top: -80px;
    right: -40px;
    width: 260px;
    height: 260px;
    background: radial-gradient(circle, rgba(87, 223, 254, 0.22) 0%, transparent 65%);
    pointer-events: none;
}

.quota-orb {
    width: 156px;
    height: 156px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto;
    background:
        radial-gradient(circle at center, rgba(255,255,255,0.96) 0 45%, transparent 46%),
        conic-gradient(from -90deg, var(--accent) 0 55%, rgba(0, 88, 190, 0.18) 55% 100%);
    box-shadow: inset 0 0 0 12px rgba(255,255,255,0.84), 0 18px 36px rgba(0, 88, 190, 0.12);
}

.quota-orb .orb-inner {
    text-align: center;
}

.quota-orb .orb-value {
    display: block;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 42px;
    font-weight: 800;
    line-height: 1;
}

.quota-orb .orb-meta {
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

.hero-copy h2 {
    margin: 0;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.03em;
}

.hero-copy p {
    margin: 10px 0 0;
    color: var(--text-soft);
    font-size: 15px;
    line-height: 1.75;
}

.hero-metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-top: 24px;
}

.hero-metric {
    padding: 18px;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(242, 246, 252, 0.88));
    border: 1px solid rgba(30, 144, 255, 0.26);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}

.hero-metric .label {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

.hero-metric .value {
    margin-top: 10px;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.03em;
}

.agent-panel {
    padding: 30px;
}

.agent-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
}

.agent-item {
    padding: 18px;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(244,248,252,0.82));
    border: 1px solid rgba(135, 146, 162, 0.08);
}

.agent-item .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}

.agent-item .name {
    font-size: 13px;
    font-weight: 800;
}

.agent-item .dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
}

.dot.online { background: var(--success); box-shadow: 0 0 16px rgba(24, 181, 106, 0.4); }
.dot.warn { background: var(--warning); box-shadow: 0 0 16px rgba(255, 154, 60, 0.35); }
.dot.idle { background: #b1bccb; }

.agent-item .meta {
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 800;
}

.agent-item .bar {
    margin-top: 12px;
    height: 8px;
    border-radius: 999px;
    overflow: hidden;
    background: rgba(135, 146, 162, 0.16);
}

.agent-item .bar > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--accent), var(--primary));
}

.analysis-shell {
    padding: 28px;
}

.analysis-grid {
    display: grid;
    grid-template-columns: 1.2fr 0.88fr;
    gap: 20px;
}

.trend-panel {
    padding: 22px;
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.60);
    border: 1px solid rgba(135, 146, 162, 0.12);
}

.trend-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
}

.trend-head h3, .risk-panel h3 {
    margin: 0;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.03em;
}

.trend-sub {
    color: var(--text-muted);
    font-size: 12px;
}

.trend-bars {
    display: flex;
    align-items: flex-end;
    gap: 14px;
    height: 190px;
}

.trend-bar-wrap {
    flex: 1;
    min-width: 0;
}

.trend-bar {
    border-radius: 18px 18px 8px 8px;
    background: linear-gradient(180deg, rgba(87, 223, 254, 0.95), rgba(0, 88, 190, 0.92));
    box-shadow: 0 16px 30px rgba(0, 88, 190, 0.14);
}

.trend-score {
    margin-bottom: 8px;
    text-align: center;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 14px;
    font-weight: 800;
}

.trend-label {
    margin-top: 10px;
    text-align: center;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 700;
}

.risk-panel {
    padding: 22px;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.84) 0%, rgba(255, 245, 236, 0.84) 100%);
    border: 1px solid rgba(227, 93, 87, 0.12);
}

.risk-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 18px;
}

.risk-item {
    padding: 16px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.74);
    border-left: 4px solid var(--warning);
}

.risk-item.danger { border-left-color: var(--danger); }

.risk-item h4 {
    margin: 0 0 8px;
    font-size: 14px;
    font-weight: 800;
}

.risk-item p {
    margin: 0;
    color: var(--text-soft);
    font-size: 13px;
    line-height: 1.6;
}

.panel-actions {
    margin-top: 18px;
}

.pending-card, .records-card {
    padding: 30px;
}

.pending-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.pending-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 18px;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(247,250,253,0.86));
    border: 1px solid rgba(30, 144, 255, 0.26);
}

.pending-main {
    display: flex;
    align-items: center;
    gap: 14px;
}

.pending-icon {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    color: var(--primary);
    background: rgba(87, 223, 254, 0.18);
}

.pending-title {
    font-size: 14px;
    font-weight: 800;
}

.pending-sub {
    margin-top: 4px;
    color: var(--text-muted);
    font-size: 12px;
}

.pending-pill {
    padding: 8px 12px;
    border-radius: 999px;
    color: var(--primary);
    background: rgba(0, 88, 190, 0.08);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.12em;
}

.alert-bar {
    margin: 0 0 20px;
    padding: 16px 18px;
    border-radius: 18px;
    background: linear-gradient(90deg, rgba(255, 244, 229, 0.90), rgba(255, 250, 245, 0.90));
    border: 1px solid rgba(255, 154, 60, 0.20);
    color: #8a5722;
    font-weight: 600;
}

.alert-bar::before {
    content: "!";
    margin-right: 10px;
    font-weight: 900;
}

.alert-bar.success {
    background: linear-gradient(90deg, rgba(234, 255, 243, 0.92), rgba(248, 255, 250, 0.92));
    border-color: rgba(24, 181, 106, 0.18);
    color: #15734a;
}

.alert-bar.error {
    background: linear-gradient(90deg, rgba(255, 237, 236, 0.92), rgba(255, 249, 249, 0.92));
    border-color: rgba(227, 93, 87, 0.18);
    color: #a6423d;
}

.table-shell {
    overflow: hidden;
    border-radius: 24px;
    border: 1px solid rgba(135, 146, 162, 0.12);
    background: rgba(255, 255, 255, 0.74);
}

.custom-table {
    width: 100%;
    border-collapse: collapse;
}

.custom-table thead th {
    height: 52px;
    padding: 0 18px;
    background: rgba(242, 244, 247, 0.82);
    color: var(--text-muted);
    text-align: left;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

.custom-table tbody td {
    height: 58px;
    padding: 0 18px;
    border-top: 1px solid rgba(135, 146, 162, 0.08);
    font-size: 13px;
    color: var(--text-soft);
}

.custom-table tbody tr:hover td {
    background: rgba(236, 246, 255, 0.42);
}

.status-tag {
    display: inline-flex;
    align-items: center;
    padding: 8px 10px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.tag-blue { background: rgba(0, 88, 190, 0.10); color: var(--primary); }
.tag-green { background: rgba(24, 181, 106, 0.12); color: #15734a; }
.tag-orange { background: rgba(255, 154, 60, 0.14); color: #8a5722; }
.tag-red { background: rgba(227, 93, 87, 0.12); color: #a6423d; }
.tag-gray { background: rgba(135, 146, 162, 0.16); color: #5c6674; }

.quick-actions {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 24px;
}

.page-row {
    gap: 24px !important;
    margin: 0 auto 18px !important;
    max-width: 1540px;
    width: 100%;
}

.page-stack {
    margin: 0 auto 18px !important;
    max-width: 1540px;
    width: 100%;
}

.stitch-section {
    padding: 26px !important;
    overflow: hidden;
}

.stitch-section-tight {
    padding: 22px !important;
    overflow: hidden;
}

.stitch-stats-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
}

.metric-pill-soft {
    padding: 18px 20px;
    border-radius: 22px;
    background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(242,246,252,0.88));
    border: 1px solid rgba(135, 146, 162, 0.12);
    box-shadow: 0 14px 28px rgba(17, 24, 39, 0.05);
}

.metric-pill-soft .label {
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
}

.metric-pill-soft .value {
    margin-top: 10px;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.03em;
}

.feature-note {
    padding: 18px 20px;
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(103, 184, 255, 0.14), rgba(30, 144, 255, 0.08));
    border: 1px solid rgba(30, 144, 255, 0.14);
    color: var(--text-soft);
    font-size: 14px;
    line-height: 1.8;
}

.page-dock {
    display: none !important;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
}

.dock-pill {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.82);
    border: 1px solid rgba(135, 146, 162, 0.10);
    color: var(--text-soft);
    font-size: 13px;
    font-weight: 700;
    box-shadow: 0 10px 20px rgba(17, 24, 39, 0.04);
    transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    white-space: nowrap;
}

.dock-pill strong {
    color: var(--text);
    font-weight: 800;
}

.dock-pill:hover {
    transform: translateY(-1px);
    border-color: rgba(30, 144, 255, 0.18);
    box-shadow: 0 14px 26px rgba(30, 144, 255, 0.08);
}

#main-tabs > .tabitem:nth-of-type(1) .page-dock .dock-pill:nth-child(3),
#main-tabs > .tabitem:nth-of-type(2) .page-dock .dock-pill:nth-child(3),
#main-tabs > .tabitem:nth-of-type(3) .page-dock .dock-pill:nth-child(3),
#main-tabs > .tabitem:nth-of-type(4) .page-dock .dock-pill:nth-child(3),
#main-tabs > .tabitem:nth-of-type(6) .page-dock .dock-pill:nth-child(3) {
    display: none !important;
}

.workspace-grid {
    display: grid;
    grid-template-columns: minmax(380px, 0.92fr) minmax(0, 1.2fr);
    gap: 22px;
    align-items: start;
}

.workspace-grid-equal {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
    align-items: start;
}

.workspace-column {
    display: flex;
    flex-direction: column;
    gap: 18px;
    min-width: 0;
}

.sticky-pane {
    position: sticky;
    top: 96px;
}

.list-shell {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.list-card {
    padding: 18px 20px;
    border-radius: 22px;
    background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(246,250,253,0.84));
    border: 1px solid rgba(135, 146, 162, 0.12);
}

.list-card:hover {
    transform: translateY(-1px);
    border-color: rgba(0, 88, 190, 0.16);
    box-shadow: 0 16px 28px rgba(17, 24, 39, 0.08);
}

.list-card.selected {
    background: linear-gradient(135deg, rgba(87,223,254,0.14), rgba(0,88,190,0.08));
    border-color: rgba(0, 88, 190, 0.18);
    box-shadow: 0 16px 32px rgba(0, 88, 190, 0.08);
}

.list-card-title {
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 19px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--text);
}

.list-card-sub {
    margin-top: 8px;
    color: var(--text-soft);
    font-size: 14px;
    line-height: 1.7;
}

.list-card-meta {
    margin-top: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.meta-chip {
    padding: 7px 10px;
    border-radius: 999px;
    background: rgba(242, 244, 247, 0.84);
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 700;
}

.kv-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.kv-row {
    display: grid;
    grid-template-columns: 84px 1fr;
    gap: 12px;
    padding: 16px 18px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.86);
    border: 1px solid rgba(30, 144, 255, 0.10);
}

.kv-label {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

.kv-value {
    color: var(--text);
    font-size: 15px;
    font-weight: 600;
    line-height: 1.8;
    word-break: break-word;
}

.ring-chart-wrap {
    padding: 22px;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.66), rgba(236,246,255,0.72));
    border: 1px solid rgba(135, 146, 162, 0.12);
}

.ring-chart {
    position: relative;
    width: 140px;
    height: 140px;
    margin: 0 auto;
}

.ring-chart .rt {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.ring-chart .rs {
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
}

.ring-chart .rl {
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

.match-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}

.match-tag {
    display: inline-flex;
    align-items: center;
    padding: 10px 14px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}

.match-tag.hit {
    color: #15734a;
    background: rgba(24, 181, 106, 0.12);
}

.match-tag.miss {
    color: #a6423d;
    background: rgba(227, 93, 87, 0.12);
}

.match-tag.weak {
    color: #8a5722;
    background: rgba(255, 154, 60, 0.16);
}

.progress-steps {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.step-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    min-width: 84px;
}

.step-dot {
    width: 38px;
    height: 38px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(135, 146, 162, 0.14);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 800;
}

.step-dot.active {
    color: white;
    background: linear-gradient(135deg, var(--accent), var(--primary));
    box-shadow: 0 14px 26px rgba(0, 88, 190, 0.18);
}

.step-dot.done {
    color: white;
    background: linear-gradient(135deg, rgba(24,181,106,0.92), rgba(0, 88, 190, 0.92));
}

.step-name {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    text-align: center;
}

.step-name.active,
.step-name.done {
    color: var(--text);
}

.step-line {
    flex: 1;
    min-width: 32px;
    height: 4px;
    border-radius: 999px;
    background: rgba(135, 146, 162, 0.14);
}

.step-line.done {
    background: linear-gradient(90deg, var(--accent), var(--primary));
}

.info-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.ic-row {
    display: grid;
    grid-template-columns: 92px 1fr;
    gap: 14px;
    padding: 16px 18px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.88);
    border: 1px solid rgba(135, 146, 162, 0.10);
}

.ic-label {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.ic-value {
    color: var(--text);
    font-size: 15px;
    line-height: 1.75;
    word-break: break-word;
}

.bar-chart {
    height: 220px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
}

.bar-item {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    height: 100%;
}

.bv {
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 14px;
    font-weight: 800;
}

.bar {
    width: 100%;
    border-radius: 18px 18px 8px 8px;
    min-height: 10px;
    background: linear-gradient(180deg, rgba(87,223,254,0.96), rgba(0,88,190,0.92));
    box-shadow: 0 16px 28px rgba(0, 88, 190, 0.14);
}

.bl {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 700;
}

.legend-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
    color: var(--text-soft);
    font-size: 13px;
}

.legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
}

.settings-banner {
    padding: 20px 22px;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(255,255,255,0.82), rgba(236,246,255,0.82));
    border: 1px solid rgba(0, 88, 190, 0.10);
}

.settings-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
}

.gradio-container button,
.gradio-container .gr-button {
    border-radius: 18px !important;
    min-height: 50px !important;
    font-family: 'Manrope', 'PingFang SC', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    border: 1px solid transparent !important;
    box-shadow: none !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease !important;
}

.gradio-container button:hover,
.gradio-container .gr-button:hover {
    transform: translateY(-1px);
}

.gradio-container button.primary,
.gradio-container .gr-button-primary {
    color: white !important;
    background: linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%) !important;
    box-shadow: 0 16px 28px rgba(0, 88, 190, 0.18) !important;
}

.gradio-container button.secondary,
.gradio-container .gr-button-secondary {
    color: var(--text) !important;
    background: rgba(255, 255, 255, 0.78) !important;
    border-color: rgba(135, 146, 162, 0.14) !important;
}

.gradio-container button.stop,
.gradio-container .gr-button-stop {
    color: var(--danger) !important;
    background: rgba(255, 255, 255, 0.84) !important;
    border-color: rgba(227, 93, 87, 0.18) !important;
}

.gradio-container .block,
.gradio-container .wrap,
.gradio-container .form {
    border-color: rgba(135, 146, 162, 0.12) !important;
}

.gradio-container .gr-box,
.gradio-container .gr-panel,
.gradio-container .panel-wrap {
    border-radius: 22px !important;
    border-color: rgba(135, 146, 162, 0.12) !important;
    background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,250,253,0.86)) !important;
    box-shadow: var(--shadow-md) !important;
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
}

.gradio-container .gr-box:hover,
.gradio-container .gr-panel:hover,
.gradio-container .panel-wrap:hover {
    transform: translateY(-1px);
    box-shadow: 0 22px 42px rgba(17, 24, 39, 0.08) !important;
}

.gradio-container input,
.gradio-container textarea,
.gradio-container select {
    border-radius: 16px !important;
    border-color: rgba(135, 146, 162, 0.16) !important;
    background: rgba(255, 255, 255, 0.92) !important;
    font-size: 15px !important;
}

.gradio-container label,
.gradio-container .wrap label,
.gradio-container .form label {
    color: var(--text) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
}

.gradio-container .markdown,
.gradio-container .prose,
.gradio-container .prose p,
.gradio-container .prose li {
    color: var(--text-soft) !important;
    font-size: 15px !important;
    line-height: 1.8 !important;
}

.gradio-container table thead th,
.gradio-container .gr-dataframe th {
    background: rgba(242, 244, 247, 0.82) !important;
    color: var(--text-muted) !important;
    font-size: 11px !important;
    font-weight: 800 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
}

.gradio-container table tbody td,
.gradio-container .gr-dataframe td {
    color: var(--text-soft) !important;
}

#main-tabs > .tabitem {
    animation: pageFadeIn 0.26s ease;
}

@keyframes pageFadeIn {
    from {
        opacity: 0;
        transform: translateY(8px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.markdown h2,
.markdown h3,
.gradio-container .prose h2,
.gradio-container .prose h3 {
    font-family: 'Manrope', 'PingFang SC', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -0.03em;
}

.markdown h2,
.gradio-container .prose h2 {
    font-size: 34px !important;
    font-weight: 800 !important;
    margin: 0 0 10px !important;
}

.markdown h3,
.gradio-container .prose h3 {
    font-size: 22px !important;
    font-weight: 800 !important;
    margin: 0 0 14px !important;
}

@media (max-width: 1200px) {
    .dashboard-grid,
    .dashboard-bottom,
    .analysis-grid,
    .workspace-grid,
    .workspace-grid-equal {
        grid-template-columns: 1fr;
    }
}

.stitch-card {
    background: rgba(255, 255, 255, 0.80);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.72);
    border-radius: 28px;
    box-shadow: var(--shadow-md);
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease, background 0.22s ease;
}

.stitch-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 22px 44px rgba(17, 24, 39, 0.10);
    border-color: rgba(0, 88, 190, 0.12);
}

.stitch-panel-title {
    margin-bottom: 16px;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.03em;
}

.stitch-muted {
    color: var(--text-soft);
    font-size: 14px;
    line-height: 1.7;
}

.stitch-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
}

.stitch-grid-main {
    display: grid;
    grid-template-columns: 1.05fr 1.25fr;
    gap: 24px;
    margin-top: 20px;
}

.stitch-stack {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.stitch-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
}

.stitch-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(255, 138, 61, 0.16);
    color: #ff7a1a;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    box-shadow: inset 0 0 0 1px rgba(255, 138, 61, 0.10);
}

.stitch-empty {
    padding: 24px;
    border-radius: 20px;
    background: rgba(242, 244, 247, 0.72);
    color: var(--text-muted);
    text-align: center;
    font-size: 14px;
}

.animated-empty {
    padding: 28px 24px;
    border-radius: 24px;
    background: linear-gradient(180deg, rgba(255,255,255,0.82), rgba(242,246,250,0.74));
    border: 1px solid rgba(135, 146, 162, 0.12);
    text-align: center;
    position: relative;
    overflow: hidden;
}

.skeleton-shell {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.skeleton-block,
.skeleton-line,
.skeleton-pill {
    position: relative;
    overflow: hidden;
    background: rgba(227, 233, 240, 0.82);
}

.skeleton-block::after,
.skeleton-line::after,
.skeleton-pill::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(110deg, transparent 18%, rgba(255,255,255,0.72) 45%, transparent 72%);
    transform: translateX(-100%);
    animation: skeletonShimmer 1.8s ease-in-out infinite;
}

.skeleton-block {
    height: 140px;
    border-radius: 22px;
}

.skeleton-line {
    height: 14px;
    border-radius: 999px;
}

.skeleton-pill {
    width: 96px;
    height: 34px;
    border-radius: 999px;
}

.skeleton-line.short { width: 36%; }
.skeleton-line.mid { width: 62%; }
.skeleton-line.long { width: 92%; }

@keyframes skeletonShimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

.animated-empty::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(110deg, transparent 20%, rgba(255,255,255,0.46) 48%, transparent 76%);
    transform: translateX(-100%);
    animation: emptyShimmer 3.2s ease-in-out infinite;
}

#main-tabs > .tabitem:nth-of-type(3) .sticky-pane .stitch-card:last-child,
#main-tabs > .tabitem:nth-of-type(4) .sticky-pane .stitch-card:last-child,
#main-tabs > .tabitem:nth-of-type(5) .page-stack .alert-bar,
#main-tabs > .tabitem:nth-of-type(5) .sticky-pane .stitch-card:last-child,
#main-tabs > .tabitem:nth-of-type(5) .workspace-column:last-child .stitch-card:last-child {
    display: none !important;
}

.empty-state-orb {
    width: 72px;
    height: 72px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 18px;
    background: radial-gradient(circle at 30% 30%, rgba(87,223,254,0.34), rgba(0,88,190,0.12));
    box-shadow: inset 0 0 0 10px rgba(255,255,255,0.76), 0 18px 34px rgba(0, 88, 190, 0.12);
    animation: floatOrb 4s ease-in-out infinite;
}

.empty-state-orb span {
    font-size: 28px;
}

.empty-state-title {
    position: relative;
    z-index: 1;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.empty-state-body {
    position: relative;
    z-index: 1;
    margin-top: 10px;
    color: var(--text-soft);
    font-size: 14px;
    line-height: 1.7;
}

.empty-state-hint {
    position: relative;
    z-index: 1;
    margin-top: 14px;
    color: var(--primary);
    font-size: 12px;
    font-weight: 700;
}

@keyframes emptyShimmer {
    0% { transform: translateX(-100%); }
    55% { transform: translateX(100%); }
    100% { transform: translateX(100%); }
}

@keyframes floatOrb {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-6px); }
}

.stitch-note {
    padding: 16px 18px;
    border-radius: 18px;
    background: rgba(255,255,255,0.58);
    border: 1px solid rgba(135,146,162,0.10);
}

.stitch-metric-strip {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
}

.stitch-mini-metric {
    padding: 16px;
    border-radius: 18px;
    background: rgba(242, 244, 247, 0.72);
    border: 1px solid rgba(135, 146, 162, 0.10);
}

.stitch-mini-metric .label {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.stitch-mini-metric .value {
    margin-top: 10px;
    font-family: 'Manrope', 'PingFang SC', sans-serif;
    font-size: 24px;
    font-weight: 800;
}

.compare-shell {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.compare-pane {
    padding: 22px;
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.54);
    border: 1px solid rgba(135, 146, 162, 0.10);
}

.compare-pane .pane-title {
    margin-bottom: 14px;
    font-size: 12px;
    font-weight: 800;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.15em;
}

.record-actions-row {
    display: grid;
    grid-template-columns: 1fr 1fr auto auto;
    gap: 14px;
    align-items: end;
}

.settings-shell .tab-nav,
#settings-tabs > .tab-wrapper > .tab-container[role="tablist"] {
    gap: 6px !important;
}

#main-tabs > .tab-wrapper::before {
    display: none !important;
    content: none !important;
}

@media (max-width: 1200px) {
    .stitch-grid-main,
    .stitch-grid-2,
    .compare-shell,
    .record-actions-row,
    .stitch-stats-4,
    .settings-grid,
    .workspace-grid,
    .workspace-grid-equal {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 960px) {
    .app-topbar {
        padding: 0 16px;
    }

    .topbar-search {
        display: none;
    }

    .topbar-center {
        justify-content: flex-start;
        padding: 0 10px;
    }

    .topbar-chip-soft {
        display: none;
    }

    #main-tabs > .tab-wrapper {
        width: 100% !important;
        min-width: 0 !important;
        max-width: none !important;
        padding: 10px 16px !important;
    }

    #main-tabs > .tab-wrapper > .tab-container[role="tablist"] {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        scrollbar-width: none;
    }

    #main-tabs > .tab-wrapper > .tab-container[role="tablist"]::-webkit-scrollbar {
        display: none;
    }

    #main-tabs > .tab-wrapper > .tab-container[role="tablist"] button {
        min-width: max-content !important;
        font-size: 13px !important;
    }

    #main-tabs > .tabitem {
        padding: 18px 16px 26px !important;
    }

    .hero-card {
        grid-template-columns: 1fr;
        text-align: center;
    }

    .hero-metrics,
    .quick-actions {
        grid-template-columns: 1fr;
    }

    .step-line {
        display: none;
    }
}
"""
# fmt: on

_DISCLAIMER = (
    "使用本工具即表示您已阅读并同意以下条款：\n\n"
    "1. 本工具仅用于个人求职辅助，不代表任何招聘平台官方。\n"
    "2. 用户需遵守招聘平台用户协议，账号风险需自行承担。\n"
    "3. 数据默认本地存储，不上传到云端。\n"
    "4. 禁止用于商业代投或恶意投递。"
)


def _accept_agreement():
    """Mark the disclaimer as accepted."""
    from app.db.crud import SysConfigCRUD

    SysConfigCRUD.set("agreement_accepted", "true")
    return gr.Column(visible=False), gr.Column(visible=True)


def _check_agreement() -> bool:
    """Check whether the user has accepted the disclaimer."""
    try:
        from app.db.crud import SysConfigCRUD

        return SysConfigCRUD.get("agreement_accepted") == "true"
    except Exception:
        return False


def create_app() -> gr.Blocks:
    """Create the main Gradio application."""
    settings = get_settings()
    snapshot = get_ui_snapshot()

    with gr.Blocks(title=settings.APP_NAME) as app:
        agreed = _check_agreement()

        with gr.Column(visible=not agreed, elem_id="agreement-panel") as agreement_panel:
            gr.Markdown(f"# {settings.APP_NAME}")
            gr.Markdown("### 用户使用须知与免责声明")
            gr.Markdown(_DISCLAIMER)
            agree_btn = gr.Button("已阅读并同意，开始使用", variant="primary", size="lg")

        with gr.Column(visible=agreed) as main_panel:
            gr.HTML(
                f"""
                <div class="app-topbar">
                    <div class="brand">
                        <div class="brand-mark">✦</div>
                        <div class="brand-copy">
                            <div class="brand-title">求职智能管家</div>
                            <div class="brand-meta">默认简历：{snapshot['default_resume_name']}</div>
                        </div>
                    </div>
                    <div class="app-nav">
                        <button class="app-nav-btn active" data-target="工作台" onclick="window.__switchJobTab && window.__switchJobTab('工作台')">工作台</button>
                        <button class="app-nav-btn" data-target="简历管理" onclick="window.__switchJobTab && window.__switchJobTab('简历管理')">简历管理</button>
                        <button class="app-nav-btn" data-target="JD匹配" onclick="window.__switchJobTab && window.__switchJobTab('JD匹配')">JD匹配</button>
                        <button class="app-nav-btn" data-target="简历优化" onclick="window.__switchJobTab && window.__switchJobTab('简历优化')">简历优化</button>
                        <button class="app-nav-btn" data-target="自动投递" onclick="window.__switchJobTab && window.__switchJobTab('自动投递')">自动投递</button>
                        <button class="app-nav-btn" data-target="投递记录" onclick="window.__switchJobTab && window.__switchJobTab('投递记录')">投递记录</button>
                    </div>
                    <div class="topbar-actions">
                        <span class="version-pill">V{settings.APP_VERSION}</span>
                        <span class="icon-pill" title="使用说明" onclick="alert('使用说明：\\n1. 先上传简历并完成解析。\\n2. 再进行 JD 匹配与简历优化。\\n3. 自动投递前必须通过风控校验并人工确认。\\n\\nJD 匹配分析流程：\\n- Parser：读取默认原始简历结构化结果。\\n- Analyst：拆解职位关键词、技能门槛和经验要求。\\n- Matchmaker：计算匹配分并输出优势、缺失项与风险建议。\\n\\n简历优化护栏：\\n- 原始简历不会被自动覆盖。\\n- 优先补强 JD 高频关键词与项目成果词。\\n- 仅调整表达顺序、量化结果和岗位相关性。\\n\\n自动投递风控：\\n- 控制单次会话岗位数量与操作节奏。\\n- 避免在非推荐时段高频连续投递。\\n- 最终提交必须经过人工确认。')">?</span>
                        <span class="icon-pill" title="系统设置" onclick="window.__switchJobTab && window.__switchJobTab('系统设置', false)">⚙</span>
                    </div>
                </div>
                """
            )

            with gr.Tabs(elem_id="main-tabs"):
                with gr.Tab("工作台"):
                    create_dashboard_page()
                with gr.Tab("简历管理"):
                    create_resume_page()
                with gr.Tab("JD匹配"):
                    create_jd_match_page()
                with gr.Tab("简历优化"):
                    create_optimize_page()
                with gr.Tab("自动投递"):
                    create_delivery_page()
                with gr.Tab("投递记录"):
                    create_records_page()
                with gr.Tab("系统设置"):
                    create_settings_page()

        agree_btn.click(fn=_accept_agreement, outputs=[agreement_panel, main_panel])
        app.load(
            fn=None,
            js="""
            () => {
                window.__applyUiCleanups = () => {
                    document.querySelectorAll('.page-dock .dock-pill').forEach((pill) => {
                        const text = (pill.textContent || '').replace(/\\s+/g, '');
                        if (text.includes('下一步')) {
                            pill.style.display = 'none';
                        }
                    });
                    document.querySelectorAll('.alert-bar').forEach((node) => {
                        node.style.display = 'none';
                    });
                    const hiddenTitles = ['分析流程', '护栏规则', '风控提示'];
                    document.querySelectorAll('.stitch-card').forEach((card) => {
                        const text = (card.textContent || '').replace(/\\s+/g, '');
                        if (hiddenTitles.some((title) => text.includes(title))) {
                            card.style.display = 'none';
                        }
                        if (text.includes('建议先在JD匹配页确认匹配分')) {
                            card.style.display = 'none';
                        }
                    });
                };
                window.__switchJobTab = (label, keepActive = true) => {
                    const tabs = [...document.querySelectorAll('#main-tabs > .tab-wrapper > .tab-container[role="tablist"] button')];
                    const target = tabs.find((btn) => btn.textContent.trim() === label);
                    if (target) target.click();
                    document.querySelectorAll('.app-nav-btn').forEach((btn) => {
                        const active = keepActive && btn.dataset.target === label;
                        btn.classList.toggle('active', active);
                    });
                    setTimeout(() => {
                        window.__applyUiCleanups && window.__applyUiCleanups();
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }, 0);
                };
                window.__applyUiCleanups();
            }
            """,
        )

    logger.info("Gradio UI 构建完成")
    return app
