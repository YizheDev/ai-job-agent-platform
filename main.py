"""AI 求职智能管家 - 项目启动入口

整合所有模块, 初始化数据库/日志/工作流, 启动 Gradio UI。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.models import init_database

logger = get_logger("main")


def _kill_port(port: int) -> None:
    """终止占用指定端口的进程 (仅 Windows)"""
    if sys.platform != "win32":
        return
    import subprocess
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid.isdigit() and int(pid) != 0:
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        capture_output=True, timeout=5,
                    )
                    logger.info("已终止占用端口 %d 的进程 (PID %s)", port, pid)
    except Exception as e:
        logger.warning("释放端口失败: %s", e)


def main():
    """主启动函数"""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("%s V%s 启动中...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("=" * 60)

    logger.info("[1/3] 初始化数据库...")
    init_database()

    logger.info("[2/3] 初始化 LangGraph 工作流...")
    try:
        from app.workflow.job_workflow import get_workflow
        get_workflow()
        logger.info("工作流初始化成功")
    except Exception as e:
        logger.warning("工作流初始化跳过 (非必需): %s", e)

    logger.info("[3/3] 启动 Gradio UI...")
    from app.ui.app import create_app, APP_THEME, APP_CSS
    app = create_app()

    logger.info("所有模块初始化完成, 正在启动服务...")
    server_port = settings.SERVER_PORT
    _kill_port(server_port)
    is_docker = os.environ.get("DOCKER_CONTAINER", "").lower() in ("1", "true")
    app.launch(
        server_name="0.0.0.0" if is_docker else "127.0.0.1",
        server_port=server_port,
        share=False,
        inbrowser=not is_docker,
        show_error=True,
        theme=APP_THEME,
        css=APP_CSS,
    )


if __name__ == "__main__":
    main()
