"""Strict allowlist for admin-edited content HTML (stored XSS hardening).

``<a>`` may carry exactly one attribute, ``href``, with a quoted value and an
allowed scheme. Any leftover attribute text, unquoted value, extra attribute,
or attribute on another tag makes the whole value invalid.
"""

import pytest

from webapp.routers.admin_content import _html_is_valid


@pytest.mark.parametrize(
    "payload",
    [
        # Unquoted handler after a valid href (the original bypass).
        '<a href="https://x" onclick=alert(1)>t</a>',
        # Quoted handlers, both quote styles.
        '<a href="https://x" onclick="alert(1)">t</a>',
        "<a href=\"https://x\" onclick='alert(1)'>t</a>",
        "<a onmouseover='alert(1)' href=\"https://x\">t</a>",
        # Unquoted href, safe or not.
        "<a href=https://x>t</a>",
        "<a href=javascript:alert(1)>t</a>",
        '<a href="javascript:alert(1)">t</a>',
        # Entity-encoded scheme.
        '<a href="java&#115;cript:alert(1)">t</a>',
        '<a href="&#x6A;avascript:alert(1)">t</a>',
        # Uppercase tag and attributes.
        '<A HREF="https://x" ONCLICK="alert(1)">t</A>',
        '<A HREF="javascript:alert(1)">t</A>',
        # Slash-separated attribute (browsers treat "/" as whitespace here).
        '<a href="https://x"/onclick=alert(1)>t</a>',
        '<a href="https://x"/onclick="alert(1)">t</a>',
        # Newline / tab separated attributes.
        '<a href="https://x"\nonclick="alert(1)">t</a>',
        '<a\nhref="https://x"\tonclick=alert(1)>t</a>',
        # Duplicate href (browsers keep the first, scanners may check the last).
        '<a href="javascript:alert(1)" href="https://x">t</a>',
        '<a href="https://x" href="javascript:alert(1)">t</a>',
        # Bare attribute / junk left in the tag.
        '<a href="https://x" autofocus>t</a>',
        '<a href="https://x" x>t</a>',
        '<a href="https://x"">t</a>',
        # Quotes smuggled inside the value.
        "<a href='https://x\" onclick=\"alert(1)'>t</a>",
        # No href at all, or an empty attribute list.
        "<a>t</a>",
        '<a title="x">t</a>',
        # Attributes on tags that allow none.
        '<b onclick="alert(1)">t</b>',
        "<b onclick=alert(1)>t</b>",
        '<i class="x">t</i>',
        '<br onload="alert(1)">',
        "<br/onload=alert(1)>",
        '<code style="x">t</code>',
        # Self-closing non-void tag: browsers ignore the slash and leave it open.
        "<b/>text",
        '<a href="https://x"/>text',
        "<b>t</b/>",
        # Disallowed tags.
        "<svg/onload=alert(1)>",
        "<img src=x onerror=alert(1)>",
        "<SCRIPT>alert(1)</SCRIPT>",
    ],
)
def test_bypass_payloads_are_rejected(payload):
    assert _html_is_valid(payload) is False


@pytest.mark.parametrize(
    "payload",
    [
        '<a href="https://lex.uz/docs/1">Lex</a>',
        "<a href='https://lex.uz/docs/1'>Lex</a>",
        '<A HREF="https://lex.uz/docs/1">Lex</A>',
        '<a href = "https://lex.uz/docs/1" >Lex</a>',
        '<a\nhref="https://lex.uz/docs/1">Lex</a>',
        '<a href="https://lex.uz/?a=1&amp;b=2">Lex</a>',
        '<a href="mailto:hr@example.uz">mail</a>',
        "<b>bold</b> <i>it</i> <u>u</u> <code>c</code><br><br/><br />",
        "Plain text with no tags",
    ],
)
def test_legitimate_markup_still_passes(payload):
    assert _html_is_valid(payload) is True


@pytest.mark.parametrize(
    "payload",
    [
        "<a" + " " * 50_000,
        '<a href="' + "x" * 50_000,
        "<b" * 25_000,
        "<" + "a" * 50_000,
        "<a " + "href=" * 10_000,
        "<a" + " /" * 25_000,
        "<b>" * 10_000 + "<a" + " " * 20_000,
    ],
)
def test_adversarial_input_validates_in_linear_time(payload):
    """A sync check inside an async handler must not stall the event loop."""
    import time

    assert len(payload) >= 50_000
    started = time.perf_counter()
    assert _html_is_valid(payload) is False
    assert time.perf_counter() - started < 0.2
