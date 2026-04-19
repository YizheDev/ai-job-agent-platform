"""UI 功能测试

覆盖: 应用构建、页面创建、基本交互。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import init_database


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("app.db.models.DB_PATH", test_db)
    monkeypatch.setattr("app.core.config.DB_PATH", test_db)
    init_database()
    yield


class TestAppCreation:
    def test_create_app(self):
        """测试 Gradio 应用创建"""
        from app.ui.app import create_app
        app = create_app()
        assert app is not None

    def test_check_agreement_default(self):
        """测试默认协议未同意"""
        from app.ui.app import _check_agreement
        assert _check_agreement() is False

    def test_accept_agreement(self):
        """测试接受协议"""
        from app.ui.app import _accept_agreement
        result = _accept_agreement({"user_name": "testuser"})
        assert result is not None


class TestDashboardData:
    def test_load_dashboard(self):
        """测试工作台数据加载"""
        from app.ui.pages.dashboard import load_dashboard_data
        cards_html, risk_html, recent_html = load_dashboard_data("testuser")
        assert isinstance(cards_html, str)
        assert isinstance(risk_html, str)
        assert isinstance(recent_html, str)


class TestResumePageFunctions:
    def test_get_resume_list_empty(self):
        """测试空简历列表"""
        from app.ui.pages.resume import _get_resume_list
        result = _get_resume_list()
        assert isinstance(result, list)


class TestSettingsPageFunctions:
    def test_load_settings(self):
        """测试加载设置"""
        from app.ui.pages.settings import _load_settings
        result = _load_settings()
        assert len(result) == 9

    def test_save_risk_settings(self):
        """测试保存风控设置 (生成器: 先 loading 态, 再最终结果)"""
        from app.ui.pages.settings import _save_risk_settings
        msgs = list(_save_risk_settings(20, 2, 4, 9, 18, 70))
        assert len(msgs) >= 1
        final = msgs[-1]
        assert "成功" in final
