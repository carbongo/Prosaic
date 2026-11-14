"""File tree widget for workspace navigation."""

import os
from collections.abc import Iterable
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DirectoryTree, Static


class FilteredDirectoryTree(DirectoryTree, inherit_bindings=False):
    """Directory tree with emoji-free labels and hidden-file filtering."""

    HIDDEN_FILES = {".git", ".DS_Store", "metrics.json", "__pycache__"}

    BINDINGS = [
        Binding("enter", "select_cursor", "open"),
        Binding("space", "toggle_node", "expand"),
        Binding("delete,backspace", "delete_file", "delete"),
        Binding("shift+left", "cursor_parent", "cursor to parent", show=False),
        Binding("shift+right", "cursor_parent_next_sibling", "cursor to next ancestor", show=False),
        Binding("shift+up", "cursor_previous_sibling", "cursor to previous sibling", show=False),
        Binding("shift+down", "cursor_next_sibling", "cursor to next sibling", show=False),
        Binding("shift+space", "toggle_expand_all", "expand or collapse all", show=False),
        Binding("up", "cursor_up", "cursor up", show=False),
        Binding("down", "cursor_down", "cursor down", show=False),
    ]

    class DeleteRequested(Message):
        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    def action_delete_file(self) -> None:
        node = self.cursor_node
        if node is None or node.data is None:
            return
        path = node.data.path
        if path.is_file():
            self.post_message(self.DeleteRequested(path))

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.name not in self.HIDDEN_FILES and not path.name.startswith(".")
        ]

    def render_label(self, node, base_style, style):
        label = (
            node._label.plain if hasattr(node._label, "plain") else str(node._label)
        )
        if node._allow_expand:
            prefix = "▾ " if node.is_expanded else "▸ "
        else:
            prefix = "  "
        return Text.assemble((prefix, base_style), (label, style))


class FileTree(Vertical):
    """File tree panel for the workspace."""

    class FileSelected(Message):
        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    def __init__(self, root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.root = root

    def compose(self):
        yield Static("files", id="tree-title", classes="panel-title")
        yield FilteredDirectoryTree(self.root, id="directory-tree")

    def _snapshot(self) -> frozenset[str]:
        """Every visible path under the root."""
        hidden = FilteredDirectoryTree.HIDDEN_FILES
        found: set[str] = set()
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in hidden and not d.startswith(".")]
            for name in dirs:
                found.add(os.path.join(base, name))
            for name in files:
                if name not in hidden and not name.startswith("."):
                    found.add(os.path.join(base, name))
        return frozenset(found)

    def refresh_from_disk(self) -> None:
        """Reload the tree when files appeared or vanished. Blocking: call off the UI thread."""
        snapshot = self._snapshot()
        previous = getattr(self, "_last_snapshot", None)
        self._last_snapshot = snapshot
        if previous is not None and snapshot != previous:
            self.app.call_from_thread(
                self.query_one("#directory-tree", FilteredDirectoryTree).reload
            )

    def expand_path(self, path: Path) -> None:
        """Expand directories leading to the given path."""
        tree = self.query_one("#directory-tree", FilteredDirectoryTree)
        
        try:
            rel_parts = path.relative_to(self.root).parts
        except ValueError:
            return
        
        dirs_to_expand: list[Path] = []
        current = self.root
        for part in rel_parts:
            current = current / part
            if current.is_dir():
                dirs_to_expand.append(current)
        
        self._pending_expands = dirs_to_expand
        self._do_expand_step(tree.root)
    
    def _do_expand_step(self, node) -> None:
        """Expand one level, then schedule next."""
        if not hasattr(self, "_pending_expands") or not self._pending_expands:
            return
        
        target = self._pending_expands[0]
        
        if node.is_collapsed:
            node.expand()
            self.set_timer(0.05, lambda: self._do_expand_step(node))
            return
        
        for child in node.children:
            if hasattr(child, "data") and child.data and hasattr(child.data, "path"):
                if child.data.path == target:
                    self._pending_expands.pop(0)
                    if self._pending_expands:
                        self._do_expand_step(child)
                    else:
                        child.expand()
                    return

    def on_directory_tree_file_selected(
        self,
        event: DirectoryTree.FileSelected,
    ) -> None:
        self.post_message(self.FileSelected(event.path))
