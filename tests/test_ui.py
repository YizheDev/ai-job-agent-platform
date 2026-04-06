"""UI 功能测试。"""

from __future__ import annotations

import sys
from pathlib import Path

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
        """测试 Gradio 应用创建。"""
        from app.ui.app import create_app

        app = create_app()
        assert app is not None

    def test_check_agreement_default(self):
        """测试默认协议未同意。"""
        from app.ui.app import _check_agreement

        assert _check_agreement() is False

    def test_accept_agreement(self):
        """测试接受协议。"""
        from app.ui.app import _accept_agreement

        result = _accept_agreement()
        assert result is not None


class TestDashboardData:
    def test_load_dashboard(self):
        """测试工作台数据加载。"""
        from app.ui.pages.dashboard import _load_dashboard_data

        remaining, today, total, avg, records, risk = _load_dashboard_data()
        assert isinstance(remaining, int)
        assert isinstance(today, int)
        assert isinstance(total, int)
        assert isinstance(records, list)
        assert isinstance(risk, str)


class TestResumePageFunctions:
    def test_get_resume_list_empty(self):
        """测试空简历列表。"""
        from app.ui.pages.resume import _get_resume_list

        result = _get_resume_list()
        assert isinstance(result, list)

    def test_view_resume_not_found(self):
        """测试查看不存在的简历。"""
        from app.ui.pages.resume import _view_resume

        result = _view_resume("99999")
        assert "不存在" in result


class TestDeliveryPageFunctions:
    def test_create_task_no_resume(self):
        """测试未选择简历创建任务。"""
        from app.ui.pages.delivery import _create_task

        msg, _ = _create_task("", "https://example.com", "Co", "Pos")
        assert "选择简历" in msg

    def test_create_task_no_url(self):
        """测试未输入链接创建任务。"""
        from app.ui.pages.delivery import _create_task

        msg, _ = _create_task("1:test.pdf", "", "Co", "Pos")
        assert "链接" in msg


class TestRecordsPageFunctions:
    def test_load_records_empty(self):
        """测试空记录加载。"""
        from app.ui.pages.records import _load_records

        result = _load_records("全部", "全部")
        assert isinstance(result, list)

    def test_load_stats(self):
        """测试统计数据加载。"""
        from app.ui.pages.records import _load_stats

        daily, dist, summary = _load_stats()
        assert isinstance(daily, str)
        assert isinstance(dist, str)
        assert isinstance(summary, str)


class TestSettingsPageFunctions:
    def test_load_settings(self):
        """测试加载设置。"""
        from app.ui.pages.settings import _load_settings

        result = _load_settings()
        assert len(result) == 9

    def test_save_risk_settings(self):
        """测试保存风控设置。"""
        from app.ui.pages.settings import _save_risk_settings

        msg = _save_risk_settings(20, 2, 4, 9, 18, 70)
        assert "成功" in msg

    def test_do_logout(self):
        """测试退出登录。"""
        from app.ui.pages.settings import _do_logout

        msg = _do_logout()
        assert "退出" in msg or "清除" in msg
