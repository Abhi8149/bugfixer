"""
main.py
-------
BugFixer Lite - main application.

Workflow:
    Step 1: Initialize (load .env, check API key, locate target file)
    Step 2: Understand expected behaviour (behavior_reader.py)
    Step 3: Generate test cases with Model 1 (test_generator.py)
    Step 4: Run initial tests in a TEMPORARY environment (test_runner.py)
    Step 5: Repair the code with Model 2 (repair_agent.py)
    Step 6: Validate the candidate fix in a TEMPORARY environment.
            Only if ALL tests pass is the fix written (propagated)
            into the original target file.
    Step 7: Generate the final report (report_generator.py)

Important: there is no persistent workspace any more. Test execution
always happens inside a temporary folder that Python deletes
automatically at the end of the run. The original target file is
modified ONLY after a candidate fix has passed every generated test
in that temporary environment. If validation fails, the original
file is left completely untouched.

Run with:
    python main.py
    python main.py path/to/your_file.py
"""

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

import behavior_reader
import repair_agent
import report_generator
import test_generator
import test_runner
from llm_client import get_api_key, get_repair_model, get_test_model

# ---------------------------------------------------------------------------
# Configuration: change this path to test a different Python file.
# ---------------------------------------------------------------------------
TARGET_FILE = Path("sample_project") / "order_processing_system.py"

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"

MAX_REPAIR_ATTEMPTS = 2


def print_heading(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def _prepare_temp_environment(env_dir: Path, module_file_name: str,
                              module_code: str, test_file_name: str,
                              test_code: str) -> Path:
    """
    Create one isolated temporary test environment and return its test file.

    Layout created:
        env_dir/
            conftest.py          (makes env_dir importable)
            <module_file_name>   (original OR candidate code)
            tests/<test_file_name>

    The same generated test code is copied into every environment, so
    the "before" and "after" runs execute byte-identical tests. Only
    the module code differs between environments.
    """
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / module_file_name).write_text(module_code, encoding="utf-8")
    # Help pytest find the module copy sitting next to this conftest.
    (env_dir / "conftest.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent))\n",
        encoding="utf-8",
    )
    tests_dir = env_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    env_test_file = tests_dir / test_file_name
    env_test_file.write_text(test_code, encoding="utf-8")
    return env_test_file


def _propagate_fix(target_file: Path, fixed_code: str, original_code: str) -> bool:
    """
    Write a validated fix into the original target file.

    Safety: after writing, the file is re-hashed. If the bytes on disk
    do not exactly match the validated candidate, the original content
    is restored and False is returned.
    """
    candidate_hash = hashlib.sha256(fixed_code.encode("utf-8")).hexdigest()
    try:
        # write_bytes (not write_text) so no newline translation happens
        # on Windows: the file must match the validated candidate exactly.
        target_file.write_bytes(fixed_code.encode("utf-8"))
    except OSError as error:
        print(f"  [Error] Could not write the fix to {target_file}: {error}")
        try:
            target_file.write_bytes(original_code.encode("utf-8"))
        except OSError:
            pass
        return False

    if test_runner.compute_file_hash(target_file) != candidate_hash:
        print("  [Error] Written file does not match the validated candidate. "
              "Restoring the original content.")
        try:
            target_file.write_bytes(original_code.encode("utf-8"))
        except OSError:
            pass
        return False
    return True


def _save_run_artifacts(test_file: Path, plan_path: Path):
    """
    Keep a copy of the generated tests and test plan in reports/.

    Execution happens in the temporary folder (deleted after the run);
    these copies exist purely so you can inspect afterwards what the
    AI generated. They are never executed from reports/.
    """
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        artifacts_dir = REPORTS_DIR / "generated_tests"
        artifacts_dir.mkdir(exist_ok=True)
        if test_file.exists():
            shutil.copy(test_file, artifacts_dir / test_file.name)
        if plan_path and Path(plan_path).exists():
            shutil.copy(plan_path, REPORTS_DIR / "test_plan.md")
        print(f"  Generated tests kept for inspection: "
              f"{artifacts_dir / test_file.name}")
        print(f"  Test plan kept for inspection     : "
              f"{REPORTS_DIR / 'test_plan.md'}")
    except OSError as error:
        print(f"  [Warning] Could not save generated test artifacts: {error}")


