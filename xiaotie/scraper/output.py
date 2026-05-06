"""
输出管理器

支持 CSV/JSON 导出、数据脱敏、格式化输出。
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


class OutputFormat(Enum):
    """输出格式"""

    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"


@dataclass
class SanitizeRule:
    """脱敏规则"""

    pattern: str
    replacement: str
    fields: List[str] = field(default_factory=list)


@dataclass
class SanitizeConfig:
    """脱敏配置"""

    enabled: bool = True
    rules: List[SanitizeRule] = field(default_factory=list)
    mask_char: str = "*"
    mask_email: bool = True
    mask_phone: bool = True
    mask_id_card: bool = True
    custom_fields: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.enabled and not self.rules:
            self._add_default_rules()

    def _add_default_rules(self):
        if self.mask_email:
            self.rules.append(
                SanitizeRule(
                    pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    replacement="***@***.***",
                )
            )
        if self.mask_phone:
            self.rules.append(
                SanitizeRule(
                    pattern=r"1[3-9]\d{9}",
                    replacement="1**********",
                )
            )
        if self.mask_id_card:
            self.rules.append(
                SanitizeRule(
                    pattern=r"\d{17}[\dXx]",
                    replacement="******************",
                )
            )


class OutputManager:
    """输出管理器

    支持 CSV/JSON/JSONL 导出，内置数据脱敏功能。
    """

    def __init__(
        self,
        sanitize_config: Optional[SanitizeConfig] = None,
    ):
        self._sanitize = sanitize_config or SanitizeConfig(enabled=False)
        self._transformers: List[Callable] = []

    def add_transformer(self, fn: Callable[[Dict], Dict]):
        """添加数据转换器"""
        self._transformers.append(fn)

    def sanitize_value(self, value: Any) -> Any:
        """对单个值进行脱敏"""
        if not self._sanitize.enabled or not isinstance(value, str):
            return value
        result = value
        for rule in self._sanitize.rules:
            result = re.sub(rule.pattern, rule.replacement, result)
        return result

    def sanitize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """对整条记录进行脱敏"""
        if not self._sanitize.enabled:
            return record
        result = {}
        for key, val in record.items():
            should_mask = key in self._sanitize.custom_fields
            if should_mask and isinstance(val, str):
                result[key] = self._sanitize.mask_char * min(len(val), 10)
            else:
                result[key] = self.sanitize_value(val)
        return result

    def _transform(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """应用所有转换器"""
        r = record
        for fn in self._transformers:
            r = fn(r)
        return self.sanitize_record(r)

    def to_csv(
        self,
        records: Sequence[Dict[str, Any]],
        fields: Optional[List[str]] = None,
    ) -> str:
        """导出为 CSV 字符串"""
        if not records:
            return ""
        processed = [self._transform(r) for r in records]
        fieldnames = fields or list(processed[0].keys())

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(processed)
        return output.getvalue()

    def to_json(
        self,
        records: Sequence[Dict[str, Any]],
        indent: int = 2,
    ) -> str:
        """导出为 JSON 字符串"""
        processed = [self._transform(r) for r in records]
        return json.dumps(processed, ensure_ascii=False, indent=indent)

    def to_jsonl(self, records: Sequence[Dict[str, Any]]) -> str:
        """导出为 JSONL 字符串"""
        lines = []
        for r in records:
            processed = self._transform(r)
            lines.append(json.dumps(processed, ensure_ascii=False))
        return "\n".join(lines)

    def export(
        self,
        records: Sequence[Dict[str, Any]],
        fmt: OutputFormat = OutputFormat.JSON,
        fields: Optional[List[str]] = None,
    ) -> str:
        """按指定格式导出"""
        if fmt == OutputFormat.CSV:
            return self.to_csv(records, fields=fields)
        elif fmt == OutputFormat.JSONL:
            return self.to_jsonl(records)
        return self.to_json(records)

    def export_to_file(
        self,
        records: Sequence[Dict[str, Any]],
        path: str,
        fmt: Optional[OutputFormat] = None,
        fields: Optional[List[str]] = None,
    ):
        """导出到文件"""
        p = Path(path)
        if fmt is None:
            ext_map = {".csv": OutputFormat.CSV, ".jsonl": OutputFormat.JSONL}
            fmt = ext_map.get(p.suffix, OutputFormat.JSON)

        content = self.export(records, fmt=fmt, fields=fields)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def archive(
        self,
        records: Sequence[Dict[str, Any]],
        archive_path: str,
        fmt: OutputFormat = OutputFormat.JSON,
        fields: Optional[List[str]] = None,
    ):
        """导出并归档为 zip 文件

        将数据导出为指定格式，然后打包为 zip 归档文件。
        文件名包含时间戳以便追溯。
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = fmt.value
        data_filename = f"data_{ts}.{ext}"

        content = self.export(records, fmt=fmt, fields=fields)

        ap = Path(archive_path)
        ap.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(ap, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(data_filename, content)
            # 写入元数据
            meta = json.dumps(
                {
                    "record_count": len(records),
                    "format": fmt.value,
                    "created_at": datetime.now().isoformat(),
                    "sanitized": self._sanitize.enabled,
                },
                ensure_ascii=False,
                indent=2,
            )
            zf.writestr("metadata.json", meta)
