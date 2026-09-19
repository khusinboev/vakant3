"""Shared drawing primitives for the fpdf2 renderers."""

import os

# DejaVu Sans covers Latin, Cyrillic and the Uzbek apostrophes.
DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font_availability() -> tuple[str, bool, bool]:
    """Return ``(family, has_regular, has_bold)`` for the current machine."""
    has_reg = os.path.exists(DEJAVU_REGULAR)
    has_bld = os.path.exists(DEJAVU_BOLD)
    return ("DejaVu" if has_reg else "Helvetica"), has_reg, has_bld


def register_fonts(pdf, has_reg: bool, has_bld: bool) -> None:
    if has_reg:
        pdf.add_font("DejaVu", fname=DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=DEJAVU_BOLD)


def make_pdf(has_reg: bool, has_bld: bool, margin_l: float = 18.0, auto_break_margin: float = 15.0):
    from fpdf import FPDF  # type: ignore[import]

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(margin_l, 0, margin_l)
    pdf.set_auto_page_break(auto=True, margin=auto_break_margin)
    register_fonts(pdf, has_reg, has_bld)
    return pdf


def set_font(pdf, fam: str, has_bld: bool, bold: bool = False, size: float = 10.0) -> None:
    pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)
