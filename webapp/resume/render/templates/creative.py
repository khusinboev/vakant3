from webapp.core.i18n import DEFAULT_LANG
from webapp.resume.i18n import strings
from webapp.resume.normalize import parse_bullets
from webapp.resume.render.base import DEJAVU_BOLD, DEJAVU_REGULAR


def render(
    doc: dict,
    ar: int,
    ag: int,
    ab: int,
    fam: str,
    has_reg: bool,
    has_bld: bool,
    lang: str = DEFAULT_LANG,
) -> bytes:  # noqa: C901
    """Creative: persistent left accent stripe (re-drawn via header()), chip skills."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    STRIPE_W = 12.0
    LM = STRIPE_W + 15.0
    RM = 15.0

    class _CreativePDF(FPDF):  # type: ignore[misc]
        def header(self) -> None:  # type: ignore[override]
            self.set_fill_color(ar, ag, ab)
            self.rect(0, 0, STRIPE_W, self.h, "F")

    pdf = _CreativePDF("P", "mm", "A4")
    pdf.set_auto_page_break(True, 15)
    pdf.set_margins(LM, 0, RM)
    if has_reg:
        pdf.add_font("DejaVu", fname=DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=DEJAVU_BOLD)
    pdf.add_page()
    UW = pdf.w - LM - RM

    def sf(bold: bool = False, size: float = 10.0) -> None:
        pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    pdf.set_text_color(15, 23, 42)
    pdf.set_xy(LM, 13)
    sf(bold=True, size=26)
    pdf.multi_cell(UW, 11, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")

    pos = str(doc.get("position") or "").strip()
    if pos:
        pdf.set_x(LM)
        sf(size=12)
        pdf.set_text_color(ar, ag, ab)
        pdf.cell(0, 6, pos, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(15, 23, 42)

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        pdf.set_x(LM)
        sf(size=8.5)
        pdf.set_text_color(90, 100, 120)
        pdf.cell(0, 5, " \u00b7 ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(15, 23, 42)

    sep_y = pdf.get_y() + 3
    pdf.set_draw_color(ar, ag, ab)
    pdf.set_line_width(1.5)
    pdf.line(LM, sep_y, LM + 35, sep_y)
    pdf.set_line_width(0.15)
    pdf.set_draw_color(180, 185, 195)
    pdf.line(LM + 38, sep_y, pdf.w - RM, sep_y)
    pdf.set_y(sep_y + 7)

    def section(title: str) -> None:
        pdf.ln(1)
        pdf.set_x(LM)
        sf(bold=True, size=9.5)
        pdf.set_text_color(ar, ag, ab)
        pdf.cell(0, 5.5, title.upper(), new_x="LMARGIN", new_y="NEXT")
        y_rule = pdf.get_y()
        pdf.set_draw_color(ar, ag, ab)
        pdf.set_line_width(0.6)
        pdf.line(LM, y_rule, LM + 28, y_rule)
        pdf.set_text_color(15, 23, 42)
        pdf.ln(2.5)

    def desc_block(text: str) -> None:
        for line in parse_bullets(text):
            pdf.set_x(LM + 3)
            sf(size=9)
            pdf.multi_cell(UW - 3, 4.6, line, new_x="LMARGIN", new_y="NEXT")

    summary = str(doc.get("summary") or "").strip()
    if summary:
        section(T["about"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, summary, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    exps: list[dict] = doc.get("experiences") or []
    if exps:
        section(T["experience_alt"])
        for i, item in enumerate(exps):
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()
            pdf.set_x(LM)
            sf(bold=True, size=10.5)
            rl = role or company or T["default_role"]
            if period:
                pdf.cell(UW * 0.65, 5.5, rl, new_x="RIGHT")
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 5.5, rl, new_x="LMARGIN", new_y="NEXT")
            if company and role:
                pdf.set_x(LM)
                sf(size=9)
                pdf.set_text_color(ar, ag, ab)
                pdf.cell(0, 4.5, company, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if loc:
                pdf.set_x(LM)
                sf(size=8)
                pdf.set_text_color(130, 130, 130)
                pdf.cell(0, 4, loc, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if desc:
                pdf.ln(0.8)
                desc_block(desc)
            if i < len(exps) - 1:
                pdf.ln(3)
        pdf.ln(2)

    edus: list[dict] = doc.get("educations") or []
    if edus:
        section(T["education"])
        for i, item in enumerate(edus):
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            tl = school or degree or T["default_education"]
            pdf.set_x(LM)
            sf(bold=True, size=10)
            if period:
                pdf.cell(UW * 0.65, 5.5, tl, new_x="RIGHT")
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 5.5, tl, new_x="LMARGIN", new_y="NEXT")
            if degree and school:
                pdf.set_x(LM)
                sf(size=9)
                pdf.set_text_color(ar, ag, ab)
                pdf.cell(0, 4.5, degree, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if desc:
                pdf.ln(0.8)
                desc_block(desc)
            if i < len(edus) - 1:
                pdf.ln(2)
        pdf.ln(2)

    skills: list[str] = doc.get("skills") or []
    if skills:
        section(T["skills"])
        CHIP_H, CHIP_PAD, CHIP_GAP = 5.5, 3.0, 2.0
        x_pos = LM
        chip_y = pdf.get_y()
        lr = min(255, ar + 190)
        lg = min(255, ag + 190)
        lb = min(255, ab + 190)
        for sk in skills:
            sf(size=8.5)
            tw = pdf.get_string_width(str(sk)) + CHIP_PAD * 2
            if x_pos + tw > pdf.w - RM:
                chip_y += CHIP_H + CHIP_GAP
                x_pos = LM
            pdf.set_fill_color(lr, lg, lb)
            pdf.set_draw_color(ar, ag, ab)
            pdf.set_line_width(0.2)
            pdf.rect(x_pos, chip_y + 1, tw, CHIP_H, "FD")
            pdf.set_text_color(ar, ag, ab)
            pdf.set_xy(x_pos + CHIP_PAD, chip_y + 1.5)
            pdf.cell(tw - CHIP_PAD * 2, CHIP_H - 1, str(sk))
            pdf.set_text_color(15, 23, 42)
            x_pos += tw + CHIP_GAP
        pdf.set_y(chip_y + CHIP_H + CHIP_GAP + 2)
        pdf.ln(1)

    langs: list[str] = doc.get("languages") or []
    if langs:
        section(T["languages"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, "  \u2022  ".join(str(ll) for ll in langs), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
