"""
Basic unit tests for BugFixer Lite modules.

These tests use MOCKED LLM responses, so they run without an API key
and without network access:

    python -m pytest unit_tests/ -v
"""

import sys
from pathlib import Path

import pytest

# Make the project root importable.
sys.path.insert(0, str(Path(__file__).parent.parent))

import behavior_reader
import repair_agent
import test_generator
import test_runner

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_FILE = PROJECT_ROOT / "sample_project" / "shopping_cart.py"

# ---------------------------------------------------------------------------
# Fake Model 1 / Model 2 responses (no real API calls in these tests)
# ---------------------------------------------------------------------------

FAKE_GENERATION_RESPONSE = """
BEHAVIOUR_SUMMARY:
A shopping cart holds items and calculates a discounted total.

TEST_PLAN:
1. test_empty_cart_total_is_zero - empty cart returns 0 (explicit docstring).
2. test_ten_percent_discount - 10% off 100 gives 90 (documented rule:
   discount is a percentage).

TEST_CODE:
```python
import pytest
from shopping_cart import ShoppingCart

def test_empty_cart_total_is_zero():
    cart = ShoppingCart()
    assert cart.calculate_total() == 0

def test_ten_percent_discount():
    cart = ShoppingCart()
    cart.add_item("Book", 100, 1)
    assert cart.calculate_total(10) == pytest.approx(90)
```

UNCERTAIN_BEHAVIOURS:
None
"""

FAKE_REVIEW_RESPONSE = """
REVIEW_REPORT:
Expected values checked against the docstrings. No changes needed.

TEST_CODE:
```python
import pytest
from shopping_cart import ShoppingCart

def test_empty_cart_total_is_zero():
    cart = ShoppingCart()
    assert cart.calculate_total() == 0

def test_ten_percent_discount():
    cart = ShoppingCart()
    cart.add_item("Book", 100, 1)
    assert cart.calculate_total(10) == pytest.approx(90)
```

UNCERTAIN_BEHAVIOURS:
None
"""

FAKE_REPAIR_RESPONSE = """
ROOT_CAUSE:
The discount was used as a raw multiplier instead of a percentage.

REPAIR_EXPLANATION:
Divide the percentage by 100 before applying it.

FIXED_CODE:
class ShoppingCart:
    def __init__(self):
        self.items = []
    def add_item(self, name, price, quantity=1):
        if not name:
            raise ValueError("Item name cannot be empty")
        if price < 0:
            raise ValueError("Price cannot be negative")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be positive")
        self.items.append({"name": name, "price": price, "quantity": quantity})
    def calculate_total(self, discount_percent=0):
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("Invalid discount percentage")
        subtotal = 0
        for item in self.items:
            subtotal += item["price"] * item["quantity"]
        total = subtotal * (1 - discount_percent / 100)
        return round(total, 2)
"""


# ---------------------------------------------------------------------------
# behavior_reader tests
# ---------------------------------------------------------------------------

def test_behavior_reader_finds_class_and_methods():
    context = behavior_reader.understand_behavior(SAMPLE_FILE)
    class_names = [c["name"] for c in context["classes"]]
    assert "ShoppingCart" in class_names
    cart = context["classes"][0]
    method_names = [m["name"] for m in cart["methods"]]
    assert "add_item" in method_names
    assert "calculate_total" in method_names


def test_behavior_reader_mode_without_spec():
    # Only behavior_spec.md.example exists, so Mode B must be selected.
    context = behavior_reader.understand_behavior(SAMPLE_FILE)
    assert context["specification_available"] is False
    assert context["behaviour_mode"] == "documentation_inference"


def test_behavior_reader_mode_with_spec(tmp_path):
    source_copy = tmp_path / "shopping_cart.py"
    source_copy.write_text(SAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "behavior_spec.md").write_text("10% off 100 gives 90.", encoding="utf-8")
    context = behavior_reader.understand_behavior(source_copy)
    assert context["specification_available"] is True
    assert context["behaviour_mode"] == "specification"


def test_sample_contains_intentional_bug():
    code = SAMPLE_FILE.read_text(encoding="utf-8")
    assert "subtotal * (1 - discount_percent)" in code


# ---------------------------------------------------------------------------
# test_generator tests (mocked LLM)
# ---------------------------------------------------------------------------

