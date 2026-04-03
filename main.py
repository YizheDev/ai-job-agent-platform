"""AI 求职智能管家 - 项目启动入口

整合所有模块, 初始化数据库/日志/工作流, 启动 Gradio UI。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.logger import get_logger
from app.db.models import init_database

logger = get_logger("main")


def main():
    """主启动函数"""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("%s V%s 启动中...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("=" * 60)

    # 1. 初始化数据库
    logger.info("[1/3] 初始化数据库...")
    init_database()

    # 2. 初始化工作流
    logger.info("[2/3] 初始化 LangGraph 工作流...")
    try:
        from app.workflow.job_workflow import get_workflow
        workflow = get_workflow()
        logger.info("工作流初始化成功")
    except Exception as e:
        logger.warning("工作流初始化跳过 (非必需): %s", e)

    # 3. 启动 UI
    logger.info("[3/3] 启动 Gradio UI...")
    from app.ui.app import create_app
    app = create_app()

    logger.info("所有模块初始化完成, 正在启动服务...")
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        show_error=True,
    )


if __name__ == "__main__":
    main()
