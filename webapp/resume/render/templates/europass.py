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
    """Europass-inspired: accent header with optional photo, two-column grid body."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    LM = 18.0
    RM = 10.0
    HDR_H = 40.0
    LABEL_W = 38.0
    CONTENT_X = LM + LABEL_W + 5.0
    CONTENT_W = 210.0 - CONTENT_X - RM
    PHOTO_SIZE = 26.0
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(True, 15)
    pdf.set_margins(LM, 0, RM)
    if has_reg:
        pdf.add_font("DejaVu", fname=DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=DEJAVU_BOLD)
    pdf.add_page()

    def sf(bold: bool = False, size: float = 10.0) -> None:
        pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    pdf.set_fill_color(ar, ag, ab)
    pdf.rect(0, 0, pdf.w, HDR_H, "F")

    photo_url = str(doc.get("photo_url") or "").strip()
    photo_x = pdf.w - RM - PHOTO_SIZE
    photo_y = (HDR_H - PHOTO_SIZE) / 2
    photo_embedded = False
    if photo_url:
        photo_data = doc.get("photo_bytes")
        if photo_data:
            try:
                clipped = clip_photo(photo_data, shape="square")
                pdf.image(io.BytesIO(clipped), x=photo_x, y=photo_y, w=PHOTO_SIZE, h=PHOTO_SIZE)
                photo_embedded = True
            except Exception:
                pass
    if not photo_embedded:
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.rect(photo_x, photo_y, PHOTO_SIZE, PHOTO_SIZE, "D")
        sf(size=7)
        pdf.set_text_color(220, 235, 232)
        pdf.set_xy(photo_x, photo_y + PHOTO_SIZE / 2 - 2)
        pdf.cell(PHOTO_SIZE, 4, T["photo"], align="C")

    text_w = pdf.w - 2 * LM - PHOTO_SIZE - 8
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(LM, 9)
    sf(bold=True, size=19)
    pdf.multi_cell(text_w, 8, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")

    pos = str(doc.get("position") or "").strip()
    if pos:
        pdf.set_x(LM)
        sf(size=10)
        pdf.set_text_color(210, 238, 235)
        pdf.cell(text_w, 5, pos, new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(HDR_H + 5)

    def grid_section(title: str) -> None:
        y = pdf.get_y() + 2
        pdf.set_fill_color(ar, ag, ab)
        pdf.rect(LM, y, LABEL_W + CONTENT_W + 5, 6.5, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(LM + 2, y + 0.5)
        sf(bold=True, size=9)
        pdf.cell(LABEL_W + CONTENT_W, 5.5, title.upper())
        pdf.set_text_color(15, 23, 42)
        pdf.set_y(y + 7.5)

    def grid_row(label: str, content: str) -> None:
        y_start = pdf.get_y() + 0.5
        pdf.set_xy(LM, y_start)
        sf(bold=True, size=8.5)
        pdf.set_text_color(ar, ag, ab)
        pdf.multi_cell(LABEL_W, 4.5, label, new_x="LMARGIN", new_y="NEXT")
        y_label_end = pdf.get_y()
        pdf.set_xy(CONTENT_X, y_start)
        sf(size=9)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(CONTENT_W, 4.5, str(content), new_x="LMARGIN", new_y="NEXT")
        y_content_end = pdf.get_y()
        y_end = max(y_label_end, y_content_end) + 0.5
        pdf.set_draw_color(215, 218, 224)
        pdf.set_line_width(0.1)
        pdf.line(LM, y_end, pdf.w - RM, y_end)
        pdf.set_y(y_end + 1)

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        grid_row(T["contact"], " \u00b7 ".join(str(c) for c in contacts))

    summary = str(doc.get("summary") or "").strip()
    if summary:
        grid_section(T["summary"])
        grid_row("", summary)

    exps: list[dict] = doc.get("experiences") or []
    if exps:
        grid_section(T["experience"])
        for item in exps:
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()
            y = pdf.get_y() + 1
            pdf.set_xy(LM, y)
            sf(bold=True, size=8)
            pdf.set_text_color(ar, ag, ab)
            pdf.multi_cell(LABEL_W, 4.5, period or " ", new_x="LMARGIN", new_y="NEXT")
            y_label_end = pdf.get_y()
            pdf.set_xy(CONTENT_X, y)
            sf(bold=True, size=10)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(CONTENT_W, 5, role or company or T["default_role"], new_x="LEFT", new_y="NEXT")
            if company and role:
                pdf.set_x(CONTENT_X)
                sf(size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(CONTENT_W, 4.5, company, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if loc:
                pdf.set_x(CONTENT_X)
                sf(size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(CONTENT_W, 4, loc, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if desc:
                for line in parse_bullets(desc):
                    pdf.set_x(CONTENT_X + 2)
                    sf(size=9)
                    pdf.multi_cell(CONTENT_W - 2, 4.6, line, new_x="LEFT", new_y="NEXT")
            y_end = max(y_label_end, pdf.get_y()) + 1
            pdf.set_draw_color(215, 218, 224)
            pdf.set_line_width(0.1)
            pdf.line(LM, y_end, pdf.w - RM, y_end)
            pdf.set_y(y_end + 1)

    edus: list[dict] = doc.get("educations") or []
    if edus:
        grid_section(T["education"])
        for item in edus:
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            y = pdf.get_y() + 1
            pdf.set_xy(LM, y)
            sf(bold=True, size=8)
            pdf.set_text_color(ar, ag, ab)
            pdf.multi_cell(LABEL_W, 4.5, period or " ", new_x="LMARGIN", new_y="NEXT")
            y_label_end = pdf.get_y()
            pdf.set_xy(CONTENT_X, y)
            sf(bold=True, size=10)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(CONTENT_W, 5, school or degree or T["default_education"], new_x="LEFT", new_y="NEXT")
            if degree and school:
                pdf.set_x(CONTENT_X)
                sf(size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(CONTENT_W, 4.5, degree, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            if desc:
                for line in parse_bullets(desc):
                    pdf.set_x(CONTENT_X + 2)
                    sf(size=9)
                    pdf.multi_cell(CONTENT_W - 2, 4.6, line, new_x="LEFT", new_y="NEXT")
            y_end = max(y_label_end, pdf.get_y()) + 1
            pdf.set_draw_color(215, 218, 224)
            pdf.set_line_width(0.1)
            pdf.line(LM, y_end, pdf.w - RM, y_end)
            pdf.set_y(y_end + 1)

    skills: list[str] = doc.get("skills") or []
    if skills:
        grid_row(T["skills"], ", ".join(str(s) for s in skills))
    langs: list[str] = doc.get("languages") or []
    if langs:
        grid_row(T["languages"], ", ".join(str(ll) for ll in langs))
    return bytes(pdf.output())