def test_generate_test_cases_with_mock(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_call_llm(prompt, model_name):
        calls["count"] += 1
        if calls["count"] == 1:
            return FAKE_GENERATION_RESPONSE
        return FAKE_REVIEW_RESPONSE

    monkeypatch.setattr(test_generator, "call_llm", fake_call_llm)

    context = behavior_reader.understand_behavior(SAMPLE_FILE)
    output_path = tmp_path / "tests" / "test_shopping_cart_generated.py"
    result = test_generator.generate_test_cases(
        context, context["source_code"], output_path
    )

    assert result["test_count"] == 2
    assert output_path.exists()
    assert "test_ten_percent_discount" in output_path.read_text(encoding="utf-8")
    # test_plan.md should also be saved.
    assert (tmp_path / "test_plan.md").exists()


def test_validate_test_code_rejects_banned_import():
    bad_code = "import subprocess\n\ndef test_x():\n    assert True\n"
    is_valid, error = test_generator.validate_test_code(bad_code, "shopping_cart")
    assert is_valid is False
    assert "subprocess" in error


def test_validate_test_code_rejects_syntax_error():
    is_valid, error = test_generator.validate_test_code(
        "def test_x(:\n", "shopping_cart"
    )
    assert is_valid is False


def test_parse_model1_response_sections():
    parsed = test_generator.parse_model1_response(FAKE_GENERATION_RESPONSE)
    assert "shopping cart" in parsed["behaviour_summary"].lower()
    assert parsed["test_count"] if "test_count" in parsed else True
    assert "def test_empty_cart_total_is_zero" in parsed["test_code"]


# ---------------------------------------------------------------------------
# test_runner tests
# ---------------------------------------------------------------------------

def test_hash_detects_change(tmp_path):
    file_path = tmp_path / "sample.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    hash1 = test_runner.compute_file_hash(file_path)
    file_path.write_text("x = 2\n", encoding="utf-8")
    hash2 = test_runner.compute_file_hash(file_path)
    assert hash1 != hash2


def test_run_tests_counts_pass_and_fail(tmp_path):
    module = tmp_path / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    tests = tmp_path / "test_calc.py"
    tests.write_text(
        "from calc import add\n\n"
        "def test_ok():\n    assert add(1, 2) == 3\n\n"
        "def test_bad():\n    assert add(1, 2) == 99\n",
        encoding="utf-8",
    )
    result = test_runner.run_tests(tmp_path, tests)
    assert result["passed"] is False
    assert result["passed_count"] == 1
    assert result["failed_count"] == 1


# ---------------------------------------------------------------------------
# repair_agent tests (mocked LLM)
# ---------------------------------------------------------------------------

def test_repair_code_with_mock(monkeypatch):
    monkeypatch.setattr(
        repair_agent, "call_llm", lambda prompt, model: FAKE_REPAIR_RESPONSE
    )
    context = behavior_reader.understand_behavior(SAMPLE_FILE)
    fake_results = {"output": "FAILED test_ten_percent_discount", "error": ""}
    repair = repair_agent.repair_code(
        source_code=context["source_code"],
        behavior_context=context,
        generated_tests="def test_x(): pass",
        test_results=fake_results,
        test_plan="plan",
    )
    assert "percentage" in repair["root_cause"].lower()
    assert "discount_percent / 100" in repair["fixed_code"]


def test_parse_repair_response_strips_fences():
    response = (
        "ROOT_CAUSE:\nBug here.\n\nREPAIR_EXPLANATION:\nFix it.\n\n"
        "FIXED_CODE:\n```python\nx = 1\n```\n"
    )
    parsed = repair_agent.parse_repair_response(response)
    assert parsed["fixed_code"].strip() == "x = 1"


# ---------------------------------------------------------------------------
# main.py tests: temporary-environment validation + propagation rule
#
# Rule under test: a candidate fix is written into the target file ONLY
# after it passes every generated test in a temporary environment.
# ---------------------------------------------------------------------------

import main as bugfixer_main

FAKE_BAD_REPAIR_RESPONSE = """
ROOT_CAUSE:
Something is wrong with the discount.

REPAIR_EXPLANATION:
This candidate deliberately keeps the buggy formula.

FIXED_CODE:
class ShoppingCart:
    def __init__(self):
        self.items = []
    def add_item(self, name, price, quantity=1):
        if not name:
            raise ValueError("Item name cannot be empty")
        if price < 0:
            raise ValueError("Price cannot be negative")
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be positive")
        self.items.append({"name": name, "price": price, "quantity": quantity})
    def calculate_total(self, discount_percent=0):
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("Invalid discount percentage")
        subtotal = 0
        for item in self.items:
            subtotal += item["price"] * item["quantity"]
        total = subtotal * (1 - discount_percent)
        return round(total, 2)
"""


def _run_main_with_mocks(monkeypatch, tmp_path, repair_text):
    """Run the full main() flow on a disposable copy of the sample file."""
    target = tmp_path / "shopping_cart.py"
    target.write_text(SAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    calls = {"count": 0}

    def fake_call_llm(prompt, model_name):
        calls["count"] += 1
        if calls["count"] == 1:
            return FAKE_GENERATION_RESPONSE
        return FAKE_REVIEW_RESPONSE

    monkeypatch.setattr(test_generator, "call_llm", fake_call_llm)
    monkeypatch.setattr(
        repair_agent, "call_llm", lambda prompt, model: repair_text
    )
    monkeypatch.setattr(bugfixer_main, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(bugfixer_main, "get_test_model", lambda: "test-model")
    monkeypatch.setattr(bugfixer_main, "get_repair_model", lambda: "test-model")
    monkeypatch.setattr(bugfixer_main, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(sys, "argv", ["main.py", str(target)])

    report = bugfixer_main.main()
    return target, report


def test_main_propagates_fix_only_after_temp_validation_passes(
    monkeypatch, tmp_path
):
    target, report = _run_main_with_mocks(
        monkeypatch, tmp_path, FAKE_REPAIR_RESPONSE
    )
    assert report["bug_detected"] is True
    assert report["tests_before_repair"]["failed"] == 1
    assert report["tests_after_repair"] == {"passed": 2, "failed": 0}
    assert report["repair_successful"] is True
    assert report["fix_applied_to_target"] is True
    # The validated fix must now be inside the target file itself.
    assert "discount_percent / 100" in target.read_text(encoding="utf-8")
    # The real sample file must not have been touched by this test.
    assert "subtotal * (1 - discount_percent)" in SAMPLE_FILE.read_text(
        encoding="utf-8"
    )


def test_main_leaves_target_untouched_when_validation_fails(
    monkeypatch, tmp_path
):
    original_text = SAMPLE_FILE.read_text(encoding="utf-8")
    target, report = _run_main_with_mocks(
        monkeypatch, tmp_path, FAKE_BAD_REPAIR_RESPONSE
    )
    assert report["repair_attempts"] == 2
    assert report["repair_successful"] is False
    assert report["fix_applied_to_target"] is False
    # Both candidates failed in temp environments, so nothing propagated.
    assert target.read_text(encoding="utf-8") == original_text
