"""Tests for MarkdownView: live updates preserve scroll position."""

import asyncio

from textual.app import App
from textual.widgets import Static

from prosaic.widgets.markdown_view import MarkdownView

DOC = "\n\n".join(f"Paragraph {i} of the document, with a little extra so it wraps." for i in range(60))


class _PreviewApp(App):
    def compose(self):
        yield MarkdownView(DOC, light=True)


def test_update_preserves_scroll():
    async def run():
        app = _PreviewApp()
        async with app.run_test(size=(80, 20)) as pilot:
            view = app.query_one(MarkdownView)
            await pilot.pause()
            view.scroll_to(y=10, animate=False, immediate=True)
            await pilot.pause()
            before = view.scroll_offset.y
            assert before > 0

            view.set_text(DOC + "\n" + "\n".join(f"extra {i}" for i in range(30)))
            await pilot.pause()
            assert view.scroll_offset.y == before

            view.set_theme(False)
            await pilot.pause()
            assert view.scroll_offset.y == before

    asyncio.run(run())


def test_empty_shows_placeholder():
    async def run():
        app = _PreviewApp()
        async with app.run_test() as pilot:
            view = app.query_one(MarkdownView)
            view.set_text("")
            await pilot.pause()
            from rich.console import Group

            assert isinstance(view._content(), Group)
            assert view.query_one(Static) is not None

    asyncio.run(run())
