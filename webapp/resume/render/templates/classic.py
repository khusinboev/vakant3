from webapp.core.i18n import DEFAULT_LANG
from webapp.resume.i18n import strings
from webapp.resume.normalize import parse_bullets
from webapp.resume.render.base import make_pdf, set_font



def render(
    doc: dict,
    ar: int,
    ag: int,
    ab: int,
    fam: str,
    has_reg: bool,
    has_bld: bool,
    lang: str = DEFAULT_LANG,
    template_id: str = "clean",
) -> bytes:  # noqa: C901
    """Clean (accent header) and Compact (dense, mono) single-column layouts."""
    T = strings(lang)

    def _make_pdf(margin_l: float = 18.0, auto_break_margin: float = 15.0):
        return make_pdf(has_reg, has_bld, margin_l, auto_break_margin)

    def sf(p, bold: bool = False, size: float = 10.0) -> None:
        set_font(p, fam, has_bld, bold, size)

    LM = 18.0
    is_compact = template_id == "compact"
    HDR_H = 40.0 if not is_compact else 0.0   # compact has no colored header
    BODY_BREAK = 12.0 if is_compact else 15.0
    BODY_SZ = 9.0 if is_compact else 9.5
    TITLE_SZ = 8.5 if is_compact else 9.0

    pdf = _make_pdf(LM, BODY_BREAK)
    pdf.add_page()
    UW = pdf.w - 2 * LM  # usable width

    # ── Header block ──────────────────────────────────────────────────
    if not is_compact:
        pdf.set_fill_color(ar, ag, ab)
        pdf.rect(0, 0, pdf.w, HDR_H, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(LM, 7)
        sf(pdf, bold=True, size=20)
        pdf.cell(0, 8, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")
        pos_text = str(doc.get("position") or "").strip()
        if pos_text:
            pdf.set_x(LM)
            sf(pdf, size=11)
            pdf.set_text_color(235, 255, 252)
            pdf.cell(0, 5, pos_text, new_x="LMARGIN", new_y="NEXT")
        contacts: list[str] = doc.get("contacts") or []
        if contacts:
            pdf.set_x(LM)
            sf(pdf, size=8.5)
            pdf.set_text_color(200, 240, 235)
            pdf.cell(0, 4, " | ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(15, 23, 42)
        pdf.set_y(HDR_H + 5)
    else:
        # Compact: plain text header block
        pdf.set_text_color(15, 23, 42)
        name_text = str(doc.get("name") or T["default_name"])
        pos_text = str(doc.get("position") or "").strip()
        contacts = doc.get("contacts") or []
        pdf.set_xy(LM, 8)
        sf(pdf, bold=True, size=16)
        if pos_text:
            # Name left, position right
            pdf.cell(UW * 0.58, 7, name_text, new_x="RIGHT")
            sf(pdf, size=10)
            pdf.set_text_color(60, 70, 90)
            pdf.cell(UW * 0.42, 7, pos_text, align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(15, 23, 42)
        else:
            pdf.cell(0, 7, name_text, new_x="LMARGIN", new_y="NEXT")
        if contacts:
            pdf.set_x(LM)
            sf(pdf, size=8)
            pdf.set_text_color(90, 100, 120)
            pdf.cell(0, 4, " · ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(15, 23, 42)
        # Hairline separator
        pdf.set_draw_color(150, 150, 150)
        pdf.set_line_width(0.2)
        pdf.line(LM, pdf.get_y() + 2, pdf.w - LM, pdf.get_y() + 2)
        pdf.set_y(pdf.get_y() + 5)

    # ── Section title helper ──────────────────────────────────────────
    def section(title: str) -> None:
        pdf.set_x(LM)
        sf(pdf, bold=True, size=TITLE_SZ)
        if is_compact:
            pdf.set_text_color(30, 30, 30)
            pdf.set_draw_color(120, 120, 120)
            pdf.set_line_width(0.15)
        else:
            pdf.set_text_color(ar, ag, ab)
            pdf.set_draw_color(ar, ag, ab)
            pdf.set_line_width(0.3)
        pdf.cell(0, 5, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.line(LM, pdf.get_y(), pdf.w - LM, pdf.get_y())
        pdf.set_text_color(15, 23, 42)
        pdf.ln(2)

    # ── Multi-cell body helper ────────────────────────────────────────
    def body(text: str, bold: bool = False, size: float = BODY_SZ, indent: float = 0) -> None:
        if not text:
            return
        pdf.set_x(LM + indent)
        sf(pdf, bold=bold, size=size)
        pdf.multi_cell(UW - indent, 4.8, str(text), new_x="LMARGIN", new_y="NEXT")

    # ── Description with bullet lines ─────────────────────────────────
    def desc_block(text: str) -> None:
        indent = 3.0 if not is_compact else 2.0
        for line in parse_bullets(text):
            pdf.set_x(LM + indent)
            sf(pdf, size=BODY_SZ)
            pdf.multi_cell(UW - indent, 4.5 if is_compact else 4.8, line,
                           new_x="LMARGIN", new_y="NEXT")

    # ── Summary ───────────────────────────────────────────────────────
    summary = str(doc.get("summary") or "").strip()
    if summary:
        section(T["summary"])
        body(summary)
        pdf.ln(3 if not is_compact else 2)

    # ── Experience ────────────────────────────────────────────────────
    experiences: list[dict] = doc.get("experiences") or []
    if experiences:
        section(T["experience"])
        for i, item in enumerate(experiences):
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()

            # Role (bold) + Period (right-aligned, muted)
            pdf.set_x(LM)
            sf(pdf, bold=True, size=10.5 if not is_compact else 9.5)
            role_label = role or company or T["default_role"]
            if period:
                pdf.cell(UW * 0.65, 5.5, role_label, new_x="RIGHT")
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 5.5, role_label, new_x="LMARGIN", new_y="NEXT")

            # Company (italic-style smaller text)
            if company and role:
                pdf.set_x(LM)
                sf(pdf, size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(0, 4.5, company, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)

            # Location
            if loc:
                pdf.set_x(LM)
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(0, 4, loc, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)

            # Description
            if desc:
                pdf.ln(0.8)
                desc_block(desc)

            if i < len(experiences) - 1:
                pdf.ln(2.5 if not is_compact else 1.5)
        pdf.ln(2)

    # ── Education ─────────────────────────────────────────────────────
    educations: list[dict] = doc.get("educations") or []
    if educations:
        section(T["education"])
        for i, item in enumerate(educations):
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            title_label = school or degree or T["default_education"]

            pdf.set_x(LM)
            sf(pdf, bold=True, size=10.5 if not is_compact else 9.5)
            if period:
                pdf.cell(UW * 0.65, 5.5, title_label, new_x="RIGHT")
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 5.5, title_label, new_x="LMARGIN", new_y="NEXT")

            if degree and school:
                pdf.set_x(LM)
                sf(pdf, size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(0, 4.5, degree, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)

            if desc:
                pdf.ln(0.8)
                desc_block(desc)

            if i < len(educations) - 1:
                pdf.ln(2 if not is_compact else 1.5)
        pdf.ln(2)

    # ── Skills ────────────────────────────────────────────────────────
    skills: list[str] = doc.get("skills") or []
    if skills:
        section(T["skills"])
        if is_compact:
            body(", ".join(str(s) for s in skills), size=9)
        else:
            # Render skills as tinted chips in rows
            CHIP_PAD_H, CHIP_PAD_V, CHIP_GAP = 3.0, 1.2, 2.0
            CHIP_H = 5.5
            x_pos = LM
            chip_y = pdf.get_y()
            lr = min(255, ar + 195)
            lg = min(255, ag + 195)
            lb = min(255, ab + 195)
            for skill in skills:
                sf(pdf, size=8.5)
                tw = pdf.get_string_width(str(skill)) + CHIP_PAD_H * 2
                if x_pos + tw > pdf.w - LM:
                    chip_y += CHIP_H + CHIP_GAP
                    x_pos = LM
                pdf.set_fill_color(lr, lg, lb)
                pdf.set_draw_color(ar, ag, ab)
                pdf.set_line_width(0.2)
                pdf.rect(x_pos, chip_y + CHIP_PAD_V, tw, CHIP_H, "FD")
                pdf.set_text_color(ar, ag, ab)
                pdf.set_xy(x_pos + CHIP_PAD_H, chip_y + CHIP_PAD_V + 0.5)
                pdf.cell(tw - CHIP_PAD_H * 2, CHIP_H - 1, str(skill))
                pdf.set_text_color(15, 23, 42)
                x_pos += tw + CHIP_GAP
            pdf.set_y(chip_y + CHIP_H + CHIP_GAP + 2)
        pdf.ln(1)

    # ── Languages ─────────────────────────────────────────────────────
    langs: list[str] = doc.get("languages") or []
    if langs:
        section(T["languages"])
        body(", ".join(str(ll) for ll in langs))

    return bytes(pdf.output())
