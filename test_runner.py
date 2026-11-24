"""
test_runner.py
--------------
Module 3: Test Execution Engine.

Executes generated tests with Pytest in a subprocess and reports counts.
Also provides the SHA-256 hash helpers used to prove the test file did
not change between the "before repair" and "after repair" runs.

Safety notes:
    - shell=True is never used.
    - A timeout is enforced.
    - This is a basic safeguard, not a full security sandbox.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 120


def compute_file_hash(file_path) -> str:
    """Return the SHA-256 hex digest of a file."""
    path = Path(file_path)
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _parse_counts(output: str) -> tuple:
    """
    Extract (passed, failed) counts from pytest output.

    Pytest summary looks like: "3 failed, 7 passed in 0.42s"
    We parse those numbers; missing values default to 0.
    Also counts lines starting with FAILED for a fallback failed count.
    """
    passed = 0
    failed = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    error_match = re.search(r"(\d+)\s+error", output)
    if error_match and failed == 0:
        # Collection errors etc. Count them as failures for reporting.
        failed = int(error_match.group(1))

    return passed, failed


def run_tests(execution_dir, test_file) -> dict:
    """
    Run a pytest test file and return a simple result dictionary.

    Args:
        execution_dir: working directory for the subprocess
                       (a temporary environment folder created by main.py
                       containing a module copy and the generated tests).
        test_file: path to the test file to execute.

    Returns:
        {
            "passed": bool (True only if return_code == 0),
            "output": combined stdout text,
            "error": stderr text,
            "return_code": int,
            "passed_count": int,
            "failed_count": int,
        }
    """
    execution_root = Path(execution_dir)
    test_path = Path(test_file)

    if not test_path.exists():
        return {
            "passed": False,
            "output": "",
            "error": f"Test file not found: {test_path}",
            "return_code": -1,
            "passed_count": 0,
            "failed_count": 0,
        }

    # Run pytest with the current Python interpreter.
    # -v gives one line per test; --tb=short keeps tracebacks readable.
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-v",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(execution_root),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "output": "",
            "error": f"Test execution timed out after {TIMEOUT_SECONDS} seconds.",
            "return_code": -1,
            "passed_count": 0,
            "failed_count": 0,
        }
    except OSError as error:
        return {
            "passed": False,
            "output": "",
            "error": f"Could not start pytest: {error}",
            "return_code": -1,
            "passed_count": 0,
            "failed_count": 0,
        }

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    passed_count, failed_count = _parse_counts(output)

    return {
        "passed": completed.returncode == 0,
        "output": completed.stdout or "",
        "error": completed.stderr or "",
        "return_code": completed.returncode,
        "passed_count": passed_count,
        "failed_count": failed_count,
    }


def combined_output(result: dict) -> str:
    """Return stdout + stderr as one string (handy for sending to Model 2)."""
    return ((result.get("output") or "") + "\n" + (result.get("error") or "")).strip()
