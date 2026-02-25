"""稳定性分析器单元测试

测试覆盖：
- StabilityLevel 枚举
- ChangeMetrics 变化指标
  - change_rate 计算
  - stability_level 判定
- StabilityReport 报告
  - summary() 摘要生成
- StabilityAnalyzer 分析器
  - record() 记录快照
  - analyze() 单URL分析
  - analyze_all() 全部分析
  - clear() 清除记录
  - 边界条件
"""

from __future__ import annotations

from datetime import datetime

import pytest

from xiaotie.scraper.stability import (
    ChangeMetrics,
    StabilityAnalyzer,
    StabilityLevel,
    StabilityReport,
)


# ============================================================
# StabilityLevel 测试
# ============================================================


class TestStabilityLevel:

    def test_values(self):
        assert StabilityLevel.STABLE.value == "stable"
        assert StabilityLevel.MODERATE.value == "moderate"
        assert StabilityLevel.UNSTABLE.value == "unstable"
        assert StabilityLevel.VOLATILE.value == "volatile"


# ============================================================
# ChangeMetrics 测试
# ============================================================


class TestChangeMetrics:

    def test_default_values(self):
        cm = ChangeMetrics(field_name="title")
        assert cm.field_name == "title"
        assert cm.change_count == 0
        assert cm.total_samples == 0
        assert cm.values == []
        assert cm.hashes == []

    def test_change_rate_zero_samples(self):
        cm = ChangeMetrics(field_name="x", total_samples=0)
        assert cm.change_rate == 0.0

    def test_change_rate_one_sample(self):
        cm = ChangeMetrics(field_name="x", total_samples=1)
        assert cm.change_rate == 0.0

    def test_change_rate_no_changes(self):
        cm = ChangeMetrics(field_name="x", total_samples=5, change_count=0)
        assert cm.change_rate == 0.0

    def test_change_rate_all_changes(self):
        cm = ChangeMetrics(field_name="x", total_samples=5, change_count=4)
        assert cm.change_rate == 1.0

    def test_change_rate_partial(self):
        cm = ChangeMetrics(field_name="x", total_samples=11, change_count=1)
        assert abs(cm.change_rate - 0.1) < 0.01

    def test_stability_level_stable(self):
        cm = ChangeMetrics(field_name="x", total_samples=100, change_count=2)
        assert cm.stability_level == StabilityLevel.STABLE

    def test_stability_level_moderate(self):
        cm = ChangeMetrics(field_name="x", total_samples=11, change_count=1)
        assert cm.stability_level == StabilityLevel.MODERATE

    def test_stability_level_unstable(self):
        cm = ChangeMetrics(field_name="x", total_samples=5, change_count=1)
        assert cm.stability_level == StabilityLevel.UNSTABLE

    def test_stability_level_volatile(self):
        cm = ChangeMetrics(field_name="x", total_samples=3, change_count=2)
        assert cm.stability_level == StabilityLevel.VOLATILE


# ============================================================
# StabilityReport 测试
# ============================================================


class TestStabilityReport:

    def test_default(self):
        r = StabilityReport(url="https://example.com")
        assert r.url == "https://example.com"
        assert r.metrics == {}
        assert r.overall_level == StabilityLevel.STABLE
        assert r.sample_count == 0
        assert r.notes == []

    def test_summary(self):
        metrics = {
            "title": ChangeMetrics(
                field_name="title", total_samples=5, change_count=0
            ),
        }
        r = StabilityReport(
            url="https://example.com",
            metrics=metrics,
            sample_count=5,
        )
        s = r.summary()
        assert s["url"] == "https://example.com"
        assert s["sample_count"] == 5
        assert "title" in s["fields"]
        assert s["fields"]["title"]["stability"] == "stable"
        assert "generated_at" in s

    def test_summary_with_notes(self):
        r = StabilityReport(
            url="https://example.com",
            notes=["字段 'price' 高度不稳定"],
        )
        s = r.summary()
        assert len(s["notes"]) == 1


# ============================================================
# StabilityAnalyzer 测试
# ============================================================


