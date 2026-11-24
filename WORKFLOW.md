# BugFixer Lite — Workflow (Short & Simple)

> One-line summary: **Model 1 (AI) writes tests → Pytest finds real failures → Model 2 (AI) fixes the code in a temporary environment → if all tests pass there, the fix is written into the original file.**

Full details are in `README.md`. This file is the quick version.

---

## 1. My Approach (in 5 points)

1. **Don't trust the code — trust the documentation.** Expected behaviour comes from docstrings / `behavior_spec.md`, never from running the buggy code.
2. **Two AI roles, two jobs.** Model 1 = test engineer (writes tests). Model 2 = debugger (fixes code). Both talk to OpenRouter through one file.
3. **AI proposes, Pytest decides.** Success is claimed only when Pytest actually passes — never because the AI says "fixed".
4. **Same tests before and after.** The test file is SHA-256 hashed; if it changes, validation is rejected. The AI cannot "fix" by editing tests.
5. **Fix the original only after proof.** Candidates are tested in a disposable temporary folder. The original file is written **only** after an all-pass result, and verified by hash.

---

## 2. Overall Workflow (7 steps)

```text
python main.py
  Step 1  Start: check API key, read target file
  Step 2  Understand: AST reads classes/methods/docstrings (+ optional spec)
  Step 3  Model 1: generate tests -> review own tests -> save to temp folder
  Step 4  Pytest in TEMP env (original code)      -> real pass/fail
  Step 5  Model 2: gets code + tests + failures   -> root cause + candidate fix
  Step 6  Pytest in TEMP env (candidate, SAME tests)
             all pass? -> write fix into ORIGINAL file (hash-verified)
             fail?     -> one more attempt (max 2); original never touched
  Step 7  Report: reports/repair_report.json + .txt
```

Temporary folders are auto-deleted. Only these survive a run (in `reports/`): the final report, `test_plan.md`, and `generated_tests/` (inspectable copies of what Model 1 wrote).

---

## 3. What Each File Does

| File | Job in one line | Key function(s) |
|---|---|---|
| `main.py` | Manager — runs Steps 1–7 in order; the **only** place the target file is ever written | `run_workflow()`, `_prepare_temp_environment()`, `_propagate_fix()` |
| `llm_client.py` | Telephone line — the only file that talks to OpenRouter (both models) | `call_llm(prompt, model_name)` |
| `behavior_reader.py` | Reader — extracts classes, methods, docstrings, type hints with AST (no code is run) | `understand_behavior()` |
| `test_generator.py` | **Model 1** — writes Pytest tests, reviews them itself, rejects unsafe imports (AST check) | `generate_test_cases()` |
| `test_runner.py` | Judge — runs Pytest in a subprocess (120s timeout), counts pass/fail, hashes files | `run_tests()`, `compute_file_hash()` |
| `repair_agent.py` | **Model 2** — receives real failure output, returns root cause + complete fixed code | `repair_code()` |
| `report_generator.py` | Reporter — writes `repair_report.json` + `.txt` from real results | `generate_report()` |
| `sample_project/order_processing_system.py` | The demo target being tested and fixed (see bugs below) | — |
| `sample_project/behavior_spec.md.example` | Optional rule book; rename to `behavior_spec.md` to activate Mode A | — |
| `sample_project/expected_bugs.md` | Private answer key — **not read by the program** | — |
| `unit_tests/test_bugfixer_units.py` | Hand-written tests of BugFixer itself, with mocked AI (no API key): `python -m pytest unit_tests/ -v` → 14 passed | — |

**How they connect:** `main` calls `behavior_reader` → context goes to `test_generator` (Model 1) → tests go to `test_runner` → failures go to `repair_agent` (Model 2) → candidate goes back to `test_runner` → result goes to `report_generator`. Only `llm_client` touches the internet or the API key.

---

## 4. Where the Bugs Are (your current sample)

Target: `sample_project/order_processing_system.py` (552 lines, 7 classes: `Product`, `Inventory`, `Cart`, `Coupon`, `PriceBreakdown`, `PricingEngine`, `Order`). There are exactly **8 planted bugs**; everything else is correct.

