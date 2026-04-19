"""工作台 Dashboard 页面 — Bento Grid 暗色玻璃拟态风

参考: Raycast Wrapped 2022 风格, 深色背景 + 多彩渐变 + 玻璃瓦片.
所有样式作用域限定在 .bento-dash 下, 不影响其他页面.

数据流: DeliveryRecordCRUD.get_* → render 各瓦片 → 组装 bento 网格 → gr.HTML.
保留对外接口签名, 不需改动 app.py:
    * load_dashboard_data(user_name) -> (stats_html, alert_html, table_html)
    * create_dashboard_page(login_state) -> 6-tuple
"""

from __future__ import annotations

import html as html_mod
from datetime import datetime, timedelta

import gradio as gr

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.crud import DeliveryRecordCRUD

logger = get_logger(__name__)


# ================================================================
# 状态 & 配色映射
# ================================================================
_STATUS_MAP = {
    "pending": ("待投递", "s-gray"),
    "confirmed": ("已确认", "s-blue"),
    "delivering": ("投递中", "s-orange"),
    "success": ("已投递", "s-green"),
    "failed": ("投递失败", "s-red"),
    "cancelled": ("已取消", "s-gray"),
    "error": ("异常", "s-red"),
}

_STATUS_COLOR = {
    "pending": "#94A3B8",
    "confirmed": "#60A5FA",
    "delivering": "#FB923C",
    "success": "#34D399",
    "failed": "#F87171",
    "cancelled": "#94A3B8",
    "error": "#F87171",
}


# ================================================================
# 工具函数
# ================================================================
def _greeting(hour: int) -> tuple[str, str, str]:
    """根据小时返回 (中文问候, 英文 tagline, hero 渐变名)"""
    if 5 <= hour < 11:
        return "早上好", "Morning Kickstart", "sunrise"
    if 11 <= hour < 13:
        return "中午好", "Midday Focus", "noon"
    if 13 <= hour < 18:
        return "下午好", "Afternoon Power-up", "afternoon"
    if 18 <= hour < 22:
        return "晚上好", "Evening Rally", "sunset"
    return "夜深了", "Night Mode", "night"


def _safe(s) -> str:
    return html_mod.escape(str(s)) if s is not None else ""


# ================================================================
# 瓦片渲染
# ================================================================
def _tile_hero(user_name: str, today_count: int, hour: int) -> str:
    """Hero 瓦片: 时段问候 + 用户名 + 今日投递数."""
    zh, en, grad = _greeting(hour)
    name = _safe(user_name) if user_name else "求职者"
    now = datetime.now()
    date_short = now.strftime("%m/%d")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    time_short = now.strftime("%H:%M")
    return (
        f'<div class="b-tile t-hero t-hero-{grad}" style="grid-area: hero;">'
        '  <div class="hero-noise"></div>'
        '  <div class="hero-grid-pattern"></div>'
        f'  <div class="hero-tagline">{en}</div>'
        f'  <div class="hero-greet">{zh}，<span class="hero-name">{name}</span></div>'
        '  <div class="hero-meta" title="' + _safe(now.strftime("%Y 年 %m 月 %d 日 %H:%M")) + '">'
        f'    <span class="hero-date">{date_short} {weekday_cn}</span>'
        '    <span class="hero-meta-dot">·</span>'
        f'    <span class="hero-time">{time_short}</span>'
        '  </div>'
        '  <div class="hero-footer">'
        f'    <span class="hero-today-num">{today_count}</span>'
        '    <span class="hero-today-label">次今日投递</span>'
        '  </div>'
        '</div>'
    )


def _tile_kpi(area: str, value: str, label: str, accent: str, icon: str) -> str:
    """四个 KPI 瓦片通用模板. accent: blue/pink/violet/teal."""
    return (
        f'<div class="b-tile t-kpi t-kpi-{accent}" style="grid-area: {area};">'
        f'  <div class="kpi-icon">{icon}</div>'
        f'  <div class="kpi-value">{value}</div>'
        f'  <div class="kpi-label">{label}</div>'
        f'  <div class="kpi-orb"></div>'
        '</div>'
    )


def _tile_trend(daily_stats: list[dict]) -> str:
    """近 7 日投递趋势瓦片 (div-based bar chart)."""
    today = datetime.now().date()
    buckets: dict[str, int] = {}
    for item in daily_stats or []:
        buckets[str(item.get("date", ""))] = int(item.get("count", 0))

    bars_html = []
    peak = max(buckets.values(), default=0) or 1
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        cnt = buckets.get(key, 0)
        pct = max(6, int(cnt / peak * 100)) if cnt > 0 else 4
        label_md = d.strftime("%m.%d")
        is_today = i == 0
        today_cls = " is-today" if is_today else ""
        bars_html.append(
            f'<div class="trend-col{today_cls}" title="{label_md}: {cnt} 次">'
            f'  <div class="trend-tip">{cnt}</div>'
            f'  <div class="trend-bar-wrap">'
            f'    <div class="trend-bar" style="height:{pct}%;"></div>'
            f'  </div>'
            f'  <div class="trend-label">{label_md}</div>'
            '</div>'
        )
    total_7d = sum(buckets.values())
    return (
        '<div class="b-tile t-trend" style="grid-area: trend;">'
        '  <div class="tile-head">'
        '    <div class="tile-title">近 7 日投递趋势</div>'
        f'    <div class="tile-sub">合计 <b>{total_7d}</b> 次</div>'
        '  </div>'
        f'  <div class="trend-chart">{"".join(bars_html)}</div>'
        '</div>'
    )


def _tile_score_dist(dist: dict) -> str:
    """匹配分分布瓦片: 三段横向条."""
    high = int(dist.get("high", 0) or 0)
    mid = int(dist.get("medium", 0) or 0)
    low = int(dist.get("low", 0) or 0)
    total = high + mid + low or 1
    hp = round(high / total * 100)
    mp = round(mid / total * 100)
    lp = round(low / total * 100)

    def row(label: str, cnt: int, pct: int, cls: str) -> str:
        return (
            f'<div class="dist-row">'
            f'  <div class="dist-row-head">'
            f'    <span class="dist-label">{label}</span>'
            f'    <span class="dist-val"><b>{cnt}</b><em>{pct}%</em></span>'
            f'  </div>'
            f'  <div class="dist-track">'
            f'    <div class="dist-fill {cls}" style="width:{pct}%;"></div>'
            f'  </div>'
            '</div>'
        )

    return (
        '<div class="b-tile t-dist" style="grid-area: scoredist;">'
        '  <div class="tile-head">'
        '    <div class="tile-title">匹配分分布</div>'
        f'    <div class="tile-sub">总样本 <b>{total if (high+mid+low)>0 else 0}</b></div>'
        '  </div>'
        '  <div class="dist-body">'
        + row("高 ≥85", high, hp, "f-high")
        + row("中 60-84", mid, mp, "f-mid")
        + row("低 <60", low, lp, "f-low")
        + '  </div>'
        '</div>'
    )


