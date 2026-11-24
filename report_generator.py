"""
report_generator.py
-------------------
Module 7: Final Report Generator.

Writes:
    reports/repair_report.json  (machine-readable)
    reports/repair_report.txt   (human-readable)

All values come from actual execution data passed in by main.py.
Nothing is hardcoded.
"""

import json
from pathlib import Path


def generate_report(report_data: dict, reports_dir) -> dict:
    """
    Save the JSON and TXT reports.

    Args:
        report_data: dictionary with all report fields (see main.py).
        reports_dir: folder where reports should be written.

    Returns:
        The same report_data dictionary (for convenience).
    """
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    json_path = reports_path / "repair_report.json"
    txt_path = reports_path / "repair_report.txt"

    # JSON report.
    json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Human-readable TXT report.
    before = report_data.get("tests_before_repair", {})
    after = report_data.get("tests_after_repair", {})
    uncertain = report_data.get("uncertain_behaviours", [])

    lines = []
    lines.append("=" * 60)
    lines.append("BugFixer Lite - Repair Report")
    lines.append("=" * 60)
    lines.append(f"Target file              : {report_data.get('target_file')}")
    lines.append(f"Behaviour mode           : {report_data.get('behaviour_mode')}")
    lines.append(f"Specification available  : {report_data.get('specification_available')}")
    lines.append("")
    lines.append("--- Problem and Root Cause ---")
    lines.append(f"Bug detected             : {report_data.get('bug_detected')}")
    lines.append(f"Root cause               : {report_data.get('root_cause') or '(none)'}")
    lines.append(f"Repair explanation       : {report_data.get('repair_explanation') or '(none)'}")
    lines.append("")
    lines.append("--- Tests ---")
    lines.append(f"Source of expected behaviour : {report_data.get('behaviour_mode')}")
    lines.append(f"Test cases generated     : {report_data.get('test_cases_generated')}")
    lines.append(f"Test file unchanged      : {report_data.get('test_file_unchanged')}")
    lines.append(f"Execution environment    : {report_data.get('execution_environment', 'temporary_directory')}")
    lines.append(f"Fix applied to target    : {report_data.get('fix_applied_to_target', False)}")
    lines.append(f"Tests before repair      : passed={before.get('passed', 0)}, failed={before.get('failed', 0)}")
    lines.append(f"Tests after repair       : passed={after.get('passed', 0)}, failed={after.get('failed', 0)}")
    lines.append("")
    lines.append("--- Repair ---")
    lines.append(f"Code modifications       : {report_data.get('repair_explanation') or '(see root cause above)'}")
    lines.append(f"Repair attempts          : {report_data.get('repair_attempts')}")
    lines.append(f"Repair successful        : {report_data.get('repair_successful')}")
    lines.append(f"Final repair status      : {'SUCCESS' if report_data.get('repair_successful') else 'NOT SUCCESSFUL'}")
    lines.append("")
    lines.append("--- Uncertain Behaviours / Limitations ---")
    if uncertain:
        for item in uncertain:
            lines.append(f"- {item}")
    else:
        lines.append("- None reported by Model 1.")
    lines.append("- Generated tests are an AI consistency check, not a proof of correctness.")
    lines.append("- AST import checks and subprocess timeouts are basic safeguards, "
                 "not a complete security sandbox.")
    lines.append("")

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return report_data
