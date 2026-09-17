"""Knowledge cards: one compact card per module for picking a starting point."""

from __future__ import annotations

from repowiki.core.graph import DependencyGraph
from repowiki.core.models import (
    Concept,
    FileDoc,
    FileInfo,
    ModuleDoc,
    ProjectContext,
    ProjectOverview,
    Relationship,
    Symbol,
    WikiData,
)
from repowiki.core.wiki_builder import WikiBuilder
from repowiki.export.markdown import export_markdown


def _project() -> ProjectContext:
    return ProjectContext(
        name="demo",
        root="/tmp/demo",
        files=[
            FileInfo(
                path="alpha/core.py",
                size=30,
                language="python",
                lines=2,
                content="import beta.runner\nX = 1\n",
            ),
            FileInfo(
                path="beta/runner.py",
                size=10,
                language="python",
                lines=2,
                content="Y = 2\n",
            ),
        ],
    )


def _graph() -> DependencyGraph:
    return DependencyGraph.build_from_project(_project())


def _wiki_data() -> WikiData:
    return WikiData(
        overview=ProjectOverview(name="demo", one_liner="demo project"),
        modules=[
            ModuleDoc(
                name="alpha",
                purpose="alpha package",
                files=[
                    FileDoc(
                        path="alpha/core.py",
                        purpose="core alpha pieces",
                        key_symbols=[
                            Symbol(name="AlphaEngine", kind="class"),
                            Symbol(name="start", kind="method", description="boots alpha"),
                        ],
                    ),
                ],
                key_concepts=[Concept(name="Engine lifecycle", explanation="boot to stop")],
                relationships=[Relationship(source="alpha", target="beta", description="drives")],
            ),
            ModuleDoc(
                name="beta",
                purpose="beta package",
                files=[
                    FileDoc(
                        path="beta/runner.py",
                        purpose="runs beta",
                        key_symbols=[Symbol(name="run_beta", kind="function")],
                    ),
                ],
            ),
        ],
    )


def _build(wiki_data: WikiData | None = None):
    return WikiBuilder().build(_project(), wiki_data or _wiki_data(), _graph())


def test_cards_page_lists_one_card_per_module() -> None:
    wiki = _build()
    cards = wiki.get_page("cards")
    assert cards is not None
    assert cards.title == "Knowledge Cards"
    assert "### `alpha`" in cards.content
    assert "### `beta`" in cards.content
    assert "> alpha package" in cards.content
    assert "1 files" in cards.content
    assert "`AlphaEngine`" in cards.content
    assert "concepts Engine lifecycle" in cards.content
    assert "`alpha` → `beta`" in cards.content
    # every card points at its full module page
    assert "[Open the full page](modules/alpha.md)" in cards.content


def test_card_shows_the_entry_file_from_the_dependency_graph() -> None:
    wiki = _build()
    cards = wiki.get_page("cards")
    assert cards is not None
    # alpha/core.py imports beta/runner.py, so it is the way in for alpha
    assert "Entry: [`alpha/core.py`](modules/alpha.md)" in cards.content
    # beta has no entry-point file, so its card omits the line entirely
    beta_section = cards.content.split("### `beta`", 1)[1]
    assert "Entry:" not in beta_section


def test_cards_page_sits_between_architecture_and_modules_in_sidebar() -> None:
    wiki = _build()
    titles = [item.title for item in wiki.sidebar]
    assert "Knowledge Cards" in titles
    assert titles.index("Knowledge Cards") < titles.index("Modules")


def test_empty_wiki_gets_no_cards_page() -> None:
    wiki = _build(WikiData(overview=ProjectOverview(name="demo")))
    assert wiki.get_page("cards") is None
    assert "Knowledge Cards" not in [item.title for item in wiki.sidebar]


def test_card_symbols_cross_link_to_the_module_page() -> None:
    wiki = _build()
    cards = wiki.get_page("cards")
    assert cards is not None
    # the shared cross-linker turns bare symbol names into module-page links
    assert "[`AlphaEngine`](modules/alpha.md)" in cards.content


def test_markdown_export_writes_cards_md(tmp_path) -> None:
    wiki = _build()
    export_markdown(wiki, tmp_path, page_inputs={})
    out = tmp_path / "cards.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# Knowledge Cards" in text
    assert "### `beta`" in text
