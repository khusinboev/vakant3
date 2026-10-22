"""HTML from sources -> safe plain text.

The output never contains markup: every tag is dropped, entities are decoded,
``<script>``/``<style>`` bodies are discarded and control characters removed.
It is still *text*, so whoever puts it into a Telegram/HTML message must
``html.escape`` it like any other user-facing string.
"""
from __future__ import annotations

import re
import unicodedata
from html import unescape
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "tr", "table", "section", "article", "blockquote", "pre", "hr",
}
_DROP_TAGS = {"script", "style", "noscript", "template", "iframe", "object", "svg", "head"}
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩﻿]")
_SPACES_RE = re.compile(r"[ \t\r\f\v\xa0]+")
_MANY_NL_RE = re.compile(r"\n{3,}")
_TAG_LEFTOVER_RE = re.compile(r"<[^>]*>")

DESCRIPTION_MAX = 20_000


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag, attrs):  # noqa: ARG002 - attributes are never kept
        if tag in _DROP_TAGS:
            self._drop_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "li" and not self._drop_depth:
            self.parts.append("• ")

    def handle_startendtag(self, tag, attrs):  # noqa: ARG002
        if tag in _BLOCK_TAGS and not self._drop_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _DROP_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._drop_depth:
            self.parts.append(data)


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _CTRL_RE.sub("", text)
    lines = [_SPACES_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return _MANY_NL_RE.sub("\n\n", text).strip()


def html_to_text(value: object, max_len: int = DESCRIPTION_MAX) -> str:
    """Plain text from an HTML fragment (or plain text), whitespace normalised, length-capped."""
    if not isinstance(value, str) or not value:
        return ""
    parser = _Extractor()
    try:
        parser.feed(value)
        parser.close()
        text = "".join(parser.parts)
    except Exception:  # pragma: no cover - HTMLParser is lenient; belt and braces
        text = unescape(_TAG_LEFTOVER_RE.sub(" ", value))
    # An entity like ``&lt;b&gt;`` decodes to "<b>"; it is text now, but strip it
    # so stored text never even looks like markup.
    text = _TAG_LEFTOVER_RE.sub("", text)
    return truncate(_clean(text), max_len)


def clean_line(value: object, max_len: int = 300) -> str:
    """Single-line text (titles, employer names): no markup, no newlines."""
    text = html_to_text(value, max_len=max_len * 2).replace("\n", " ")
    return truncate(_SPACES_RE.sub(" ", text).strip(), max_len)


def truncate(text: str, max_len: int) -> str:
    """Cut at a word boundary and add an ellipsis when longer than ``max_len``."""
    if max_len <= 0 or len(text) <= max_len:
        return text
    cut = text[: max_len - 1]
    space = cut.rfind(" ")
    if space > max_len * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + "…"


def excerpt(text: str, max_len: int = 400) -> str:
    """Short one-paragraph preview of a stored description (for the UI / posts)."""
    return truncate(" ".join(text.split()), max_len)
