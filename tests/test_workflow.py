"""LangGraph 工作流集成测试

覆盖: 主流程编译、节点路由逻辑、异常分支。
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


class TestWorkflowBuild:
    def test_build_workflow(self):
        """测试工作流编译成功"""
        from app.workflow.job_workflow import build_workflow
        workflow = build_workflow()
        assert workflow is not None

    def test_get_workflow_singleton(self):
        """测试工作流单例"""
        from app.workflow import job_workflow
        job_workflow._workflow_instance = None
        w1 = job_workflow.get_workflow()
        w2 = job_workflow.get_workflow()
        assert w1 is w2

    def test_mermaid_graph(self):
        """测试 Mermaid 可视化代码生成"""
        from app.workflow.job_workflow import get_workflow_graph_mermaid
        mermaid = get_workflow_graph_mermaid()
        assert "parse_resume" in mermaid
        assert "match_jd" in mermaid
        assert "delivery" in mermaid
        assert "END" in mermaid


class TestWorkflowRouting:
    def test_route_after_match_pass(self):
        """测试匹配通过路由"""
        from app.workflow.job_workflow import _route_after_match
        with patch("app.workflow.job_workflow.get_settings") as mock_s:
            mock_s.return_value = MagicMock(MATCH_THRESHOLD=70)
            result = _route_after_match({"match_score": 85})
        assert result == "optimize_resume"

    def test_route_after_match_low(self):
        """测试低匹配路由"""
        from app.workflow.job_workflow import _route_after_match
        with patch("app.workflow.job_workflow.get_settings") as mock_s:
            mock_s.return_value = MagicMock(MATCH_THRESHOLD=70)
            result = _route_after_match({"match_score": 50})
        assert result == "record_result"

    def test_route_after_match_error(self):
        """测试匹配异常路由"""
        from app.workflow.job_workflow import _route_after_match
        result = _route_after_match({"error_code": "E002", "match_score": 0})
        assert result == "handle_exception"

    def test_route_after_risk_pass(self):
        """测试风控通过路由"""
        from app.workflow.job_workflow import _route_after_risk
        result = _route_after_risk({"risk_passed": True})
        assert result == "delivery"

    def test_route_after_risk_blocked(self):
        """测试风控拦截路由"""
        from app.workflow.job_workflow import _route_after_risk
        result = _route_after_risk({"risk_passed": False, "risk_message": "限流"})
        assert result == "record_result"

    def test_route_after_delivery_success(self):
        """测试投递成功路由"""
        from app.workflow.job_workflow import _route_after_delivery
        result = _route_after_delivery({"delivery_status": "success"})
        assert result == "record_result"

    def test_route_after_delivery_error(self):
        """测试投递失败路由"""
        from app.workflow.job_workflow import _route_after_delivery
        result = _route_after_delivery({"delivery_status": "failed"})
        assert result == "handle_exception"

    def test_route_after_exception_retry(self):
        """测试异常可重试路由"""
        from app.workflow.job_workflow import _route_after_exception
        result = _route_after_exception({"retry": True})
        assert result == "delivery"

    def test_route_after_exception_abort(self):
        """测试异常终止路由"""
        from app.workflow.job_workflow import _route_after_exception
        result = _route_after_exception({"retry": False})
        assert result == "record_result"


class TestRecordResultNode:
    def test_record_success(self):
        """测试成功记录投递结果"""
        from app.workflow.job_workflow import record_result_node
        result = record_result_node({
            "company": "TestCo",
            "position": "Engineer",
            "position_url": "https://example.com",
            "match_score": 85,
            "delivery_status": "success",
        })
        assert result.get("delivery_record_id") is not None
        assert result.get("delivery_record_id") > 0

    def test_record_error(self):
        """测试记录异常结果"""
        from app.workflow.job_workflow import record_result_node
        result = record_result_node({
            "company": "ErrCo",
            "position": "Dev",
            "position_url": "https://example.com",
            "error_code": "E003",
            "error_msg": "验证码",
            "delivery_status": "failed",
        })
        assert result.get("delivery_record_id") is not None
