"""
稳定性分析器

计算数据变化率、生成稳定性报告、检测异常波动。
"""

from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class StabilityLevel(Enum):
    """稳定性等级"""

    STABLE = "stable"  # 变化率 < 5%
    MODERATE = "moderate"  # 变化率 5-20%
    UNSTABLE = "unstable"  # 变化率 20-50%
    VOLATILE = "volatile"  # 变化率 > 50%


@dataclass
class ChangeMetrics:
    """变化指标"""

    field_name: str
    change_count: int = 0
    total_samples: int = 0
    values: List[Any] = field(default_factory=list)
    hashes: List[str] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    @property
    def change_rate(self) -> float:
        if self.total_samples <= 1:
            return 0.0
        return self.change_count / (self.total_samples - 1)

    @property
    def stability_level(self) -> StabilityLevel:
        rate = self.change_rate
        if rate < 0.05:
            return StabilityLevel.STABLE
        elif rate < 0.20:
            return StabilityLevel.MODERATE
        elif rate < 0.50:
            return StabilityLevel.UNSTABLE
        return StabilityLevel.VOLATILE


@dataclass
class StabilityReport:
    """稳定性报告"""

    url: str
    metrics: Dict[str, ChangeMetrics] = field(default_factory=dict)
    overall_level: StabilityLevel = StabilityLevel.STABLE
    id_columns: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    sample_count: int = 0
    notes: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        field_summaries = {}
        for name, m in self.metrics.items():
            field_summaries[name] = {
                "change_rate": f"{m.change_rate:.1%}",
                "stability": m.stability_level.value,
                "samples": m.total_samples,
                "changes": m.change_count,
            }
        return {
            "url": self.url,
            "overall_stability": self.overall_level.value,
            "sample_count": self.sample_count,
            "id_columns": self.id_columns,
            "fields": field_summaries,
            "notes": self.notes,
            "generated_at": self.generated_at.isoformat(),
        }


class StabilityAnalyzer:
    """稳定性分析器

    跟踪多次抓取结果的变化，计算字段级别的变化率，
    生成稳定性报告。
    """

    def __init__(self):
        self._snapshots: Dict[str, List[Dict[str, Any]]] = {}
        self._timestamps: Dict[str, List[datetime]] = {}

    @staticmethod
    def detect_id_columns(records: Sequence[Dict[str, Any]]) -> List[str]:
        """自动检测 ID 列

        通过以下启发式规则识别 ID 列：
        1. 字段名包含 'id'（不区分大小写）
        2. 所有值唯一且非空
        3. 值为整数或类 UUID 字符串
        """
        if not records:
            return []

        candidates: List[str] = []
        all_keys = set()
        for r in records:
            all_keys.update(r.keys())

        for key in all_keys:
            values = [r.get(key) for r in records if key in r]
            if not values:
                continue

            # 名称启发式
            key_lower = key.lower()
            name_match = any(p in key_lower for p in ("id", "_id", "key", "uuid", "pk"))

            # 唯一性检查
            non_none = [v for v in values if v is not None]
            is_unique = len(set(str(v) for v in non_none)) == len(non_none)

            # 类型检查：整数或类 UUID 字符串
            is_id_type = (
                all(
                    isinstance(v, int) or (isinstance(v, str) and (v.isdigit() or len(v) >= 8))
                    for v in non_none
                )
                if non_none
                else False
            )

            if name_match and is_unique:
                candidates.append(key)
            elif is_unique and is_id_type and len(non_none) >= 2:
                candidates.append(key)

        return candidates

    def record(self, url: str, data: Dict[str, Any]):
        """记录一次抓取快照"""
        if url not in self._snapshots:
            self._snapshots[url] = []
            self._timestamps[url] = []
        self._snapshots[url].append(data)
        self._timestamps[url].append(datetime.now())

    def _compute_hash(self, value: Any) -> str:
        return hashlib.sha256(str(value).encode()).hexdigest()[:16]

    def analyze(self, url: str) -> StabilityReport:
        """分析指定 URL 的稳定性"""
        snapshots = self._snapshots.get(url, [])
        timestamps = self._timestamps.get(url, [])

        if not snapshots:
            return StabilityReport(url=url)

        # 收集所有出现过的字段
        all_fields: set = set()
        for snap in snapshots:
            all_fields.update(snap.keys())

        metrics: Dict[str, ChangeMetrics] = {}
        for fname in all_fields:
            cm = ChangeMetrics(field_name=fname, total_samples=len(snapshots))
            prev_hash: Optional[str] = None
            for i, snap in enumerate(snapshots):
                val = snap.get(fname)
                h = self._compute_hash(val)
                cm.values.append(val)
                cm.hashes.append(h)
                if i < len(timestamps):
                    cm.timestamps.append(timestamps[i])
                if prev_hash is not None and h != prev_hash:
                    cm.change_count += 1
                prev_hash = h
            metrics[fname] = cm

        # 计算整体稳定性
        if metrics:
            rates = [m.change_rate for m in metrics.values()]
            avg_rate = statistics.mean(rates)
            if avg_rate < 0.05:
                overall = StabilityLevel.STABLE
            elif avg_rate < 0.20:
                overall = StabilityLevel.MODERATE
            elif avg_rate < 0.50:
                overall = StabilityLevel.UNSTABLE
            else:
                overall = StabilityLevel.VOLATILE
        else:
            overall = StabilityLevel.STABLE

        notes = []
        # 自动检测 ID 列
        id_columns = self.detect_id_columns(snapshots)
        if id_columns:
            notes.append(f"检测到 ID 列: {', '.join(id_columns)}")

        for name, m in metrics.items():
            if m.stability_level == StabilityLevel.VOLATILE:
                notes.append(f"字段 '{name}' 高度不稳定 (变化率: {m.change_rate:.1%})")
            elif m.stability_level == StabilityLevel.UNSTABLE:
                notes.append(f"字段 '{name}' 不稳定 (变化率: {m.change_rate:.1%})")

        return StabilityReport(
            url=url,
            metrics=metrics,
            overall_level=overall,
            id_columns=id_columns,
            sample_count=len(snapshots),
            notes=notes,
        )

    def analyze_all(self) -> Dict[str, StabilityReport]:
        """分析所有已记录 URL 的稳定性"""
        return {url: self.analyze(url) for url in self._snapshots}

    def clear(self, url: Optional[str] = None):
        """清除记录"""
        if url:
            self._snapshots.pop(url, None)
            self._timestamps.pop(url, None)
        else:
            self._snapshots.clear()
            self._timestamps.clear()
