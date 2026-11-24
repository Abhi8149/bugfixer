"""
behavior_reader.py
------------------
Module 1 helper: Behaviour Understanding Engine (data collection only).

This module does NOT call the LLM. It collects everything Model 1 needs:
source code, class/method names, docstrings, type hints, comments and an
optional user-provided behaviour specification (behavior_spec.md).

Priority of evidence (also explained to Model 1 in the prompt):
    1. Explicit user-provided specification
    2. Docstrings and documented examples
    3. README / existing tests
    4. Type hints, signatures, comments
    5. Conventional behaviour from general programming knowledge
    6. Existing implementation (supporting context only)
"""

import ast
from pathlib import Path


def _extract_type_hints(node) -> list:
    """Collect simple type-hint strings from a function definition node."""
    hints = []
    for arg in node.args.args:
        if arg.annotation is not None:
            try:
                hints.append(f"{arg.arg}: {ast.unparse(arg.annotation)}")
            except Exception:
                hints.append(f"{arg.arg}: <unknown>")
    if node.returns is not None:
        try:
            hints.append(f"returns: {ast.unparse(node.returns)}")
        except Exception:
            pass
    # Default values are useful evidence too.
    defaults = node.args.defaults
    if defaults:
        for default in defaults:
            try:
                hints.append(f"default: {ast.unparse(default)}")
            except Exception:
                pass
    return hints


def _collect_comments(source_code: str) -> list:
    """Collect lines that look like comments (# ...). Simple line scan."""
    comments = []
    for line in source_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            comments.append(stripped)
    return comments


def understand_behavior(source_file, specification_file=None) -> dict:
    """
    Collect behaviour information for a Python source file.

    Args:
        source_file: path to the target .py file.
        specification_file: optional path to behavior_spec.md.
            If None, we look for behavior_spec.md next to the source file.

    Returns:
        A dictionary (behavior_context) with everything Model 1 needs.
    """
    source_path = Path(source_file)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    source_code = source_path.read_text(encoding="utf-8")

    # Parse with AST to understand structure (no code is executed here).
    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        raise ValueError(f"Source file has a syntax error: {error}") from error

    module_docstring = ast.get_docstring(tree) or ""

    classes = []
    functions = []
    all_docstrings = []
    if module_docstring:
        all_docstrings.append({"where": "module", "docstring": module_docstring})

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_info = {
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "methods": [],
            }
            if class_info["docstring"]:
                all_docstrings.append(
                    {"where": f"class {node.name}", "docstring": class_info["docstring"]}
                )
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_info = {
                        "name": item.name,
                        "docstring": ast.get_docstring(item) or "",
                        "type_hints": _extract_type_hints(item),
                        "signature": _build_signature(item),
                    }
                    class_info["methods"].append(method_info)
                    if method_info["docstring"]:
                        all_docstrings.append(
                            {
                                "where": f"{node.name}.{item.name}",
                                "docstring": method_info["docstring"],
                            }
                        )
            classes.append(class_info)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_info = {
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "type_hints": _extract_type_hints(node),
                "signature": _build_signature(node),
            }
            functions.append(func_info)
            if func_info["docstring"]:
                all_docstrings.append(
                    {"where": f"function {node.name}", "docstring": func_info["docstring"]}
                )

    comments = _collect_comments(source_code)

    # --- Optional behaviour specification ---------------------------------
    spec_path = None
    spec_text = ""
    specification_available = False

    if specification_file is not None:
        candidate = Path(specification_file)
        if candidate.exists():
            spec_path = candidate
    else:
        # Default location: behavior_spec.md next to the source file.
        candidate = source_path.parent / "behavior_spec.md"
        if candidate.exists():
            spec_path = candidate

    if spec_path is not None:
        spec_text = spec_path.read_text(encoding="utf-8")
        specification_available = True

    # Mode A vs Mode B.
    if specification_available:
        behaviour_mode = "specification"
    else:
        behaviour_mode = "documentation_inference"

    # Look for a README or existing tests nearby (light context only).
    extra_docs = []
    parent = source_path.parent
    for name in ("README.md", "readme.md"):
        readme = parent / name
        if readme.exists():
            extra_docs.append({"file": str(readme), "content": readme.read_text(encoding="utf-8")[:4000]})
            break
    # Also check project root README (one level up).
    if not extra_docs:
        root_readme = parent.parent / "README.md"
        if root_readme.exists():
            extra_docs.append({"file": str(root_readme), "content": root_readme.read_text(encoding="utf-8")[:4000]})

    context = {
        "source_file": str(source_path),
        "source_code": source_code,
        "module_name": source_path.stem,
        "module_docstring": module_docstring,
        "classes": classes,
        "functions": functions,
        "docstrings": all_docstrings,
        "comments": comments,
        "specification_available": specification_available,
        "specification_file": str(spec_path) if spec_path else None,
        "specification_text": spec_text,
        "behaviour_mode": behaviour_mode,
        "extra_docs": extra_docs,
    }
    return context


def _build_signature(node) -> str:
    """Build a readable signature string like: add_item(self, name, price, quantity=1)"""
    try:
        args = ast.unparse(node.args)
        return f"{node.name}({args})"
    except Exception:
        return f"{node.name}(...)"


def format_behavior_context(context: dict) -> str:
    """
    Turn the collected dictionary into readable text for the LLM prompt.
    Used by test_generator.py and repair_agent.py.
    """
    lines = []
    lines.append(f"TARGET FILE: {context.get('source_file')}")
    lines.append(f"MODULE NAME: {context.get('module_name')}")
    lines.append(f"BEHAVIOUR MODE: {context.get('behaviour_mode')}")
    lines.append(f"SPECIFICATION AVAILABLE: {context.get('specification_available')}")

    if context.get("specification_available"):
        lines.append("\n--- USER-PROVIDED BEHAVIOUR SPECIFICATION (highest priority) ---")
        lines.append(context.get("specification_text", ""))
    else:
        lines.append("\n--- NO USER SPECIFICATION: infer behaviour from docs below ---")

    lines.append("\n--- SOURCE CODE ---")
    lines.append(context.get("source_code", ""))

    lines.append("\n--- STRUCTURE (from AST) ---")
    for cls in context.get("classes", []):
        lines.append(f"Class: {cls['name']}")
        if cls.get("docstring"):
            lines.append(f"  Class docstring: {cls['docstring']}")
        for method in cls.get("methods", []):
            lines.append(f"  Method: {method['signature']}")
            if method.get("docstring"):
                lines.append(f"    Docstring: {method['docstring']}")
            if method.get("type_hints"):
                lines.append(f"    Type hints/defaults: {', '.join(method['type_hints'])}")
    for func in context.get("functions", []):
        lines.append(f"Function: {func['signature']}")
        if func.get("docstring"):
            lines.append(f"  Docstring: {func['docstring']}")

    if context.get("comments"):
        lines.append("\n--- COMMENTS ---")
        for comment in context["comments"]:
            lines.append(comment)

    for doc in context.get("extra_docs", []):
        lines.append(f"\n--- EXTRA DOC: {doc['file']} ---")
        lines.append(doc["content"])

    return "\n".join(lines)
