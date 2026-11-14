"""Tests for picking up changes made outside the app."""

import asyncio
import functools
import os

import pytest
from textual.app import App
from textual.widgets import TextArea

from prosaic.core.book import get_chapters
from prosaic.core.metrics import MetricsTracker
from prosaic.screens.editor import EditorScreen
from prosaic.utils import CONFLICT_MARKER
from prosaic.widgets import FileTree


def run_async(test):
    """Run a coroutine test without an async pytest plugin."""

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        asyncio.run(test(*args, **kwargs))

    return wrapper


class _Host(App):
    def __init__(self, workspace, initial_file):
        super().__init__()
        self._workspace = workspace
        self._initial_file = initial_file

    def on_mount(self):
        self.push_screen(
            EditorScreen(MetricsTracker(self._workspace), initial_file=self._initial_file)
        )


@pytest.fixture
def workspace(tmp_workspace, write_config):
    write_config(
        {
            "app_version": "1.5.2",
            "setup_complete": True,
            "active_profile": "default",
            "profiles": {"default": {"archive_dir": str(tmp_workspace)}},
        }
    )
    return tmp_workspace.resolve()


def _write_outside(path, text):
    """Write as another program would, with a clearly newer mtime."""
    path.write_text(text, encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))


def _tree_labels(screen):
    tree = screen.query_one("#directory-tree")
    return {str(child.label) for child in tree.root.children}


@run_async
async def test_unedited_file_reloads(workspace):
    note = workspace / "note.md"
    note.write_text("one\ntwo\nthree\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause()
        editor = pilot.app.screen.query_one("#editor", TextArea)
        editor.move_cursor((1, 2))

        _write_outside(note, "one\ntwo\nthree\nfour\n")
        await pilot.pause(2.5)

        assert editor.text == "one\ntwo\nthree\nfour\n"
        assert editor.cursor_location == (1, 2)
        assert pilot.app.screen.modified is False


@run_async
async def test_edited_file_keeps_buffer_and_conflict_copy(workspace):
    note = workspace / "note.md"
    note.write_text("mine\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        editor = screen.query_one("#editor", TextArea)
        editor.insert("typed here ")
        await pilot.pause()
        assert screen.modified is True

        _write_outside(note, "theirs\n")
        screen._save_file(silent=True)

        assert note.read_text(encoding="utf-8") == editor.text
        assert "typed here" in editor.text
        copies = [p for p in workspace.iterdir() if CONFLICT_MARKER in p.name]
        assert len(copies) == 1
        assert copies[0].read_text(encoding="utf-8") == "theirs\n"


@run_async
async def test_own_save_is_not_a_reload(workspace):
    note = workspace / "note.md"
    note.write_text("text\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause()
        screen = pilot.app.screen
        editor = screen.query_one("#editor", TextArea)
        editor.insert("more ")
        await pilot.pause()
        screen._save_file(silent=True)
        editor.insert("again ")
        await pilot.pause(2.5)

        assert editor.text == "more again text\n"
        assert not [p for p in workspace.iterdir() if CONFLICT_MARKER in p.name]


@run_async
async def test_tree_follows_added_and_removed_files(workspace):
    note = workspace / "note.md"
    note.write_text("text\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause(2.5)
        screen = pilot.app.screen
        assert _tree_labels(screen) == {"note.md"}

        (workspace / "new.md").write_text("new\n", encoding="utf-8")
        (workspace / "pieces").mkdir()
        await pilot.pause(3)
        assert _tree_labels(screen) == {"note.md", "new.md", "pieces"}

        (workspace / "new.md").unlink()
        await pilot.pause(3)
        assert _tree_labels(screen) == {"note.md", "pieces"}


def test_conflict_copies_stay_out_of_the_manuscript(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "01-a.md").write_text("## A\n")
    (chapters / f"01-a{CONFLICT_MARKER}20260101-000000.md").write_text("## A\n")
    assert [p.name for p in get_chapters(tmp_path)] == ["01-a.md"]


def test_metrics_keep_counts_written_elsewhere(tmp_path):
    here = MetricsTracker(tmp_path)
    there = MetricsTracker(tmp_path)
    there.record_save(10, tmp_path / "a.md")
    here.record_save(5, tmp_path / "b.md")
    today = MetricsTracker(tmp_path).get_today_stats()
    assert today["saves"] == 2
    assert today["words"] == 15


@run_async
async def test_delete_from_tree_asks_then_deletes(workspace):
    note = workspace / "note.md"
    other = workspace / "other.md"
    note.write_text("text\n", encoding="utf-8")
    other.write_text("other\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause(0.5)
        screen = pilot.app.screen
        tree = screen.query_one("#directory-tree")
        tree.focus()
        target = next(c for c in tree.root.children if str(c.label) == "other.md")
        tree.move_cursor(target)
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert other.exists()

        await pilot.press("backspace")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause(0.5)
        assert not other.exists()
        assert note.exists()
        assert _tree_labels(screen) == {"note.md"}


@run_async
async def test_deleting_the_open_file_empties_the_editor(workspace):
    note = workspace / "note.md"
    note.write_text("text\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause(0.5)
        screen = pilot.app.screen
        editor = screen.query_one("#editor", TextArea)
        editor.insert("unsaved ")
        await pilot.pause()
        screen._delete_file(note)
        await pilot.pause(0.5)

        assert editor.text == ""
        assert screen.current_file is None
        screen._save_file(silent=True)
        assert not note.exists()


def test_deleting_a_chapter_updates_the_book(workspace, write_config):
    book = workspace / "books" / "b"
    chapters = book / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "01-a.md").write_text("## A\n\nalpha\n")
    (chapters / "02-b.md").write_text("## B\n\nbeta\n")
    (book / "chapters.md").write_text("01-a.md\n02-b.md\n")

    @run_async
    async def scenario():
        async with _Host(workspace, chapters / "01-a.md").run_test() as pilot:
            await pilot.pause(0.5)
            pilot.app.screen._delete_file(chapters / "02-b.md")
            await pilot.pause(0.5)

    scenario()
    assert (book / "chapters.md").read_text() == "01-a.md\n"
    assert "beta" not in (book / "manuscript.md").read_text()


@run_async
async def test_ctrl_f_toggles_focus_mode(workspace):
    note = workspace / "note.md"
    note.write_text("one two\n", encoding="utf-8")
    async with _Host(workspace, note).run_test() as pilot:
        await pilot.pause(0.5)
        screen = pilot.app.screen
        await pilot.press("ctrl+f")
        await pilot.pause()
        assert screen.focus_mode is True
        assert screen.query_one("#editor", TextArea).text == "one two\n"
        await pilot.press("ctrl+f")
        await pilot.pause()
        assert screen.focus_mode is False
