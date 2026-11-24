# BugFixer Lite

## AI-Based Automated Test Generation, Bug Detection and Code Repair System

A detailed, beginner-friendly guide to what this project does, what every file does, how the files work together, how to run the project, how tests run in a temporary environment and the validated fix is propagated into the original file, and how to understand (decode) every line of the output.

---

## Table of Contents

1. [What is BugFixer Lite? (In Simple Words)](#1-what-is-bugfixer-lite-in-simple-words)
2. [The Complete Flow at a Glance](#2-the-complete-flow-at-a-glance)
3. [Project Structure](#3-project-structure)
4. [Every File Explained in Detail](#4-every-file-explained-in-detail)
5. [How the Files Talk to Each Other](#5-how-the-files-talk-to-each-other)
6. [How to Run the Code](#6-how-to-run-the-code)
7. [The Temporary Environment — How Tests Run and When the Original File Changes](#7-the-temporary-environment--how-tests-run-and-when-the-original-file-changes)
8. [The `reports/` Folder — The Final Report Explained](#8-the-reports-folder--the-final-report-explained)
9. [Decoding the Output of `python main.py`](#9-decoding-the-output-of-python-mainpy)
10. [The Unit Test File in `unit_tests/` Explained](#10-the-unit-test-file-in-unit_tests-explained)
11. [Will This Approach Work on Slightly More Complex Projects?](#11-will-this-approach-work-on-slightly-more-complex-projects)
12. [Safety — In Simple Words](#12-safety--in-simple-words)
13. [Limitations](#13-limitations)
14. [Troubleshooting](#14-troubleshooting)
15. [Useful Commands Cheat Sheet](#15-useful-commands-cheat-sheet)
16. [How to Explain This Project in a Viva / Presentation](#16-how-to-explain-this-project-in-a-viva--presentation)
17. [Glossary](#17-glossary)

---

## 1. What is BugFixer Lite? (In Simple Words)

BugFixer Lite is a small Python program that can **test another Python program and fix its bug automatically**, using AI.

Think of it like a hospital for code:

| Role in BugFixer Lite | Real-life comparison | What it does |
|---|---|---|
| **Model 1** (an AI model) | A test engineer | Reads your code and its documentation, understands what the code *should* do, and writes test cases for it. |
| **Pytest** | A judge / examiner | Actually runs the test cases and honestly reports which ones passed and which ones failed. |
| **Model 2** (an AI model) | A doctor | Reads the failed tests, finds the root cause of the bug, and writes the corrected code. |
| **`main.py`** | The manager | Gives work to everyone in the correct order and collects the final result. |

The most important idea is this:

> **The AI never marks its own homework.** Model 1 writes tests, but only Pytest decides if the code is correct. Model 2 writes a fix, but only Pytest (running the *same* tests again) decides if the fix worked. If the tests do not pass, the project honestly reports failure — it never fakes success.

### The demonstration example

The sample program is a `ShoppingCart` class (`sample_project/shopping_cart.py`). It has one **intentional bug**:

- Correct behaviour: items worth 100 with a 10% discount should cost **90**.
- Buggy behaviour: the code calculates `100 * (1 - 10) = -900`. It uses the number `10` directly instead of converting the percentage to `10 / 100`.

Nobody tells the AI models where this bug is. Model 1 must *discover* the expected behaviour from the docstrings, Model 1's tests must *expose* the bug, and Model 2 must *diagnose and fix* it from the test failures. That discovery process is the whole point of the project.

---

## 2. The Complete Flow at a Glance

```text
                ┌──────────────────────────────┐
                │  sample_project/             │
                │  shopping_cart.py (ORIGINAL) │  <-- edited ONLY after
                └──────────────┬───────────────┘     a fix passes all tests
                               │ read; copies go to a
                               v temporary folder
┌──────────────────┐   ┌──────────────────┐
│ behavior_spec.md │   │  TEMPORARY ENV   │
│ (optional file)  │   │  (auto-deleted)  │
└────────┬─────────┘   └────────┬─────────┘
         v                      v
   ┌─────────────────────────────────┐
   │  behavior_reader.py             │  reads code structure with AST:
   │  classes, methods, docstrings,  │  docstrings, type hints, comments,
   │  type hints, optional spec      │  + optional specification
   └────────────────┬────────────────┘
                    │ behaviour context (a dictionary)
                    v
   ┌─────────────────────────────────┐
   │  MODEL 1 (test_generator.py)    │  Call 1: write test plan + tests
   │                                 │  Call 2: review its own tests
   └────────────────┬────────────────┘
                    │ test file + test plan created in temp folder
                    v
   ┌─────────────────────────────────┐
   │  PYTEST — RUN 1 (before repair) │  test_runner.py runs the tests
   └────────────────┬────────────────┘
                    │ real pass/fail results
              failures? ──── no ───> report "no defect exposed", stop
                    │ yes
                    v
   ┌─────────────────────────────────┐
   │  MODEL 2 (repair_agent.py)      │  gets source + tests + real
   │                                 │  failure output, returns fix
   └────────────────┬────────────────┘
                    │ candidate code placed in a temp env only
                    v
   ┌─────────────────────────────────┐
   │  PYTEST — RUN 2 (after repair)  │  EXACT same tests (hash-checked)
   └────────────────┬────────────────┘
                    │
               pass? ─┬─ yes ─> propagate fix into ORIGINAL file
                     └─ no ──> one more Model 2 attempt (max 2),
                               else original left untouched, report failure
                    v
   ┌─────────────────────────────────┐
   │  reports/repair_report.json     │  final result, written by
   │  reports/repair_report.txt      │  report_generator.py
   └─────────────────────────────────┘
```

### The 7 steps printed on the terminal

`main.py` prints these exact headings so you can follow the flow live:

| Step | Name | Which file does the work |
|---|---|---|
| Step 1 | Initialize the application | `main.py` + `llm_client.py` |
| Step 2 | Understand expected behaviour | `behavior_reader.py` |
| Step 3 | Generate test cases (Model 1) | `test_generator.py` + `llm_client.py` |
| Step 4 | Run initial tests | `test_runner.py` |
| Step 5 | Repair the code (Model 2) | `repair_agent.py` + `llm_client.py` |
| Step 6 | Validate the repair | `test_runner.py` |
| Step 7 | Generate final report | `report_generator.py` |

---

## 3. Project Structure

```text
bugfixer/                              (project root — this is "BugFixer Lite")
│
├── main.py                            Step-by-step manager of the whole flow
├── llm_client.py                      The only file that talks to OpenRouter (AI)
├── behavior_reader.py                 Reads & understands the target code (no AI)
├── test_generator.py                  Model 1: generates + reviews test cases
├── test_runner.py                     Runs Pytest, counts results, hashes files
├── repair_agent.py                    Model 2: diagnoses bug, returns fixed code
├── report_generator.py                Writes the final JSON + TXT reports
│
├── sample_project/                    The demo program to be tested & fixed
│   ├── shopping_cart.py               ShoppingCart class (intentionally buggy)
│   └── behavior_spec.md.example       Example of the optional specification file
│
├── (no workspace/ folder — test runs use an auto-deleted temporary folder)
├── reports/                           Final results of the last run
│   ├── .gitkeep
│   ├── repair_report.json             (generated) machine-readable report
│   └── repair_report.txt              (generated) human-readable report
│
├── unit_tests/                        Hand-written tests OF BugFixer itself
│   └── test_bugfixer_units.py         12 tests, mocked AI, no API key needed
│
├── requirements.txt                   List of Python packages to install
├── .env                               Your secret API key + model names (private)
├── .env.example                       Template showing what .env should contain
├── .gitignore                         Tells Git which files not to upload
└── README.md                          This file
```

**Key idea to remember:** files marked *(generated)* are created fresh on every run of `python main.py`. You never edit them by hand. The only demo file you might edit is `sample_project/shopping_cart.py` (to try a different bug), and the only file you *must* edit is `.env` (to add your API key).

---

## 4. Every File Explained in Detail

For each Python file you will learn four things: **what it does**, **how it does it**, **its main functions**, and **how it affects the rest of the codebase** (who calls it, whom it calls, and what would break without it).

---

### 4.1 `main.py` — The Manager

**What it does (one line):** It runs the whole show, step by step, in the correct order.

**How it works:**

1. At the top, `TARGET_FILE = Path("sample_project") / "shopping_cart.py"` selects which file will be tested. You can change this one line to test a different file, or pass a path when running: `python main.py some_other_file.py`.
2. `main()` first creates a `report_data` dictionary filled with safe default values (`bug_detected: False`, `repair_successful: False`, all counts 0). This is deliberate: the report starts by assuming *nothing* worked, and real results overwrite the defaults only when they actually happen. This is how the project guarantees it never reports fake success.
3. `main()` calls `run_workflow()`, which performs Steps 1–6 (explained below).
4. If anything goes wrong (missing API key, file not found, API failure), the error is caught, a simple message is printed, and the program still continues to Step 7 and writes a report instead of crashing with a scary stack trace.
5. `run_workflow()` in detail:
   - **Step 1:** Checks the API key exists (without printing it), prints both model names, reads the target file into memory (`original_code`, the in-run safety copy) and remembers its SHA-256 hash. It creates **one temporary root folder** for Steps 3–6; nothing is copied into any persistent workspace.
   - **Step 2:** Calls `behavior_reader.understand_behavior()` and prints what was found (which mode, which classes and methods).
   - **Step 3:** Calls `test_generator.generate_test_cases()` and stores the test count and uncertain behaviours into `report_data`.
   - **Step 4:** Runs the tests with `test_runner.run_tests()`. It takes a SHA-256 hash of the generated test file. **Special case:** if *all* tests pass, it does not assume the code is correct — it asks Model 1 for exactly *one* improved attempt (better boundary cases) and runs again. If tests still all pass, it honestly reports "the generated tests did not expose a defect" and **never calls Model 2** — because there is no real failure to repair.
   - **Steps 5–6 (repair loop, maximum 2 attempts):** Calls `repair_agent.repair_code()`, places Model 2's candidate into a **fresh temporary environment** (`after_repair_attempt_N/`), re-hashes the master test file to prove it did not change, and re-runs the *exact same* tests there. **Pass → and only then** `_propagate_fix()` writes the candidate into the original target file and verifies it by hash. Fail → loop once more with the new failure output; the target file is never written on a failure path.
   - If no repair succeeded, it re-hashes the target file at the end to *confirm* it is byte-identical to the start of the run.

**Main functions:**

| Function | Job |
|---|---|
| `main()` | Entry point. Sets up default report data, runs the workflow, handles errors politely, always writes the final report. |
| `run_workflow(target_file, report_data)` | Steps 1–6: setup, understand, generate, test, repair, validate. Fills `report_data` with real results. |
| `print_heading(title)` | Prints the `==== Step N ====` banners you see on the terminal. |
| `_prepare_temp_environment(...)` | Builds one isolated env (module copy + tests + `conftest.py`) inside the temporary folder and returns its test file. |
| `_propagate_fix(...)` | The only function that writes the target file: writes candidate bytes, verifies by hash, restores original content on any mismatch/error. |
| `_save_run_artifacts(...)` | Copies the generated tests + test plan into `reports/` for inspection (never executed from there). |

**How it affects the whole codebase:** `main.py` is the *only* file that knows the full order of operations. Every other file is a specialist that knows only its own job. If you remove `main.py`, the other files still work individually (the unit tests prove this), but nothing runs the full flow. If you want to change the workflow — for example, allow 3 repair attempts — this is the file you change (`MAX_REPAIR_ATTEMPTS = 2`).

---

### 4.2 `llm_client.py` — The Telephone Line to the AI

**What it does (one line):** It is the *only* file that talks to OpenRouter. Both AI models are contacted through this one file.

**How it works:**

1. When the file is imported, `load_dotenv()` reads the `.env` file, so the API key and model names become available through `os.getenv(...)`.
2. `get_api_key()`, `get_test_model()` and `get_repair_model()` simply read those values. If a model name is missing from `.env`, a sensible default (`deepseek/deepseek-v4.1-flash`) is used.
3. `create_client()` builds an OpenAI-SDK client, but pointed at OpenRouter's address (`https://openrouter.ai/api/v1`). Before that, it checks the key: if the key is empty or still the placeholder text `your_openrouter_api_key_here`, it raises a clear error telling you to fix `.env`. The key itself is **never printed anywhere**.
4. `call_llm(prompt, model_name)` is the single reusable function used for *every* AI call in the project:
   - It rejects empty prompts and empty model names.
   - It sends one system message ("You are a helpful Python software engineering assistant.") plus your prompt, with `temperature=0.2`. Low temperature means "be more consistent and less random", which is what we want for code.
   - If OpenRouter is unreachable or rejects the request, it converts the error into a simple `RuntimeError` message (with no key inside it).
   - If the model replies with empty text, that is treated as an error too — empty replies are never silently accepted.

**Main functions:**

| Function | Job |
|---|---|
| `call_llm(prompt, model_name)` | Send one prompt to one model, return the reply text. Handles all errors. |
| `create_client()` | Build the OpenRouter-connected client; validates the API key first. |
| `get_api_key()` / `get_base_url()` | Read credentials/settings from `.env`. |
| `get_test_model()` / `get_repair_model()` | Return Model 1's and Model 2's names (independently configurable). |

**How it affects the whole codebase:** `test_generator.py` (Model 1) and `repair_agent.py` (Model 2) both call `call_llm()`. They do not know anything about API keys, URLs, or the OpenAI SDK. So if you ever want to change provider settings, retry logic, or the temperature, you change exactly one file. This is also the security boundary of the project: because only this file ever sees the API key, generated code can never accidentally receive it.

---

### 4.3 `behavior_reader.py` — The Careful Reader

**What it does (one line):** Before any AI is involved, this file collects *evidence* about what the target program is supposed to do.

**How it works:**

1. `understand_behavior(source_file, specification_file=None)` reads the target `.py` file as text and parses it with Python's built-in **`ast`** module. Parsing means building a tree of the code's structure — it does **not run** the code, so even buggy or unsafe code is safe to read.
2. From that tree it extracts:
   - class names (e.g. `ShoppingCart`),
   - method and function names (e.g. `add_item`, `calculate_total`),
   - docstrings (the `"""..."""` documentation inside classes/methods),
   - type hints and default values (e.g. `quantity=1`, `discount_percent=0`) — these are strong hints about intended behaviour,
   - plain `#` comments.
3. It then looks for the optional specification: if you pass a path it uses that, otherwise it checks for a file named exactly `behavior_spec.md` sitting next to the source file. Note: `behavior_spec.md.example` is deliberately **not** matched — only the exact name counts.
4. It also picks up a nearby `README.md` (the sample folder first, then the project root) as extra light context.
5. Everything is packed into one dictionary, the **behaviour context**, including a `behaviour_mode` field: `"specification"` (Mode A) if the spec file was found, otherwise `"documentation_inference"` (Mode B).
6. `format_behavior_context(context)` converts that dictionary into one clean text block. This text block is what actually gets pasted into the AI prompts later.

**The evidence priority** (also written into Model 1's prompt) is:

1. Your `behavior_spec.md` (highest trust)
2. Docstrings and documented examples
3. README / existing tests
4. Type hints, signatures, comments
5. Common-sense programming conventions
6. The existing code itself (lowest — it may be buggy, so it is *context*, never *proof*)

**Main functions:**

| Function | Job |
|---|---|
| `understand_behavior(...)` | Main entry. Returns the behaviour-context dictionary. Raises clear errors if the file is missing or has a syntax error. |
| `format_behavior_context(context)` | Turns the dictionary into prompt-ready text. |
| `_extract_type_hints(node)` | Collects argument annotations and default values from a function. |
| `_collect_comments(source_code)` | Collects `#` comment lines. |
| `_build_signature(node)` | Builds a readable signature like `add_item(self, name, price, quantity=1)`. |

**How it affects the whole codebase:** This file decides *what the AI gets to see*. Both Model 1 and Model 2 receive its output. If the docstrings in the target file are poor, this file has little evidence to pass on, and the generated tests will be weaker — which is why the project keeps reminding you that good documentation produces good tests. If you remove this file, `main.py` cannot proceed past Step 2.

---

### 4.4 `test_generator.py` — Model 1, the Test Engineer

**What it does (one line):** It asks Model 1 to write Pytest test cases, asks Model 1 to review its own tests, checks the tests are safe and valid, and saves them into the temporary run folder.

**How it works — `generate_test_cases()` step by step:**

1. **Build the prompt.** `build_test_prompt()` combines the long instruction text (`MODEL1_INSTRUCTIONS`) with the formatted behaviour context and the full source code. The instructions tell the model: understand first, do not trust the existing implementation, derive expected answers from documentation (never from running the buggy code), cover normal/boundary/empty/invalid cases, and label every behaviour as *explicit*, *strongly inferred*, or *uncertain*.
2. **First AI call.** `call_llm(prompt, TEST_MODEL)` returns text in four labelled sections: `BEHAVIOUR_SUMMARY`, `TEST_PLAN`, `TEST_CODE`, `UNCERTAIN_BEHAVIOURS`. `parse_model1_response()` cuts the reply into those four pieces (it finds each heading, and removes the ```python fences around the code).
3. **Second AI call — the review.** `build_review_prompt()` sends the source, the context, the plan and the generated code back to Model 1 and asks: are the expected values actually correct? Does any test just copy the buggy behaviour? The model replies with a `REVIEW_REPORT` plus possibly corrected `TEST_CODE`. This is a *consistency check*, not a proof — the README and the viva answer should describe it exactly that way.
4. **Safety validation.** `validate_test_code()` checks the final code with AST:
   - the syntax must be valid Python,
   - only `pytest` and the target module (e.g. `shopping_cart`) may be imported,
   - dangerous things are rejected: `subprocess`, `socket`, `os`, `sys`, `shutil`, `pathlib`, `requests`, `urllib`, `http`, and the names `eval`, `exec`, `open`, `__import__`, `compile`,
   - there must be at least one function whose name starts with `test_`.
   
   If the *reviewed* code fails validation but the *original* generated code passes, the original is used with a warning printed. If both fail, the run stops with a clear error instead of saving bad tests.
5. **Save.** The test code is written to `reports/generated_tests/test_<module>_generated.py`, and a human-readable plan (behaviour summary + test plan + review report + uncertain behaviours) is written to `reports/test_plan.md`.

The file also contains `generate_improved_tests()`: this is used only when the first suite passes 100%. It asks Model 1 to look specifically for missed boundary cases and documented numeric examples, and produces a fresh full suite (which is then re-validated before replacing the old file). `main.py` allows this exactly once.

**Main functions:**

| Function | Job |
|---|---|
| `generate_test_cases(context, source_code, output_path)` | Full Model 1 pipeline: generate → review → validate → save. |
| `generate_improved_tests(...)` | The single second-chance generation when all tests passed. |
| `build_test_prompt(...)` / `build_review_prompt(...)` | Assemble the two prompts. |
| `parse_model1_response(...)` / `parse_review_response(...)` | Split AI replies into sections; strip code fences. |
| `validate_test_code(code, module)` | AST syntax + import allow-list + banned-name checks. |
| `count_tests(code)` | Counts `test_` functions (this becomes `test_cases_generated` in the report). |

**How it affects the whole codebase:** This file decides *what "correct" means* for the entire run. Pytest only runs what this file produces, and Model 2 only fixes what these tests catch. Its output files (the generated test file and `test_plan.md`) are the contract between the "testing half" and the "repair half" of the project. No test case is hardcoded anywhere in BugFixer — delete the generated file and re-run, and Model 1 writes a fresh one.

---

### 4.5 `test_runner.py` — The Honest Judge

**What it does (one line):** It runs Pytest for real, reports the true pass/fail counts, and provides the hash function that proves the test file never changed.

**How it works:**

1. `run_tests(execution_dir, test_file)` builds a command list — `[python, -m, pytest, <test file>, -v, --tb=short, -p no:cacheprovider]` — and executes it with `subprocess.run(...)`:
   - `shell=False` (the default, set explicitly by design): no shell tricks are possible.
   - `cwd=<temporary environment>`: Pytest runs *inside* the temporary environment, next to the module copy being judged.
   - `capture_output=True`: both normal output and error output are collected as text.
   - `timeout=120` seconds: a stuck or infinite-looping test file is killed instead of hanging forever.
2. It counts results by searching the Pytest summary line (e.g. `10 failed, 23 passed in 0.27s`) with regular expressions. Collection errors are counted as failures so they can never be mistaken for success.
3. It returns a simple dictionary: `passed` (true only if Pytest's return code is 0), `output`, `error`, `return_code`, `passed_count`, `failed_count`.
4. `compute_file_hash(file_path)` reads a file's bytes and returns its **SHA-256 hash** — a fingerprint string. Even a one-character change produces a completely different fingerprint. `main.py` hashes the generated test file before repair and again after repair; if the two fingerprints differ, the validation is rejected. This is the mechanical guarantee behind the line `Test file unchanged: True`.
5. `combined_output(result)` joins stdout + stderr into one string — this is the text that gets sent to Model 2 as "actual failure evidence".

**Main functions:**

| Function | Job |
|---|---|
| `run_tests(execution_dir, test_file)` | Execute Pytest in a subprocess; return counts and output. Handles missing file, timeout, and start-up errors. |
| `compute_file_hash(file_path)` | SHA-256 fingerprint of any file. |
| `_parse_counts(output)` | Extract passed/failed numbers from Pytest's summary. |
| `combined_output(result)` | Merge output + error text for Model 2. |

**How it affects the whole codebase:** This file is the project's source of truth. Every number in the final report (`tests_before_repair`, `tests_after_repair`) comes from here, and the before/after fairness guarantee comes from its hash function. Without it, the AI models would be grading themselves — with it, claims like "repair successful" are backed by an actual test execution.

---

### 4.6 `repair_agent.py` — Model 2, the Doctor

**What it does (one line):** When tests fail, it sends the code, the expected behaviour, the tests and the *real* failure output to Model 2, and brings back a root-cause explanation plus a complete corrected file.

**How it works:**

1. `repair_code(source_code, behavior_context, generated_tests, test_results, test_plan)` builds one big prompt from:
   - the (buggy) source code,
   - the behaviour context from `behavior_reader.py`,
   - Model 1's test plan (so Model 2 knows *why* each test expects what it expects),
   - the generated test code,
   - the actual Pytest failure text from `test_runner.py`.
2. The instructions (`MODEL2_INSTRUCTIONS`) force a disciplined process: understand → analyse failures → find root cause → smallest possible fix → keep all class/method names and validation rules → never modify tests → if a test contradicts the documented behaviour, say so instead of bending correct code to satisfy a wrong test.
3. The reply must have three sections: `ROOT_CAUSE`, `REPAIR_EXPLANATION`, `FIXED_CODE`. `parse_repair_response()` extracts them, and `_clean_fixed_code()` removes any Markdown fences the model may have added around the code despite being told not to.
4. `validate_fixed_code()` checks the proposal *before* it is trusted: it must be non-empty, it must parse as valid Python (AST), and it must still contain every original class name (so the model cannot "fix" the problem by deleting or renaming the class).
5. The validated result is returned to `main.py` as a dictionary. Note what this file does **not** do: it never writes the fix to any file. Testing the candidate in a temporary environment — and only then propagating it into the original file — is `main.py`'s job.

**Main functions:**

| Function | Job |
|---|---|
| `repair_code(...)` | Build the Model 2 prompt, call the model, parse and validate the answer. |
| `parse_repair_response(response)` | Extract `ROOT_CAUSE` / `REPAIR_EXPLANATION` / `FIXED_CODE`. |
| `_clean_fixed_code(code)` | Strip Markdown fences from the returned code. |
| `validate_fixed_code(code, context)` | Syntax check + original class names must still exist. |

**How it affects the whole codebase:** This file is only ever called when Pytest has produced *real* failures — `main.py` refuses to call it otherwise, so the project never invents a bug to fix. Its output decides whether Step 6 (validation) will pass or fail. Because the fix is validated but applied elsewhere, a bad AI answer can waste one repair attempt but can never corrupt the original file.

---

### 4.7 `report_generator.py` — The Reporter

**What it does (one line):** At the end of every run — success, failure, or early error — it writes the final results to `reports/repair_report.json` and `reports/repair_report.txt`.

**How it works:** `generate_report(report_data, reports_dir)` receives the dictionary that `main.py` has been filling with *actual* results throughout the run. It writes that dictionary directly to JSON (no values are invented or adjusted), then formats the same values into a readable text report with sections: problem and root cause, tests, repair outcome, and uncertain behaviours/limitations.

**How it affects the whole codebase:** It is a pure output file — nothing else depends on it, and it depends on nothing except the data it is given. This is deliberate: reporting can never influence the repair logic. If reporting itself fails, `main.py` prints a warning but the run's real outcome has already been shown on the terminal.

The meaning of every JSON field is decoded in Section 8.

---

### 4.8 `sample_project/shopping_cart.py` — The Patient (Demo Target)

**What it does:** A small, normal-looking `ShoppingCart` class:

- `__init__` creates an empty list `self.items`.
- `add_item(name, price, quantity=1)` validates: name cannot be empty, price cannot be negative, quantity must be a positive integer — otherwise it raises `ValueError`. Valid items are stored as dictionaries.
- `calculate_total(discount_percent=0)` validates the discount is between 0 and 100, adds up `price * quantity` for all items, applies the discount, and returns the result rounded to 2 decimal places.

**The intentional bug** is one line inside `calculate_total`:

```python
total = subtotal * (1 - discount_percent)      # BUG: 10 means "10", not "10%"
```

It should divide the percentage by 100. With a subtotal of 20 and a 50% discount, the buggy line gives `20 * (1 - 50) = -980` instead of `10`. Negative money is the visible symptom.

**Why this file matters:** The docstrings are the "specification" Model 1 reads. Notice that the docstring says "Apply the provided percentage discount" and "Discount must be between 0 and 100" — a human (and the AI) can derive the correct formula from those words plus common sense, without ever seeing a correct implementation. That is exactly the skill the project demonstrates. Do not fix this file by hand before a run — if it is already correct, there is no bug for the system to find and the demonstration collapses. After a *successful* run this file itself will contain the fix (that is the new approach); restore the buggy line when you want to demonstrate again.

---

### 4.9 `sample_project/behavior_spec.md.example` — The Optional Rule Book (Template)

**What it does:** It is an *example* of the optional specification file, written in plain English: 15 numbered rules for the shopping cart (including worked examples like "10 percent discount on 100 gives 90").

**How it is used:**

- The `.example` file itself is **never loaded** by the program. It exists purely as a template for you.
- To activate it, copy/rename it to exactly `behavior_spec.md` in the same folder and edit the rules as you like.
- On the next run, `behavior_reader.py` finds it, `main.py` prints "Mode A", and Model 1 treats your rules as the highest-priority truth — above docstrings.
- Delete or rename it back, and the system returns to Mode B (inference).

**How it affects the codebase:** It changes *test quality*, not code. A precise spec produces precise tests. If your spec contradicts a docstring, Model 1 is instructed to report the conflict rather than silently choose — watch for that in the test plan and uncertain behaviours.

---

### 4.10 Configuration files

| File | What it does | Effect on the project |
|---|---|---|
| `requirements.txt` | Lists `openai`, `python-dotenv`, `pytest` — nothing else. | `pip install -r requirements.txt` prepares any new machine. Keeping it tiny keeps the project explainable. |
| `.env` | Holds your real `OPENROUTER_API_KEY`, the base URL, and `TEST_MODEL` / `REPAIR_MODEL`. | Read once by `llm_client.py`. The two model names are independent, so Model 1 and Model 2 can be different models. Never upload this file. |
| `.env.example` | Same file with a placeholder key. | Safe template to share; copy it to `.env` and fill in your key. |
| `.gitignore` | Tells Git to ignore `.env`, caches, and the generated contents of `reports/`. | Prevents accidentally publishing your API key or generated clutter. |
| `.gitkeep` | Empty placeholder file in `reports/`. | Git does not track empty folders; this keeps `reports/` existing in a fresh clone so the program always has somewhere to write its report. |

---

## 5. How the Files Talk to Each Other

No file does everything. Each file has one job, and `main.py` passes data between them like an assembly line:

```text
main.py
  │
  ├──> llm_client.get_api_key() / get_test_model() / get_repair_model()
  │         (reads .env — Step 1 checks)
  │
  ├──> behavior_reader.understand_behavior(target)
  │         returns: behaviour context dict ──────────────┐
  │                                                       │ reused by
  ├──> test_generator.generate_test_cases(context, code)  │ both models
  │         └──> llm_client.call_llm(prompt, TEST_MODEL)  │
  │         returns: test count, plan, uncertain list     │
  │         writes (temp): generated/tests/test_..._generated.py + test_plan.md
  │                  reports/test_plan.md               │
  │                                                       │
  ├──> test_runner.compute_file_hash(test_file)           │
  ├──> test_runner.run_tests(temp_env, temp_test_file)      │
  │         returns: passed/failed counts + output ───┐   │
  │                                                   │   │
  ├──> repair_agent.repair_code(code, context, tests, │   │
  │                             results, plan) <──────┘   │
  │         └──> llm_client.call_llm(prompt, REPAIR_MODEL)
  │         returns: root cause + fixed code
  │
  ├──> test_runner.run_tests(...) again (same tests, hash re-checked)
  │
  └──> report_generator.generate_report(report_data)
            writes: reports/repair_report.json + .txt
```

Three design rules keep this clean:

1. **Only `llm_client.py` knows about the internet.** Everything else works with plain Python values (strings, dictionaries, file paths).
2. **Data flows in one direction.** Context → tests → results → fix → results → report. Nothing reaches backwards and edits an earlier stage (the test file, for example, is never edited after Step 4 — and the hash proves it).
3. **Files on disk are the interfaces.** The generated test file, the candidate file and the report are real files you can open and inspect at every stage. Nothing important is hidden inside the program's memory.

---

## 6. How to Run the Code

### 6.1 Before you start

- Python 3.10 or newer (`python --version`).
- An OpenRouter account and API key (for the live run).
- Internet access (only the live run needs it; the unit tests do not).

### 6.2 Install (one time)

Windows PowerShell:

```powershell
cd C:\Users\abhinav\OneDrive\Desktop\Term-paper\bugfixer

# optional but recommended: a virtual environment
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

Linux/Mac: same commands, except activate with `source venv/bin/activate`.

### 6.3 Configure `.env` (one time)

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace the placeholder with your real key:

```env
OPENROUTER_API_KEY=<your real key - never share this file>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
TEST_MODEL=deepseek/deepseek-v4.1-flash
REPAIR_MODEL=deepseek/deepseek-v4.1-flash
```

You may use a different (cheaper or stronger) model for either role — for example the code-specialised `qwen/qwen3-coder-30b-a3b-instruct` — by changing only these two lines. No code changes are needed because `llm_client.py` reads the names at runtime. If a run fails with a "model not found" style error, the ID in `.env` is the first thing to check on `openrouter.ai/models`.

Quick sanity check (does **not** print your key):

```powershell
python -c "from llm_client import get_api_key, get_test_model, get_repair_model; print('key loaded:', bool(get_api_key())); print(get_test_model(), '|', get_repair_model())"
```

### 6.4 The main run

```powershell
python main.py
```

That single command performs the full flow: initialisation → behaviour understanding → test generation + review → test run 1 → (if failures) repair → validation run 2 → report. A typical successful run takes under a minute; most of the time is spent waiting for the 3–4 AI replies.

To test a **different file** instead of the shopping cart:

```powershell
python main.py path\to\your_file.py
```

(or change the `TARGET_FILE` line at the top of `main.py`). Remember: one file at a time.

### 6.5 Mode A — running with your own specification (optional)

```powershell
Copy-Item sample_project\behavior_spec.md.example sample_project\behavior_spec.md
# edit sample_project\behavior_spec.md if you want different rules
python main.py
```

Step 2 will now print "Mode A", and the report will show `"specification_available": true`. Remove the file (`Remove-Item sample_project\behavior_spec.md`) to return to Mode B. Both modes should be demonstrated — they prove the system works with and without a written specification.

### 6.6 Run the unit tests (no API key needed)

```powershell
python -m pytest unit_tests/ -v
```

Expected: **12 passed** (about 5–10 seconds). Run this after any code change to make sure you did not break a module. What these tests are is explained fully in Section 10.

### 6.7 Running again

Just run `python main.py` again — but note the new approach: after a successful run the target file itself is fixed, so a second run on the same target will find no bug (restore the buggy line first if you are re-demonstrating). The two report files are overwritten with fresh results each run. Because Model 1 is an AI, the generated tests will be similar but not identical each time — a different test count (say 28 instead of 33) is normal and not a problem. What must stay consistent is the *pattern*: discount tests fail before repair, everything passes after.

---

## 7. The Temporary Environment — How Tests Run and When the Original File Changes

### Why a temporary environment?

BugFixer generates and *executes* code written by an AI, and it now fixes the **original target file directly** — but only at the very last safe moment. The rule is:

> **A candidate fix must pass every generated test inside a temporary environment first. Only then is it written (propagated) into the original file. If anything fails, the original file is never touched.**

A *temporary environment* is a normal folder created by Python's `tempfile.TemporaryDirectory()` (for example `C:\Users\...\Temp\bugfixer_ab12cd34\`). `main.py` creates one temporary root folder for the whole run, and Python automatically deletes it — with everything inside — when the run ends, whether the run succeeded, failed, or crashed. There is no persistent `workspace/` folder any more, so nothing stale can leak from one run into the next.

### What is inside the temporary folder during a run?

| Temporary path | Created by | When | What it contains and why |
|---|---|---|---|
| `generated/tests/test_<module>_generated.py` | `test_generator.py` (Step 3) | Test generation | The master copy of Model 1's test file. Its SHA-256 hash is taken here; this exact text is copied into every execution environment below, so before/after runs use byte-identical tests. |
| `generated/test_plan.md` | `test_generator.py` (Step 3) | Test generation | Model 1's reasoning (summary, plan, review, uncertain behaviours), in temporary form. |
| `before_repair/<module>.py` + `before_repair/tests/...` + `before_repair/conftest.py` | `main.py` (Step 4) | Before run | An execution environment holding the **original** code and a copy of the generated tests. The 3-line `conftest.py` inserts the environment folder into `sys.path` so the test file can import the module sitting next to it. A `before_repair_improved/` twin is created only if the one improved test attempt is needed. |
| `after_repair_attempt_1/<module>.py` + `tests/...` + `conftest.py` | `main.py` (Step 6) | Validation | Same layout, but the module is Model 2's **candidate** code. A separate `after_repair_attempt_2/` is created only if a second attempt is needed. |

### The propagation moment (the heart of the new approach)

1. The candidate runs in `after_repair_attempt_N/`. Pytest's verdict comes from *that* folder only.
2. **If all tests pass:** `main.py` calls `_propagate_fix()`, which writes the candidate bytes into the original target file (using `write_bytes` so Windows cannot alter line endings), then re-hashes the target file. Only if the hash exactly matches the validated candidate is the run marked successful (`fix_applied_to_target: true` in the report).
3. **If any test fails:** nothing is written anywhere outside the temporary folder. The next attempt (if any) gets a fresh environment. After two failed attempts the report says `repair_successful: false` and the program re-hashes the target file to *confirm* it is unchanged.
4. The original file content is also kept in memory (`original_code`) for the whole run, so even a disk error during propagation restores the original text.

### What survives after the temporary folder is deleted?

Only things you actually need as evidence, copied into `reports/` at the end of Step 4 (they are records, never executed from there):

- `reports/generated_tests/test_<module>_generated.py` — the tests Model 1 wrote, for inspection.
- `reports/test_plan.md` — Model 1's reasoning.
- `reports/repair_report.json` / `repair_report.txt` — the final result (Step 7).

### One consequence you must know

Because a successful run now **fixes `sample_project/shopping_cart.py` itself**, the demo target is no longer buggy after a successful run — running `python main.py` a second time will (correctly) find no failing discount tests. To demonstrate again, first restore the buggy line in the sample file (`total = subtotal * (1 - discount_percent)`). This is the visible difference from the old workspace approach, where the fixed file stayed in a workspace folder and the sample stayed buggy forever.
## 8. The `reports/` Folder — The Final Report Explained

Every run (including failed or interrupted ones) ends by writing two files. They contain the same information in two shapes: `repair_report.json` for machines/other programs, and `repair_report.txt` for humans.

### Every JSON field decoded

| Field | Meaning in simple words |
|---|---|
| `project` | Always `"BugFixer Lite"`. Identifies which system produced the report. |
| `target_file` | The file that was tested, e.g. `shopping_cart.py`. |
| `behaviour_mode` | `"documentation_inference"` (Mode B — behaviour inferred from docstrings) or `"specification"` (Mode A — your `behavior_spec.md` was used). |
| `specification_available` | `true`/`false`: was a `behavior_spec.md` found for this run? |
| `bug_detected` | `true` if at least one generated test actually failed in Run 1. `false` means the tests exposed nothing — the program does **not** claim the code is bug-free, only that these tests found nothing. |
| `root_cause` | Model 2's explanation of the bug, in its own words. Empty if no repair was attempted. |
| `repair_explanation` | What Model 2 changed and why. Empty if no repair was attempted. |
| `test_cases_generated` | How many `test_` functions Model 1 produced (33 in the sample run). |
| `test_file_unchanged` | `true` if the SHA-256 hash of the generated test file was identical before and after repair — proof the same tests judged both versions. |
| `fix_applied_to_target` | `true` only when a candidate passed all tests in the temporary environment AND was written into the original target file and verified by hash. `false` in every other outcome. |
| `execution_environment` | Always `"temporary_directory"`: records that test execution happened in an auto-deleted temporary folder, not in a persistent workspace. |
| `tests_before_repair` | `{"passed": 23, "failed": 10}` — Pytest counts against the buggy code. |
| `tests_after_repair` | `{"passed": 33, "failed": 0}` — Pytest counts against the fixed code, same tests. |
| `repair_successful` | `true` only if every test passed in validation. This is set from Pytest's real return code, never assumed. |
| `repair_attempts` | How many times Model 2 was asked to fix the code (1 or 2; 0 if there was nothing to repair). |
| `uncertain_behaviours` | The list of behaviours Model 1 was unsure about. A non-empty list is honest reporting, not an error. |

The values start as pessimistic defaults in `main.py` (`false`, `0`, empty strings) and are only overwritten by real events. So a report from a run that died at Step 3 will truthfully show `test_cases_generated: 0` and `repair_successful: false` instead of pretending anything worked.

---

## 9. Decoding the Output of `python main.py`

This section walks through a **real successful run** (the shopping cart demo, Mode B) line by line, so you can explain exactly what every block means.

### 9.1 The header (Step 1)

```text
BugFixer Lite - AI Test Generation and Code Repair
  API key found (value hidden).
  Model 1 (tests)  : deepseek/deepseek-v4.1-flash
  Model 2 (repair) : deepseek/deepseek-v4.1-flash
  Target file      : ...\sample_project\shopping_cart.py
  Approach         : tests run in a temporary environment;
                     the target file is edited ONLY after a
                     candidate fix passes all tests there.
  Temporary environment created: C:\Users\...\Temp\bugfixer_xxxxxxxx
  (It will be deleted automatically at the end of the run.)
```

Decoded:

- "API key found" means `.env` was read and the key is not the placeholder. The value is hidden on purpose.
- The two model names show which AI plays which role. They can be different models; here both are the same.
- The "Approach" lines state the safety contract of the whole system: the **target** (original) is read-only *until* a candidate fix has passed every test in the temporary environment; only at that moment is it edited. The temporary folder path is shown so you can even peek inside it while the run is paused — it disappears when the run ends.

### 9.2 Step 2 — behaviour understanding

```text
Mode B - no behavior_spec.md found.
Information sources: docstrings, comments, type hints, ...
Found class ShoppingCart with methods: __init__, add_item, calculate_total
```

Decoded:

- No file named exactly `behavior_spec.md` exists next to the target, so the system runs in inference mode. (The `.example` file is ignored, by design.)
- The class and method list came from AST parsing (`behavior_reader.py`) — the code was *read as structure*, not executed. No AI has been called yet at this point.

### 9.3 Step 3 — Model 1 generates and reviews tests

```text
[Model 1] Calling deepseek/deepseek-v4.1-flash to generate tests...
[Model 1] Reviewing generated tests (consistency check)...
Generated 33 test cases.
```

Decoded:

- Two separate AI calls happened: generation, then a self-review of the generated tests.
- "33 test cases" means the final saved file contains 33 functions starting with `test_`. The number varies between runs because an AI writes them fresh each time.
- Two files now exist: `reports/generated_tests/test_shopping_cart_generated.py` (the tests) and `reports/test_plan.md` (the reasoning).

Then comes the **uncertain behaviours** list. In the sample run it had about 20 items, for example:

- "Whether an item name consisting only of whitespace is considered empty."
- "Whether quantity=True (bool) should be accepted... because bool is a subclass of int in Python."
- "Whether non-integer discount percentages such as 12.5 are intended to be supported."

How to read this list correctly:

- These are things the documentation genuinely does not decide. Model 1 is *refusing to guess*. That is the designed behaviour: hard test assertions are only written for documented or strongly supported behaviour, and doubts are reported instead.
- A long list is not a failure — it is evidence the model is not inventing requirements. (In the sample run one item about `quantity=True` appears twice; that is a harmless duplicate created when the generation list and the review list were merged.)
- Tip for a stronger demo: every item on this list that you can answer is a rule you can add to `behavior_spec.md`, after which Mode A removes the uncertainty.

### 9.4 Step 4 — Pytest runs against the buggy code

```text
collected 33 items
tests/test_shopping_cart_generated.py::test_add_item_empty_name PASSED
tests/test_shopping_cart_generated.py::test_calculate_total_discount_50 FAILED
...
======================== 10 failed, 23 passed in 0.27s ========================
```

Decoded:

- Each line is one test: the file, the test name, and `PASSED` or `FAILED`. Pytest — not the AI — produced this verdict.
- The **failure blocks** that follow are the most informative part. Example:

```text
______________________ test_calculate_total_discount_50 _______________________
    assert cart.calculate_total(50) == pytest.approx(10.0)
E   assert -980.0 == 10.0 ± 1.0e-05
E     comparison failed
E     Obtained: -980.0
E     Expected: 10.0 ± 1.0e-05
```

  Reading it: the test put items worth 20 in the cart and asked for a 50% discount. *Expected* (from the documentation): `10.0`. *Obtained* (from the buggy code): `-980.0`, because the buggy formula computes `20 * (1 - 50) = 20 * (-49) = -980`. Negative money is the bug's fingerprint, and every one of the 10 failures shows the same fingerprint with different numbers.
- **The pattern matters more than any single failure:** all 10 failures are discount/rounding-with-discount tests, while all 23 `add_item` and validation tests pass. In one glance this says: "adding items and validation are correct; only the discount maths is wrong." That pattern is exactly what Model 2 uses to locate the bug.
- `Passed: 23  Failed: 10` under the Pytest output is `test_runner.py`'s own count of the same result — these two numbers become `tests_before_repair` in the report.

> If this step ever shows **all tests passed**, the program asks Model 1 for one improved set of tests (better boundary/documented-example coverage) and runs again. If they still all pass, it reports that the generated tests did not expose a defect and stops — it never fabricates failures and never calls Model 2 without real failures.

### 9.5 Step 5 — Model 2 diagnoses and repairs

```text
[Model 2] Calling deepseek/deepseek-v4.1-flash to diagnose and repair...
Root cause: In `calculate_total`, the discount percentage is treated as a
decimal fraction... The correct percentage calculation must divide
`discount_percent` by 100.
Candidate received. It will be tested in a temporary environment BEFORE the target file is touched.
```

Decoded:

- Model 2 received the source, the behaviour context, Model 1's plan, the test code, and the real failure text from Step 4.
- "Root cause" is its diagnosis in plain English; "Repair" describes the change. In the sample run the proposed change is exactly the one-line conversion `discount_percent / 100` — the *smallest* fix, with all validation rules and method signatures preserved, as instructed.
- The reply is validated (syntax + class names) and placed as the module inside a fresh temporary environment (`after_repair_attempt_1/`). At this point the original in `sample_project/` has still not been touched — the candidate exists only in the temporary folder and in memory.

### 9.6 Step 6 — validation with the same tests

```text
Test file unchanged: True
...
============================== 33 passed in 0.06s ==============================
Passed: 33  Failed: 0
All tests passed in the temporary environment.
Propagating the validated fix into: ...\sample_project\shopping_cart.py
Fix applied to the target file and verified by hash.
```

Decoded:

- "Test file unchanged: True" = the SHA-256 fingerprint of the generated test file is identical to the one taken before repair. The fixed code was judged by *exactly* the 33 tests that caught the bug — no test was edited, weakened, or deleted to make the result look good.
- `33 passed` against the fixed copy, compared with `23 passed / 10 failed` against the buggy copy, is the objective proof of repair. These become `tests_after_repair` in the report.
- Only after this all-pass verdict does **propagation** happen: the candidate bytes are written into `sample_project/shopping_cart.py` itself and the file is re-hashed; "verified by hash" means the bytes on disk are exactly the bytes that passed the tests. You can confirm it yourself: the sample file now contains `subtotal * (1 - discount_percent / 100)`. (Remember Section 7: to demo again, restore the buggy line first.)
- If this step had failed, Model 2 would get one more attempt with the new failure output (maximum 2 attempts), each in a fresh temporary environment. If that also failed, **no write to the target would ever have happened**, the program would confirm the target's hash is unchanged, and the report would say `repair_successful: false, fix_applied_to_target: false`.

### 9.7 Step 7 — and the final verdict

```text
JSON report : ...\reports\repair_report.json
Text report : ...\reports\repair_report.txt
Done.
```

The terminal has already told the story; the report files are its permanent record. For the sample run the report reads:

```json
{
  "behaviour_mode": "documentation_inference",
  "specification_available": false,
  "bug_detected": true,
  "test_cases_generated": 33,
  "test_file_unchanged": true,
  "tests_before_repair": { "passed": 23, "failed": 10 },
  "tests_after_repair":  { "passed": 33, "failed": 0 },
  "repair_successful": true,
  "repair_attempts": 1,
  "fix_applied_to_target": true,
  "execution_environment": "temporary_directory"
}
```

One sentence that summarises a perfect run: **"33 AI-generated tests found 10 real failures in the buggy code; Model 2 fixed the root cause in one attempt; the identical 33 tests (hash-proven unchanged) then all passed inside a temporary environment — and only then was the fix written into the original file and verified by hash."**

---

## 10. The Unit Test File in `unit_tests/` Explained

The file is **`unit_tests/test_bugfixer_units.py`** (note the exact name — there is no file called "test_bugfixed"; if you remember a name like that, this is the file you mean).

### What is it for?

It tests **BugFixer itself** — not the shopping cart.

This is the most commonly confused point in the project, so here is the distinction clearly:

| | `unit_tests/test_bugfixer_units.py` | `reports/generated_tests/test_shopping_cart_generated.py` |
|---|---|---|
| Written by | You / the developer (by hand, once) | Model 1 (AI, fresh on every run) |
| What it tests | BugFixer's own modules (`behavior_reader`, `test_generator`, `test_runner`, `repair_agent`) | The `ShoppingCart` class |
| Needs API key / internet? | **No** | Created by the AI during `python main.py` |
| When does it change? | Only when you edit BugFixer's code | Every run (overwritten) |
| How to run it | `python -m pytest unit_tests/ -v` | Runs automatically inside `python main.py` (or manually with pytest) |

### How can it test AI features without an API key? (Mocking)

Near the top of the file are three ready-made fake AI replies: `FAKE_GENERATION_RESPONSE`, `FAKE_REVIEW_RESPONSE`, and `FAKE_REPAIR_RESPONSE`. They look exactly like real Model 1 / Model 2 answers (same section headings), but they are fixed strings stored in the file.

Inside the tests, a pytest feature called **`monkeypatch`** temporarily swaps the real `call_llm` function for a fake one that returns these strings. In simple words:

> "For the duration of this test, pretend the AI answered *this*. Now check that our code handles that answer correctly."

This is called **mocking**. It makes the tests fast, free, repeatable, and independent of OpenRouter being up or your key having balance — while still exercising the real parsing, validation, saving and repair code. The moment the test ends, the real function is restored.

### The 12 tests, grouped by what they prove

**`behavior_reader` (4 tests):**

| Test | Proves |
|---|---|
| `test_behavior_reader_finds_class_and_methods` | AST reading finds `ShoppingCart`, `add_item`, `calculate_total` in the sample file. |
| `test_behavior_reader_mode_without_spec` | With only the `.example` file present, Mode B is selected and `specification_available` is `False`. |
| `test_behavior_reader_mode_with_spec` | When a real `behavior_spec.md` is placed next to a copy of the source, Mode A is selected. |
| `test_sample_contains_intentional_bug` | The demo file still contains the buggy expression — guards against someone "helpfully" fixing the demo and silently breaking the project. |

**`test_generator` (4 tests):**

| Test | Proves |
|---|---|
| `test_generate_test_cases_with_mock` | With a mocked Model 1, the full pipeline saves a test file containing 2 tests and a `test_plan.md`. |
| `test_validate_test_code_rejects_banned_import` | Test code containing `import subprocess` is rejected by the safety validator. |
| `test_validate_test_code_rejects_syntax_error` | Broken Python in generated tests is rejected, not saved. |
| `test_parse_model1_response_sections` | A Model 1 reply is correctly split into summary / plan / code. |

**`test_runner` (2 tests):**

| Test | Proves |
|---|---|
| `test_hash_detects_change` | Changing one character in a file changes its SHA-256 hash (the fairness guarantee rests on this). |
| `test_run_tests_counts_pass_and_fail` | A tiny module with one passing and one failing test is reported as exactly `passed=1, failed=1`. |

**`repair_agent` (2 tests):**

| Test | Proves |
|---|---|
| `test_repair_code_with_mock` | With a mocked Model 2, the root cause and the fixed code (containing `discount_percent / 100`) are extracted correctly. |
| `test_parse_repair_response_strips_fences` | Even if the model wraps its fixed code in ``` fences against instructions, they are stripped and the code is clean. |

### How to run them and read the result

```powershell
python -m pytest unit_tests/ -v
```

Each line names one test and ends with `PASSED`. The summary `12 passed` means every module behaved as designed *without any AI involvement*. Run this after changing any BugFixer file: if all 12 still pass, your change did not break the machinery. (These tests do not prove the *live AI* works — only a real `python main.py` run proves that. Both kinds of evidence together are the complete verification story.)

---

## 11. Will This Approach Work on Slightly More Complex Projects?

**Short answer: yes — within clear limits.** The same approach works well on a somewhat bigger *single file* with good documentation. It does not, in its current form, handle whole multi-file projects, databases, or live services. Here is the honest breakdown.

### Complexity ladder

| Level | Example target | Expected result |
|---|---|---|
| 1 — Current demo | One class, 2–3 methods, pure calculations and validation | Works reliably (proven: 33 tests, one-attempt repair). |
| 2 — A bit bigger, still one file | One file with 3–5 classes or 10–20 functions (~200–500 lines), e.g. a bank account + transaction classes, a marks/grade calculator, a small inventory system, string/date utility functions — all with docstrings | **Generally works.** Model 1 can read the whole file in one prompt, tests are still plain pytest, and Model 2 can still see the whole file when repairing. This is the realistic "next step" for this project. |
| 3 — One file using only the standard library | Target imports `math`, `datetime`, `re`, `json` etc. | **Mostly works.** The target's own imports are fine (they run inside the copied module). The import restriction applies to the *test file* (only `pytest` + the target module), and tests normally only need the target's public functions anyway. |
| 4 — One file importing *your other* files | `from helpers import ...`, `from models import ...` | **Breaks by default.** Only the single target file is copied into the temporary environment, so the import fails and tests error out. Workarounds today: test the helper file separately, or test a self-contained file. (Copying companion modules into the temporary environment is the natural future improvement.) |
| 5 — Database / API / GUI / network code | Flask routes, SQL queries, file downloads, Tkinter windows | **Poor fit without changes.** Behaviour depends on external state; generated tests would need fixtures, temporary databases, or mocks, which the current prompts and import allow-list do not set up. Repair also cannot be validated by simply running functions. |

### What decides success more than size

1. **Documentation quality.** A 400-line file with clear docstrings and examples will test *better* than a 60-line file with none. In Mode B the docstrings effectively *are* the specification. For anything beyond the demo, writing a `behavior_spec.md` (Mode A) is the single highest-value habit — it converts the AI's guesses into your stated rules, and the worked numeric examples ("10% off 100 = 90") are what produce bug-catching tests.
2. **Deterministic, side-effect-free logic.** Calculations, validation, parsing, sorting, state machines held in memory — ideal. Anything involving randomness, current time, files on disk, or the network makes expected results hard to state and tests flaky.
3. **Bug type.** Wrong formula, wrong boundary (`<` vs `<=`), missing validation, wrong rounding — the approach shines. Concurrency bugs, performance bugs, memory issues, and "wrong only with this production data" bugs are largely invisible to it.
4. **File size vs. context.** The whole file is sent to the model several times per run. A few hundred lines is comfortable; several thousand lines makes prompts slow, costly, and more likely to be summarised imperfectly by the model.
5. **Interaction depth.** Methods that must be called in sequence on one object (like the cart) already work — Model 1 writes multi-step tests. Deep object graphs or long setup rituals in every test increase the chance of AI-written setup mistakes, which show up as test failures that are actually *test* bugs, not code bugs. The review call reduces this risk but cannot eliminate it.

### Practical recipe for trying a bigger target

1. Pick **one** self-contained `.py` file (stdlib imports only).
2. Add/complete docstrings, ideally with one numeric example per rule.
3. Write a `behavior_spec.md` next to it listing the rules you care about most.
4. Run `python main.py your_file.py` and read `reports/test_plan.md` first — check the expected values yourself before trusting the pass/fail pattern.
5. Read the uncertain-behaviours list: each item is either a documentation gap to fix or a rule to add to the spec.
6. If repair fails twice, the candidate existed only inside the (now deleted) temporary environment — use the terminal failure output and `reports/test_plan.md` to understand what documentation or specification was missing, then re-run.

### What you would add to support the next level (future work, in order of value)

- Copy the target's sibling modules (or the whole small folder) into the temporary environment so local imports resolve.
- Allow a configurable import list for generated tests (still deny dangerous modules).
- Support pytest fixtures / `tmp_path` in the Model 1 prompt for file-based code.
- Split very large files class-by-class for test generation, then merge the suites.
- Keep a history of runs instead of overwriting reports.

**Bottom line for your viva:** the *approach* (documented behaviour → AI tests → real execution → AI repair → same-test validation) scales conceptually to real projects — professional AI test-generation tools follow the same loop. This *implementation* is intentionally a one-file, pure-Python version of that loop, and its limits (single file, no external state) are known, deliberate, and easy to explain.

---

## 12. Safety — In Simple Words

This program writes and *executes* AI-generated Python, so it includes basic seatbelts:

- The **original file is never modified** (copies only; proven by hash at the end of every run).
- Generated tests are checked with AST: only `pytest` and the target module may be imported; `subprocess`, `socket`, `os`, `eval`, `exec` and friends are rejected.
- Pytest runs in a subprocess inside an auto-deleted temporary environment, without `shell=True`, with a 120-second timeout.
- Proposed fixes are syntax-checked and must keep the original class names before they are trusted — and even then, they are executed only inside the temporary environment. The original file is written only after an all-pass verdict, with its original content kept in memory during the run for restoration on any write error.
- The API key lives only in `.env`, is read only by `llm_client.py`, is never printed, and is never sent to generated code.

**Honest limit:** these are *basic safeguards for a trusted, educational setting — not a security sandbox*. AST checks can be bypassed by sufficiently clever code, and a subprocess still runs with your user permissions. **Only run BugFixer Lite on source files you trust.** Do not point it at random downloaded repositories.

---

## 13. Limitations

- **One Python file at a time.** No multi-file packages, no other languages.
- **Tests can be wrong.** Model 1 + its review reduce errors but cannot prove correctness. Ambiguous behaviour is reported under uncertain behaviours rather than asserted — check `test_plan.md` before trusting results.
- **No failure, no repair.** If the generated tests (plus one improved attempt) never expose the bug, Model 2 is never called and the report says so.
- **Maximum 2 repair attempts.** Harder bugs may need a human after that.
- **Pure-logic bias.** External state (databases, APIs, files, GUIs, network, randomness, time) is out of scope for the generated tests.
- **AI variability.** Test counts and phrasing differ per run; the pass/fail pattern is the stable signal.
- **Live runs need a valid OpenRouter key and internet.** Only the unit tests work fully offline.

---

## 14. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `[Error] OPENROUTER_API_KEY is missing...` | `.env` missing, or key still the placeholder | Copy `.env.example` to `.env`, paste your real key, re-run. |
| API error mentioning the model / "not found" | Model ID in `.env` is wrong or unavailable on your account | Check the exact ID at `openrouter.ai/models`; update `TEST_MODEL` / `REPAIR_MODEL`. |
| `Generated test code failed validation...` | Model 1 produced code with a banned import or no `test_` functions | Re-run (a fresh generation usually behaves); if it repeats, try a stronger/coder model for `TEST_MODEL`. |
| All tests pass, no repair happens | The generated tests genuinely did not cover the buggy behaviour (the program already used its one improved attempt) | Add a `behavior_spec.md` with worked numeric examples and re-run. |
| `Repair successful: false`, attempts = 2 | Model 2 could not produce a fix passing all tests | Read the last failure output in the terminal and `reports/test_plan.md`; improve documentation/spec and re-run. The target file was never modified. |
| Tests fail with `ModuleNotFoundError` for your own module | Running pytest manually from the wrong place, or the target imports sibling files | Let `main.py` run the tests (it builds each temporary environment with its own `conftest.py`). Sibling imports are a Level-4 limitation (Section 11). |
| Everything suddenly fails after your edit to BugFixer code | A module contract changed | Run `python -m pytest unit_tests/ -v` and fix the first failing test it reports. |

---

## 15. Useful Commands Cheat Sheet

```powershell
# --- setup (once) ---
pip install -r requirements.txt
Copy-Item .env.example .env          # then paste your key into .env

# --- verify the machinery (offline, free, ~10 seconds) ---
python -m pytest unit_tests/ -v      # expect: 12 passed

# --- the real thing ---
python main.py                       # full flow on sample_project/shopping_cart.py
python main.py path\to\other.py      # full flow on a different single file

# --- Mode A (with specification) ---
Copy-Item sample_project\behavior_spec.md.example sample_project\behavior_spec.md
python main.py
Remove-Item sample_project\behavior_spec.md   # back to Mode B

# --- inspect what the AI produced ---
Get-Content reports\test_plan.md
Get-Content reports\generated_tests\test_shopping_cart_generated.py
Get-Content reports\repair_report.json
# (inspectable copies are in reports/; execution itself happened in the deleted temp env)

# --- prove original vs fixed with your own eyes ---
Select-String -Path sample_project\shopping_cart.py -Pattern "1 - discount_percent"
Select-String -Path sample_project\shopping_cart.py -Pattern "discount_percent / 100"   # after a successful run, the fix is HERE
```

---

## 16. How to Explain This Project in a Viva / Presentation

**The 60-second version:**

> "BugFixer Lite automatically tests and repairs a Python file using two AI roles. First, `behavior_reader.py` reads the code's structure and documentation with Python's AST module — without running the code. Model 1, the test engineer, uses that evidence — or my written specification if I provide one — to write Pytest tests, and then reviews its own tests. Pytest runs them for real inside a temporary environment: in our demo, 23 passed and 10 failed, and every failure showed negative money, which exposed the discount bug. Only then does Model 2, the debugging engineer, receive the code, the tests and the actual failure output; it diagnosed that the percentage was never divided by 100 and produced a corrected file. That candidate is placed in a fresh temporary environment — the original file is still untouched — and the *exact same* tests, proven unchanged by a SHA-256 hash, are re-run: 33 out of 33 pass. Only at that moment is the fix written into the original file and verified by hash; if the candidate had failed, the original would never have been modified. Everything is recorded in a JSON and text report. The AI proposes, Pytest disposes, and the original file changes only after proof."

**Answers to likely questions:**

- *"Why two models?"* — Separation of concerns: one prompt specialises in expected behaviour and test design, the other in root-cause analysis and minimal fixes. They are independently configurable in `.env`, so they can literally be two different models.
- *"How do you know the tests themselves are right?"* — Three layers: expected values must be derived from documentation (not from running the buggy code), Model 1 reviews its own tests against the documentation, and ambiguous behaviour must be reported as uncertain instead of asserted. It is a consistency check, not a proof — and the project says so.
- *"Can the AI cheat by changing the tests?"* — No. The master test file is hashed before repair and re-hashed after; any change rejects the validation. Repair attempts are also capped at two, and failed candidates never reach the original file.
- *"Why not just fix the file directly at once?"* — That is exactly what the system avoids doing blindly. The candidate must first pass every test in a disposable temporary environment; propagation into the original file is a single hash-verified write that happens only after that proof, and the original content is held in memory during the run in case the write itself fails.
- *"Does it work on real projects?"* — The loop does; this implementation is deliberately scoped to one documented, self-contained Python file. Section 11 explains exactly where it works, where it breaks (local imports, external state), and what you would add next.

---

## 17. Glossary

| Term | Simple meaning |
|---|---|
| **LLM / Model** | The AI (accessed via OpenRouter) that writes tests (Model 1) and fixes code (Model 2). |
| **Prompt** | The instruction text sent to a model. BugFixer's prompts live in `test_generator.py` and `repair_agent.py`. |
| **OpenRouter** | A service that gives one API for many AI models. BugFixer talks to it through the OpenAI Python SDK. |
| **AST (Abstract Syntax Tree)** | A tree-shaped reading of code's structure produced by Python's `ast` module — classes, functions, docstrings — *without executing the code*. |
| **Docstring** | The `"""documentation"""` text inside a class or method. In Mode B, docstrings are effectively the specification. |
| **Mode A / Mode B** | With a user-written `behavior_spec.md` (A) vs. behaviour inferred from documentation (B). |
| **Behaviour context** | The dictionary `behavior_reader.py` builds (code, docstrings, hints, spec) and both models consume. |
| **Pytest** | The standard Python test runner. The independent judge of both the bug and the fix. |
| **Temporary environment / Candidate / Propagation** | A disposable folder (created by `tempfile`) where original and candidate code are executed; the candidate is Model 2's proposed fix; *propagation* is the single moment a fully-passing candidate is written into the original file. |
| **SHA-256 hash** | A fingerprint string for a file's exact bytes. Same file → same fingerprint; one changed character → different fingerprint. Used to prove the test file and the original file did not change. |
| **Subprocess** | Running another program (here: Pytest) from inside Python, with captured output and a timeout. |
| **Mocking** | In tests, temporarily replacing a real function (e.g. the AI call) with a fake that returns a fixed answer — used by the unit tests so they need no API key. |
| **`monkeypatch`** | The pytest tool that performs that temporary replacement and undoes it after the test. |
| **Allow-list** | "Only these imports are permitted" — the opposite of trying to list everything dangerous. Used to validate generated tests. |