| # | Location | Bug in simple words | Example: correct → buggy |
|---|---|---|---|
| 1 | `PricingEngine.calculate_discount` (line 334) | % coupon applied on the **whole cart** instead of only eligible categories | 10% electronics-only on books 100 + electronics 100: **10 → 20** |
| 2 | `PricingEngine.calculate_tax_for_line` (line 384) | Tax charged on the price **before** discount (ignores the discount argument) | Electronics 100, discount 10: tax **16.2 → 18.0** |
| 3 | `PricingEngine.calculate_shipping` (line 413) | Free-shipping check uses **pre-discount** subtotal | 550 with 20% coupon (= 440): shipping **40 → free** |
| 4 | `PricingEngine.calculate_shipping` (line 422) | Extra weight **cut off** (`int()`) instead of rounded **up** | 7.2 kg: surcharge **90 → 60** |
| 5 | `Order.place` (line 530) | If one item can't be reserved, items reserved before it **stay reserved** (not all-or-nothing) | Failed order: product A available **5 → 3** |
| 6 | `Inventory.commit` (line 148) | Shipping reduces physical stock but **never clears the reservation** | Order of 3 shipped from stock 10: available **7 → 4** |
| 7 | `Order.cancel` (line 592) | Cancel releases the reservation **and restocks on top** — invents units | Stock 10, cancelled order of 3: available **10 → 13** |
| 8 | `Order.return_items` (line 638) | Refund uses the product's **current** price instead of the price frozen at payment | Paid 106.2/unit, price later 150: refund **106.2 → 177.0** |

Why they're "complex": each needs tracing across methods — e.g. Bug 6 only corrupts `available = stock − reserved` after shipping; Bug 5 only appears on the *failure path* of a loop; Bug 8 is invisible unless the price changes after payment. Bugs 1+2 also compound, so a partial fix still fails validation and is never propagated.

---

## 5. How to Read (Decode) the Output of `python main.py`

Using the real run on this sample (Mode B):

| Output you see | What it means |
|---|---|
| `API key found (value hidden)` | `.env` loaded; key is never printed |
| `Model 1 / Model 2 : deepseek/deepseek-v4.1-flash` | Which AI plays which role (set in `.env`) |
| `Temporary environment created: ...Temp\bugfixer_...` | Disposable folder for this run; deleted at the end |
| Step 2: `Mode B - no behavior_spec.md found` | No spec file → behaviour inferred from docstrings. `Found class ...` lines = AST reading, no code executed yet |
| Step 3: `Generated 89 test cases` | Model 1 wrote 89 `test_` functions (+ reviewed them). Count varies per run — normal |
| Step 3: `Uncertain behaviours: ...` | Things the docs don't decide. The AI reports doubt instead of guessing — a good sign, not an error |
| Step 4: `71 passed, 18 failed` | **Bug exposed.** 18 > 8 bugs because several tests hit the same bug and pricing bugs compound |
| A failure block: `Obtained: -980.0 / Expected: 10.0` | What the buggy code returned vs what the documentation demands. Read 2–3 of these and you can see the bug pattern yourself |
| Step 5: `Root cause: ...` | Model 2's diagnosis + what it changed. It received the code, tests, test plan and the *actual* failure text |
| Step 6: `Test file unchanged: True` | SHA-256 proof: the candidate was judged by the *identical* tests that caught the bug |
| Step 6: `89 passed` → `Propagating the validated fix into: ...` → `verified by hash` | The only moment the original file is written — after full proof, byte-identical to the validated candidate |
| If instead: `Target file NOT modified` | Candidate failed validation (max 2 attempts). The original is guaranteed untouched |
| Step 7 + `Done.` | Report saved. Read `reports/repair_report.json` |

**Key report fields:** `bug_detected` (did Run 1 fail?) · `tests_before_repair` / `tests_after_repair` (real Pytest counts) · `test_file_unchanged` (same tests?) · `repair_attempts` (1–2) · `repair_successful` (only from a real all-pass) · `fix_applied_to_target` (was the original actually written?) · `uncertain_behaviours` (AI's admitted doubts).

---

## 6. Run It / See the Generated Tests

```powershell
pip install -r requirements.txt        # once; put your key in .env
python -m pytest unit_tests/ -v        # offline check: 14 passed
python main.py                         # full flow on order_processing_system.py

# See what Model 1 generated:
code reports\generated_tests\test_order_processing_system_generated.py
Get-Content reports\test_plan.md

# Mode A (with the 22-rule spec):
Copy-Item sample_project\behavior_spec.md.example sample_project\behavior_spec.md
python main.py
Remove-Item sample_project\behavior_spec.md
```

⚠️ A successful run **fixes `sample_project/order_processing_system.py` itself**. Restore the buggy demo before running again:

```powershell
Copy-Item sample_project\order_processing_system_buggy_copy.txt sample_project\order_processing_system.py
```
