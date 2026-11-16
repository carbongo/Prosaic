"""Render Markdown to Rich renderables in Prosaic's warm, minimal aesthetic.

Used by the reader view and the live preview pane. Parsing is delegated to
markdown-it-py (GFM: tables, strikethrough, links, emphasis); rendering to Rich
keeps the look consistent with the editor's inline highlighting.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from prosaic.core.markdown import strip_frontmatter

# One parser for the whole app: GFM-ish (tables, emphasis, strikethrough, links).
# Task lists are not in the core, so they are detected manually in list items.
_PARSER = MarkdownIt("default")

_TASK_RE = re.compile(r"^\[([ xX])\]\s+")


class MdTheme:
    """Rich styles for one colour scheme, mirroring the editor's syntax palette."""

    def __init__(self, body, heading, code, code_block, link, quote, marker,
                 border, checkbox, panel_title, table_row):
        self.body = body
        self.heading = heading
        self.code = code
        self.code_block = code_block
        self.link = link
        self.quote = quote
        self.marker = marker
        self.border = border
        self.checkbox = checkbox
        self.panel_title = panel_title
        self.table_row = table_row

    @classmethod
    def light(cls) -> "MdTheme":
        return cls(
            body=Style(color="#5a3d35"),
            heading=[
                Style(color="#703327", bold=True),
                Style(color="#8a4d3f", bold=True),
                Style(color="#5a3d35", bold=True),
                Style(color="#8a6d60", bold=True),
                Style(color="#a89080", bold=True),
                Style(color="#a89080"),
            ],
            code=Style(color="#715e12", bgcolor="#f0ece0"),
            code_block=Style(color="#715e12"),
            link=Style(color="#4a6da0", underline=True),
            quote=Style(color="#8a6d60", italic=True),
            marker=Style(color="#8a6d60"),
            border=Style(color="#c8c8c4"),
            checkbox=Style(color="#715e12"),
            panel_title=Style(color="#703327", bold=True),
            table_row=Style(color="#c8c8c4"),
        )

    @classmethod
    def dark(cls) -> "MdTheme":
        return cls(
            body=Style(color="#e8d5c4"),
            heading=[
                Style(color="#dcae91", bold=True),
                Style(color="#c8b5a4", bold=True),
                Style(color="#e8d5c4", bold=True),
                Style(color="#8a7a6a", bold=True),
                Style(color="#6a5a4a", bold=True),
                Style(color="#6a5a4a"),
            ],
            code=Style(color="#c9a86c", bgcolor="#2a2520"),
            code_block=Style(color="#c9a86c"),
            link=Style(color="#7aa2d0", underline=True),
            quote=Style(color="#8a7a6a", italic=True),
            marker=Style(color="#8a7a6a"),
            border=Style(color="#4a4030"),
            checkbox=Style(color="#c9a86c"),
            panel_title=Style(color="#dcae91", bold=True),
            table_row=Style(color="#4a4030"),
        )


def get_theme(light: bool = True) -> MdTheme:
    return MdTheme.light() if light else MdTheme.dark()


def _style_for(flags: dict[str, bool], theme: MdTheme) -> Style:
    style = theme.link if flags.get("link") else theme.body
    if flags.get("bold"):
        style += Style(bold=True)
    if flags.get("em"):
        style += Style(italic=True)
    if flags.get("strike"):
        style += Style(strike=True)
    return style


def _render_inline(inline, theme: MdTheme, in_list: bool = False) -> Text:
    """Turn an inline token (and its children) into a single Rich Text."""
    text = Text()
    flags: dict[str, bool] = {}
    first_text = True
    for child in inline.children or []:
        ct = child.type
        if ct == "text":
            s = child.content
            if first_text and in_list:
                m = _TASK_RE.match(s)
                if m:
                    # Strip the task marker; the checkbox becomes the list marker.
                    s = s[m.end():]
            text.append(s.replace("\n", " "), _style_for(flags, theme))
        elif ct == "strong_open":
            flags["bold"] = True
        elif ct == "strong_close":
            flags.pop("bold", None)
        elif ct == "em_open":
            flags["em"] = True
        elif ct == "em_close":
            flags.pop("em", None)
        elif ct == "s_open":
            flags["strike"] = True
        elif ct == "s_close":
            flags.pop("strike", None)
        elif ct == "code_inline":
            text.append(child.content, theme.code)
        elif ct == "link_open":
            flags["link"] = True
        elif ct == "link_close":
            flags.pop("link", None)
        elif ct == "softbreak":
            text.append(" ", _style_for(flags, theme))
        elif ct == "hardbreak":
            text.append("\n", _style_for(flags, theme))
        # image / image_open / image_close: notes carry no displayable images.
        first_text = False
    return text


def _prefix_item(text: Text, marker: str, indent: int, theme: MdTheme) -> Text:
    """Prefix a list marker (and indent); continuation lines are left as-is."""
    color = theme.checkbox if marker in ("☑", "☐") else theme.marker
    prefix = Text(" " * indent + marker + " ", color)
    return prefix + text


