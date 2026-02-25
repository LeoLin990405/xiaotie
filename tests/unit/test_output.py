"""OutputManager 单元测试

测试覆盖：
- OutputFormat 枚举
- SanitizeRule / SanitizeConfig 脱敏配置
- OutputManager
  - to_csv() CSV导出
  - to_json() JSON导出
  - to_jsonl() JSONL导出
  - export() 统一导出
  - export_to_file() 文件导出
  - sanitize_value() 值脱敏
  - sanitize_record() 记录脱敏
  - add_transformer() 数据转换
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xiaotie.scraper.output import (
    OutputFormat,
    OutputManager,
    SanitizeConfig,
    SanitizeRule,
)


# ============================================================
# OutputFormat 测试
# ============================================================


class TestOutputFormat:

    def test_values(self):
        assert OutputFormat.CSV.value == "csv"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.JSONL.value == "jsonl"


# ============================================================
# SanitizeConfig 测试
# ============================================================


class TestSanitizeConfig:

    def test_defaults_disabled(self):
        c = SanitizeConfig(enabled=False)
        assert c.enabled is False
        assert c.rules == []

    def test_defaults_enabled(self):
        c = SanitizeConfig(enabled=True)
        assert c.enabled is True
        assert len(c.rules) > 0  # default rules added

    def test_default_rules_email(self):
        c = SanitizeConfig(enabled=True, mask_email=True)
        patterns = [r.pattern for r in c.rules]
        assert any("@" in p for p in patterns)

    def test_default_rules_phone(self):
        c = SanitizeConfig(enabled=True, mask_phone=True)
        patterns = [r.pattern for r in c.rules]
        assert any("1[3-9]" in p for p in patterns)

    def test_custom_rules(self):
        rule = SanitizeRule(pattern=r"\d{4}", replacement="****")
        c = SanitizeConfig(enabled=True, rules=[rule])
        assert len(c.rules) == 1

    def test_mask_char(self):
        c = SanitizeConfig(mask_char="#")
        assert c.mask_char == "#"


# ============================================================
# OutputManager 基础测试
# ============================================================


class TestOutputManagerInit:

    def test_default(self):
        om = OutputManager()
        assert om._sanitize.enabled is False

    def test_with_sanitize(self):
        config = SanitizeConfig(enabled=True)
        om = OutputManager(sanitize_config=config)
        assert om._sanitize.enabled is True


# ============================================================
# OutputManager 导出测试
# ============================================================


class TestOutputManagerCSV:

    def test_empty_records(self):
        om = OutputManager()
        result = om.to_csv([])
        assert result == ""

    def test_single_record(self):
        om = OutputManager()
        records = [{"name": "Alice", "age": "30"}]
        csv_str = om.to_csv(records)
        assert "name" in csv_str
        assert "Alice" in csv_str
        assert "30" in csv_str

    def test_multiple_records(self):
        om = OutputManager()
        records = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        csv_str = om.to_csv(records)
        assert "Alice" in csv_str
        assert "Bob" in csv_str

    def test_custom_fields(self):
        om = OutputManager()
        records = [{"name": "Alice", "age": "30", "email": "a@b.com"}]
        csv_str = om.to_csv(records, fields=["name", "age"])
        assert "name" in csv_str
        assert "email" not in csv_str.split("\n")[0]  # header


class TestOutputManagerJSON:

    def test_empty_records(self):
        om = OutputManager()
        result = om.to_json([])
        assert json.loads(result) == []

    def test_single_record(self):
        om = OutputManager()
        records = [{"name": "Alice"}]
        result = om.to_json(records)
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_chinese_characters(self):
        om = OutputManager()
        records = [{"name": "张三", "city": "北京"}]
        result = om.to_json(records)
        assert "张三" in result
        assert "北京" in result


class TestOutputManagerJSONL:

    def test_empty_records(self):
        om = OutputManager()
        result = om.to_jsonl([])
        assert result == ""

    def test_multiple_records(self):
        om = OutputManager()
        records = [{"a": 1}, {"b": 2}]
        result = om.to_jsonl(records)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}


class TestOutputManagerExport:

    def test_export_json(self):
        om = OutputManager()
        records = [{"x": 1}]
        result = om.export(records, fmt=OutputFormat.JSON)
        assert json.loads(result) == [{"x": 1}]

    def test_export_csv(self):
        om = OutputManager()
        records = [{"x": "1"}]
        result = om.export(records, fmt=OutputFormat.CSV)
        assert "x" in result

    def test_export_jsonl(self):
        om = OutputManager()
        records = [{"x": 1}]
        result = om.export(records, fmt=OutputFormat.JSONL)
        assert json.loads(result) == {"x": 1}


class TestOutputManagerExportToFile:

    def test_export_json_file(self, tmp_path):
        om = OutputManager()
        records = [{"name": "Test"}]
        path = tmp_path / "out.json"
        om.export_to_file(records, str(path))
        data = json.loads(path.read_text())
        assert data[0]["name"] == "Test"

    def test_export_csv_file(self, tmp_path):
        om = OutputManager()
        records = [{"name": "Test"}]
        path = tmp_path / "out.csv"
        om.export_to_file(records, str(path))
        content = path.read_text()
        assert "name" in content
        assert "Test" in content

    def test_export_jsonl_file(self, tmp_path):
        om = OutputManager()
        records = [{"a": 1}, {"b": 2}]
        path = tmp_path / "out.jsonl"
        om.export_to_file(records, str(path))
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_auto_detect_format(self, tmp_path):
        om = OutputManager()
        records = [{"x": 1}]
        csv_path = tmp_path / "data.csv"
        om.export_to_file(records, str(csv_path))
        assert "x" in csv_path.read_text()

    def test_creates_parent_dirs(self, tmp_path):
        om = OutputManager()
        records = [{"x": 1}]
        path = tmp_path / "sub" / "dir" / "out.json"
        om.export_to_file(records, str(path))
        assert path.exists()


# ============================================================
# OutputManager 脱敏测试
# ============================================================


class TestOutputManagerSanitize:

    def test_sanitize_disabled(self):
        om = OutputManager()
        assert om.sanitize_value("test@example.com") == "test@example.com"

    def test_sanitize_email(self):
        config = SanitizeConfig(enabled=True, mask_email=True)
        om = OutputManager(sanitize_config=config)
        result = om.sanitize_value("contact: test@example.com here")
        assert "test@example.com" not in result
        assert "***@***.***" in result

    def test_sanitize_phone(self):
        config = SanitizeConfig(enabled=True, mask_phone=True)
        om = OutputManager(sanitize_config=config)
        result = om.sanitize_value("电话: 13812345678")
        assert "13812345678" not in result

    def test_sanitize_non_string(self):
        config = SanitizeConfig(enabled=True)
        om = OutputManager(sanitize_config=config)
        assert om.sanitize_value(12345) == 12345

    def test_sanitize_record(self):
        config = SanitizeConfig(enabled=True, mask_email=True)
        om = OutputManager(sanitize_config=config)
        record = {"name": "Alice", "email": "alice@example.com"}
        result = om.sanitize_record(record)
        assert "alice@example.com" not in result["email"]

    def test_sanitize_custom_fields(self):
        config = SanitizeConfig(
            enabled=True,
            custom_fields=["secret"],
            mask_char="*",
        )
        om = OutputManager(sanitize_config=config)
        record = {"name": "Alice", "secret": "my-password"}
        result = om.sanitize_record(record)
        assert result["secret"] == "**********"
        assert result["name"] == "Alice"


# ============================================================
# OutputManager 转换器测试
# ============================================================


class TestOutputManagerTransformer:

    def test_add_transformer(self):
        om = OutputManager()
        om.add_transformer(lambda r: {**r, "extra": True})
        records = [{"name": "Test"}]
        result = om.to_json(records)
        data = json.loads(result)
        assert data[0]["extra"] is True

    def test_multiple_transformers(self):
        om = OutputManager()
        om.add_transformer(lambda r: {**r, "step1": True})
        om.add_transformer(lambda r: {**r, "step2": True})
        records = [{"name": "Test"}]
        result = om.to_json(records)
        data = json.loads(result)
        assert data[0]["step1"] is True
        assert data[0]["step2"] is True


# ============================================================
# OutputManager archive() 测试
# ============================================================


class TestOutputManagerArchive:

    def test_archive_creates_zip(self, tmp_path):
        import zipfile
        om = OutputManager()
        records = [{"name": "Alice", "age": 30}]
        archive_path = tmp_path / "archive.zip"
        om.archive(records, str(archive_path))
        assert archive_path.exists()
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            assert len(names) == 2
            assert any(n.startswith("data_") and n.endswith(".json") for n in names)
            assert "metadata.json" in names

    def test_archive_metadata_content(self, tmp_path):
        import zipfile
        om = OutputManager()
        records = [{"x": 1}, {"x": 2}]
        archive_path = tmp_path / "test.zip"
        om.archive(records, str(archive_path))
        with zipfile.ZipFile(archive_path, "r") as zf:
            meta = json.loads(zf.read("metadata.json"))
            assert meta["record_count"] == 2
            assert meta["format"] == "json"
            assert meta["sanitized"] is False
            assert "created_at" in meta

    def test_archive_csv_format(self, tmp_path):
        import zipfile
        om = OutputManager()
        records = [{"name": "Bob"}]
        archive_path = tmp_path / "csv_archive.zip"
        om.archive(records, str(archive_path), fmt=OutputFormat.CSV)
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            assert any(n.endswith(".csv") for n in names)
            meta = json.loads(zf.read("metadata.json"))
            assert meta["format"] == "csv"

    def test_archive_jsonl_format(self, tmp_path):
        import zipfile
        om = OutputManager()
        records = [{"a": 1}, {"b": 2}]
        archive_path = tmp_path / "jsonl_archive.zip"
        om.archive(records, str(archive_path), fmt=OutputFormat.JSONL)
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            assert any(n.endswith(".jsonl") for n in names)

    def test_archive_creates_parent_dirs(self, tmp_path):
        om = OutputManager()
        records = [{"x": 1}]
        archive_path = tmp_path / "sub" / "dir" / "archive.zip"
        om.archive(records, str(archive_path))
        assert archive_path.exists()

    def test_archive_with_sanitization(self, tmp_path):
        import zipfile
        config = SanitizeConfig(enabled=True, mask_email=True)
        om = OutputManager(sanitize_config=config)
        records = [{"email": "test@example.com", "name": "Alice"}]
        archive_path = tmp_path / "sanitized.zip"
        om.archive(records, str(archive_path))
        with zipfile.ZipFile(archive_path, "r") as zf:
            data_files = [n for n in zf.namelist() if n.startswith("data_")]
            content = zf.read(data_files[0]).decode("utf-8")
            assert "test@example.com" not in content
            meta = json.loads(zf.read("metadata.json"))
            assert meta["sanitized"] is True

    def test_archive_with_fields(self, tmp_path):
        import zipfile
        om = OutputManager()
        records = [{"name": "Alice", "age": 30, "secret": "hidden"}]
        archive_path = tmp_path / "fields.zip"
        om.archive(
            records, str(archive_path),
            fmt=OutputFormat.CSV, fields=["name", "age"],
        )
        with zipfile.ZipFile(archive_path, "r") as zf:
            data_files = [n for n in zf.namelist() if n.startswith("data_")]
            content = zf.read(data_files[0]).decode("utf-8")
            assert "name" in content
            assert "secret" not in content
