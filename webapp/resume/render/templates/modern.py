from webapp.core.i18n import DEFAULT_LANG
from webapp.resume.i18n import strings
from webapp.resume.normalize import parse_bullets
from webapp.resume.render.base import DEJAVU_BOLD, DEJAVU_REGULAR, set_font



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
    """Modern: full-height accent sidebar (contacts/skills/languages) + main column."""
    T = strings(lang)

    from fpdf import FPDF  # type: ignore[import]

    def sf(p, bold: bool = False, size: float = 10.0) -> None:
        set_font(p, fam, has_bld, bold, size)

    SB_W = 62.0          # sidebar width mm
    SB_M = 7.0           # sidebar inner margin
    SB_UW = SB_W - SB_M * 2
    MAIN_X = SB_W + 6.0  # main column starts here
    MAIN_W = 210.0 - MAIN_X - 10.0  # right margin 10mm
    MAIN_BRK = 15.0

    # Sidebar background uses header() so it redraws on every page
    class _ModernPDF(FPDF):  # type: ignore[misc]
        _sb_w: float = SB_W
        _sb_rgb: tuple[int, int, int] = (ar, ag, ab)

        def header(self) -> None:  # type: ignore[override]
            self.set_fill_color(*self._sb_rgb)
            self.rect(0, 0, self._sb_w, self.h, "F")

    pdf = _ModernPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=MAIN_BRK)
    pdf.set_margins(SB_W + 6.0, 0, 10.0)
    if has_reg:
        pdf.add_font("DejaVu", fname=DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=DEJAVU_BOLD)

    pdf.add_page()

    # ── Sidebar helper: track sb_y manually (no auto-break in sidebar) ────
    sb_y = 12.0

    def sb_sf(bold: bool = False, size: float = 8.5) -> None:
        pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    def sb_set(y: float) -> None:
        pdf.set_xy(SB_M, y)

    def sb_text(text: str, bold: bool = False, size: float = 8.5) -> None:
        nonlocal sb_y
        if sb_y > 270:
            return  # silently clip near bottom
        sb_set(sb_y)
        sb_sf(bold=bold, size=size)
        pdf.set_text_color(230, 245, 242)
        pdf.multi_cell(SB_UW, 4.8, str(text), new_x="LMARGIN", new_y="NEXT")
        sb_y = pdf.get_y() + 0.8

    def sb_section_title(title: str) -> None:
        nonlocal sb_y
        sb_y += 4
        sb_set(sb_y)
        sb_sf(bold=True, size=7.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(SB_UW, 4.5, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.15)
        pdf.line(SB_M, pdf.get_y(), SB_W - SB_M, pdf.get_y())
        sb_y = pdf.get_y() + 2.5
        pdf.set_text_color(225, 242, 240)

    # Sidebar: name + position header
    sb_set(sb_y)
    sb_sf(bold=True, size=14)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(SB_UW, 6.5, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")
    sb_y = pdf.get_y() + 1
    pos_text = str(doc.get("position") or "").strip()
    if pos_text:
        sb_set(sb_y)
        sb_sf(size=9)
        pdf.set_text_color(210, 238, 234)
        pdf.multi_cell(SB_UW, 4.8, pos_text, new_x="LMARGIN", new_y="NEXT")
        sb_y = pdf.get_y() + 3

    # Sidebar: contacts
    contacts_sb: list[str] = doc.get("contacts") or []
    if contacts_sb:
        sb_section_title(T["contact"])
        for c in contacts_sb:
            sb_text(str(c))

    # Sidebar: skills
    skills_sb: list[str] = doc.get("skills") or []
    if skills_sb:
        sb_section_title(T["skills"])
        for sk in skills_sb[:20]:
            sb_text("• " + str(sk))

    # Sidebar: languages
    langs_sb: list[str] = doc.get("languages") or []
    if langs_sb:
        sb_section_title(T["languages"])
        for ll in langs_sb:
            sb_text("• " + str(ll))

    # ── Main column helpers ───────────────────────────────────────────────
    pdf.set_text_color(15, 23, 42)
    main_y = 10.0

    def main_set(y: float) -> None:
        pdf.set_xy(MAIN_X, y)

    def main_section(title: str) -> None:
        nonlocal main_y
        main_y += 4
        main_set(main_y)
        sf(pdf, bold=True, size=9)
        pdf.set_text_color(ar, ag, ab)
        pdf.cell(MAIN_W, 5, title.upper(), new_x="LEFT", new_y="NEXT")
        pdf.set_draw_color(ar, ag, ab)
        pdf.set_line_width(0.3)
        pdf.line(MAIN_X, pdf.get_y(), MAIN_X + MAIN_W, pdf.get_y())
        pdf.set_text_color(15, 23, 42)
        pdf.ln(2)
        main_y = pdf.get_y()

    def main_body(text: str, bold: bool = False, size: float = 9.5) -> None:
        nonlocal main_y
        if not text:
            return
        main_set(main_y)
        sf(pdf, bold=bold, size=size)
        pdf.multi_cell(MAIN_W, 4.8, str(text), new_x="LEFT", new_y="NEXT")
        main_y = pdf.get_y()

    def main_desc(text: str) -> None:
        nonlocal main_y
        for line in parse_bullets(text):
            main_set(main_y)
            sf(pdf, size=9)
            pdf.multi_cell(MAIN_W - 2, 4.6, line, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

    # Main: summary
    summary_m = str(doc.get("summary") or "").strip()
    if summary_m:
        main_section(T["summary"])
        main_body(summary_m)
        main_y += 2

    # Main: experience
    experiences_m: list[dict] = doc.get("experiences") or []
    if experiences_m:
        main_section(T["experience"])
        for i, item in enumerate(experiences_m):
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()

            main_set(main_y)
            sf(pdf, bold=True, size=10)
            role_label = role or company or T["default_role"]
            if period:
                pdf.cell(MAIN_W * 0.65, 5.5, role_label, new_x="RIGHT")
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(MAIN_W, 5.5, role_label, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

            if company and role:
                main_set(main_y)
                sf(pdf, size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(MAIN_W, 4.5, company, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()

            if loc:
                main_set(main_y)
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W, 4, loc, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()

            if desc:
                main_y += 0.8
                main_desc(desc)

            if i < len(experiences_m) - 1:
                main_y += 3
        main_y += 2

    # Main: education
    educations_m: list[dict] = doc.get("educations") or []
    if educations_m:
        main_section(T["education"])
        for i, item in enumerate(educations_m):
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            title_label = school or degree or T["default_education"]

            main_set(main_y)
            sf(pdf, bold=True, size=10)
            if period:
                pdf.cell(MAIN_W * 0.65, 5.5, title_label, new_x="RIGHT")
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(MAIN_W, 5.5, title_label, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

            if degree and school:
                main_set(main_y)
                sf(pdf, size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(MAIN_W, 4.5, degree, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()

            if desc:
                main_y += 0.8
                main_desc(desc)

            if i < len(educations_m) - 1:
                main_y += 2

    return bytes(pdf.output())
