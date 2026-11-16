"""A scrollable pane that renders Markdown to Rich for reading and previewing.

The view is a `VerticalScroll` around a single `Static`. Re-rendering updates the
`Static`'s renderable in place, which keeps the scroller's offset — so a live
preview stays put while you type. Colour follows the editor's light/dark theme.
"""

from __future__ import annotations

from rich.console import Group
from rich.text import Text

from textual.containers import VerticalScroll
from textual.widgets import Static

from prosaic.core.markdown_render import render_markdown

_PLACEHOLDER = Text("Nothing to preview yet.", style="dim")


class MarkdownView(VerticalScroll):
    """Scrollable rendered Markdown; updates live without losing scroll position."""

    DEFAULT_CSS = """
    MarkdownView {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }
    MarkdownView > Static {
        width: 100%;
    }
    """

    def __init__(self, text: str = "", *, light: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._text = text
        self._light = light
        self._inner: Static | None = None

    def compose(self):
        self._inner = Static(self._content(), id="md-content", classes="md-content")
        yield self._inner

    def _content(self):
        """The Rich renderable shown in the pane (a placeholder when empty)."""
        if not self._text.strip():
            return Group(_PLACEHOLDER)
        return render_markdown(self._text, light=self._light)

    def _update(self) -> None:
        if self._inner is not None:
            self._inner.update(self._content())

    def set_text(self, text: str, *, light: bool | None = None) -> None:
        """Set the source and re-render, preserving the scroll offset."""
        if light is not None:
            self._light = light
        self._text = text
        self._update()

    def set_theme(self, light: bool) -> None:
        """Re-render in the given colour scheme, preserving the scroll offset."""
        if light == self._light:
            return
        self._light = light
        self._update()