def _tile_status_dist(all_records: list[dict]) -> str:
    """投递状态分布瓦片: conic 环形图 + 图例."""
    counts: dict[str, int] = {}
    for r in all_records or []:
        s = r.get("status", "") or "pending"
        counts[s] = counts.get(s, 0) + 1
    total = sum(counts.values()) or 1

    main_keys = ["success", "delivering", "confirmed", "pending", "failed", "cancelled", "error"]
    ordered = [(k, counts.get(k, 0)) for k in main_keys if counts.get(k, 0) > 0]
    if not ordered:
        ordered = [("pending", 0)]

    # 构建 conic-gradient
    stops: list[str] = []
    acc = 0.0
    for k, c in ordered:
        color = _STATUS_COLOR.get(k, "#94A3B8")
        start = acc
        acc += c / (sum(c for _, c in ordered) or 1) * 360
        stops.append(f"{color} {start:.1f}deg {acc:.1f}deg")
    conic = ", ".join(stops) if stops else "#2C2750 0deg 360deg"

    legend_html = "".join(
        f'<li class="leg-item">'
        f'  <span class="leg-dot" style="background:{_STATUS_COLOR.get(k, "#94A3B8")};"></span>'
        f'  <span class="leg-name">{_STATUS_MAP.get(k, (k, ""))[0]}</span>'
        f'  <span class="leg-val">{c}</span>'
        '</li>'
        for k, c in ordered
    )

    shown_total = sum(counts.values())
    return (
        '<div class="b-tile t-statusdist" style="grid-area: statusdist;">'
        '  <div class="tile-head">'
        '    <div class="tile-title">投递状态分布</div>'
        f'    <div class="tile-sub">累计 <b>{shown_total}</b> 条</div>'
        '  </div>'
        '  <div class="statusdist-body">'
        f'    <div class="donut" style="background: conic-gradient({conic});">'
        f'      <div class="donut-hole">'
        f'        <div class="donut-num">{shown_total}</div>'
        f'        <div class="donut-lbl">总数</div>'
        '      </div>'
        '    </div>'
        f'    <ul class="legend">{legend_html}</ul>'
        '  </div>'
        '</div>'
    )


def _tile_tips(
    remaining: int,
    max_daily: int,
    today_count: int,
    hour: int,
    start_hour: int,
    end_hour: int,
) -> str:
    """智能提示瓦片: 时段 / 额度 / 建议."""
    tips: list[tuple[str, str, str]] = []

    in_window = start_hour <= hour < end_hour
    if in_window:
        tips.append(("✅", "投递时段", f"当前 {hour}:00，处于 {start_hour}:00–{end_hour}:00 投递窗口"))
    else:
        tips.append(("⏰", "非投递时段", f"建议在 {start_hour}:00–{end_hour}:00 投递，提高到达率"))

    if remaining == 0:
        tips.append(("🛑", "额度用尽", f"今日 {max_daily} 次已满，明日自动重置"))
    elif remaining <= max_daily * 0.2:
        tips.append(("⚡", "额度告急", f"仅剩 {remaining} 次，建议优先高匹配岗位"))
    else:
        tips.append(("🎯", "额度充足", f"还可投递 {remaining} 次"))

    if today_count == 0 and in_window:
        tips.append(("🚀", "准备出发", "今日尚未投递，开启自动投递开始一天"))
    elif today_count >= max_daily * 0.5:
        tips.append(("🔥", "状态在线", f"今日已投 {today_count} 次，保持节奏"))
    else:
        tips.append(("📈", "持续推进", f"今日已投 {today_count} 次"))

    items_html = "".join(
        f'<li class="tip-item">'
        f'  <span class="tip-ico">{emoji}</span>'
        f'  <div class="tip-body"><div class="tip-head">{title}</div><div class="tip-desc">{desc}</div></div>'
        '</li>'
        for emoji, title, desc in tips
    )
    return (
        '<div class="b-tile t-tips" style="grid-area: tips;">'
        '  <div class="tile-head">'
        '    <div class="tile-title">智能提示</div>'
        '    <div class="tile-sub">实时策略建议</div>'
        '  </div>'
        f'  <ul class="tip-list">{items_html}</ul>'
        '</div>'
    )


def _render_stats_html(
    remaining: int,
    today_count: int,
    total_count: int,
    avg_score: float,
    daily_stats: list[dict],
    score_dist: dict,
    all_records: list[dict],
    max_daily: int,
    start_hour: int,
    end_hour: int,
    user_name: str,
) -> str:
    """组装整个 Bento 统计网格 (不含表格)."""
    hour = datetime.now().hour
    return (
        '<div class="bento-dash">'
        + _BENTO_STYLE
        + '  <div class="bento-grid">'
        + _tile_hero(user_name, today_count, hour)
        + _tile_kpi("remain", str(remaining), "今日可投递额度", "blue", "📬")
        + _tile_kpi("today", str(today_count), "今日已投递", "pink", "🚀")
        + _tile_kpi("total", str(total_count), "累计投递总数", "violet", "📊")
        + _tile_kpi("avg", f"{avg_score:.1f}", "近 7 日均分", "teal", "⭐")
        + _tile_trend(daily_stats)
        + _tile_score_dist(score_dist)
        + _tile_status_dist(all_records)
        + _tile_tips(remaining, max_daily, today_count, hour, start_hour, end_hour)
        + '  </div>'
        '</div>'
    )


def _render_alert(msg: str) -> str:
    """顶部风险提示条 (可选)."""
    if not msg:
        return ""
    return f'<div class="bento-dash"><div class="bento-alert">{msg}</div></div>'


