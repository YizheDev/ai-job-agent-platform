"""Shared UI helpers and cached cross-page snapshot data."""

from __future__ import annotations

import time
from datetime import datetime
from html import escape

from app.core.config import get_settings
from app.db.crud import DeliveryRecordCRUD, ResumeCRUD

_SNAPSHOT_TTL_SECONDS = 15.0
_SNAPSHOT_CACHE: dict[str, object] = {"value": None, "expires_at": 0.0}


def invalidate_ui_snapshot() -> None:
    """Clear the cached UI snapshot after write operations."""
    _SNAPSHOT_CACHE["value"] = None
    _SNAPSHOT_CACHE["expires_at"] = 0.0


def get_ui_snapshot(force: bool = False) -> dict:
    """Return a small cross-page snapshot used by headers and status chips."""
    now = time.monotonic()
    cached_value = _SNAPSHOT_CACHE.get("value")
    if not force and cached_value and now < float(_SNAPSHOT_CACHE["expires_at"]):
        return cached_value  # type: ignore[return-value]

    settings = get_settings()
    resumes = ResumeCRUD.get_all()
    status_counts = DeliveryRecordCRUD.get_status_counts()
    recent = DeliveryRecordCRUD.get_recent(5)
    today = DeliveryRecordCRUD.get_today_count()
    total = DeliveryRecordCRUD.get_total_count()
    avg = DeliveryRecordCRUD.get_avg_score(7)

    original_count = sum(1 for item in resumes if item.get("is_original"))
    optimized_count = max(0, len(resumes) - original_count)
    default_resume = next((item for item in resumes if item.get("is_default")), None)
    latest_resume = resumes[0]["create_time"] if resumes else "暂无记录"

    current_hour = datetime.now().hour
    window_open = settings.DELIVERY_START_HOUR <= current_hour < settings.DELIVERY_END_HOUR
    remaining = max(0, settings.MAX_DAILY_DELIVERY - today)

    top_company = recent[0]["company"] if recent else "暂无目标公司"
    top_position = recent[0]["position"] if recent else "等待导入岗位"
    if not resumes:
        next_action = "先上传简历并完成结构化解析。"
    elif total == 0:
        next_action = "先完成一轮 JD 匹配，筛出优先投递岗位。"
    else:
        next_action = "优先处理待确认任务，再进入投递执行。"

    snapshot = {
        "resume_total": len(resumes),
        "resume_original": original_count,
        "resume_optimized": optimized_count,
        "default_resume_name": default_resume["file_name"] if default_resume else "尚未设置",
        "latest_resume_time": latest_resume,
        "delivery_today": today,
        "delivery_total": total,
        "delivery_success": status_counts.get("success", 0),
        "delivery_pending": status_counts.get("pending", 0),
        "delivery_confirmed": status_counts.get("confirmed", 0),
        "delivery_failed": status_counts.get("failed", 0),
        "delivery_cancelled": status_counts.get("cancelled", 0),
        "delivery_remaining": remaining,
        "avg_score_7d": round(float(avg or 0), 1),
        "window_open": window_open,
        "window_label": f"{settings.DELIVERY_START_HOUR}:00 - {settings.DELIVERY_END_HOUR}:00",
        "top_company": top_company,
        "top_position": top_position,
        "next_action": next_action,
        "recent_records": recent,
        "app_version": settings.APP_VERSION,
    }

    _SNAPSHOT_CACHE["value"] = snapshot
    _SNAPSHOT_CACHE["expires_at"] = now + _SNAPSHOT_TTL_SECONDS
    return snapshot


def render_empty_state(title: str, body: str, hint: str = "", icon: str = "AI") -> str:
    """Render a shared empty-state block."""
    hint_html = f'<div class="empty-state-hint">{escape(hint)}</div>' if hint else ""
    return f"""
    <div class="animated-empty">
        <div class="empty-state-orb"><span>{escape(icon)}</span></div>
        <div class="empty-state-title">{escape(title)}</div>
        <div class="empty-state-body">{escape(body)}</div>
        {hint_html}
    </div>
    """


def render_snapshot_note(prefix: str, body: str) -> str:
    """Render a compact highlighted note block."""
    return (
        '<div class="feature-note">'
        f'<span class="eyebrow" style="display:block;margin-bottom:8px;">{escape(prefix)}</span>'
        f"{escape(body)}"
        "</div>"
    )


def render_skeleton_card(lines: int = 4, with_block: bool = True, with_pills: bool = False) -> str:
    """Render a generic skeleton placeholder."""
    pills = ""
    if with_pills:
        pills = (
            '<div style="display:flex;gap:10px;flex-wrap:wrap;">'
            '<div class="skeleton-pill"></div>'
            '<div class="skeleton-pill"></div>'
            '<div class="skeleton-pill"></div>'
            "</div>"
        )
    block = '<div class="skeleton-block"></div>' if with_block else ""
    line_classes = ["long", "mid", "long", "short", "mid", "long"]
    rows = "".join(
        f'<div class="skeleton-line {line_classes[index % len(line_classes)]}"></div>'
        for index in range(lines)
    )
    return f'<div class="skeleton-shell">{pills}{block}{rows}</div>'


def tab_switch_js(label: str) -> str:
    """Return JS that switches the main tab by its label text."""
    safe_label = label.replace("\\", "\\\\").replace("'", "\\'")
    return f"""
    () => {{
        if (window.__switchJobTab) {{
            window.__switchJobTab('{safe_label}');
            return;
        }}
        const tabs = [...document.querySelectorAll('#main-tabs > .tab-wrapper > .tab-container[role="tablist"] button')];
        const target = tabs.find((btn) => btn.textContent.trim() === '{safe_label}');
        if (target) target.click();
        document.querySelectorAll('.app-nav-btn').forEach((btn) => {{
            btn.classList.toggle('active', btn.dataset.target === '{safe_label}');
        }});
        if (window.__hideNextDockPills) {{
            setTimeout(() => window.__hideNextDockPills(), 0);
        }}
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}
    """
