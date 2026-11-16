"""Tests for the Markdown renderer (markdown-it-py -> Rich)."""

from rich.console import Console, Group

from prosaic.core.markdown_render import render_markdown


def _text(markdown: str, *, light: bool = True, width: int = 100) -> str:
    console = Console(width=width, record=True)
    console.print(render_markdown(markdown, light=light))
    return console.export_text()


def test_returns_group():
    assert isinstance(render_markdown("# Hi"), Group)


def test_headings():
    out = _text("# One\n\n## Two\n\n### Three")
    assert "One" in out and "Two" in out and "Three" in out


def test_inline():
    out = _text("Some **bold**, *italic*, `code`, ~~gone~~ and [link](http://x).")
    assert "bold" in out and "italic" in out and "code" in out and "link" in out


def test_task_lists():
    out = _text("- [x] done\n- [ ] todo")
    assert "☑" in out and "done" in out and "☐" in out and "todo" in out


def test_ordered_and_bulleted():
    out = _text("1. first\n2. second\n\n- a\n- b")
    assert "first" in out and "second" in out and "a" in out and "b" in out


def test_blockquote():
    out = _text("> quoted text")
    assert "quoted text" in out


def test_table():
    out = _text("| A | B |\n|-|-|\n| 1 | 2 |", width=40)
    assert "A" in out and "B" in out and "1" in out and "2" in out


def test_code_fence():
    out = _text("```python\nprint('hi')\n```")
    assert "print('hi')" in out


def test_horizontal_rule():
    out = _text("a\n\n---\n\nb")
    assert "a" in out and "b" in out


def test_empty_returns_group():
    assert isinstance(render_markdown(""), Group)


def test_light_and_dark_produce_output():
    assert "One" in _text("# One", light=True)
    assert "One" in _text("# One", light=False)