def _render_recent_table(records: list) -> str:
    """最近投递记录瓦片表格."""
    rows_html = ""
    if not records:
        rows_html = (
            '<div class="recent-empty">'
            '  <div class="recent-empty-emoji">📭</div>'
            '  <div class="recent-empty-txt">暂无投递记录</div>'
            '  <div class="recent-empty-sub">点击下方按钮, 开启你的第一次智能投递</div>'
            '  <button class="recent-empty-cta" type="button"'
            '    onclick="var b=document.querySelector(\'#bento-actions-row .ba-pink button\')||document.querySelector(\'#bento-actions-row .ba-pink\');if(b){b.click();}return false;">'
            '    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>'
            '      <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
            '    </svg>'
            '    <span>去「自动投递」</span>'
            '    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>'
            '  </button>'
            '</div>'
        )
    else:
        head = (
            '<div class="recent-row recent-head">'
            '  <div class="rc rc-co">公司</div>'
            '  <div class="rc rc-pos">岗位</div>'
            '  <div class="rc rc-score">匹配分</div>'
            '  <div class="rc rc-time">投递时间</div>'
            '  <div class="rc rc-st">状态</div>'
            '</div>'
        )
        body = []
        for r in records:
            status_key = r[4]
            label, cls = _STATUS_MAP.get(status_key, (status_key, "s-gray"))
            score = r[2]
            try:
                score_int = int(score)
            except (TypeError, ValueError):
                score_int = 0
            score_cls = "sc-high" if score_int >= 85 else ("sc-mid" if score_int >= 60 else "sc-low")
            body.append(
                '<div class="recent-row">'
                f'  <div class="rc rc-co"><span class="co-dot"></span>{_safe(r[0])}</div>'
                f'  <div class="rc rc-pos">{_safe(r[1])}</div>'
                f'  <div class="rc rc-score"><span class="sc-chip {score_cls}">{_safe(score)}</span></div>'
                f'  <div class="rc rc-time">{_safe(r[3])}</div>'
                f'  <div class="rc rc-st"><span class="s-tag {cls}">{_safe(label)}</span></div>'
                '</div>'
            )
        rows_html = head + "".join(body)

    return (
        '<div class="bento-dash">'
        '<div class="b-tile t-recent">'
        '  <div class="tile-head">'
        '    <div class="tile-title">最近投递记录</div>'
        '    <div class="tile-sub">展示最近 5 条</div>'
        '  </div>'
        f'  <div class="recent-list">{rows_html}</div>'
        '</div>'
        '</div>'
    )


# ================================================================
# 对外接口 (保持签名)
# ================================================================
def load_dashboard_data(user_name: str = ""):
    """加载工作台全部数据, 返回 (stats_html, alert_html, table_html)."""
    try:
        settings = get_settings()
        today_count = DeliveryRecordCRUD.get_today_count(user_name=user_name)
        total_count = DeliveryRecordCRUD.get_total_count(user_name=user_name)
        avg_score = DeliveryRecordCRUD.get_avg_score(7, user_name=user_name)
        remaining = max(0, settings.MAX_DAILY_DELIVERY - today_count)
        daily_stats = DeliveryRecordCRUD.get_daily_stats(7, user_name=user_name)
        score_dist = DeliveryRecordCRUD.get_score_distribution(user_name=user_name)
        all_records = DeliveryRecordCRUD.get_all(limit=200, user_name=user_name)

        recent = DeliveryRecordCRUD.get_recent(5, user_name=user_name)
        table_rows = [
            [r["company"], r["position"], r["match_score"], r["create_time"], r["status"]]
            for r in recent
        ]

        hour = datetime.now().hour
        risk_parts: list[str] = []
        if today_count >= settings.MAX_DAILY_DELIVERY:
            risk_parts.append("⚠ 今日投递已达上限，明日解锁")
        if not (settings.DELIVERY_START_HOUR <= hour < settings.DELIVERY_END_HOUR):
            risk_parts.append(
                f"⚠ 当前非投递时段，建议在 "
                f"{settings.DELIVERY_START_HOUR}:00 – {settings.DELIVERY_END_HOUR}:00 投递"
            )
        risk_msg = "  ·  ".join(risk_parts)

        stats_html = _render_stats_html(
            remaining=remaining,
            today_count=today_count,
            total_count=total_count,
            avg_score=avg_score,
            daily_stats=daily_stats,
            score_dist=score_dist,
            all_records=all_records,
            max_daily=settings.MAX_DAILY_DELIVERY,
            start_hour=settings.DELIVERY_START_HOUR,
            end_hour=settings.DELIVERY_END_HOUR,
            user_name=user_name,
        )
        return stats_html, _render_alert(risk_msg), _render_recent_table(table_rows)
    except Exception as e:
        logger.error("加载工作台数据失败: %s", e)
        settings = get_settings()
        empty = _render_stats_html(
            remaining=settings.MAX_DAILY_DELIVERY,
            today_count=0,
            total_count=0,
            avg_score=0.0,
            daily_stats=[],
            score_dist={"high": 0, "medium": 0, "low": 0},
            all_records=[],
            max_daily=settings.MAX_DAILY_DELIVERY,
            start_hour=settings.DELIVERY_START_HOUR,
            end_hour=settings.DELIVERY_END_HOUR,
            user_name=user_name,
        )
        return (
            empty,
            f'<div class="bento-dash"><div class="bento-alert err">数据加载失败: {_safe(e)}</div></div>',
            _render_recent_table([]),
        )


def create_dashboard_page(login_state):
    """创建工作台页面

    Returns:
        6-tuple: (btn_upload, btn_delivery, btn_records,
                  data_cards, risk_alert, recent_table)
    """
    with gr.Column(elem_id="bento-dashboard-root"):
        init_cards, init_alert, init_table = load_dashboard_data("")

        data_cards = gr.HTML(value=init_cards, elem_id="bento-stats-slot")
        risk_alert = gr.HTML(value=init_alert, elem_id="bento-alert-slot")

        with gr.Row(elem_id="bento-actions-row"):
            btn_upload = gr.Button(
                "📄 上传简历", variant="primary", size="lg",
                elem_classes=["bento-action-btn", "ba-blue"],
            )
            btn_delivery = gr.Button(
                "🚀 新建投递任务", variant="secondary", size="lg",
                elem_classes=["bento-action-btn", "ba-pink"],
            )
            btn_records = gr.Button(
                "📋 查看投递记录", variant="secondary", size="lg",
                elem_classes=["bento-action-btn", "ba-violet"],
            )

        recent_table = gr.HTML(value=init_table, elem_id="bento-table-slot")

        with gr.Row(elem_id="bento-refresh-row"):
            refresh_btn = gr.Button(
                "⟳  刷新数据", variant="secondary", size="sm",
                elem_classes=["bento-refresh-btn"],
            )

        def _refresh(state):
            user_name = state.get("user_name", "") if state else ""
            return load_dashboard_data(user_name)

        refresh_btn.click(
            fn=_refresh,
            inputs=[login_state],
            outputs=[data_cards, risk_alert, recent_table],
        )

    return btn_upload, btn_delivery, btn_records, data_cards, risk_alert, recent_table


