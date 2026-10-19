import html
import json
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class ReportResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        super().startTest(test)
        self.started_at = time.perf_counter()

    def record(self, test, status, details=""):
        self.records.append({
            "test": test.id(),
            "status": status,
            "duration_seconds": round(
                time.perf_counter() - self.started_at, 3
            ),
            "details": details,
            "data": getattr(test, "report_data", {}),
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(
            test, "FAIL", self._exc_info_to_string(err, test)
        )

    def addError(self, test, err):
        super().addError(test, err)
        self.record(
            test, "ERROR", self._exc_info_to_string(err, test)
        )

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "SKIP", reason)


def save_report(result):
    output_dir = BASE_DIR / "reports"
    output_dir.mkdir(exist_ok=True)

    counts = {
        status: sum(
            record["status"] == status
            for record in result.records
        )
        for status in ("PASS", "FAIL", "ERROR", "SKIP")
    }

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tests_run": result.testsRun,
        "successful": result.wasSuccessful(),
        "counts": counts,
        "results": result.records,
    }

    json_path = output_dir / "report.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = []

    for record in result.records:
        sections = []

        for label, value in record["data"].items():
            if not isinstance(value, str):
                value = json.dumps(
                    value,
                    indent=2,
                    ensure_ascii=False,
                )

            sections.append(
                f"<h3>{html.escape(label)}</h3>"
                f"<pre>{html.escape(value)}</pre>"
            )

        if record["details"]:
            sections.append(
                "<h3>Details</h3>"
                f"<pre>{html.escape(record['details'])}</pre>"
            )

        details = ""

        if sections:
            details = (
                    "<details>"
                    "<summary>View details</summary>"
                    + "".join(sections)
                    + "</details>"
            )

        rows.append(
            "<tr>"
            f"<td>{html.escape(record['test'])}</td>"
            f"<td class='{record['status']}'>{record['status']}</td>"
            f"<td>{record['duration_seconds']:.3f} s</td>"
            f"<td>{details}</td>"
            "</tr>"
        )

    summary = " · ".join(
        f"{status}: {count}" for status, count in counts.items()
    )

    page = (
        """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Call Analysis Evals — Test Report</title>
<style>
body {
    font-family: system-ui, sans-serif;
    margin: 40px;
    color: #172033;
    background: #f5f7fb;
}
table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}
th, td {
    padding: 12px;
    border: 1px solid #dce2eb;
    text-align: left;
    vertical-align: top;
}
th { background: #e9eef7; }
.PASS { color: #137333; font-weight: bold; }
.FAIL, .ERROR { color: #b3261e; font-weight: bold; }
.SKIP { color: #805600; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
</head>
<body>
<h1>Call Analysis Evals</h1>
"""
        + f"<p>{html.escape(report['created_at'])}</p>"
        + f"<p>Tests: {result.testsRun} · {summary}</p>"
        + "<table><thead><tr>"
        + "<th>Test</th><th>Status</th>"
        + "<th>Duration</th><th>Failure details</th>"
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )

    html_path = output_dir / "report.html"
    html_path.write_text(page, encoding="utf-8")

    print(f"\nHTML report: {html_path}")
    print(f"JSON report: {json_path}")


def main():
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(BASE_DIR / "tests"),
        pattern="test_*.py",
    )

    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=ReportResult,
    )

    result = runner.run(suite)
    save_report(result)

    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())