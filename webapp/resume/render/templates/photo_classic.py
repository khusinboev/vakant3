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
    """Classic accent header with profile photo embedded in the top-right corner."""
    T = strings(lang)
    from fpdf import FPDF  # type: ignore[import]

    LM = 18.0
    PHOTO_SIZE = 32.0
    HDR_H = 48.0
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

    photo_url = str(doc.get("photo_url") or "").strip()
    photo_x = pdf.w - LM - PHOTO_SIZE
    photo_y = (HDR_H - PHOTO_SIZE) / 2
    photo_embedded = False
    if photo_url:
        photo_data = doc.get("photo_bytes")
        if photo_data:
            try:
                clipped = clip_photo(photo_data, shape="rounded")
                pdf.image(io.BytesIO(clipped), x=photo_x, y=photo_y, w=PHOTO_SIZE, h=PHOTO_SIZE)
                photo_embedded = True
            except Exception:
                pass
    if not photo_embedded:
        # Placeholder: white rounded-rect outline
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.rect(photo_x, photo_y, PHOTO_SIZE, PHOTO_SIZE, "D")

    text_w = pdf.w - 2 * LM - (PHOTO_SIZE + 5 if photo_url else 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(LM, 10)
    sf(bold=True, size=20)
    pdf.multi_cell(text_w, 8.5, str(doc.get("name") or T["default_name"]), new_x="LMARGIN", new_y="NEXT")

    pos = str(doc.get("position") or "").strip()
    if pos:
        pdf.set_x(LM)
        sf(size=11)
        pdf.set_text_color(220, 240, 238)
        pdf.cell(text_w, 5.5, pos, new_x="LMARGIN", new_y="NEXT")

    contacts: list[str] = doc.get("contacts") or []
    if contacts:
        pdf.set_x(LM)
        sf(size=8.5)
        pdf.set_text_color(185, 225, 220)
        pdf.cell(text_w, 4.5, " | ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")

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

    def desc_block(text: str) -> None:
        for line in parse_bullets(text):
            pdf.set_x(LM + 3)
            sf(size=9)
            pdf.multi_cell(UW - 3, 4.8, line, new_x="LMARGIN", new_y="NEXT")

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
                pdf.set_text_color(100, 116, 139)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 5.5, rl, new_x="LMARGIN", new_y="NEXT")
            if company and role:
                pdf.set_x(LM)
                sf(size=9)
                pdf.set_text_color(55, 80, 115)
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
                pdf.set_text_color(100, 116, 139)
                pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 5.5, tl, new_x="LMARGIN", new_y="NEXT")
            if degree and school:
                pdf.set_x(LM)
                sf(size=9)
                pdf.set_text_color(55, 80, 115)
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
        CHIP_PAD_H, CHIP_PAD_V, CHIP_GAP = 3.0, 1.2, 2.0
        CHIP_H = 5.5
        x_pos = LM
        chip_y = pdf.get_y()
        lr = min(255, ar + 195)
        lg = min(255, ag + 195)
        lb = min(255, ab + 195)
        for skill in skills:
            sf(size=8.5)
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

    langs: list[str] = doc.get("languages") or []
    if langs:
        section(T["languages"])
        pdf.set_x(LM)
        sf(size=9.5)
        pdf.multi_cell(UW, 4.8, ", ".join(str(ll) for ll in langs), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
