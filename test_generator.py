"""
test_generator.py
-----------------
Module 2: AI Test Case Generator (Model 1).

Responsibilities:
    1. Build a prompt from the behaviour context + source code.
    2. Call Model 1 to generate BEHAVIOUR_SUMMARY / TEST_PLAN / TEST_CODE /
       UNCERTAIN_BEHAVIOURS.
    3. Ask Model 1 again to review its own tests (consistency check).
    4. Validate the final test code with AST and an import allow-list.
    5. Save test code and the plan to the (temporary) output path it is given.

The test cases genuinely come from the LLM. Nothing is hardcoded here.
"""

import ast
import re
from pathlib import Path

from behavior_reader import format_behavior_context
from llm_client import call_llm, get_test_model

# Imports that generated test code is allowed to use.
# pytest is required; the target module name is added dynamically.
ALWAYS_ALLOWED_IMPORTS = {"pytest"}

# Things that must never appear in generated test code.
BANNED_NAMES = {"eval", "exec", "open", "__import__", "compile"}
BANNED_IMPORTS = {
    "subprocess",
    "socket",
    "os",
    "sys",
    "shutil",
    "pathlib",
    "requests",
    "urllib",
    "http",
}

MODEL1_INSTRUCTIONS = """You are an experienced Python software testing engineer.

Your task is to understand the intended behaviour of the provided Python class or functions and generate meaningful test cases.

FIRST: Understand the functionality.

Read all provided source code and documentation.

If a user-provided behaviour specification exists, treat it as the highest-priority description of expected behaviour.

If no specification exists, infer the intended behaviour using docstrings, comments, function names, class names, type hints, examples, existing tests and your general programming knowledge.

Do not assume that the existing implementation is correct.

Do not use the actual output of the buggy implementation as the expected output.

SECOND: Prepare a test plan.

Cover the following wherever the documented behaviour supports them:

1. Normal test cases.
2. Boundary conditions.
3. Empty inputs and collections.
4. Invalid inputs.
5. Different object states.
6. Multiple method interactions.
7. Repeated method calls.
8. Expected exceptions.
9. Edge cases.

For each proposed test, explain:

- What it tests.
- What result is expected.
- Why this result is expected.
- Which specification, docstring or other evidence supports it.
- Whether the behaviour is explicit, strongly inferred or uncertain.

Do not invent unsupported business rules.

THIRD: Generate actual Pytest tests.

Write clean and understandable Python test code.

Use:

- pytest assertions.
- pytest.approx for floating-point calculations where appropriate.
- pytest.raises for expected exceptions.
- Simple test functions.
- Clear test names.
- Comments explaining important cases.

Each expected result must be derived independently from the documented behaviour, not copied from the existing implementation's output.

Only generate executable tests for explicit or sufficiently supported inferred behaviour.

List unclear behaviour separately instead of generating misleading assertions.

Do not modify the original source file.

Do not import dangerous modules.

Do not execute operating-system commands.

Do not access external networks.

Your final response must contain:

1. BEHAVIOUR_SUMMARY
2. TEST_PLAN
3. TEST_CODE
4. UNCERTAIN_BEHAVIOURS

Return valid, clearly separated sections.

Do not include unrelated explanations.

Format your response EXACTLY like this:

BEHAVIOUR_SUMMARY:
<summary here>

TEST_PLAN:
<plan here>

TEST_CODE:
```python
<pytest code here>
```

UNCERTAIN_BEHAVIOURS:
<one per line, or the word None>
"""


def _extract_section(text: str, start_marker: str, end_marker: str = None) -> str:
    """Extract text between two section markers (case-insensitive search)."""
    upper = text.upper()
    start = upper.find(start_marker.upper())
    if start == -1:
        return ""
    start = start + len(start_marker)
    # Skip the ":" that usually follows a marker, e.g. "TEST_CODE:".
    if start < len(text) and text[start] == ":":
        start += 1
    if end_marker:
        end = upper.find(end_marker.upper(), start)
        if end == -1:
            return text[start:].strip()
        return text[start:end].strip()
    return text[start:].strip()


