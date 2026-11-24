"""
repair_agent.py
---------------
Module 4: AI Bug Detection and Repair (Model 2).

Receives the original source, behaviour context, generated tests and the
real Pytest failure output. Asks Model 2 for ROOT_CAUSE / REPAIR_EXPLANATION /
FIXED_CODE, validates the fixed code with AST, and returns it.

This module never writes the fix to disk. main.py first validates the
candidate in a temporary environment and writes it into the original
target file only if every generated test passes there.
"""

import ast
import re
from pathlib import Path

from behavior_reader import format_behavior_context
from llm_client import call_llm, get_repair_model

MODEL2_INSTRUCTIONS = """You are an experienced Python debugging and automated program repair engineer.

Your job is to identify and correct the actual programming bug.

You are given:

1. Original Python source code.
2. Intended behaviour and requirements.
3. Generated test cases.
4. The reasoning behind each test.
5. Actual test execution results.

Perform these steps:

STEP 1: Understand the original class and its methods.

STEP 2: Understand the intended behaviour from the documentation and specification.

STEP 3: Analyse the failed tests.

STEP 4: Identify the root cause of each relevant failure.

STEP 5: Explain why the current implementation produces incorrect results.

STEP 6: Generate the smallest reasonable code correction.

STEP 7: Preserve the original class name, method names, parameters and expected functionality.

STEP 8: Do not modify the test cases.

STEP 9: Do not remove validation rules just to make tests pass.

STEP 10: Do not introduce unrelated changes.

IMPORTANT:

Do not blindly trust every generated test if its expected behaviour is unsupported or marked uncertain.

Prioritise explicit user specifications and documented requirements.

If the tests contradict the documented behaviour, explain the conflict rather than changing correct code to satisfy an incorrect test.

Return:

ROOT_CAUSE:
Explain the bug in simple language.

REPAIR_EXPLANATION:
Explain what needs to change.

FIXED_CODE:
Return the complete corrected Python source file.

Do not return Markdown code fences around FIXED_CODE.
"""


def _extract_section(text: str, start_marker: str, end_marker: str = None) -> str:
    """Extract text between two markers."""
    start = text.upper().find(start_marker.upper())
    if start == -1:
        return ""
    start = start + len(start_marker)
    # Skip the ":" that usually follows a marker, e.g. "FIXED_CODE:".
    if start < len(text) and text[start] == ":":
        start += 1
    if end_marker:
        end = text.upper().find(end_marker.upper(), start)
        if end == -1:
            return text[start:].strip()
        return text[start:end].strip()
    return text[start:].strip()


def _clean_fixed_code(code: str) -> str:
    """Remove markdown fences from FIXED_CODE if the model added them anyway."""
    cleaned = code.strip()
    # Remove a leading ```python / ``` fence and trailing fence.
    cleaned = re.sub(r"^```(?:python)?\s*\n", "", cleaned)
    cleaned = re.sub(r"\n```\s*$", "", cleaned)
    return cleaned.strip() + "\n"


def parse_repair_response(response: str) -> dict:
    """Split Model 2's response into root cause / explanation / fixed code."""
    root_cause = _extract_section(response, "ROOT_CAUSE", "REPAIR_EXPLANATION")
    explanation = _extract_section(response, "REPAIR_EXPLANATION", "FIXED_CODE")
    fixed_raw = _extract_section(response, "FIXED_CODE")
    fixed_code = _clean_fixed_code(fixed_raw) if fixed_raw else ""
    return {
        "root_cause": root_cause,
        "repair_explanation": explanation,
        "fixed_code": fixed_code,
        "raw_response": response,
    }


def validate_fixed_code(fixed_code: str, behavior_context: dict) -> tuple:
    """
    Basic checks on the proposed fix:
        - Not empty.
        - Syntax is valid.
        - Original class names are still present.

    Returns (is_valid, error_message).
    """
    if not fixed_code or not fixed_code.strip():
        return False, "Model 2 returned empty FIXED_CODE."

    try:
        tree = ast.parse(fixed_code)
    except SyntaxError as error:
        return False, f"Fixed code has a syntax error: {error}"

    # The fix must keep the original class names.
    found_classes = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    for cls in behavior_context.get("classes", []):
        if cls["name"] not in found_classes:
            return False, f"Fixed code is missing the original class: {cls['name']}"

    return True, ""


def repair_code(source_code: str, behavior_context: dict,
                generated_tests: str, test_results: dict,
                test_plan: str = "") -> dict:
    """
    Ask Model 2 to repair the code.

    Args:
        source_code: current (buggy) source code text.
        behavior_context: dict from behavior_reader.
        generated_tests: generated test code text.
        test_results: result dict from test_runner.run_tests().
        test_plan: Model 1's test plan / reasoning text.

    Returns:
        dict with root_cause, repair_explanation, fixed_code.
    """
    model_name = get_repair_model()
    context_text = format_behavior_context(behavior_context)

    failure_output = (
        (test_results.get("output") or "")
        + "\n"
        + (test_results.get("error") or "")
    ).strip()

    prompt = (
        MODEL2_INSTRUCTIONS
        + "\n\n=== BEHAVIOUR CONTEXT ===\n"
        + context_text
        + "\n\n=== ORIGINAL SOURCE CODE ===\n"
        + source_code
        + "\n\n=== MODEL 1 TEST PLAN AND REASONING ===\n"
        + (test_plan or "(not provided)")
        + "\n\n=== GENERATED TEST CODE (do not modify these) ===\n"
        + generated_tests
        + "\n\n=== ACTUAL PYTEST FAILURE OUTPUT ===\n"
        + failure_output
    )

    print(f"  [Model 2] Calling {model_name} to diagnose and repair...")
    response = call_llm(prompt, model_name)
    parsed = parse_repair_response(response)

    is_valid, error = validate_fixed_code(parsed["fixed_code"], behavior_context)
    if not is_valid:
        raise ValueError(f"Model 2 returned invalid fixed code: {error}")

    return parsed