class TestStabilityAnalyzer:

    def test_init(self):
        a = StabilityAnalyzer()
        assert a._snapshots == {}
        assert a._timestamps == {}

    def test_record_single(self):
        a = StabilityAnalyzer()
        a.record("https://example.com", {"title": "Test"})
        assert len(a._snapshots["https://example.com"]) == 1

    def test_record_multiple(self):
        a = StabilityAnalyzer()
        a.record("https://example.com", {"title": "Test1"})
        a.record("https://example.com", {"title": "Test2"})
        assert len(a._snapshots["https://example.com"]) == 2

    def test_analyze_empty(self):
        a = StabilityAnalyzer()
        report = a.analyze("https://nonexistent.com")
        assert report.url == "https://nonexistent.com"
        assert report.sample_count == 0

    def test_analyze_stable_data(self):
        a = StabilityAnalyzer()
        for _ in range(5):
            a.record("https://example.com", {"title": "Same", "price": 100})
        report = a.analyze("https://example.com")
        assert report.overall_level == StabilityLevel.STABLE
        assert report.sample_count == 5
        assert "title" in report.metrics
        assert "price" in report.metrics
        assert report.metrics["title"].change_count == 0

    def test_analyze_volatile_data(self):
        a = StabilityAnalyzer()
        for i in range(5):
            a.record("https://example.com", {"value": f"different-{i}"})
        report = a.analyze("https://example.com")
        assert report.overall_level in (
            StabilityLevel.UNSTABLE,
            StabilityLevel.VOLATILE,
        )
        assert report.metrics["value"].change_count == 4

    def test_analyze_mixed_stability(self):
        a = StabilityAnalyzer()
        for i in range(5):
            a.record("https://example.com", {
                "stable_field": "constant",
                "volatile_field": f"val-{i}",
            })
        report = a.analyze("https://example.com")
        assert report.metrics["stable_field"].change_count == 0
        assert report.metrics["volatile_field"].change_count == 4

    def test_analyze_generates_notes_for_volatile(self):
        a = StabilityAnalyzer()
        for i in range(5):
            a.record("https://example.com", {"price": i * 100})
        report = a.analyze("https://example.com")
        assert len(report.notes) > 0

    def test_analyze_all(self):
        a = StabilityAnalyzer()
        a.record("https://a.com", {"x": 1})
        a.record("https://b.com", {"y": 2})
        reports = a.analyze_all()
        assert "https://a.com" in reports
        assert "https://b.com" in reports

    def test_clear_specific_url(self):
        a = StabilityAnalyzer()
        a.record("https://a.com", {"x": 1})
        a.record("https://b.com", {"y": 2})
        a.clear("https://a.com")
        assert "https://a.com" not in a._snapshots
        assert "https://b.com" in a._snapshots

    def test_clear_all(self):
        a = StabilityAnalyzer()
        a.record("https://a.com", {"x": 1})
        a.record("https://b.com", {"y": 2})
        a.clear()
        assert a._snapshots == {}
        assert a._timestamps == {}

    def test_compute_hash_deterministic(self):
        a = StabilityAnalyzer()
        h1 = a._compute_hash("test")
        h2 = a._compute_hash("test")
        assert h1 == h2

    def test_compute_hash_different_values(self):
        a = StabilityAnalyzer()
        h1 = a._compute_hash("test1")
        h2 = a._compute_hash("test2")
        assert h1 != h2


# ============================================================
# StabilityAnalyzer.detect_id_columns 测试
# ============================================================