def main():
    load_dotenv()

    # ------------------------------------------------------------------
    # Step 1: Initialize the application
    # ------------------------------------------------------------------
    print_heading("BugFixer Lite - AI Test Generation and Code Repair")

    # Allow an optional command-line path, e.g. python main.py other_file.py
    target_file = Path(sys.argv[1]) if len(sys.argv) > 1 else TARGET_FILE
    if not target_file.is_absolute():
        target_file = BASE_DIR / target_file

    # Report data is filled in as the program runs (never hardcoded).
    # Defaults assume failure; real results overwrite them.
    report_data = {
        "project": "BugFixer Lite",
        "target_file": target_file.name,
        "behaviour_mode": "documentation_inference",
        "specification_available": False,
        "bug_detected": False,
        "root_cause": "",
        "repair_explanation": "",
        "test_cases_generated": 0,
        "test_file_unchanged": True,
        "tests_before_repair": {"passed": 0, "failed": 0},
        "tests_after_repair": {"passed": 0, "failed": 0},
        "repair_successful": False,
        "repair_attempts": 0,
        "fix_applied_to_target": False,
        "execution_environment": "temporary_directory",
        "uncertain_behaviours": [],
    }

    try:
        run_workflow(target_file, report_data)
    except FileNotFoundError as error:
        print(f"\n[Error] {error}")
        print("Check that the target file path in main.py (TARGET_FILE) is correct.")
    except ValueError as error:
        # Covers missing API key, invalid generated code and invalid fixes.
        print(f"\n[Error] {error}")
        print("If this is an API key problem: copy .env.example to .env and "
              "add your real OPENROUTER_API_KEY. The key is never printed.")
    except RuntimeError as error:
        # Covers OpenRouter connection problems and empty model responses.
        print(f"\n[Error] {error}")
        print("Check your internet connection, model names in .env "
              f"(TEST_MODEL / REPAIR_MODEL) and that your OpenRouter key is valid.")
    except Exception as error:  # last-resort: explain instead of crashing silently
        print(f"\n[Unexpected error] {type(error).__name__}: {error}")

    # ------------------------------------------------------------------
    # Step 7: Generate final report (always, even after an early error)
    # ------------------------------------------------------------------
    print_heading("Step 7: Generating final report")
    try:
        report_generator.generate_report(report_data, REPORTS_DIR)
        print(f"  JSON report : {REPORTS_DIR / 'repair_report.json'}")
        print(f"  Text report : {REPORTS_DIR / 'repair_report.txt'}")
    except Exception as error:
        print(f"  [Error] Could not write the report: {error}")

    print("\nDone.")
    return report_data


