"""PDF rendering entry point: picks a template renderer and runs it.

There is no fallback renderer any more — a failure raises so the caller can mark
the export row "failed" and answer with PDF_RENDER_FAILED instead of silently
shipping an unreadable ASCII document.
"""

from typing import Callable

from webapp.core.i18n import DEFAULT_LANG
from webapp.resume.normalize import hex_to_rgb
from webapp.resume.render.base import font_availability
from webapp.resume.render.templates import (
    classic,
    creative,
    europass,
    executive,
    infographic,
    minimal,
    modern,
    photo_classic,
    photo_sidebar,
    timeline,
)

RENDERERS: dict[str, Callable[..., bytes]] = {
    "executive": executive.render,
    "timeline": timeline.render,
    "minimal": minimal.render,
    "creative": creative.render,
    "photo_classic": photo_classic.render,
    "photo_sidebar": photo_sidebar.render,
    "europass": europass.render,
    "infographic": infographic.render,
    "modern": modern.render,
}


def generate_pdf_bytes(doc: dict, accent_hex: str = "#0f766e", template_id: str = "clean", lang: str = DEFAULT_LANG) -> bytes:
    """Render ``doc`` as an A4 PDF. Raises on any rendering problem."""
    ar, ag, ab = hex_to_rgb(accent_hex)
    fam, has_reg, has_bld = font_availability()

    renderer = RENDERERS.get(template_id)
    if renderer is not None:
        return renderer(doc, ar, ag, ab, fam, has_reg, has_bld, lang)

    # "clean" and "compact" share one renderer.
    return classic.render(doc, ar, ag, ab, fam, has_reg, has_bld, lang, template_id=template_id)
