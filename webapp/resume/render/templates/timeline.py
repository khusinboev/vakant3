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
    """Timeline layout: vertical accent line + dot markers alongside each entry."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    LM = 18.0
    HDR_H = 40.0
    TL_X = LM + 6.0
    ENTRY_X = TL_X + 10.0
    ENTRY_W = 210.0 - ENTRY_X - 10.0
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

    pdf.set_fill_color(ar, ag, ab)
    pdf.rect(0, 0, pdf.w, HDR_H, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(LM, 8)
    sf(bold=True, size=22)
    pdf.cell(0, 9, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")

    pos = str(doc.get("position") or "").strip()
    if pos:
        pdf.set_x(LM)
        sf(size=11)
        pdf.set_text_color(220, 240, 238)
        pdf.cell(0, 5.5, pos, new_x="LMARGIN", new_y="NEXT")

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        pdf.set_x(LM)
        sf(size=8)
        pdf.set_text_color(180, 220, 215)
        pdf.cell(0, 4.5, " | ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(15, 23, 42)
    pdf.set_y(HDR_H + 7)

    def section(title: str) -> None:
        pdf.set_x(LM)
        sf(bold=True, size=9)
        pdf.set_text_color(ar, ag, ab)
        pdf.cell(0, 5, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(ar, ag, ab)
        pdf.set_line_width(0.3)
        pdf.line(LM, pdf.get_y(), pdf.w - LM, pdf.get_y())
        pdf.set_text_color(15, 23, 42)
        pdf.ln(2)

    summary = str(doc.get("summary") or "").strip()
    if summary:
        section(T["summary"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, summary, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    def timeline_entries(items: list[dict], is_edu: bool = False) -> None:
        for item in items:
            role = str((item.get("school") if is_edu else item.get("role")) or "").strip()
            company = str((item.get("degree") if is_edu else item.get("company")) or "").strip()
            period = str(item.get("period") or "").strip()
            loc = "" if is_edu else str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()

            dot_y = pdf.get_y() + 2.0
            entry_start_y = dot_y - 1.0
            pdf.set_xy(ENTRY_X, entry_start_y)
            sf(bold=True, size=10.5)
            rl = role or company or T["default_role"]
            if period:
                pdf.cell(ENTRY_W * 0.65, 5.5, rl, new_x="RIGHT")
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(ENTRY_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(ENTRY_W, 5.5, rl, new_x="LEFT", new_y="NEXT")
            if company and role:
                pdf.set_x(ENTRY_X)
                sf(size=9)
                pdf.set_text_color(ar, ag, ab)
                pdf.cell(ENTRY_W, 4.5, company, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if loc:
                pdf.set_x(ENTRY_X)
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(ENTRY_W, 4, loc, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if desc:
                pdf.ln(0.5)
                for line in parse_bullets(desc):
                    pdf.set_x(ENTRY_X + 2)
                    sf(size=9)
                    pdf.multi_cell(ENTRY_W - 2, 4.6, line, new_x="LEFT", new_y="NEXT")

            entry_end_y = pdf.get_y() + 1.5
            pdf.set_draw_color(ar, ag, ab)
            pdf.set_line_width(0.6)
            pdf.line(TL_X, entry_start_y, TL_X, entry_end_y)
            pdf.set_fill_color(ar, ag, ab)
            r = 1.8
            pdf.ellipse(TL_X - r, dot_y - r, r * 2, r * 2, "F")
            pdf.ln(3)

    exps: list[dict] = doc.get("experiences") or []
    if exps:
        section(T["experience"])
        timeline_entries(exps)
        pdf.ln(1)

    edus: list[dict] = doc.get("educations") or []
    if edus:
        section(T["education"])
        timeline_entries(edus, is_edu=True)
        pdf.ln(1)

    skills: list[str] = doc.get("skills") or []
    if skills:
        section(T["skills"])
        cols = 3
        col_w = UW / cols
        for i, sk in enumerate(skills):
            col = i % cols
            pdf.set_x(LM + col * col_w)
            sf(size=9)
            if col < cols - 1:
                pdf.cell(col_w, 5.5, "\u25c6 " + str(sk), new_x="RIGHT")
            else:
                pdf.cell(col_w, 5.5, "\u25c6 " + str(sk), new_x="LMARGIN", new_y="NEXT")
        if len(skills) % cols != 0:
            pdf.ln(5.5)
        pdf.ln(1)

    langs: list[str] = doc.get("languages") or []
    if langs:
        section(T["languages"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, "  \u2022  ".join(str(ll) for ll in langs), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