def run_workflow(target_file: Path, report_data: dict):
    """Run Steps 1-6. Fills report_data with actual execution results."""

    # --- Step 1 (continued): check API key and read the target -----------
    api_key = get_api_key()
    if not api_key or api_key == "your_openrouter_api_key_here":
        raise ValueError(
            "OPENROUTER_API_KEY is missing. "
            "Copy .env.example to .env and put your real OpenRouter key there."
        )
    print("  API key found (value hidden).")
    print(f"  Model 1 (tests)  : {get_test_model()}")
    print(f"  Model 2 (repair) : {get_repair_model()}")

    if not target_file.exists():
        raise FileNotFoundError(f"Target source file not found: {target_file}")

    REPORTS_DIR.mkdir(exist_ok=True)

    module_name = target_file.stem
    test_file_name = f"test_{module_name}_generated.py"

    # Keep the original content in memory. It is our safety copy: the
    # file on disk is only overwritten after a fix passes every test.
    original_code = target_file.read_text(encoding="utf-8")
    original_hash = test_runner.compute_file_hash(target_file)

    print(f"  Target file      : {target_file}")
    print("  Approach         : tests run in a temporary environment;")
    print("                     the target file is edited ONLY after a")
    print("                     candidate fix passes all tests there.")

    # ------------------------------------------------------------------
    # Step 2: Understand the expected behaviour
    # ------------------------------------------------------------------
    print_heading("Step 2: Understanding expected behaviour")
    context = behavior_reader.understand_behavior(target_file)
    source_code = context["source_code"]

    report_data["behaviour_mode"] = context["behaviour_mode"]
    report_data["specification_available"] = context["specification_available"]

    if context["specification_available"]:
        print(f"  Mode A - user specification found: {context['specification_file']}")
        print("  Information source: behavior_spec.md (highest priority), "
              "then docstrings and code.")
    else:
        print("  Mode B - no behavior_spec.md found.")
        print("  Information sources: docstrings, comments, type hints, "
              "function/class names and general programming knowledge.")
        print("  (Tip: rename sample_project/behavior_spec.md.example to "
              "behavior_spec.md to use Mode A.)")

    for cls in context["classes"]:
        methods = ", ".join(m["name"] for m in cls["methods"])
        print(f"  Found class {cls['name']} with methods: {methods}")
    for func in context["functions"]:
        print(f"  Found function {func['name']}")

    # ------------------------------------------------------------------
    # Steps 3-6 happen inside ONE temporary folder for the whole run.
    # Python deletes it automatically when this block ends.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory(prefix="bugfixer_") as temp_name:
        temp_root = Path(temp_name)
        print(f"\n  Temporary environment created: {temp_root}")
        print("  (It will be deleted automatically at the end of the run.)")

        # --------------------------------------------------------------
        # Step 3: Generate test cases with Model 1
        # --------------------------------------------------------------
        print_heading("Step 3: Generating test cases (Model 1)")
        generated_dir = temp_root / "generated"
        test_file = generated_dir / "tests" / test_file_name

        gen_result = test_generator.generate_test_cases(
            context, source_code, test_file
        )
        report_data["test_cases_generated"] = gen_result["test_count"]
        report_data["uncertain_behaviours"] = gen_result["uncertain_behaviours"]

        print(f"  Generated {gen_result['test_count']} test cases.")
        print(f"  Test file (temporary): {test_file}")
        print(f"  Test plan (temporary): {gen_result['plan_path']}")
        if gen_result["uncertain_behaviours"]:
            print("  Uncertain behaviours reported by Model 1:")
            for item in gen_result["uncertain_behaviours"]:
                print(f"    - {item}")
        else:
            print("  Uncertain behaviours: none reported.")

        generated_tests = test_file.read_text(encoding="utf-8")

        # Hash BEFORE repair: the same tests must judge the candidate.
        hash_before = test_runner.compute_file_hash(test_file)

        # --------------------------------------------------------------
        # Step 4: Run initial tests in a temporary "before" environment
        # --------------------------------------------------------------
        print_heading("Step 4: Running generated tests in temporary "
                      "environment (before repair)")
        before_env = temp_root / "before_repair"
        before_test_file = _prepare_temp_environment(
            before_env, target_file.name, original_code,
            test_file_name, generated_tests,
        )
        result_before = test_runner.run_tests(before_env, before_test_file)
        print(result_before["output"])
        if result_before["error"]:
            print(result_before["error"])
        print(f"  Passed: {result_before['passed_count']}  "
              f"Failed: {result_before['failed_count']}")

        # If everything passed, the bug may be missed by the tests.
        # Give Model 1 exactly one improved attempt.
        if result_before["passed"]:
            print("\n  All tests passed. Asking Model 1 for one improved "
                  "attempt to look for missed boundary/documented-example "
                  "cases...")
            try:
                gen_result = test_generator.generate_improved_tests(
                    context, source_code, gen_result, test_file
                )
                generated_tests = test_file.read_text(encoding="utf-8")
                report_data["test_cases_generated"] = gen_result["test_count"]
                report_data["uncertain_behaviours"] = \
                    gen_result["uncertain_behaviours"]
                hash_before = test_runner.compute_file_hash(test_file)

                print(f"  Improved suite: {gen_result['test_count']} test "
                      "cases. Re-running in a fresh temporary environment...")
                before_env = temp_root / "before_repair_improved"
                before_test_file = _prepare_temp_environment(
                    before_env, target_file.name, original_code,
                    test_file_name, generated_tests,
                )
                result_before = test_runner.run_tests(
                    before_env, before_test_file
                )
                print(result_before["output"])
                if result_before["error"]:
                    print(result_before["error"])
                print(f"  Passed: {result_before['passed_count']}  "
                      f"Failed: {result_before['failed_count']}")
            except (ValueError, RuntimeError) as error:
                print(f"  [Warning] Improved test attempt failed: {error}")
                print("  Keeping the original generated tests.")

        # Keep inspectable copies in reports/ (never executed from there).
        _save_run_artifacts(test_file, Path(gen_result["plan_path"]))

        report_data["tests_before_repair"] = {
            "passed": result_before["passed_count"],
            "failed": result_before["failed_count"],
        }

        if result_before["passed"]:
            # No failure -> do NOT invent a repair request.
            print("\n  The generated tests did not expose a defect.")
            print("  No repair request will be sent to Model 2.")
            print(f"  Target file NOT modified: {target_file}")
            report_data["bug_detected"] = False
            report_data["tests_after_repair"] = dict(
                report_data["tests_before_repair"]
            )
            return

        report_data["bug_detected"] = True
        print("\n  Failures detected. These real failures will be sent "
              "to Model 2.")

        # --------------------------------------------------------------
        # Steps 5 + 6: Candidate repair, validated in temp environments
        # --------------------------------------------------------------
        current_source = original_code
        current_result = result_before
        repair_successful = False
        attempts = 0

        while attempts < MAX_REPAIR_ATTEMPTS:
            attempts += 1
            report_data["repair_attempts"] = attempts
            print_heading(f"Step 5: Repair attempt {attempts} (Model 2)")

            try:
                repair = repair_agent.repair_code(
                    source_code=current_source,
                    behavior_context=context,
                    generated_tests=generated_tests,
                    test_results=current_result,
                    test_plan=gen_result["test_plan"],
                )
            except (ValueError, RuntimeError) as error:
                print(f"  [Error] Repair attempt {attempts} failed: {error}")
                break

            report_data["root_cause"] = repair["root_cause"]
            report_data["repair_explanation"] = repair["repair_explanation"]
            print(f"  Root cause: {repair['root_cause']}")
            print(f"  Repair    : {repair['repair_explanation']}")
            print("  Candidate received. It will be tested in a temporary "
                  "environment BEFORE the target file is touched.")

            # ----------------------------------------------------------
            # Step 6: Validate the candidate in its own temp environment
            # ----------------------------------------------------------
            print_heading(f"Step 6: Validating repair attempt {attempts} "
                          "in temporary environment")
            hash_after = test_runner.compute_file_hash(test_file)
            test_file_unchanged = hash_after == hash_before
            report_data["test_file_unchanged"] = test_file_unchanged
            print(f"  Test file unchanged: {test_file_unchanged}")
            if not test_file_unchanged:
                print("  [Error] The test file changed. Validation result "
                      "rejected; target file NOT modified.")
                break

            after_env = temp_root / f"after_repair_attempt_{attempts}"
            after_test_file = _prepare_temp_environment(
                after_env, target_file.name, repair["fixed_code"],
                test_file_name, generated_tests,
            )
            result_after = test_runner.run_tests(after_env, after_test_file)
            print(result_after["output"])
            if result_after["error"]:
                print(result_after["error"])
            print(f"  Passed: {result_after['passed_count']}  "
                  f"Failed: {result_after['failed_count']}")

            report_data["tests_after_repair"] = {
                "passed": result_after["passed_count"],
                "failed": result_after["failed_count"],
            }

            if result_after["passed"]:
                # THE ONLY PLACE the original target file is written.
                print("\n  All tests passed in the temporary environment.")
                print(f"  Propagating the validated fix into: {target_file}")
                if _propagate_fix(target_file, repair["fixed_code"],
                                  original_code):
                    repair_successful = True
                    report_data["fix_applied_to_target"] = True
                    print("  Fix applied to the target file and verified "
                          "by hash.")
                else:
                    print("  [Error] Propagation failed; original content "
                          "was restored where possible.")
                break

            # Failed: try once more with the new failure output.
            current_source = repair["fixed_code"]
            current_result = result_after
            if attempts < MAX_REPAIR_ATTEMPTS:
                print("  Candidate did not pass. Target file NOT modified. "
                      "Sending the new failures to Model 2 for one more "
                      "attempt...")
            else:
                print("  Second candidate also failed validation. "
                      "Target file NOT modified.")

        report_data["repair_successful"] = repair_successful
        if not repair_successful:
            # We never wrote to the target on failure paths; verify it.
            if test_runner.compute_file_hash(target_file) == original_hash:
                print(f"  Confirmed: target file is unchanged: {target_file}")
            else:
                print(f"  [Warning] Target file hash differs unexpectedly: "
                      f"{target_file}")


if __name__ == "__main__":
    main()