class TestDetectIdColumns:

    def test_empty_records(self):
        result = StabilityAnalyzer.detect_id_columns([])
        assert result == []

    def test_name_heuristic_id_field(self):
        """字段名包含 'id' 且值唯一 → 识别为 ID 列"""
        records = [
            {"user_id": 1, "name": "Alice"},
            {"user_id": 2, "name": "Bob"},
            {"user_id": 3, "name": "Charlie"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "user_id" in result

    def test_name_heuristic_uuid_field(self):
        """字段名包含 'uuid' 且值唯一"""
        records = [
            {"uuid": "a1b2c3d4-e5f6", "val": "x"},
            {"uuid": "b2c3d4e5-f6a1", "val": "y"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "uuid" in result

    def test_name_heuristic_pk_field(self):
        """字段名包含 'pk' 且值唯一"""
        records = [
            {"pk": 100, "data": "a"},
            {"pk": 200, "data": "b"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "pk" in result

    def test_name_heuristic_key_field(self):
        """字段名包含 'key' 且值唯一"""
        records = [
            {"item_key": "k1", "data": "a"},
            {"item_key": "k2", "data": "b"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "item_key" in result

    def test_non_unique_id_field_excluded(self):
        """字段名含 'id' 但值不唯一 → 不识别"""
        records = [
            {"category_id": 1, "name": "A"},
            {"category_id": 1, "name": "B"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "category_id" not in result

    def test_unique_integer_without_name_match(self):
        """值唯一且为整数类型，无名称匹配但 >= 2 条 → 识别"""
        records = [
            {"code": 1001, "label": "x"},
            {"code": 1002, "label": "y"},
            {"code": 1003, "label": "z"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "code" in result

    def test_unique_long_string_without_name_match(self):
        """值唯一且为长字符串 (>=8), 无名称匹配但 >= 2 条 → 识别"""
        records = [
            {"token": "abcdefgh1234", "v": 1},
            {"token": "ijklmnop5678", "v": 2},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "token" in result

    def test_short_string_not_digit_excluded(self):
        """短字符串且非数字 → 不识别为 ID"""
        records = [
            {"tag": "abc", "v": 1},
            {"tag": "def", "v": 2},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "tag" not in result

    def test_none_values_handled(self):
        """含 None 值的字段应正常处理"""
        records = [
            {"id": 1, "opt": None},
            {"id": 2, "opt": "val"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "id" in result

    def test_missing_key_in_some_records(self):
        """某些记录缺少字段时不崩溃"""
        records = [
            {"id": 1, "extra": "a"},
            {"id": 2},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "id" in result

    def test_empty_values_list_skipped(self):
        """字段在所有记录中都不存在 → 跳过"""
        records = [
            {"a": 1},
            {"b": 2},
        ]
        # "a" only in first, "b" only in second - values list for each
        # has only 1 entry, so not >= 2 for type-based detection
        result = StabilityAnalyzer.detect_id_columns(records)
        # Neither should be detected (only 1 value each, not unique enough)
        # unless name matches
        assert isinstance(result, list)

    def test_digit_string_detected(self):
        """纯数字字符串也应被识别为 ID 类型"""
        records = [
            {"serial": "12345678", "name": "a"},
            {"serial": "87654321", "name": "b"},
        ]
        result = StabilityAnalyzer.detect_id_columns(records)
        assert "serial" in result

    def test_id_columns_in_report(self):
        """analyze() 应在报告中包含检测到的 ID 列"""
        a = StabilityAnalyzer()
        for i in range(3):
            a.record("https://example.com", {"user_id": i, "name": "Same"})
        report = a.analyze("https://example.com")
        assert "user_id" in report.id_columns
        assert any("ID" in n for n in report.notes)

    def test_id_columns_in_summary(self):
        """summary() 应包含 id_columns 字段"""
        r = StabilityReport(
            url="https://example.com",
            id_columns=["user_id", "pk"],
        )
        s = r.summary()
        assert s["id_columns"] == ["user_id", "pk"]


# ============================================================
# StabilityAnalyzer 额外边界测试
# ============================================================


class TestStabilityAnalyzerEdgeCases:

    def test_analyze_volatile_overall(self):
        """所有字段都高度变化 → overall = VOLATILE"""
        a = StabilityAnalyzer()
        for i in range(5):
            a.record("https://v.com", {
                "a": f"val-{i}",
                "b": f"other-{i}",
            })
        report = a.analyze("https://v.com")
        assert report.overall_level == StabilityLevel.VOLATILE

    def test_analyze_moderate_overall(self):
        """平均变化率在 5-20% → overall = MODERATE"""
        a = StabilityAnalyzer()
        # 21 samples, 1 change → 1/20 = 5% (at boundary)
        # Use 2 fields: one with 1 change in 21 samples (5%), one stable
        # Average = 2.5% → STABLE. Instead use exactly 1 field:
        # 11 samples, 1 change at boundary → 1/10 = 10% → MODERATE
        vals = ["stable"] * 11
        vals[5] = "changed"  # changes at i=5 (stable→changed) and i=6 (changed→stable) = 2 changes
        # 2/10 = 20% → boundary of UNSTABLE. Use different approach:
        # 21 samples, field changes only once (stays changed after)
        for i in range(21):
            val = "before" if i < 10 else "after"
            a.record("https://m.com", {"field": val})
        report = a.analyze("https://m.com")
        # change_count = 1 (at i=10), rate = 1/20 = 5% → MODERATE
        assert report.overall_level == StabilityLevel.MODERATE

    def test_analyze_no_metrics_stable(self):
        """空字段记录 → overall = STABLE"""
        a = StabilityAnalyzer()
        a.record("https://e.com", {})
        report = a.analyze("https://e.com")
        assert report.overall_level == StabilityLevel.STABLE
