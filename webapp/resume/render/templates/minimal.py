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
    """Ultra-minimal: oversized dark name, hairline separators, no colored blocks."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    LM = 22.0
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(True, 15)
    pdf.set_margins(LM, 0, LM)
    if has_reg:
        pdf.add_font("DejaVu", fname=DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=DEJAVU_BOLD)
    pdf.add_page()
    UW = pdf.w - 2 * LM

    def sf(bold: bool = False, size: float = 10.0) -> None:
        pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    pdf.set_text_color(30, 30, 30)
    pdf.set_xy(LM, 13)
    sf(bold=True, size=28)
    pdf.cell(0, 12, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")

    pos = str(doc.get("position") or "").strip()
    if pos:
        pdf.set_x(LM)
        sf(size=12)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 6, pos, new_x="LMARGIN", new_y="NEXT")

    pdf.set_draw_color(195, 195, 195)
    pdf.set_line_width(0.12)
    pdf.line(LM, pdf.get_y() + 2.5, pdf.w - LM, pdf.get_y() + 2.5)
    pdf.ln(6)

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        pdf.set_x(LM)
        sf(size=8.5)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 4.5, "  \u00b7  ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    def section(title: str) -> None:
        pdf.ln(2)
        pdf.set_x(LM)
        sf(bold=True, size=7.5)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 4, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(195, 195, 195)
        pdf.set_line_width(0.1)
        pdf.line(LM, pdf.get_y(), pdf.w - LM, pdf.get_y())
        pdf.set_text_color(30, 30, 30)
        pdf.ln(2.5)

    def desc_block(text: str) -> None:
        for line in parse_bullets(text):
            pdf.set_x(LM + 4)
            sf(size=9)
            pdf.multi_cell(UW - 4, 4.6, line, new_x="LMARGIN", new_y="NEXT")

    summary = str(doc.get("summary") or "").strip()
    if summary:
        section(T["summary"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, summary, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

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
            sf(bold=True, size=10)
            rl = role or company or T["default_role"]
            if period:
                pdf.cell(UW * 0.65, 5.5, rl, new_x="RIGHT")
                sf(size=8)
                pdf.set_text_color(140, 140, 140)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(30, 30, 30)
            else:
                pdf.cell(0, 5.5, rl, new_x="LMARGIN", new_y="NEXT")
            if company and role:
                pdf.set_x(LM)
                sf(size=9)
                pdf.set_text_color(90, 90, 90)
                pdf.cell(0, 4.5, company, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(30, 30, 30)
            if loc:
                pdf.set_x(LM)
                sf(size=8)
                pdf.set_text_color(140, 140, 140)
                pdf.cell(0, 4, loc, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(30, 30, 30)
            if desc:
                pdf.ln(0.8)
                desc_block(desc)
            if i < len(exps) - 1:
                pdf.ln(2.5)
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
                pdf.set_text_color(140, 140, 140)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(30, 30, 30)
            else:
                pdf.cell(0, 5.5, tl, new_x="LMARGIN", new_y="NEXT")
            if degree and school:
                pdf.set_x(LM)
                sf(size=9)
                pdf.set_text_color(90, 90, 90)
                pdf.cell(0, 4.5, degree, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(30, 30, 30)
            if desc:
                pdf.ln(0.8)
                desc_block(desc)
            if i < len(edus) - 1:
                pdf.ln(2)
        pdf.ln(2)

    skills: list[str] = doc.get("skills") or []
    if skills:
        section(T["skills"])
        mid = (len(skills) + 1) // 2
        col_w = UW / 2 - 3
        for s1, s2 in zip(skills[:mid], skills[mid:] + [""]):
            pdf.set_x(LM)
            sf(size=9)
            pdf.cell(col_w, 5, "\u2013 " + str(s1), new_x="RIGHT")
            if s2:
                pdf.cell(col_w, 5, "\u2013 " + str(s2), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(5)
        pdf.ln(1)

    langs: list[str] = doc.get("languages") or []
    if langs:
        section(T["languages"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, "  /  ".join(str(ll) for ll in langs), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
