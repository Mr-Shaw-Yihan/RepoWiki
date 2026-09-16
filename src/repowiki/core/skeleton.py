"""Symbol-level skeletons for oversized files.

A 2,000-line module tells the analyzer more through its structure than
through its first 4,096 characters. For Python sources over the context
budget, replace the blind head truncation with an ast-derived skeleton:
the module docstring, then every top-level class and function with its
signature and docstring, in source order.
"""

from __future__ import annotations

import ast

_MAX_DOC_CHARS = 240


def _short_doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node, clean=True)
    if not doc:
        return ""
    first = doc.strip().split("\n\n", 1)[0].replace("\n", " ")
    if len(first) > _MAX_DOC_CHARS:
        first = first[: _MAX_DOC_CHARS - 1].rstrip() + "…"
    return first


def _render_function(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "") -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    sig = f"{indent}{prefix} {node.name}({ast.unparse(node.args)})"
    if node.returns is not None:
        sig += f" -> {ast.unparse(node.returns)}"
    sig += ":"
    doc = _short_doc(node)
    if doc:
        sig += f'\n{indent}    """{doc}"""'
    return sig


def _render_class(node: ast.ClassDef) -> str:
    parts = [ast.unparse(b) for b in node.bases]
    parts.extend(f"{k.arg}={ast.unparse(k.value)}" for k in node.keywords if k.arg)
    head = f"class {node.name}({', '.join(parts)}):" if parts else f"class {node.name}:"
    doc = _short_doc(node)
    lines = [head]
    if doc:
        lines.append(f'    """{doc}"""')
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(_render_function(child, indent="    "))
    return "\n".join(lines)


def python_skeleton(source: str, max_chars: int) -> str | None:
    """Return a symbol skeleton of Python source within max_chars.

    Returns None when the source does not parse or carries no extractable
    structure, so the caller can fall back to plain truncation.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, MemoryError):
        return None

    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(_render_class(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(_render_function(node))

    module_doc = _short_doc(tree)
    if not symbols and not module_doc:
        return None

    total_lines = source.count("\n") + 1
    head = f"# [skeleton: {len(symbols)} symbols from {total_lines} lines]\n"
    if module_doc:
        head += f'"""{module_doc}"""\n\n'

    out = head
    kept = 0
    for symbol in symbols:
        if len(out) + len(symbol) + 2 > max_chars:
            break
        out += symbol + "\n\n"
        kept += 1
    if kept < len(symbols):
        out += f"# ... {len(symbols) - kept} more symbols omitted\n"
    return out.rstrip() + "\n"


def context_for_file(
    content: str,
    language: str,
    budget: int = 4096,
) -> str:
    """The file context the analyzer sees for one file, within budget.

    Oversized Python files contribute their symbol skeleton instead of a
    head truncation; everything else keeps the original behavior.
    """
    if len(content) <= budget:
        return content
    if language == "python":
        skeleton = python_skeleton(content, budget)
        if skeleton is not None:
            return skeleton
    return content[:budget] + "\n... (truncated)"
