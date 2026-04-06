"""Project entrypoint for the AI job copilot app."""

from __future__ import annotations

import io
import os
import socket
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.models import init_database

logger = get_logger("main")


def _find_available_port(preferred_port: int, search_span: int = 20) -> int:
    """Find an available localhost port starting from the preferred one."""
    for port in range(preferred_port, preferred_port + search_span + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError(f"Cannot find an available port from {preferred_port} to {preferred_port + search_span}.")


def main() -> None:
    """Launch the database, workflow and Gradio UI."""
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
    except Exception as exc:
        logger.warning("工作流初始化跳过（非必须）：%s", exc)

    logger.info("[3/3] 启动 Gradio UI...")
    from app.ui.app import APP_CSS, APP_THEME, create_app

    app = create_app()
    preferred_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    server_port = _find_available_port(preferred_port)

    logger.info("所有模块初始化完成，准备启动服务，端口=%s", server_port)
    app.launch(
        server_name="127.0.0.1",
        server_port=server_port,
        share=False,
        inbrowser=os.getenv("GRADIO_INBROWSER", "1") == "1",
        show_error=True,
        theme=APP_THEME,
        css=APP_CSS,
    )


if __name__ == "__main__":
    main()