def _task_checkbox(tokens, start: int) -> str | None:
    """Return the checkbox glyph if the list item at `start` is a task item."""
    j = start + 1
    while j < len(tokens) and tokens[j].type != "list_item_close":
        inline = tokens[j]
        if inline.type == "inline" and inline.children:
            first = inline.children[0]
            if first.type == "text":
                m = _TASK_RE.match(first.content)
                if m:
                    return "☑" if m.group(1) in "xX" else "☐"
            return None
        j += 1
    return None


def _wrap_quote(text: Text, depth: int, theme: MdTheme) -> Text:
    result = Text("│ " * depth, theme.marker)
    result += text
    return result


def _make_table(rows: list[list[Text]], theme: MdTheme) -> RenderableType:
    if not rows:
        return Text("")
    has_header = len(rows) > 1
    header = rows[0] if has_header else [Text("") for _ in rows[0]]
    table = Table(
        expand=False,
        padding=(0, 1),
        border_style=theme.table_row,
        header_style=theme.heading[2] if has_header else None,
    )
    for h in header:
        table.add_column(h)
    body = rows[1:] if has_header else rows
    for r in body:
        table.add_row(*r)
    return table


class _BlockRenderer:
    """Walks markdown-it-py's flat token stream into a list of Rich blocks."""

    def __init__(self, theme: MdTheme) -> None:
        self.theme = theme
        self.blocks: list[RenderableType] = []
        self.list_stack: list[list] = []
        self.item_stack: list[tuple[str, int]] = []
        self.quote_depth = 0
        self.table_rows: list[list[Text]] = []

    def _emit(self, block: RenderableType) -> None:
        self.blocks.append(block)
        self.blocks.append(Text(""))

    def render(self, tokens) -> list[RenderableType]:
        i, n = 0, len(tokens)
        while i < n:
            tok = tokens[i]
            t = tok.type

            if t in ("bullet_list_open", "ordered_list_open"):
                kind = "bullet" if t == "bullet_list_open" else "ordered"
                self.list_stack.append([kind, 0, 2 + 2 * len(self.list_stack)])
            elif t in ("bullet_list_close", "ordered_list_close"):
                self.list_stack.pop()
            elif t == "list_item_open":
                top = self.list_stack[-1]
                top[1] += 1
                indent = top[2]
                checkbox = _task_checkbox(tokens, i)
                if checkbox:
                    marker = checkbox
                else:
                    marker = "•" if top[0] == "bullet" else f"{top[1]}."
                self.item_stack.append((marker, indent))
            elif t == "list_item_close":
                self.item_stack.pop()
            elif t == "blockquote_open":
                self.quote_depth += 1
            elif t == "blockquote_close":
                self.quote_depth -= 1
            elif t == "heading_open":
                level = int(tok.tag[1])
                out = _render_inline(tokens[i + 1], self.theme)
                out.stylize(self.theme.heading[level - 1])
                if level == 1:
                    self.blocks.append(out)
                    self.blocks.append(Rule(style=self.theme.border))
                    self.blocks.append(Text(""))
                else:
                    self._emit(out)
                i += 2
            elif t == "paragraph_open":
                out = _render_inline(tokens[i + 1], self.theme, in_list=bool(self.item_stack))
                if self.quote_depth:
                    out = _wrap_quote(out, self.quote_depth, self.theme)
                elif self.item_stack:
                    out = _prefix_item(out, *self.item_stack[-1], self.theme)
                self._emit(out)
                i += 2
            elif t == "fence":
                lang = tok.info.strip()
                code = Text(tok.content.rstrip("\n"), style=self.theme.code_block)
                title = f" {lang} " if lang else None
                self._emit(Panel(
                    code, title=title, title_align="left",
                    border_style=self.theme.border, padding=(0, 1),
                ))
            elif t == "hr":
                self._emit(Rule(style=self.theme.border))
            elif t == "table_open":
                self.table_rows = []
            elif t == "tr_open":
                self.table_rows.append([])
            elif t in ("td_open", "th_open"):
                cell = _render_inline(tokens[i + 1], self.theme)
                if t == "th_open":
                    cell.stylize("bold")
                self.table_rows[-1].append(cell)
                i += 2
            elif t == "table_close":
                self._emit(_make_table(self.table_rows, self.theme))
            elif t == "inline":
                self._emit(_render_inline(tok, self.theme, in_list=bool(self.item_stack)))
            else:
                i += 1
                continue
            i += 1

        # Collapse runs of blank spacers and trim the ends.
        collapsed: list[RenderableType] = []
        prev_blank = True  # trim leading blanks
        for block in self.blocks:
            blank = isinstance(block, Text) and not block.plain
            if blank and prev_blank:
                continue
            collapsed.append(block)
            prev_blank = blank
        return collapsed


def render_markdown(text: str, *, light: bool = True) -> Group:
    """Render markdown text to a Rich Group, ready for a scrollable widget."""
    blocks = _BlockRenderer(get_theme(light)).render(_PARSER.parse(strip_frontmatter(text)))
    return Group(*blocks)
