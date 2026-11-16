"""Tests for MarkdownView, the rendered pane behind reader mode and live preview."""

import asyncio

from textual.app import App
from textual.widgets._markdown import MarkdownBullet, MarkdownFence, MarkdownHeader, MarkdownTable

from prosaic.widgets.markdown_view import MarkdownView

DOC = "---\ntitle: x\n---\n\n" + "\n\n".join(
    f"## Section {i}\n\nParagraph {i} of the document, with a little extra so it wraps." for i in range(60)
)


class _PreviewApp(App):
    def __init__(self, text: str = DOC) -> None:
        super().__init__()
        self._text = text

    def compose(self):
        yield MarkdownView(self._text)


def _run(text, check):
    async def run():
        app = _PreviewApp(text)
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            await check(app.query_one(MarkdownView), pilot)

    asyncio.run(run())


def _plain(view) -> str:
    return "\n".join(str(block._content.plain) for block in view.query("MarkdownBlock"))


def test_update_preserves_scroll():
    async def check(view, pilot):
        view.scroll_to(y=10, animate=False, immediate=True)
        await pilot.pause()
        before = view.scroll_offset.y
        assert before > 0
        await view.set_text(DOC + "\n\nextra")
        await pilot.pause()
        assert view.scroll_offset.y == before

    _run(DOC, check)


def test_frontmatter_hidden():
    async def check(view, pilot):
        assert "title: x" not in _plain(view)

    _run(DOC, check)


def test_blocks():
    text = "# T\n\n- a\n  - b\n\n```python\nif x:\n    y\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"

    async def check(view, pilot):
        assert len(view.query(MarkdownHeader)) == 1
        assert len(view.query(MarkdownBullet)) == 2
        assert view.query_one(MarkdownFence).code.rstrip() == "if x:\n    y"
        assert len(view.query(MarkdownTable)) == 1

    _run(text, check)


def test_task_lists():
    async def check(view, pilot):
        plain = _plain(view)
        assert "☑ done" in plain and "☐ todo" in plain and "[x]" not in plain

    _run("- [x] done\n- [ ] todo\n", check)


def test_scroll_to_line_follows_source():
    async def check(view, pilot):
        view.scroll_to_line(DOC.count("\n"))
        await pilot.pause()
        assert view.scroll_offset.y == view.max_scroll_y > 0
        view.scroll_to_line(0)
        await pilot.pause()
        assert view.scroll_offset.y == 0

    _run(DOC, check)


def test_scroll_to_heading():
    async def check(view, pilot):
        view.scroll_to_heading(30)
        await pilot.pause()
        header = view.query(MarkdownHeader)[30]
        assert 0 <= header.region.y <= header.styles.margin.top

    _run(DOC, check)
