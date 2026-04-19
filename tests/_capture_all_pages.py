"""批量截图当前 Gradio 服务的所有页面 (登录 + 7 个主 Tab).

用途: 一次性验证全局暗色主题在所有页面的表现.
产物: test_screenshots/page_<n>_<name>.png
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PAGES: list[tuple[str, str]] = [
    # (展示名, 左侧导航按钮文本: 严格匹配界面实际文本)
    ("dashboard", "工作台"),
    ("resume", "简历管理"),
    ("jd_match", "JD匹配"),
    ("optimize", "简历优化"),
    ("boss_account", "BOSS账号"),
    ("delivery", "自动投递"),
    ("records", "投递记录"),
    ("settings", "系统设置"),
]


def _read_env(key: str, default: str = "") -> str:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def main() -> None:
    out_dir = PROJECT_ROOT / "test_screenshots"
    out_dir.mkdir(exist_ok=True)

    from playwright.sync_api import sync_playwright

    url = "http://127.0.0.1:7860/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        page.on(
            "console",
            lambda msg: print(f"  [console {msg.type}] {msg.text}"[:300]),
        )
        page.on(
            "pageerror",
            lambda err: print(f"  [pageerror] {err}"[:300]),
        )

        # 1) 登录页截图
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 等 Gradio 注入样式 + 组件
        try:
            page.wait_for_selector("#login-panel, #main-tabs", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        shot = out_dir / "page_00_login.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"[0/8] login → {shot.name}")

        # 2) 检查是否已经登录 (持久化恢复的 case)
        main_tabs_visible = False
        try:
            page.wait_for_selector("#main-tabs:visible", timeout=3000)
            main_tabs_visible = True
        except Exception:
            pass

        if not main_tabs_visible:
            print("  未登录, 填表登录...")
            api_key = _read_env("LLM_API_KEY")
            base_url = _read_env("LLM_BASE_URL", "https://api.deepseek.com")
            model = _read_env("LLM_MODEL", "deepseek-chat")
            print(f"  凭据: user=zhangsan, url={base_url}, model={model}")

            page.locator('#login-card input[type="text"]').first.fill("zhangsan")
            page.locator('#login-card input[type="password"]').first.fill(api_key)
            page.locator("#login-btn").click()

            # 轮询 login-panel 是否隐藏 (成功 or 进入协议页)
            import time as _time
            deadline = _time.time() + 60
            passed = False
            while _time.time() < deadline:
                page.wait_for_timeout(800)
                login_vis = page.locator("#login-panel").is_visible()
                if not login_vis:
                    passed = True
                    break
                err_text = ""
                try:
                    err_text = page.locator(".login-error-text").first.inner_text(timeout=200)
                except Exception:
                    pass
                if err_text:
                    print(f"  登录错误: {err_text}")
                    page.screenshot(
                        path=str(out_dir / "page_99_login_error.png"),
                        full_page=True,
                    )
                    browser.close()
                    return

            if not passed:
                print("  登录超时")
                page.screenshot(
                    path=str(out_dir / "page_99_timeout.png"),
                    full_page=True,
                )
                browser.close()
                return

            # 登录面板已隐藏, 凭据已落盘到 .env + BrowserState (localStorage).
            # Gradio 的 lazy 渲染 bug: click 更新 visible=True 时有时不会 mount main_panel.
            # 解决: 重载页面, 让 app.load 从 BrowserState 恢复 session, 此时主面板会在
            # 初始 config 中就拿到 visible=True, 正常渲染.
            print("  登录成功, 重载页面以触发 session 恢复...")
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # 判断当前处于协议页 还是 主面板
            for i in range(45):
                if (
                    page.locator("#main-panel").count() > 0
                    and page.locator("#main-panel").is_visible()
                ):
                    break
                if page.locator("#agreement-panel").is_visible():
                    print("  协议页, 点击 '已阅读并同意'...")
                    btn = page.locator(
                        '#agreement-panel button:has-text("已阅读并同意")'
                    ).first
                    if btn.count() == 0:
                        btn = page.locator("#agreement-panel button").first
                    try:
                        btn.click(timeout=3000)
                    except Exception as e:
                        print(f"  点击失败: {e}")
                    page.wait_for_timeout(2000)
                    continue
                if i % 5 == 0:
                    print(
                        "  等待主面板/协议页...",
                        f"main-panel 存在={page.locator('#main-panel').count()}",
                        f"agreement 可见={page.locator('#agreement-panel').is_visible()}",
                    )
                page.wait_for_timeout(800)

            if not page.locator("#main-panel").is_visible():
                print("  主面板未出现, 当前 DOM:")
                try:
                    print("    login-panel:", page.locator("#login-panel").is_visible())
                    print("    agreement-panel:", page.locator("#agreement-panel").is_visible())
                    print("    main-panel:", page.locator("#main-panel").is_visible())
                    print("    main-tabs:", page.locator("#main-tabs").is_visible())
                    # dump DOM for 排查
                    html_dump = page.content()
                    (out_dir / "page_99_dom.html").write_text(
                        html_dump, encoding="utf-8"
                    )
                    print(f"    已写出 DOM 到 {out_dir/'page_99_dom.html'}")
                except Exception as e:
                    print(f"    调试异常: {e}")
                page.screenshot(
                    path=str(out_dir / "page_99_noTabs.png"),
                    full_page=True,
                )
                browser.close()
                return
            print("  主面板已可见")

        # 3) 等主界面稳定
        page.wait_for_timeout(2500)

        # 3.1) 如果 #main-panel 仍带 hide 类, 手动去掉 (Gradio lazy 渲染遗留)
        page.evaluate(
            """
            () => {
                const p = document.querySelector('#main-panel');
                if (p) p.classList.remove('hide');
                document.querySelectorAll('#main-tabs, #main-tabs > .tab-wrapper, #main-tabs > .tabitem, #main-tabs .tab-container').forEach(el => el.classList.remove('hide'));
            }
            """
        )
        # 存主界面初始截图
        page.screenshot(
            path=str(out_dir / "page_00b_mainloaded.png"), full_page=True
        )
        # 把主界面全文 dump 一下, 方便对照实际 tab label
        (out_dir / "page_main_dom.html").write_text(
            page.content(), encoding="utf-8"
        )
        print("  主界面 DOM 已 dump 到 page_main_dom.html")

        # 4) 遍历所有 tab. 选中可见的 role=tab 按钮
        for i, (slug, label) in enumerate(PAGES, start=1):
            try:
                btn = page.locator(
                    f'#main-tabs [role="tab"]:has-text("{label}")'
                ).first
                if btn.count() == 0:
                    print(f"[{i}/8] {slug} ({label}) — 未找到按钮, 跳过")
                    continue
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click(timeout=5000)
                page.wait_for_timeout(2500)
                shot = out_dir / f"page_{i:02d}_{slug}.png"
                page.screenshot(path=str(shot), full_page=True)
                selected = page.evaluate(
                    """
                    () => {
                        const s = document.querySelector(
                          '#main-tabs [role="tab"][aria-selected="true"]'
                        );
                        return s ? s.textContent.trim() : null;
                    }
                    """
                )
                print(f"[{i}/8] {slug} -> {shot.name} (selected: {selected})")
            except Exception as e:
                safe = str(e).encode("ascii", "ignore").decode("ascii")
                print(f"[{i}/8] {slug} FAIL: {safe[:200]}")

        browser.close()

    print("done.")


if __name__ == "__main__":
    main()
