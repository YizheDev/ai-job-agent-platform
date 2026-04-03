"""数据库 CRUD 单元测试

覆盖: 简历表、投递记录表、系统配置表、异常日志表、JD匹配记录表。
"""

from __future__ import annotations

import os
import sys
import json
import pytest
import sqlite3
from pathlib import Path

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import init_database, get_connection
from app.db.crud import (
    ResumeCRUD,
    DeliveryRecordCRUD,
    SysConfigCRUD,
    ExceptionLogCRUD,
    JDMatchRecordCRUD,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库"""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("app.db.models.DB_PATH", test_db)
    monkeypatch.setattr("app.core.config.DB_PATH", test_db)
    init_database()
    yield


class TestResumeCRUD:
    def test_create_and_get(self):
        rid = ResumeCRUD.create("test.pdf", "/path/test.pdf", "pdf", 1024)
        assert rid > 0
        resume = ResumeCRUD.get_by_id(rid)
        assert resume is not None
        assert resume["file_name"] == "test.pdf"
        assert resume["is_original"] == 1

    def test_get_all(self):
        ResumeCRUD.create("a.pdf", "/a.pdf", "pdf")
        ResumeCRUD.create("b.docx", "/b.docx", "docx")
        all_resumes = ResumeCRUD.get_all()
        assert len(all_resumes) >= 2

    def test_update(self):
        rid = ResumeCRUD.create("test.pdf", "/path/test.pdf", "pdf")
        ok = ResumeCRUD.update(rid, file_name="updated.pdf")
        assert ok
        resume = ResumeCRUD.get_by_id(rid)
        assert resume["file_name"] == "updated.pdf"

    def test_set_default(self):
        r1 = ResumeCRUD.create("a.pdf", "/a.pdf", "pdf")
        r2 = ResumeCRUD.create("b.pdf", "/b.pdf", "pdf")
        ResumeCRUD.set_default(r2)
        assert ResumeCRUD.get_by_id(r2)["is_default"] == 1
        assert ResumeCRUD.get_by_id(r1)["is_default"] == 0

    def test_delete_original_fails(self):
        rid = ResumeCRUD.create("test.pdf", "/test.pdf", "pdf", is_original=True)
        ok = ResumeCRUD.delete(rid)
        assert not ok

    def test_delete_non_original(self):
        parent = ResumeCRUD.create("orig.pdf", "/orig.pdf", "pdf")
        child = ResumeCRUD.create("opt.pdf", "/opt.pdf", "pdf", is_original=False, parent_id=parent)
        ok = ResumeCRUD.delete(child)
        assert ok
        assert ResumeCRUD.get_by_id(child) is None

    def test_count_versions(self):
        parent = ResumeCRUD.create("orig.pdf", "/orig.pdf", "pdf")
        for i in range(3):
            ResumeCRUD.create(f"v{i}.pdf", f"/v{i}.pdf", "pdf", is_original=False, parent_id=parent)
        assert ResumeCRUD.count_versions(parent) == 3


class TestDeliveryRecordCRUD:
    def test_create_and_get(self):
        rid = DeliveryRecordCRUD.create("TestCo", "Engineer", "https://example.com")
        assert rid > 0
        record = DeliveryRecordCRUD.get_by_id(rid)
        assert record["company"] == "TestCo"

    def test_get_today_count(self):
        for _ in range(3):
            DeliveryRecordCRUD.create("Co", "Pos", "https://url.com", status="success")
        count = DeliveryRecordCRUD.get_today_count()
        assert count >= 3

    def test_update_status(self):
        rid = DeliveryRecordCRUD.create("Co", "Pos", "https://url.com")
        DeliveryRecordCRUD.update_status(rid, "success")
        record = DeliveryRecordCRUD.get_by_id(rid)
        assert record["status"] == "success"

    def test_get_recent(self):
        for i in range(10):
            DeliveryRecordCRUD.create(f"Co{i}", f"Pos{i}", f"https://url{i}.com")
        recent = DeliveryRecordCRUD.get_recent(5)
        assert len(recent) == 5

    def test_delete(self):
        rid = DeliveryRecordCRUD.create("Co", "Pos", "https://url.com")
        DeliveryRecordCRUD.delete(rid)
        assert DeliveryRecordCRUD.get_by_id(rid) is None

    def test_score_distribution(self):
        DeliveryRecordCRUD.create("A", "P", "u", match_score=90)
        DeliveryRecordCRUD.create("B", "P", "u", match_score=70)
        DeliveryRecordCRUD.create("C", "P", "u", match_score=40)
        dist = DeliveryRecordCRUD.get_score_distribution()
        assert dist["high"] >= 1
        assert dist["medium"] >= 1
        assert dist["low"] >= 1


class TestSysConfigCRUD:
    def test_set_and_get(self):
        SysConfigCRUD.set("test_key", "test_value")
        assert SysConfigCRUD.get("test_key") == "test_value"

    def test_update_existing(self):
        SysConfigCRUD.set("key", "v1")
        SysConfigCRUD.set("key", "v2")
        assert SysConfigCRUD.get("key") == "v2"

    def test_get_all(self):
        SysConfigCRUD.set("a", "1")
        SysConfigCRUD.set("b", "2")
        configs = SysConfigCRUD.get_all()
        assert "a" in configs
        assert "b" in configs

    def test_delete(self):
        SysConfigCRUD.set("del_key", "val")
        SysConfigCRUD.delete("del_key")
        assert SysConfigCRUD.get("del_key") is None


class TestExceptionLogCRUD:
    def test_create_and_get(self):
        lid = ExceptionLogCRUD.create("E001", "Test error")
        assert lid > 0
        logs = ExceptionLogCRUD.get_all()
        assert len(logs) >= 1

    def test_mark_resolved(self):
        lid = ExceptionLogCRUD.create("E003", "Captcha")
        ExceptionLogCRUD.mark_resolved(lid)

    def test_get_recent(self):
        for i in range(5):
            ExceptionLogCRUD.create(f"E00{i}", f"Error {i}")
        recent = ExceptionLogCRUD.get_recent(3)
        assert len(recent) == 3


class TestJDMatchRecordCRUD:
    def test_create_and_get(self):
        parent = ResumeCRUD.create("r.pdf", "/r.pdf", "pdf")
        mid = JDMatchRecordCRUD.create(parent, "JD text here", match_score=85)
        assert mid > 0
        records = JDMatchRecordCRUD.get_by_resume(parent)
        assert len(records) >= 1

    def test_delete(self):
        parent = ResumeCRUD.create("r2.pdf", "/r2.pdf", "pdf")
        mid = JDMatchRecordCRUD.create(parent, "JD2")
        JDMatchRecordCRUD.delete(mid)
        assert len(JDMatchRecordCRUD.get_all()) == 0 or all(r["id"] != mid for r in JDMatchRecordCRUD.get_all())