def _extract_code(text: str) -> str:
    """Extract python code from a section, removing markdown fences if present."""
    # Prefer a fenced block.
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_model1_response(response: str) -> dict:
    """Split Model 1's response into summary / plan / code / uncertain parts."""
    behaviour_summary = _extract_section(response, "BEHAVIOUR_SUMMARY", "TEST_PLAN")
    test_plan = _extract_section(response, "TEST_PLAN", "TEST_CODE")
    code_section = _extract_section(response, "TEST_CODE", "UNCERTAIN_BEHAVIOURS")
    uncertain_text = _extract_section(response, "UNCERTAIN_BEHAVIOURS")

    test_code = _extract_code(code_section)

    uncertain = []
    if uncertain_text:
        for line in uncertain_text.splitlines():
            cleaned = line.strip(" -*\t")
            if cleaned and cleaned.lower() != "none":
                uncertain.append(cleaned)

    return {
        "behaviour_summary": behaviour_summary,
        "test_plan": test_plan,
        "test_code": test_code,
        "uncertain_behaviours": uncertain,
        "raw_response": response,
    }


def validate_test_code(test_code: str, allowed_module: str) -> tuple:
    """
    Validate generated test code.

    Checks:
        - Syntax is valid (AST parse).
        - Only allowed imports are used.
        - Banned names/imports are rejected.

    Returns (is_valid, error_message).
    """
    if not test_code or not test_code.strip():
        return False, "Generated test code is empty."

    try:
        tree = ast.parse(test_code)
    except SyntaxError as error:
        return False, f"Generated test code has a syntax error: {error}"

    allowed = set(ALWAYS_ALLOWED_IMPORTS)
    allowed.add(allowed_module)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BANNED_IMPORTS:
                    return False, f"Banned import in generated tests: {alias.name}"
                if root not in allowed:
                    return False, f"Import not allowed in generated tests: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in BANNED_IMPORTS:
                    return False, f"Banned import in generated tests: {node.module}"
                if root not in allowed:
                    return False, f"Import not allowed in generated tests: {node.module}"
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                return False, f"Banned name used in generated tests: {node.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr in ("system", "popen", "run", "call"):
                # Only flag when combined with banned modules; basic attr check.
                pass

    # Must contain at least one test function.
    has_test = any(
        isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        for node in ast.walk(tree)
    )
    if not has_test:
        return False, "Generated test code contains no test_ functions."

    return True, ""


def count_tests(test_code: str) -> int:
    """Count test_ functions in the generated code."""
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return 0
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )


def build_test_prompt(behavior_context: dict, source_code: str) -> str:
    """Build the full prompt for Model 1 (test generation)."""
    context_text = format_behavior_context(behavior_context)
    module_name = behavior_context.get("module_name", "target_module")
    prompt = (
        MODEL1_INSTRUCTIONS
        + "\n\n=== BEHAVIOUR CONTEXT ===\n"
        + context_text
        + "\n\n=== SOURCE CODE ===\n"
        + source_code
        + f"\n\nIMPORTANT: In TEST_CODE, import the class/functions from the module "
        f"named '{module_name}' (for example: from {module_name} import ...). "
        f"The test file will be placed next to a copy of that module."
    )
    return prompt


def build_review_prompt(behavior_context: dict, source_code: str, parsed: dict) -> str:
    """Build the prompt for Model 1's self-review of its generated tests."""
    context_text = format_behavior_context(behavior_context)
    prompt = f"""Review these generated tests carefully.

Check whether:

1. Each expected result follows from the documented behaviour.
2. The expected values are calculated correctly.
3. Normal cases are covered.
4. Boundary cases are covered.
5. Invalid inputs are tested where required.
6. Class and method interactions are handled correctly.
7. Any test accidentally assumes behaviour that is not specified.
8. Any test simply reproduces the current implementation instead of checking intended behaviour.

Identify incorrect or unsupported assertions.

Correct the test code where necessary.

Do not introduce undocumented requirements.

Return the revised test code and a brief review report.

Format your response EXACTLY like this:

REVIEW_REPORT:
<brief report here>

TEST_CODE:
```python
<revised pytest code here>
```

UNCERTAIN_BEHAVIOURS:
<one per line, or the word None>

=== BEHAVIOUR CONTEXT ===
{context_text}

=== ORIGINAL SOURCE CODE ===
{source_code}

=== BEHAVIOUR SUMMARY FROM GENERATION ===
{parsed.get('behaviour_summary', '')}

=== TEST PLAN FROM GENERATION ===
{parsed.get('test_plan', '')}

=== GENERATED TEST CODE TO REVIEW ===
{parsed.get('test_code', '')}
"""
    return prompt


