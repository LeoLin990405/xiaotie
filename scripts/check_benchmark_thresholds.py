import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _check_metric(name: str, actual: float, baseline: float, ratio: float) -> tuple[bool, str]:
    required = baseline * ratio
    passed = actual >= required
    status = "PASS" if passed else "FAIL"
    message = (
        f"[{status}] {name}: actual={actual:.2f}, required>={required:.2f}, "
        f"baseline={baseline:.2f}, ratio={ratio:.2f}"
    )
    return passed, message


def _build_report(baseline: dict, latest: dict) -> dict:
    ratio = float(baseline.get("threshold_ratio", 0.9))
    checks = [
        (
            "event.batch_events_per_sec",
            float(latest["event_benchmark"]["batch_events_per_sec"]),
            float(baseline["event_benchmark"]["batch_events_per_sec"]),
        ),
        (
            "storage.insert_per_sec",
            float(latest["storage_benchmark"]["insert_per_sec"]),
            float(baseline["storage_benchmark"]["insert_per_sec"]),
        ),
    ]
    metric_results = []
    all_passed = True
    for name, actual, expected in checks:
        required = expected * ratio
        passed = actual >= required
        metric_results.append(
            {
                "name": name,
                "actual": round(actual, 2),
                "baseline": round(expected, 2),
                "required": round(required, 2),
                "ratio": ratio,
                "passed": passed,
            }
        )
        if not passed:
            all_passed = False
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_timestamp": latest.get("timestamp"),
        "threshold_ratio": ratio,
        "passed": all_passed,
        "metrics": metric_results,
    }


def _render_markdown(report: dict) -> str:
    status = "PASS" if report["passed"] else "FAIL"
    lines = [
        "# Performance Gate Report",
        "",
        f"- Status: **{status}**",
        f"- Generated At: {report['generated_at']}",
        f"- Threshold Ratio: {report['threshold_ratio']:.2f}",
        "",
        "| Metric | Actual | Required | Baseline | Result |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for metric in report["metrics"]:
        result = "PASS" if metric["passed"] else "FAIL"
        lines.append(
            f"| {metric['name']} | {metric['actual']:.2f} | {metric['required']:.2f} | {metric['baseline']:.2f} | {result} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="benchmarks/baseline.json")
    parser.add_argument("--latest", default="benchmarks/results/latest.json")
    parser.add_argument("--report-json", default="benchmarks/results/performance-gate-report.json")
    parser.add_argument("--report-md", default="benchmarks/results/performance-gate-report.md")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    latest_path = Path(args.latest)

    baseline = _read_json(baseline_path)
    latest = _read_json(latest_path)

    report = _build_report(baseline, latest)
    for metric in report["metrics"]:
        passed, message = _check_metric(
            metric["name"],
            float(metric["actual"]),
            float(metric["baseline"]),
            float(metric["ratio"]),
        )
        print(message)
        if not passed:
            report["passed"] = False

    report_json_path = Path(args.report_json)
    report_md_path = Path(args.report_md)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(_render_markdown(report), encoding="utf-8")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
