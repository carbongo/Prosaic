"""A scrollable pane of rendered Markdown, for reader mode and the live preview."""

from __future__ import annotations

import asyncio
import re

from markdown_it import MarkdownIt
from textual.containers import VerticalScroll
from textual.widgets import Markdown
from textual.widgets._markdown import MarkdownHeader

from prosaic.core.markdown import strip_frontmatter

_TASK_RE = re.compile(r"^\[([ xX])\] ")


def _task_lists(state) -> None:
    """Show GFM task list markers as checkboxes."""
    tokens = state.tokens
    for i in range(2, len(tokens)):
        if tokens[i].type != "inline" or tokens[i - 2].type != "list_item_open":
            continue
        children = tokens[i].children
        if children and children[0].type == "text":
            children[0].content = _TASK_RE.sub(
                lambda m: "☐ " if m.group(1) == " " else "☑ ", children[0].content
            )


def _parser() -> MarkdownIt:
    parser = MarkdownIt("gfm-like")
    parser.core.ruler.push("task_lists", _task_lists)
    return parser


def _split(text: str) -> list[tuple[str, int]]:
    """Cut a document into its top-level blocks: (source, first line) each."""
    lines = text.split("\n")
    return [
        ("\n".join(lines[token.map[0] : token.map[1]]), token.map[0])
        for token in _parser().parse(text)
        if token.level == 0 and token.map and token.nesting >= 0
    ]


class MarkdownView(VerticalScroll):
    """Rendered Markdown, one Textual `Markdown` widget per top-level block.

    A new text re-renders only the blocks that changed, so typing in a long
    document stays cheap and the scroll offset holds.
    """

    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._text = text
        self._shown = ""
        self._rendering = False
        self._line_offset = 0
        self._chunks: list[tuple[str, int]] = []
        self._widgets: list[Markdown] = []

    async def on_mount(self) -> None:
        await self.set_text(self._text)

    async def set_text(self, text: str) -> None:
        """Render `text`; a call during a render only queues its text."""
        self._text = text
        if self._rendering or not self.is_attached:
            return
        self._rendering = True
        try:
            while self._shown != self._text:
                await self._render_text(self._text)
        finally:
            self._rendering = False

    async def _render_text(self, text: str) -> None:
        body = strip_frontmatter(text)
        self._line_offset = text.count("\n", 0, len(text) - len(body))
        chunks = await asyncio.to_thread(_split, body)
        old, new = [c[0] for c in self._chunks], [c[0] for c in chunks]
        head = 0
        while head < min(len(old), len(new)) and old[head] == new[head]:
            head += 1
        tail = 0
        while tail < min(len(old), len(new)) - head and old[-1 - tail] == new[-1 - tail]:
            tail += 1
        stale = self._widgets[head : len(old) - tail]
        fresh = [Markdown(source, parser_factory=_parser) for source in new[head : len(new) - tail]]
        anchor = self._widgets[len(old) - tail] if tail else None
        with self.app.batch_update():
            if stale:
                await self.remove_children(stale)
            if fresh:
                await self.mount_all(fresh, before=anchor)
        self._widgets[head : len(old) - tail] = fresh
        self._chunks = chunks
        self._shown = text

    def scroll_to_line(self, line: int) -> None:
        """Bring the block rendered from source line `line` (0-based) into view."""
        line -= self._line_offset
        target = None
        for widget, (_, start) in zip(self._widgets, self._chunks):
            if start > line:
                break
            target = widget
        if target is None:
            self.scroll_home(animate=False)
        else:
            self.call_after_refresh(self.scroll_to_widget, target, animate=False)

    def scroll_to_heading(self, index: int) -> None:
        """Scroll to the document's `index`-th heading."""
        headers = self.query(MarkdownHeader)
        if 0 <= index < len(headers):
            self.scroll_to_widget(headers[index], top=True, animate=False)
