"""Tests for the symbol-skeleton path of oversized Python files."""

from __future__ import annotations

from repowiki.core.skeleton import context_for_file, python_skeleton

BIG_MODULE = '''"""Module docstring for the big module."""


CONSTANT = 42


def top_level(arg: int, flag: bool = False) -> str:
    """Convert the argument to text."""
    return str(arg)


class Widget(BaseWidget, metaclass=Meta):
    """A widget with a couple of methods."""

    def render(self, width: int) -> str:
        """Render the widget at the given width."""
        return "x" * width

    async def fetch(self) -> None:
        """Fetch widget data."""
        ...


def helper(value):
    return value * 2
'''


def test_skeleton_extracts_module_doc_classes_and_functions():
    skeleton = python_skeleton(BIG_MODULE, 4096)

    assert skeleton is not None
    assert skeleton.startswith("# [skeleton: 3 symbols from")
    assert '"""Module docstring for the big module."""' in skeleton
    assert "def top_level(arg: int, flag: bool=False) -> str:" in skeleton
    assert '"""Convert the argument to text."""' in skeleton
    assert "class Widget(BaseWidget, metaclass=Meta):" in skeleton
    assert "def render(self, width: int) -> str:" in skeleton
    assert "async def fetch(self) -> None:" in skeleton
    # module-level assignments and bare bodies do not leak in
    assert "CONSTANT" not in skeleton
    assert "return value * 2" not in skeleton


def test_skeleton_fits_budget_by_dropping_trailing_symbols():
    budget = 200
    skeleton = python_skeleton(BIG_MODULE, budget)

    assert skeleton is not None
    assert len(skeleton) <= budget + 60  # marker line may exceed slightly
    assert "def top_level" in skeleton  # the first symbol still fits
    assert "class Widget" not in skeleton
    assert "2 more symbols omitted" in skeleton
    # never leaves a half-written class block
    assert "metaclass=Meta" not in skeleton


def test_skeleton_returns_none_on_syntax_error():
    assert python_skeleton("def broken(:\n", 4096) is None


def test_skeleton_returns_none_when_no_structure():
    assert python_skeleton("x = 1\ny = 2\n", 4096) is None


def test_context_for_file_passes_small_files_through():
    small = "def tiny():\n    return 1\n"
    assert context_for_file(small, "python") == small


def test_context_for_file_prefers_skeleton_for_big_python():
    big = BIG_MODULE * 40
    context = context_for_file(big, "python")

    assert context.startswith("# [skeleton:")
    assert "(truncated)" not in context


def test_context_for_file_falls_back_to_truncation_for_other_languages():
    big = "body { color: red; }\n" * 400
    context = context_for_file(big, "css")

    assert context.endswith("(truncated)")
    assert not context.startswith("# [skeleton:")