def parse_review_response(response: str, fallback_code: str) -> dict:
    """Parse the review response; fall back to the original code if needed."""
    review_report = _extract_section(response, "REVIEW_REPORT", "TEST_CODE")
    code_section = _extract_section(response, "TEST_CODE", "UNCERTAIN_BEHAVIOURS")
    uncertain_text = _extract_section(response, "UNCERTAIN_BEHAVIOURS")
    revised_code = _extract_code(code_section) if code_section else ""

    if not revised_code:
        revised_code = fallback_code

    uncertain = []
    if uncertain_text:
        for line in uncertain_text.splitlines():
            cleaned = line.strip(" -*\t")
            if cleaned and cleaned.lower() != "none":
                uncertain.append(cleaned)

    return {
        "review_report": review_report,
        "test_code": revised_code,
        "uncertain_behaviours": uncertain,
        "raw_response": response,
    }


def generate_test_cases(behavior_context: dict, source_code: str, output_path) -> dict:
    """
    Main entry point for Model 1.

    Args:
        behavior_context: dict from behavior_reader.understand_behavior()
        source_code: original source code text
        output_path: where to save the generated test file
                     (a path inside the temporary run folder)

    Returns:
        dict with keys: behaviour_summary, test_plan, test_code,
        uncertain_behaviours, review_report, test_count, output_path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # test_plan.md lives next to the tests folder (inside the temp run folder)
    plan_path = output_path.parent.parent / "test_plan.md"
    if output_path.parent.name != "tests":
        plan_path = output_path.parent / "test_plan.md"

    model_name = get_test_model()
    module_name = behavior_context.get("module_name", "target_module")

    # --- Step 1: generate tests ------------------------------------------
    prompt = build_test_prompt(behavior_context, source_code)
    print(f"  [Model 1] Calling {model_name} to generate tests...")
    response = call_llm(prompt, model_name)
    parsed = parse_model1_response(response)

    if not parsed["test_code"]:
        raise ValueError("Model 1 did not return TEST_CODE. Cannot continue.")

    # --- Step 2: review the generated tests ------------------------------
    print("  [Model 1] Reviewing generated tests (consistency check)...")
    review_prompt = build_review_prompt(behavior_context, source_code, parsed)
    review_response = call_llm(review_prompt, model_name)
    reviewed = parse_review_response(review_response, parsed["test_code"])

    final_code = reviewed["test_code"]
    # Merge uncertain behaviours from both stages (keep unique, preserve order).
    merged_uncertain = []
    for item in parsed["uncertain_behaviours"] + reviewed["uncertain_behaviours"]:
        if item not in merged_uncertain:
            merged_uncertain.append(item)

    # --- Step 3: validate -------------------------------------------------
    is_valid, error = validate_test_code(final_code, module_name)
    if not is_valid:
        # Try the pre-review code as a fallback.
        ok2, _ = validate_test_code(parsed["test_code"], module_name)
        if ok2:
            print(f"  [Warning] Reviewed test code failed validation ({error}). "
                  "Using the original generated code instead.")
            final_code = parsed["test_code"]
        else:
            raise ValueError(f"Generated test code failed validation: {error}")

    # --- Step 4: save ------------------------------------------------------
    output_path.write_text(final_code, encoding="utf-8")

    plan_text = (
        "# Test Plan (generated by Model 1)\n\n"
        "## Behaviour Summary\n\n"
        f"{parsed['behaviour_summary']}\n\n"
        "## Test Plan\n\n"
        f"{parsed['test_plan']}\n\n"
        "## Review Report\n\n"
        f"{reviewed['review_report']}\n\n"
        "## Uncertain Behaviours\n\n"
        + ("\n".join(f"- {u}" for u in merged_uncertain) if merged_uncertain else "- None reported")
        + "\n"
    )
    plan_path.write_text(plan_text, encoding="utf-8")

    result = {
        "behaviour_summary": parsed["behaviour_summary"],
        "test_plan": parsed["test_plan"],
        "test_code": final_code,
        "uncertain_behaviours": merged_uncertain,
        "review_report": reviewed["review_report"],
        "test_count": count_tests(final_code),
        "output_path": str(output_path),
        "plan_path": str(plan_path),
    }
    return result


def generate_improved_tests(behavior_context: dict, source_code: str,
                            previous_result: dict, output_path) -> dict:
    """
    One extra generation attempt when the first tests all passed.

    Asks Model 1 to find missing boundary / documented-example cases.
    Overwrites the test file only if the new code validates.
    """
    output_path = Path(output_path)
    model_name = get_test_model()
    module_name = behavior_context.get("module_name", "target_module")
    context_text = format_behavior_context(behavior_context)

    prompt = (
        MODEL1_INSTRUCTIONS
        + f"""

