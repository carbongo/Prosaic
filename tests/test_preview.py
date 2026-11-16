"""Tests for reader mode and the live preview on the editor screen."""

from textual.widgets import TextArea
from textual.widgets._markdown import MarkdownHeader

from prosaic.themes import PROSAIC_LIGHT_CSS
from prosaic.widgets import OutlinePanel
from tests.test_live_reload import _Host as _BareHost, run_async, workspace  # noqa: F401

DOC = "\n\n".join(f"## Section {i}\n\nParagraph {i}." for i in range(40))


class _Host(_BareHost):
    CSS = PROSAIC_LIGHT_CSS


def _plain(screen) -> str:
    return "\n".join(block._content.plain for block in screen.preview.query("MarkdownBlock"))


@run_async
async def test_f8_toggles_live_preview_from_the_editor(workspace):
    note = workspace / "note.md"
    note.write_text("# Title\n", encoding="utf-8")
    app = _Host(workspace, note)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause(0.2)
        screen = app.screen
        editor = screen.query_one("#editor", TextArea)
        assert editor.has_focus and not screen.preview.display

        await pilot.press("f8")
        await pilot.pause(0.2)
        assert screen.preview.display and editor.display
        assert "Title" in _plain(screen)

        await pilot.press("end", "!")
        await pilot.pause(0.6)
        assert "Title!" in _plain(screen)

        await pilot.press("f8")
        await pilot.pause()
        assert not screen.preview.display


@run_async
async def test_preview_follows_the_cursor(workspace):
    note = workspace / "note.md"
    note.write_text(DOC, encoding="utf-8")
    app = _Host(workspace, note)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause(0.2)
        screen = app.screen
        await pilot.press("f8")
        await pilot.pause(0.3)
        assert screen.preview.scroll_offset.y == 0

        editor = screen.query_one("#editor", TextArea)
        editor.move_cursor((editor.document.line_count - 1, 0))
        await pilot.pause(0.3)
        assert screen.preview.scroll_offset.y == screen.preview.max_scroll_y > 0


@run_async
async def test_reader_mode_renders_and_outline_jumps(workspace):
    note = workspace / "note.md"
    note.write_text(DOC, encoding="utf-8")
    app = _Host(workspace, note)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause(0.2)
        screen = app.screen
        await pilot.press("f6")
        await pilot.pause(0.3)
        editor = screen.query_one("#editor", TextArea)
        assert screen.preview.display and screen.preview.has_focus
        assert not editor.parent.display

        screen.on_outline_panel_heading_selected(OutlinePanel.HeadingSelected(line=20 * 4 + 1))
        await pilot.pause(0.2)
        header = screen.preview.query(MarkdownHeader)[20]
        assert 0 <= header.region.y - screen.preview.content_region.y <= header.styles.margin.top

        await pilot.press("f6")
        await pilot.pause(0.2)
        assert editor.parent.display and editor.has_focus and not screen.preview.display
