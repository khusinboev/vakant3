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
    """Infographic style: dark blended header, accent markers, horizontal skill bars."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    LM = 20.0
    HDR_H = 55.0
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

    hr = max(10, min(70, int(ar * 0.3 + 12)))
    hg = max(10, min(70, int(ag * 0.3 + 12)))
    hb = max(30, min(100, int(ab * 0.35 + 35)))
    pdf.set_fill_color(hr, hg, hb)
    pdf.rect(0, 0, pdf.w, HDR_H, "F")
    pdf.set_fill_color(ar, ag, ab)
    pdf.rect(0, 0, 6, HDR_H - 3.5, "F")
    pdf.rect(0, HDR_H - 3.5, pdf.w, 3.5, "F")

    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(LM, 10)
    sf(bold=True, size=24)
    pdf.cell(0, 10, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")

    pos = str(doc.get("position") or "").strip()
    if pos:
        pdf.set_x(LM)
        sf(size=12)
        pdf.set_text_color(205, 235, 230)
        pdf.cell(0, 6, pos, new_x="LMARGIN", new_y="NEXT")

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        mid = (len(contacts) + 1) // 2
        pdf.set_x(LM)
        sf(size=8.5)
        pdf.set_text_color(165, 200, 196)
        pdf.cell(0, 4.5, "  |  ".join(str(c) for c in contacts[:mid]), new_x="LMARGIN", new_y="NEXT")
        if contacts[mid:]:
            pdf.set_x(LM)
            pdf.cell(0, 4.5, "  |  ".join(str(c) for c in contacts[mid:]), new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(15, 23, 42)
    pdf.set_y(HDR_H + 8)

    def section(title: str) -> None:
        y = pdf.get_y() + 1
        pdf.set_fill_color(ar, ag, ab)
        pdf.rect(LM, y, 2.0, 6, "F")
        pdf.set_xy(LM + 5, y)
        sf(bold=True, size=9.5)
        pdf.set_text_color(ar, ag, ab)
        pdf.cell(0, 6, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(218, 222, 228)
        pdf.set_line_width(0.15)
        pdf.line(LM, pdf.get_y(), pdf.w - LM, pdf.get_y())
        pdf.set_text_color(15, 23, 42)
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
        pdf.ln(3)

    exps: list[dict] = doc.get("experiences") or []
    if exps:
        section(T["experience"])
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
                pdf.set_text_color(ar, ag, ab)
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
                pdf.set_text_color(100, 116, 139)
                pdf.cell(0, 4, loc, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
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
                pdf.set_text_color(ar, ag, ab)
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
        BAR_W = (UW - 5) / 2
        BAR_H = 4.5
        TRACK_H = 2.5
        for i, sk in enumerate(skills):
            col = i % 2
            x_off = LM + col * (BAR_W + 5)
            y = pdf.get_y()
            pdf.set_xy(x_off, y)
            sf(size=8.5)
            label_w = BAR_W - 20
            pdf.cell(label_w, BAR_H, str(sk), new_x="RIGHT")
            bar_x = x_off + label_w + 2
            bar_y = y + (BAR_H - TRACK_H) / 2
            pdf.set_fill_color(218, 222, 230)
            pdf.rect(bar_x, bar_y, 17, TRACK_H, "F")
            fill_ratio = 0.55 + (i * 0.17 % 0.45)
            pdf.set_fill_color(ar, ag, ab)
            pdf.rect(bar_x, bar_y, 17 * fill_ratio, TRACK_H, "F")
            if col == 1 or i == len(skills) - 1:
                pdf.ln(BAR_H + 1.5)
            else:
                pdf.set_y(y)
        pdf.ln(1)

    langs: list[str] = doc.get("languages") or []
    if langs:
        section(T["languages"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, "  \u2022  ".join(str(ll) for ll in langs), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