# ================================================================
# 作用域 CSS (限定在 .bento-dash 下, 不影响其他页面)
# ================================================================
_BENTO_STYLE = """
<style>
/* =========================================================
   Bento Dashboard — 暗色玻璃拟态风 (作用域: .bento-dash)
   ========================================================= */

/* Dashboard 容器 (全局暗色主题已提供页面背景, 这里只做局部强化) */
#bento-dashboard-root {
    position: relative;
    padding: 4px 0 !important;
}
#bento-dashboard-root > * { position: relative; z-index: 1; }

/* 统一卡片外层容器 */
.bento-dash { color: #E6E9F5; }
.bento-dash * { box-sizing: border-box; }

/* Grid 主骨架 */
.bento-dash .bento-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    grid-template-rows: 140px 140px 220px;
    grid-template-areas:
        "hero hero hero hero remain remain today today trend trend trend trend"
        "hero hero hero hero total  total  avg   avg   trend trend trend trend"
        "scoredist scoredist scoredist scoredist statusdist statusdist statusdist statusdist tips tips tips tips";
    gap: 18px;
    margin: 0 0 20px;
    animation: bentoFadeIn 0.6s cubic-bezier(0.2, 0.8, 0.2, 1);
}
@keyframes bentoFadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* 通用瓦片基础样式: 玻璃拟态 */
.bento-dash .b-tile {
    position: relative;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015)),
        rgba(18,14,48,0.55);
    backdrop-filter: blur(20px) saturate(130%);
    -webkit-backdrop-filter: blur(20px) saturate(130%);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    padding: 18px 20px;
    overflow: hidden;
    transition: transform 0.35s cubic-bezier(0.2,0.8,0.2,1),
                border-color 0.3s ease,
                box-shadow 0.3s ease;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.06) inset,
        0 12px 32px rgba(0,0,0,0.35);
}
.bento-dash .b-tile::before {
    content: '';
    position: absolute; inset: 0;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), transparent 60%);
    pointer-events: none;
}
.bento-dash .b-tile:hover {
    transform: translateY(-4px) scale(1.005);
    border-color: rgba(255,255,255,0.18);
    box-shadow:
        0 1px 0 rgba(255,255,255,0.10) inset,
        0 24px 56px rgba(0,0,0,0.55),
        0 6px 18px rgba(79,139,255,0.16);
}

/* 瓦片通用: 标题行 */
.bento-dash .tile-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px;
}
.bento-dash .tile-title {
    font-size: 14px; font-weight: 600; color: #F0F2FA; letter-spacing: 0.3px;
}
.bento-dash .tile-sub {
    font-size: 11.5px; color: rgba(230,233,245,0.55); font-weight: 500;
}
.bento-dash .tile-sub b { color: #E6E9F5; font-weight: 700; }

/* ========== Hero ========== */
.bento-dash .t-hero {
    padding: 28px 30px;
    display: flex; flex-direction: column; justify-content: space-between;
    background:
        radial-gradient(500px 260px at 15% 110%, rgba(255,79,139,0.35), transparent 55%),
        radial-gradient(540px 300px at 100% -20%, rgba(121,90,255,0.45), transparent 55%),
        linear-gradient(135deg, #2A1E62 0%, #391F6F 50%, #5A2A8C 100%);
}
.bento-dash .t-hero-sunrise {
    background:
        radial-gradient(500px 260px at 15% 110%, rgba(255,180,79,0.38), transparent 55%),
        radial-gradient(540px 300px at 100% -20%, rgba(255,90,165,0.35), transparent 55%),
        linear-gradient(135deg, #4C1F5B 0%, #6B265E 50%, #A8384E 100%);
}
.bento-dash .t-hero-noon {
    background:
        radial-gradient(500px 260px at 15% 110%, rgba(79,255,200,0.30), transparent 55%),
        radial-gradient(540px 300px at 100% -20%, rgba(79,139,255,0.40), transparent 55%),
        linear-gradient(135deg, #152B4F 0%, #1D3A70 50%, #224E92 100%);
}
.bento-dash .t-hero-afternoon {
    background:
        radial-gradient(500px 260px at 15% 110%, rgba(255,79,139,0.38), transparent 55%),
        radial-gradient(540px 300px at 100% -20%, rgba(121,90,255,0.48), transparent 55%),
        linear-gradient(135deg, #2A1E62 0%, #391F6F 50%, #5A2A8C 100%);
}
.bento-dash .t-hero-sunset {
    background:
        radial-gradient(500px 260px at 15% 110%, rgba(255,135,79,0.38), transparent 55%),
        radial-gradient(540px 300px at 100% -20%, rgba(181,55,155,0.45), transparent 55%),
        linear-gradient(135deg, #3A1640 0%, #5B1F55 50%, #7D2655 100%);
}
.bento-dash .t-hero-night {
    background:
        radial-gradient(500px 260px at 15% 110%, rgba(79,139,255,0.28), transparent 55%),
        radial-gradient(540px 300px at 100% -20%, rgba(121,90,255,0.28), transparent 55%),
        linear-gradient(135deg, #0C0F2A 0%, #141440 50%, #1E1550 100%);
}
.bento-dash .hero-noise {
    position: absolute; inset: 0; pointer-events: none;
    background-image:
        radial-gradient(rgba(255,255,255,0.10) 1px, transparent 1.2px);
    background-size: 3.5px 3.5px;
    mix-blend-mode: overlay;
    opacity: 0.35;
}
.bento-dash .hero-grid-pattern {
    position: absolute; inset: 0; pointer-events: none;
    background-image:
        linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px);
    background-size: 44px 44px;
    mask-image: radial-gradient(ellipse at 70% 30%, black 0%, transparent 75%);
    -webkit-mask-image: radial-gradient(ellipse at 70% 30%, black 0%, transparent 75%);
    opacity: 0.45;
}
.bento-dash .hero-tagline {
    font-size: 13px; font-weight: 600; letter-spacing: 2.5px; text-transform: uppercase;
    color: rgba(255,255,255,0.72);
    display: inline-block;
    position: relative;
}
.bento-dash .hero-tagline::before {
    content: ''; display: inline-block; vertical-align: middle;
    width: 22px; height: 2px; margin-right: 10px;
    background: linear-gradient(90deg, #FFB4D8, transparent);
}
.bento-dash .hero-greet {
    font-size: 36px; font-weight: 800; color: #FFFFFF;
    line-height: 1.15; letter-spacing: -0.5px;
    text-shadow: 0 2px 24px rgba(0,0,0,0.35);
    margin: 12px 0 2px;
}
.bento-dash .hero-name {
    background: linear-gradient(135deg, #FFD1E4 0%, #C4B5FF 50%, #A8E9FF 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
}
.bento-dash .hero-meta {
    font-size: 13px; color: rgba(255,255,255,0.92); font-weight: 600;
    display: inline-flex; align-items: center; gap: 6px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 100%;
    font-variant-numeric: tabular-nums;
    text-shadow: 0 1px 8px rgba(0,0,0,0.45);
}
.bento-dash .hero-date {
    color: #FFFFFF !important;
    letter-spacing: 0.4px;
}
.bento-dash .hero-meta-dot { opacity: 0.6; color: rgba(255,255,255,0.85); }
.bento-dash .hero-time {
    color: #FFFFFF;
    font-weight: 700;
    letter-spacing: 0.4px;
}
.bento-dash .hero-footer {
    display: flex; align-items: baseline; gap: 10px;
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid rgba(255,255,255,0.10);
}
.bento-dash .hero-today-num {
    font-size: 42px; font-weight: 800; color: #FFFFFF;
    line-height: 1;
    background: linear-gradient(135deg, #FFFFFF 0%, #E0D5FF 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 40px rgba(255,255,255,0.2);
}
.bento-dash .hero-today-label {
    font-size: 13px; color: rgba(255,255,255,0.7); font-weight: 500;
}

/* ========== KPI ========== */
.bento-dash .t-kpi {
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 18px 20px;
}
.bento-dash .t-kpi-blue   { background:
    linear-gradient(180deg, rgba(79,139,255,0.20), rgba(39,99,234,0.08)),
    rgba(18,14,48,0.55);
    border-color: rgba(79,139,255,0.25); }
.bento-dash .t-kpi-pink   { background:
    linear-gradient(180deg, rgba(255,95,143,0.22), rgba(199,48,117,0.08)),
    rgba(18,14,48,0.55);
    border-color: rgba(255,95,143,0.25); }
.bento-dash .t-kpi-violet { background:
    linear-gradient(180deg, rgba(168,115,245,0.22), rgba(110,67,216,0.08)),
    rgba(18,14,48,0.55);
    border-color: rgba(168,115,245,0.25); }
.bento-dash .t-kpi-teal   { background:
    linear-gradient(180deg, rgba(45,212,191,0.22), rgba(15,157,140,0.08)),
    rgba(18,14,48,0.55);
    border-color: rgba(45,212,191,0.25); }

.bento-dash .kpi-icon {
    font-size: 18px; opacity: 0.9;
    width: 32px; height: 32px;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 10px;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.08);
}
.bento-dash .kpi-value {
    font-size: 36px; font-weight: 800; color: #FFFFFF;
    line-height: 1; letter-spacing: -0.5px;
    margin-top: auto;
}
.bento-dash .t-kpi-blue   .kpi-value { background: linear-gradient(135deg,#FFFFFF 0%, #B8D4FF 100%); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.bento-dash .t-kpi-pink   .kpi-value { background: linear-gradient(135deg,#FFFFFF 0%, #FFC4DA 100%); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.bento-dash .t-kpi-violet .kpi-value { background: linear-gradient(135deg,#FFFFFF 0%, #E0D1FF 100%); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.bento-dash .t-kpi-teal   .kpi-value { background: linear-gradient(135deg,#FFFFFF 0%, #B6F5EA 100%); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }

.bento-dash .kpi-label {
    font-size: 12.5px; color: rgba(230,233,245,0.70);
    font-weight: 500; margin-top: 4px;
}
.bento-dash .kpi-orb {
    position: absolute; right: -30px; bottom: -30px;
    width: 110px; height: 110px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.16) 0%, transparent 70%);
    pointer-events: none;
    filter: blur(4px);
}

/* ========== Trend ========== */
.bento-dash .t-trend {
    padding: 18px 16px 14px;
    display: flex; flex-direction: column;
    overflow: hidden;
}
.bento-dash .trend-chart {
    flex: 1; display: grid; grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 8px; align-items: end;
    padding: 10px 4px 0; min-height: 0;
}
.bento-dash .trend-col {
    position: relative; height: 100%; min-width: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: flex-end;
}
.bento-dash .trend-bar-wrap {
    width: 100%; flex: 1; display: flex; align-items: flex-end;
    min-height: 0;
}
.bento-dash .trend-bar {
    width: 100%;
    background: linear-gradient(180deg, #A67AFF 0%, #6E43D8 100%);
    border-radius: 6px 6px 2px 2px;
    box-shadow:
        0 0 24px rgba(168,115,245,0.35),
        inset 0 1px 0 rgba(255,255,255,0.25);
    transition: transform 0.3s ease;
    min-height: 4px;
}
.bento-dash .trend-col.is-today .trend-bar {
    background: linear-gradient(180deg, #FF8AB8 0%, #D8439F 100%);
    box-shadow:
        0 0 28px rgba(255,138,184,0.45),
        inset 0 1px 0 rgba(255,255,255,0.3);
}
.bento-dash .trend-col:hover .trend-bar { transform: scaleY(1.04); transform-origin: bottom; }
.bento-dash .trend-col:hover .trend-tip { opacity: 1; transform: translateY(0); }
.bento-dash .trend-label {
    font-size: 10.5px; color: rgba(230,233,245,0.6);
    margin-top: 6px; font-variant-numeric: tabular-nums;
    white-space: nowrap; text-align: center;
    width: 100%; overflow: visible;
    letter-spacing: 0;
}
.bento-dash .trend-col.is-today .trend-label {
    color: #FFB4D8; font-weight: 700;
}
.bento-dash .trend-tip {
    position: absolute; top: -4px; left: 50%;
    transform: translate(-50%, 0);
    font-size: 10.5px; font-weight: 700; color: rgba(255,255,255,0.75);
    padding: 0; border-radius: 0;
    background: transparent;
    border: none;
    opacity: 0.85; transition: color 0.2s ease, opacity 0.2s ease;
    pointer-events: none; white-space: nowrap;
}
.bento-dash .trend-col.is-today .trend-tip { color: #FFD9EA; opacity: 1; }
.bento-dash .trend-col:hover .trend-tip { opacity: 1; color: #FFFFFF; }

/* ========== Dist (Score) ========== */
.bento-dash .t-dist { padding: 18px 20px; }
.bento-dash .dist-body { display: flex; flex-direction: column; gap: 12px; margin-top: 6px; }
.bento-dash .dist-row-head {
    display: flex; align-items: baseline; justify-content: space-between;
    margin-bottom: 6px;
}
.bento-dash .dist-label { font-size: 12px; color: rgba(230,233,245,0.70); font-weight: 500; }
.bento-dash .dist-val   { font-size: 12px; color: rgba(230,233,245,0.8); }
.bento-dash .dist-val b { font-weight: 700; color: #FFFFFF; margin-right: 6px; font-size: 13px; }
.bento-dash .dist-val em { font-style: normal; color: rgba(230,233,245,0.5); font-size: 11.5px; }
.bento-dash .dist-track {
    width: 100%; height: 8px; border-radius: 6px;
    background: rgba(255,255,255,0.06);
    overflow: hidden;
}
.bento-dash .dist-fill {
    height: 100%; border-radius: 6px;
    transition: width 0.7s cubic-bezier(0.2,0.8,0.2,1);
    box-shadow: 0 0 12px rgba(255,255,255,0.1);
}
.bento-dash .dist-fill.f-high { background: linear-gradient(90deg, #34D399 0%, #10B981 100%); }
.bento-dash .dist-fill.f-mid  { background: linear-gradient(90deg, #60A5FA 0%, #3B82F6 100%); }
.bento-dash .dist-fill.f-low  { background: linear-gradient(90deg, #F87171 0%, #DC2626 100%); }

/* ========== Status dist (Donut) ========== */
.bento-dash .t-statusdist { padding: 18px 20px; }
.bento-dash .statusdist-body {
    display: flex; align-items: center; gap: 20px;
    margin-top: 6px;
    height: calc(100% - 42px);
}
.bento-dash .donut {
    position: relative; flex-shrink: 0;
    width: 132px; height: 132px; border-radius: 50%;
    box-shadow: 0 0 28px rgba(0,0,0,0.25), inset 0 0 0 1px rgba(255,255,255,0.1);
    transition: transform 0.4s cubic-bezier(0.2,0.8,0.2,1);
}
.bento-dash .donut:hover { transform: rotate(6deg) scale(1.03); }
.bento-dash .donut-hole {
    position: absolute; inset: 16px; border-radius: 50%;
    background: radial-gradient(circle at 50% 30%, #1D1847 0%, #100B28 100%);
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
}
.bento-dash .donut-num {
    font-size: 26px; font-weight: 800; color: #FFFFFF; line-height: 1;
}
.bento-dash .donut-lbl {
    font-size: 10.5px; color: rgba(230,233,245,0.55);
    letter-spacing: 1px; margin-top: 4px; text-transform: uppercase;
}
.bento-dash .legend {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 7px;
    flex: 1; min-width: 0; font-size: 12.5px;
}
.bento-dash .leg-item {
    display: flex; align-items: center; gap: 8px;
    color: rgba(230,233,245,0.82);
    min-width: 0;
}
.bento-dash .leg-dot {
    width: 9px; height: 9px; border-radius: 3px; flex-shrink: 0;
    box-shadow: 0 0 8px currentColor;
}
.bento-dash .leg-name {
    flex: 1; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
}
.bento-dash .leg-val {
    color: #FFFFFF; font-weight: 700;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
}

/* ========== Tips ========== */
.bento-dash .t-tips {
    padding: 18px 20px;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden;
}
.bento-dash .tip-list {
    list-style: none; padding: 4px 6px 4px 0; margin: 4px 0 0;
    display: flex; flex-direction: column; gap: 8px;
    flex: 1 1 auto;
    overflow-y: auto;
    min-height: 0;
    /* 自定义滚动条 */
    scrollbar-width: thin;
    scrollbar-color: rgba(168,115,245,0.55) transparent;
    -webkit-mask-image: linear-gradient(180deg,
        transparent 0,
        #000 6px,
        #000 calc(100% - 6px),
        transparent 100%);
            mask-image: linear-gradient(180deg,
        transparent 0,
        #000 6px,
        #000 calc(100% - 6px),
        transparent 100%);
}
.bento-dash .tip-list::-webkit-scrollbar { width: 4px; }
.bento-dash .tip-list::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, rgba(168,115,245,0.55), rgba(141,187,255,0.55));
    border-radius: 4px;
}
.bento-dash .tip-list::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, rgba(168,115,245,0.85), rgba(141,187,255,0.85));
}
.bento-dash .tip-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 10px;
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    transition: background 0.2s ease, border-color 0.2s ease;
}
.bento-dash .tip-item:hover {
    background: rgba(255,255,255,0.06);
    border-color: rgba(255,255,255,0.12);
}
.bento-dash .tip-ico {
    flex-shrink: 0; font-size: 15px; line-height: 1.4;
    width: 24px; text-align: center;
}
.bento-dash .tip-body { flex: 1; min-width: 0; }
.bento-dash .tip-head {
    font-size: 12.5px; font-weight: 600; color: #FFFFFF;
    margin-bottom: 1px;
}
.bento-dash .tip-desc {
    font-size: 11.5px; color: rgba(230,233,245,0.62);
    line-height: 1.35;
}

/* ========== Alert bar ========== */
.bento-dash .bento-alert {
    margin: 0 0 18px;
    padding: 10px 16px;
    background: linear-gradient(90deg, rgba(255,125,0,0.18), rgba(255,125,0,0.06));
    border: 1px solid rgba(255,125,0,0.35);
    border-radius: 12px;
    color: #FFD7AD; font-size: 13px; font-weight: 500;
    box-shadow: 0 0 24px rgba(255,125,0,0.1);
    animation: alertPulse 3s ease-in-out infinite;
}
.bento-dash .bento-alert.err {
    background: linear-gradient(90deg, rgba(245,63,63,0.2), rgba(245,63,63,0.06));
    border-color: rgba(245,63,63,0.4);
    color: #FFB4B4;
}
@keyframes alertPulse {
    0%, 100% { box-shadow: 0 0 24px rgba(255,125,0,0.10); }
    50%      { box-shadow: 0 0 32px rgba(255,125,0,0.22); }
}

/* ========== Recent table ========== */
.bento-dash .t-recent { padding: 20px 22px; }
.bento-dash .recent-list {
    display: flex; flex-direction: column;
    margin-top: 6px;
}
.bento-dash .recent-row {
    display: grid; grid-template-columns: 1.4fr 1.8fr 80px 1.3fr 100px;
    align-items: center; gap: 12px;
    padding: 11px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 13px; color: rgba(230,233,245,0.85);
    transition: background 0.15s ease;
}
.bento-dash .recent-row:last-child { border-bottom: none; }
.bento-dash .recent-row:not(.recent-head):hover {
    background: rgba(255,255,255,0.03);
    border-radius: 10px;
}
.bento-dash .recent-head {
    font-size: 11px; font-weight: 600; color: rgba(230,233,245,0.45);
    text-transform: uppercase; letter-spacing: 1px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding-bottom: 10px;
}
.bento-dash .rc-co { color: #FFFFFF; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.bento-dash .co-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: linear-gradient(135deg, #A873F5, #FF5F8F);
    box-shadow: 0 0 8px rgba(168,115,245,0.6);
    flex-shrink: 0;
}
.bento-dash .sc-chip {
    display: inline-block;
    padding: 3px 10px; border-radius: 12px;
    font-size: 12px; font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.bento-dash .sc-chip.sc-high { background: rgba(52,211,153,0.15); color: #6EE7B7; border: 1px solid rgba(52,211,153,0.3); }
.bento-dash .sc-chip.sc-mid  { background: rgba(96,165,250,0.15); color: #93C5FD; border: 1px solid rgba(96,165,250,0.3); }
.bento-dash .sc-chip.sc-low  { background: rgba(248,113,113,0.15); color: #FCA5A5; border: 1px solid rgba(248,113,113,0.3); }
.bento-dash .s-tag {
    display: inline-block;
    padding: 3px 10px; border-radius: 12px;
    font-size: 11.5px; font-weight: 600;
}
.bento-dash .s-tag.s-gray   { background: rgba(148,163,184,0.15); color: #CBD5E1; border: 1px solid rgba(148,163,184,0.3); }
.bento-dash .s-tag.s-blue   { background: rgba(96,165,250,0.15);  color: #93C5FD; border: 1px solid rgba(96,165,250,0.3); }
.bento-dash .s-tag.s-orange { background: rgba(251,146,60,0.15);  color: #FDBA74; border: 1px solid rgba(251,146,60,0.3); }
.bento-dash .s-tag.s-green  { background: rgba(52,211,153,0.15);  color: #6EE7B7; border: 1px solid rgba(52,211,153,0.3); }
.bento-dash .s-tag.s-red    { background: rgba(248,113,113,0.15); color: #FCA5A5; border: 1px solid rgba(248,113,113,0.3); }
.bento-dash .recent-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 42px 16px; text-align: center;
}
.bento-dash .recent-empty-emoji { font-size: 36px; margin-bottom: 10px; opacity: 0.65; }
.bento-dash .recent-empty-txt { font-size: 14px; color: rgba(230,233,245,0.8); font-weight: 600; }
.bento-dash .recent-empty-sub { font-size: 12px; color: rgba(230,233,245,0.45); margin-top: 4px; }

/* ========== 快捷操作按钮行 ========== */
#bento-dashboard-root #bento-actions-row {
    gap: 16px !important;
    margin: 4px 0 20px !important;
}
#bento-dashboard-root .bento-action-btn {
    height: 58px !important; min-height: 58px !important;
    border-radius: 16px !important;
    font-size: 15px !important; font-weight: 600 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #FFFFFF !important;
    backdrop-filter: blur(20px) saturate(130%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(130%) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.08) inset,
        0 10px 30px rgba(0,0,0,0.35) !important;
    transition: all 0.25s cubic-bezier(0.2,0.8,0.2,1) !important;
    letter-spacing: 0.3px !important;
}
#bento-dashboard-root .bento-action-btn:hover {
    transform: translateY(-2px) !important;
    border-color: rgba(255,255,255,0.2) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.12) inset,
        0 14px 40px rgba(0,0,0,0.5) !important;
}
#bento-dashboard-root .bento-action-btn.ba-blue {
    background: linear-gradient(135deg, #4F8BFF 0%, #2763EA 100%) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.12) inset,
        0 10px 30px rgba(39,99,234,0.35) !important;
}
#bento-dashboard-root .bento-action-btn.ba-pink {
    background: linear-gradient(135deg, #FF5F8F 0%, #C73075 100%) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.12) inset,
        0 10px 30px rgba(199,48,117,0.35) !important;
}
#bento-dashboard-root .bento-action-btn.ba-violet {
    background: linear-gradient(135deg, #A873F5 0%, #6E43D8 100%) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.12) inset,
        0 10px 30px rgba(110,67,216,0.35) !important;
}

/* ========== 刷新按钮 — 绝对定位到 Bento 右上角 (1280+) ========== */
#bento-dashboard-root { position: relative !important; }
#bento-dashboard-root #bento-refresh-row {
    position: absolute !important;
    top: 12px !important;
    right: 12px !important;
    width: auto !important;
    z-index: 8 !important;
    margin: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
    justify-content: flex-end !important;
}
/* 窄屏: 不再绝对定位, 跟随文档流, 防止与 Bento 内容重叠 */
@media (max-width: 1279px) {
    #bento-dashboard-root #bento-refresh-row {
        position: static !important;
        margin-top: 8px !important;
        margin-bottom: 8px !important;
        justify-content: flex-end !important;
    }
}
#bento-dashboard-root .bento-refresh-btn {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: rgba(230,233,245,0.85) !important;
    border-radius: 999px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 7px 14px !important;
    min-width: 0 !important;
    max-width: none !important;
    width: auto !important;
    backdrop-filter: blur(14px) saturate(140%) !important;
    -webkit-backdrop-filter: blur(14px) saturate(140%) !important;
    box-shadow:
        0 4px 14px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.08) !important;
    transition: all 0.22s cubic-bezier(0.2,0.8,0.2,1) !important;
    letter-spacing: 0.3px !important;
}
#bento-dashboard-root .bento-refresh-btn:hover {
    background: linear-gradient(135deg, rgba(79,139,255,0.22), rgba(121,90,255,0.16)) !important;
    color: #F0F2FA !important;
    border-color: rgba(79,139,255,0.42) !important;
    transform: translateY(-1px);
    box-shadow:
        0 8px 20px rgba(79,139,255,0.32),
        inset 0 1px 0 rgba(255,255,255,0.14) !important;
}

/* ========== 最近投递空态 CTA ========== */
.bento-dash button.recent-empty-cta,
.bento-dash .recent-empty-cta {
    margin-top: 14px !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    padding: 10px 18px !important;
    border-radius: 999px !important;
    background: linear-gradient(135deg, #FF5F8F 0%, #C73075 100%) !important;
    background-image: linear-gradient(135deg, #FF5F8F 0%, #C73075 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.22) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px !important;
    cursor: pointer !important;
    box-shadow:
        0 8px 22px rgba(199,48,117,0.45),
        inset 0 1px 0 rgba(255,255,255,0.24) !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.18);
    transition: transform 0.22s cubic-bezier(0.2,0.8,0.2,1), box-shadow 0.25s ease, background 0.25s ease !important;
    width: auto !important;
    min-width: 0 !important;
    line-height: 1.2 !important;
}
.bento-dash button.recent-empty-cta:hover,
.bento-dash .recent-empty-cta:hover {
    transform: translateY(-1px);
    background: linear-gradient(135deg, #FF7AA0 0%, #D63D85 100%) !important;
    box-shadow:
        0 12px 30px rgba(199,48,117,0.58),
        inset 0 1px 0 rgba(255,255,255,0.32) !important;
}
.bento-dash button.recent-empty-cta:active,
.bento-dash .recent-empty-cta:active { transform: translateY(0) !important; }
.bento-dash .recent-empty-cta svg {
    color: rgba(255,255,255,0.98) !important;
    stroke: currentColor !important;
}

/* ========== 强制覆盖 Gradio 容器样式 ========== */
#bento-dashboard-root > .block,
#bento-dashboard-root .gradio-container,
#bento-dashboard-root .html-container,
#bento-dashboard-root .prose {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    color: inherit !important;
}
#bento-dashboard-root .html-container { padding: 0 !important; }

/* ================================================================
   响应式断点
   - >= 1440px : 12 列宽屏 (默认)
   - 1280–1439 : 12 列, 略缩
   - 1024–1279 : 8 列布局
   - 768–1023  : 6 列, 把 trend 单独一行
   - <  768    : 2 列堆叠 (移动端)
   ================================================================ */
@media (max-width: 1439px) {
    .bento-dash .bento-grid {
        gap: 14px;
        grid-template-rows: 132px 132px 210px;
    }
    .bento-dash .b-tile { padding: 16px 18px; border-radius: 18px; }
    .bento-dash .hero-greet { font-size: 30px; }
    .bento-dash .hero-today-num { font-size: 36px; }
    .bento-dash .kpi-value { font-size: 32px; }
}
@media (max-width: 1279px) {
    .bento-dash .bento-grid {
        grid-template-columns: repeat(8, 1fr);
        grid-template-rows: 130px 130px 200px 240px;
        grid-template-areas:
            "hero hero hero hero remain remain today today"
            "hero hero hero hero total  total  avg    avg"
            "trend trend trend trend trend trend trend trend"
            "scoredist scoredist scoredist statusdist statusdist statusdist tips tips";
    }
}
@media (max-width: 1023px) {
    .bento-dash .bento-grid {
        grid-template-columns: repeat(6, 1fr);
        grid-template-rows: 140px 140px 200px auto auto;
        gap: 12px;
        grid-template-areas:
            "hero hero hero hero hero hero"
            "remain remain today today total total"
            "avg avg avg trend trend trend"
            "scoredist scoredist scoredist statusdist statusdist statusdist"
            "tips tips tips tips tips tips";
    }
    .bento-dash .t-hero { min-height: 220px; }
}
@media (max-width: 767px) {
    #bento-dashboard-root {
        padding: 16px !important;
        margin: -12px !important;
    }
    .bento-dash .bento-grid {
        grid-template-columns: repeat(2, 1fr);
        grid-auto-rows: auto;
        gap: 10px;
        grid-template-areas:
            "hero hero"
            "hero hero"
            "remain today"
            "total avg"
            "trend trend"
            "scoredist scoredist"
            "statusdist statusdist"
            "tips tips";
    }
    .bento-dash .b-tile {
        padding: 14px 14px;
        border-radius: 14px;
    }
    .bento-dash .t-hero { min-height: 200px; padding: 16px; }
    .bento-dash .trend-chart { min-height: 120px; }
    .bento-dash .hero-greet { font-size: 26px; line-height: 1.2; }
    .bento-dash .hero-today-num { font-size: 32px; }
    .bento-dash .kpi-value { font-size: 26px; }
    .bento-dash .kpi-label { font-size: 11px; }
    .bento-dash .recent-row {
        grid-template-columns: 1fr 1fr 56px 80px;
        font-size: 12px;
        gap: 8px;
    }
    .bento-dash .rc-time { display: none; }
    .bento-dash .tile-title { font-size: 13px; }
    .bento-dash .tile-sub { font-size: 11px; }
    /* hover 在触屏上去掉 transform, 避免 sticky 残留 */
    .bento-dash .b-tile:hover {
        transform: none;
        box-shadow:
            0 1px 0 rgba(255,255,255,0.06) inset,
            0 12px 32px rgba(0,0,0,0.35);
    }
}
@media (max-width: 480px) {
    .bento-dash .bento-grid {
        grid-template-columns: 1fr;
        grid-template-areas:
            "hero"
            "remain"
            "today"
            "total"
            "avg"
            "trend"
            "scoredist"
            "statusdist"
            "tips";
    }
    .bento-dash .recent-row {
        grid-template-columns: 1fr 80px;
        font-size: 12px;
    }
    .bento-dash .rc-pos, .bento-dash .rc-score { display: none; }
}
</style>
"""
