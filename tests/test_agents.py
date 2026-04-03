"""智能体模块单元测试

覆盖: 简历解析、JD 匹配、AI 优化、风控校验、异常处理。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import init_database


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    """测试环境准备"""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("app.db.models.DB_PATH", test_db)
    monkeypatch.setattr("app.core.config.DB_PATH", test_db)
    monkeypatch.setattr("app.core.config.RESUME_DIR", tmp_path / "resumes")
    (tmp_path / "resumes").mkdir()
    init_database()
    yield


class TestResumeAgent:
    def test_parse_resume_pdf(self, tmp_path):
        """测试 PDF 简历解析 (mock PyPDF2)"""
        from app.agents.resume_agent import parse_resume_node

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")

        with patch("app.agents.resume_agent._parse_pdf", return_value="张三\n手机: 13800138000\nPython Java"):
            with patch("app.agents.resume_agent._extract_structure_with_llm") as mock_extract:
                mock_extract.return_value = {
                    "name": "张三", "phone": "13800138000",
                    "skills": ["Python", "Java"], "education": "本科",
                    "experience_years": 3, "email": "", "work_experience": [],
                    "project_experience": [], "education_background": [], "summary": "",
                }
                result = parse_resume_node({"resume_path": str(pdf_file)})

        assert result.get("error_code") == ""
        assert result["resume_struct"]["name"] == "张三"
        assert "Python" in result["resume_struct"]["skills"]
        assert result["resume_id"] > 0

    def test_parse_resume_not_found(self):
        """测试简历文件不存在"""
        from app.agents.resume_agent import parse_resume_node
        result = parse_resume_node({"resume_path": "/nonexistent/file.pdf"})
        assert result["error_code"] == "E001"

    def test_parse_resume_unsupported_format(self, tmp_path):
        """测试不支持的文件格式"""
        from app.agents.resume_agent import parse_resume_node
        txt_file = tmp_path / "resume.txt"
        txt_file.write_text("text content")
        result = parse_resume_node({"resume_path": str(txt_file)})
        assert result["error_code"] == "E001"


class TestJDAgent:
    def test_jd_match_basic(self):
        """测试基础 JD 匹配"""
        from app.agents.jd_agent import jd_match_node

        state = {
            "jd_text": "招聘 Python 后端工程师, 要求 3 年以上经验, 本科学历, 熟悉 Django Flask MySQL Redis Docker",
            "resume_struct": {
                "name": "张三", "skills": ["Python", "Django", "MySQL", "Docker"],
                "education": "本科", "experience_years": 4,
            },
        }

        with patch("app.agents.jd_agent._parse_jd_with_llm") as mock_parse:
            mock_parse.return_value = {
                "position": "Python 后端工程师", "company": "测试公司",
                "required_skills": ["Python", "Django", "Flask", "MySQL", "Redis", "Docker"],
                "experience_years": 3, "education": "本科",
                "responsibilities": [], "keywords": [], "salary": "",
            }
            result = jd_match_node(state)

        assert result.get("error_code") == ""
        assert 0 <= result["match_score"] <= 100
        assert isinstance(result["match_items"], list)
        assert isinstance(result["missing_items"], list)

    def test_jd_text_too_short(self):
        """测试 JD 文本过短"""
        from app.agents.jd_agent import jd_match_node
        result = jd_match_node({"jd_text": "太短了", "resume_struct": {}})
        assert result["error_code"] == "E002"


class TestOptimizeAgent:
    def test_optimize_no_api_key(self):
        """测试未配置 API 时优化失败"""
        from app.agents.optimize_agent import optimize_resume_node

        with patch("app.agents.optimize_agent.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(LLM_API_KEY="")
            result = optimize_resume_node({
                "resume_text": "简历内容", "jd_text": "JD内容",
                "resume_struct": {}, "jd_struct": {},
                "missing_items": [], "weak_items": [],
            })
        assert result["error_code"] == "E008"


class TestRiskAgent:
    def test_risk_check_pass(self):
        """测试风控校验通过"""
        from app.agents.risk_agent import risk_check_node

        with patch("app.agents.risk_agent.DeliveryRecordCRUD.get_today_count", return_value=0):
            with patch("app.agents.risk_agent.get_settings") as mock_s:
                mock_s.return_value = MagicMock(
                    MAX_DAILY_DELIVERY=20, MIN_DELAY_SECONDS=0,
                    MAX_DELAY_SECONDS=0.01,
                    DELIVERY_START_HOUR=0, DELIVERY_END_HOUR=23,
                )
                result = risk_check_node({})

        assert result["risk_passed"] is True

    def test_risk_check_daily_limit(self):
        """测试日投递上限拦截"""
        from app.agents.risk_agent import risk_check_node

        with patch("app.agents.risk_agent.DeliveryRecordCRUD.get_today_count", return_value=20):
            with patch("app.agents.risk_agent.get_settings") as mock_s:
                mock_s.return_value = MagicMock(
                    MAX_DAILY_DELIVERY=20, DELIVERY_START_HOUR=0, DELIVERY_END_HOUR=23,
                )
                result = risk_check_node({})

        assert result["risk_passed"] is False


class TestExceptionAgent:
    def test_handle_captcha(self):
        """测试验证码异常处理"""
        from app.agents.exception_agent import handle_exception_node
        result = handle_exception_node({"error_code": "E003", "error_msg": "验证码"})
        assert result["need_human_intervene"] is True
        assert result["delivery_status"] == "failed"

    def test_handle_login_expired(self):
        """测试登录失效处理"""
        from app.agents.exception_agent import handle_exception_node
        result = handle_exception_node({"error_code": "E004"})
        assert result["need_human_intervene"] is True

    def test_handle_timeout_retry(self):
        """测试超时可重试"""
        from app.agents.exception_agent import handle_exception_node
        result = handle_exception_node({"error_code": "E007"})
        assert result["retry"] is True

    def test_handle_risk_control(self):
        """测试风控触发"""
        from app.agents.exception_agent import handle_exception_node
        result = handle_exception_node({"error_code": "E006"})
        assert result["need_human_intervene"] is True
        assert "风控" in result["error_msg"]