=== IMPORTANT EXTRA INSTRUCTION ===
The previous test suite passed completely against the current implementation,
but the implementation may still contain a bug that those tests missed.

Re-examine the documented behaviour, especially:
- Documented examples with concrete numbers.
- Boundary conditions (0%, 100%, empty, invalid values).
- Interactions between methods.

Generate an IMPROVED, complete test suite (not just extra tests) that covers
any missing documented-example and boundary cases. Still only assert behaviour
that is documented or strongly supported. List uncertain behaviour separately.

=== BEHAVIOUR CONTEXT ===
{context_text}

=== SOURCE CODE ===
{source_code}

=== PREVIOUS TEST PLAN ===
{previous_result.get('test_plan', '')}

=== PREVIOUS TEST CODE (all passed) ===
{previous_result.get('test_code', '')}

IMPORTANT: In TEST_CODE, import from the module named '{module_name}'.
"""
    )
    print(f"  [Model 1] Calling {model_name} for one improved test attempt...")
    response = call_llm(prompt, model_name)
    parsed = parse_model1_response(response)

    if not parsed["test_code"]:
        raise ValueError("Model 1 did not return TEST_CODE for the improved tests.")

    is_valid, error = validate_test_code(parsed["test_code"], module_name)
    if not is_valid:
        raise ValueError(f"Improved test code failed validation: {error}")

    output_path.write_text(parsed["test_code"], encoding="utf-8")

    # Append a note to the plan file.
    plan_path = Path(previous_result.get("plan_path", output_path.parent.parent / "test_plan.md"))
    try:
        with open(plan_path, "a", encoding="utf-8") as handle:
            handle.write("\n\n## Improved Test Attempt\n\n")
            handle.write("First suite passed fully; Model 1 was asked to look for "
                         "missing documented-example and boundary cases.\n\n")
            handle.write(parsed["test_plan"] + "\n")
    except OSError:
        pass

    merged_uncertain = list(previous_result.get("uncertain_behaviours", []))
    for item in parsed["uncertain_behaviours"]:
        if item not in merged_uncertain:
            merged_uncertain.append(item)

    return {
        "behaviour_summary": parsed["behaviour_summary"] or previous_result.get("behaviour_summary", ""),
        "test_plan": parsed["test_plan"],
        "test_code": parsed["test_code"],
        "uncertain_behaviours": merged_uncertain,
        "review_report": previous_result.get("review_report", ""),
        "test_count": count_tests(parsed["test_code"]),
        "output_path": str(output_path),
        "plan_path": str(plan_path),
    }
