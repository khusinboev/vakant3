import io

from webapp.core.i18n import DEFAULT_LANG
from webapp.resume.i18n import strings
from webapp.resume.normalize import parse_bullets
from webapp.resume.photos import clip_photo
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
    """Wide accent sidebar with profile photo at top; main column for experience/education."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    SB_W = 68.0
    SB_M = 8.0
    SB_UW = SB_W - SB_M * 2
    MAIN_X = SB_W + 8.0
    MAIN_W = 210.0 - MAIN_X - 10.0
    PHOTO_SIZE = 42.0

    class _PSidebarPDF(FPDF):  # type: ignore[misc]
        def header(self) -> None:  # type: ignore[override]
            self.set_fill_color(ar, ag, ab)
            self.rect(0, 0, SB_W, self.h, "F")

    pdf = _PSidebarPDF("P", "mm", "A4")
    pdf.set_auto_page_break(True, 15)
    pdf.set_margins(MAIN_X, 0, 10.0)
    if has_reg:
        pdf.add_font("DejaVu", fname=DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=DEJAVU_BOLD)
    pdf.add_page()

    def sf(bold: bool = False, size: float = 10.0) -> None:
        pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    sb_y = 10.0

    def sb_set(y: float) -> None:
        pdf.set_xy(SB_M, y)

    def sb_text(text: str, bold: bool = False, size: float = 8.5) -> None:
        nonlocal sb_y
        if sb_y > 270:
            return
        sb_set(sb_y)
        sf(bold=bold, size=size)
        pdf.set_text_color(230, 245, 242)
        pdf.multi_cell(SB_UW, 4.8, str(text), new_x="LMARGIN", new_y="NEXT")
        sb_y = pdf.get_y() + 0.5

    def sb_section(title: str) -> None:
        nonlocal sb_y
        sb_y += 4
        sb_set(sb_y)
        sf(bold=True, size=7.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(SB_UW, 4.5, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.15)
        pdf.line(SB_M, pdf.get_y(), SB_W - SB_M, pdf.get_y())
        sb_y = pdf.get_y() + 2.5

    photo_url = str(doc.get("photo_url") or "").strip()
    photo_x = (SB_W - PHOTO_SIZE) / 2
    photo_embedded = False
    if photo_url:
        photo_data = doc.get("photo_bytes")
        if photo_data:
            try:
                clipped = clip_photo(photo_data, shape="circle")
                pdf.image(io.BytesIO(clipped), x=photo_x, y=sb_y, w=PHOTO_SIZE, h=PHOTO_SIZE)
                sb_y += PHOTO_SIZE + 5
                photo_embedded = True
            except Exception:
                pass
    if not photo_embedded:
        initials = "".join(w[0].upper() for w in str(doc.get("name") or "N").split()[:2]) or "N"
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.5)
        pdf.ellipse(photo_x, sb_y, PHOTO_SIZE, PHOTO_SIZE, "D")
        sb_set(sb_y + PHOTO_SIZE / 2 - 5)
        sf(bold=True, size=18)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(SB_UW, 10, initials, align="C", new_x="LMARGIN", new_y="NEXT")
        sb_y += PHOTO_SIZE + 5

    sb_set(sb_y)
    sf(bold=True, size=13)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(SB_UW, 6, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")
    sb_y = pdf.get_y() + 1.5

    pos_text = str(doc.get("position") or "").strip()
    if pos_text:
        sb_set(sb_y)
        sf(size=9)
        pdf.set_text_color(210, 238, 234)
        pdf.multi_cell(SB_UW, 4.8, pos_text, new_x="LMARGIN", new_y="NEXT")
        sb_y = pdf.get_y() + 2

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        sb_section(T["contact"])
        for c in contacts:
            sb_text(str(c))

    skills: list[str] = doc.get("skills") or []
    if skills:
        sb_section(T["skills"])
        for sk in skills[:20]:
            sb_text("\u2022 " + str(sk))

    langs: list[str] = doc.get("languages") or []
    if langs:
        sb_section(T["languages"])
        for ll in langs:
            sb_text("\u2022 " + str(ll))

    pdf.set_text_color(15, 23, 42)
    main_y = 10.0

    def main_set(y: float) -> None:
        pdf.set_xy(MAIN_X, y)

    def main_section(title: str) -> None:
        nonlocal main_y
        main_y += 4
        main_set(main_y)
        sf(bold=True, size=9)
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
        sf(bold=bold, size=size)
        pdf.multi_cell(MAIN_W, 4.8, str(text), new_x="LEFT", new_y="NEXT")
        main_y = pdf.get_y()

    def main_desc(text: str) -> None:
        nonlocal main_y
        for line in parse_bullets(text):
            main_set(main_y)
            sf(size=9)
            pdf.multi_cell(MAIN_W - 2, 4.6, line, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

    summary = str(doc.get("summary") or "").strip()
    if summary:
        main_section(T["summary"])
        main_body(summary)
        main_y += 2

    exps: list[dict] = doc.get("experiences") or []
    if exps:
        main_section(T["experience"])
        for i, item in enumerate(exps):
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()
            main_set(main_y)
            sf(bold=True, size=10)
            rl = role or company or T["default_role"]
            if period:
                pdf.cell(MAIN_W * 0.65, 5.5, rl, new_x="RIGHT")
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(MAIN_W, 5.5, rl, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()
            if company and role:
                main_set(main_y)
                sf(size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(MAIN_W, 4.5, company, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()
            if loc:
                main_set(main_y)
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W, 4, loc, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()
            if desc:
                main_y += 0.8
                main_desc(desc)
            if i < len(exps) - 1:
                main_y += 3
        main_y += 2

    edus: list[dict] = doc.get("educations") or []
    if edus:
        main_section(T["education"])
        for i, item in enumerate(edus):
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            tl = school or degree or T["default_education"]
            main_set(main_y)
            sf(bold=True, size=10)
            if period:
                pdf.cell(MAIN_W * 0.65, 5.5, tl, new_x="RIGHT")
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(MAIN_W, 5.5, tl, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()
            if degree and school:
                main_set(main_y)
                sf(size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(MAIN_W, 4.5, degree, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()
            if desc:
                main_y += 0.8
                main_desc(desc)
            if i < len(edus) - 1:
                main_y += 2
    return bytes(pdf.output())
