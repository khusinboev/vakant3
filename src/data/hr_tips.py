# ============================================================
# src/data/hr_tips.py
# HR Maslahatlar — statik ma'lumotlar
# ============================================================

from typing import TypedDict

from src.i18n import DEFAULT_LANG, LANGS, normalize_lang

# Ko'p tilli matn: {"uz": ..., "ru": ..., "en": ...}. ru/en bo'lmasa uz ga qaytadi.
LocalizedText = dict[str, str]


class HrTip(TypedDict):
    """Ko'p tilli maslahat (eksport qilinadigan shakl)."""

    id: str
    title: LocalizedText
    summary: LocalizedText
    full_text: LocalizedText


class HrTipFlat(TypedDict):
    """Bitta til uchun tekislangan maslahat."""

    id: str
    title: str
    summary: str
    full_text: str


# O'zbekcha manba matnlar. Tarjimalar TIP_TRANSLATIONS da saqlanadi.
_HR_TIPS_UZ: list[dict[str, str]] = [
    {
        "id": "cv-structure",
        "title": "Samarali rezyume qanday tuziladi?",
        "summary": "Rezyume 1–2 sahifada, aniq formatda bo'lishi kerak. HR 6 soniyada qaror qiladi — birinchi taassurot hal qiluvchi.",
        "full_text": (
            "💡 <b>Samarali rezyume qanday tuziladi?</b>\n\n"
            "<b>Asosiy qoidalar:</b>\n"
            "• Hajm: <b>1 sahifa</b> (5 yildan kam tajriba), <b>2 sahifa</b> (ko'p tajriba)\n"
            "• HR rezyumeni o'rtacha <b>6–10 soniya</b> ko'zdan kechirgandan so'ng qaror qiladi\n"
            "• Shrift: Arial, Calibri yoki Times New Roman, <b>10–12pt</b>\n\n"
            "<b>To'g'ri tartib:</b>\n"
            "1. <b>Ism va kontaktlar</b> — telefon, email, LinkedIn/GitHub (agar mavjud)\n"
            "2. <b>Kasbiy maqsad</b> (2–3 jumla) — qaysi lavozimga va nima uchun\n"
            "3. <b>Tajriba</b> — yangi ishdan qadimgisiga qarab (oxirgi ish birinchi)\n"
            "4. <b>Ta'lim</b> — diplom, kurslar, sertifikatlar\n"
            "5. <b>Ko'nikmalar</b> — texnik va qo'shimcha (dasturlar, tillar)\n\n"
            "<b>Nima yozmaslik kerak:</b>\n"
            "✗ Rasm (agar so'ralmagan bo'lsa)\n"
            "✗ Tug'ilgan sana, jinsi, millati (ko'pchilik xorijiy kompaniyalarda)\n"
            "✗ 'Mas'uliyatli, ​​tirishqoq' — bu klishe, dalil bilan ko'rsating\n"
            "✗ Har bir lavozim uchun 1 sahifadan ko'proq\n\n"
            "<b>Ish tavsifi uchun formula:</b>\n"
            "<i>Fe'l + nima + natija</i>\n"
            "«Savdo jarayonini avtomatlashtirib, oy davomida 30% vaqt tejaladim» ✓\n"
            "«Savdo bilan shug'ullandim» ✗\n\n"
            "<b>Pro maslahat:</b> Har bir ish e'loniga rezyumeni moslang. E'londagi asosiy kalit so'zlarni rezyumegizda ishlating — ATS (avtomatik saralash tizimi) uchun juda muhim."
        ),
    },
    {
        "id": "interview-prep",
        "title": "Intervyu oldidan tayyorgarlik: to'liq qo'llanma",
        "summary": "Intervyuga tayyorgarlik: kompaniyani o'rganish, STAR usuli bilan javob berish, to'g'ri savollar berish va maosh haqida gaplashish.",
        "full_text": (
            "💡 <b>Intervyu oldidan tayyorgarlik: to'liq qo'llanma</b>\n\n"
            "<b>1 kun oldin:</b>\n"
            "• Kompaniyaning <b>veb-sayti, ijtimoiy tarmoqlari va yangiliklari</b>ni o'qing\n"
            "• Ish tavsifini qayta o'qib, <b>3–5 ta o'z tajribangizdan misol</b> tayyorlang\n"
            "• <b>STAR usuli</b>: Vaziyat → Vazifa → Harakat → Natija\n\n"
            "<b>Eng ko'p beriladigan savollar va ularga javob:</b>\n\n"
            "❓ <i>«O'zingizni tanishtiring»</i>\n"
            "Ish tajribangizni qisqacha (2 daqiqa), ushbu lavozimga bog'liq holda aytib bering.\n\n"
            "❓ <i>«Kuchli va zaif tomonlaringiz»</i>\n"
            "Zaif tomonni ayting, lekin uni qanday yaxshilayotganingizni ham qo'shing.\n\n"
            "❓ <i>«5 yil keyingi rejalaringiz»</i>\n"
            "Kompaniyada o'sishni istaganingizni aks ettiring — lekin shoshilmang.\n\n"
            "<b>Maosh haqida:</b>\n"
            "• Avval ular so'rasin — birinchi raqamni siz aytmang\n"
            "• Bozor bahosini oldindan o'rganib boring (hh.uz, glassdoor)\n"
            "• Diapazon bering, aniq raqam emas\n\n"
            "<b>Siz ham savol bering:</b>\n"
            "• «Jamoada qanday ish oqimi?»\n"
            "• «Ushbu lavozimda muvaffaqiyatni qanday o'lchaysiz?»\n"
            "• «Eng katta joriy qiyinchilik nima?»\n\n"
            "<b>Nima qilmang:</b>\n"
            "✗ Oldingi ish beruvchini tanqid qilmang\n"
            "✗ Telefoningizni stolga ochiq qo'ymang\n"
            "✗ «Javobim yo'q» emas, «Hozir bilmayman, lekin shunday yondashaman...» deying"
        ),
    },
    {
        "id": "salary-negotiation",
        "title": "Maosh muzokarasi: haq talab qilish san'ati",
        "summary": "Ko'pchilik haqiqiy bozor bahosidan 20–30% kam ishlaydi. Oddiy muzokarani bilish sizga yiliga millionlar qo'shishi mumkin.",
        "full_text": (
            "💡 <b>Maosh muzokarasi: haq talab qilish san'ati</b>\n\n"
            "<b>Nima uchun muzokara qilish kerak:</b>\n"
            "Tadqiqotlarga ko'ra, ish beruvchilar birinchi taklifni qabul qilgan nomzodlar bilan «<i>pul ustida gap yo'q</i>» deb o'ylashadi — bu ko'pincha <b>20–30% past to'lash</b> demakdir.\n\n"
            "<b>Muzokara bosqichlari:</b>\n\n"
            "<b>1. Bozorni bilish</b>\n"
            "• hh.uz, glassdoor.com, linkedin.com/salary saytlarini tekshiring\n"
            "• Shu lavozimda ishlayotganlar bilan gaplashing\n"
            "• Diapazon aniqlang: minimal, maqsad, maksimal\n\n"
            "<b>2. Taklif keyin muzokara qilish</b>\n"
            "• Taklifni olgandan so'ng: <i>«Rahmat, bu juda yaxshi. Men bir oz ko'rib chiqishim mumkinmi?»</i>\n"
            "• Raqam yozmang — telefonda gapirishdan qo'rqmang\n\n"
            "<b>3. Kontr-taklif berish</b>\n"
            "• Bir raqam emas, diapazon bering: <i>«Men X dan Y gacha ko'rmoqda edim»</i>\n"
            "• Asoslang: bozor baho + o'z qiymatiz\n\n"
            "<b>4. Agar maosh qo'zg'atilmasa:</b>\n"
            "Boshqa narsalarni so'rang:\n"
            "• Ish boshlash bonusi\n"
            "• 3 oydan so'ng qayta ko'rib chiqish va'dasi\n"
            "• Uzoqdan ishlash imkoniyati\n"
            "• Qo'shimcha dam olish kunlari\n\n"
            "<b>Muhim ibora:</b>\n"
            "<i>«Men ushbu imkoniyatdan juda manfaatdorman. [RAQAM] atrofida kelisha olamizmi?»</i> — bu oddiy, to'g'ridan-to'g'ri va professional."
        ),
    },
]


# ============================================================
# Ko'p tillilik qatlami
# ============================================================

_PROSE_FIELDS: tuple[str, ...] = ("title", "summary", "full_text")

# Tarjimalar shu yerga qo'shiladi: tip_id -> {maydon: {til: matn}}.
# ru/en tarjimalari src/data/translations/hr_tips_{ru,en}.py da saqlanadi
# (har biri tip_id -> {maydon: matn} shaklida); shu yerda ular
# {tip_id: {maydon: {til: matn}}} shakliga birlashtiriladi.
from src.data.translations.hr_tips_en import TRANSLATIONS as _TIPS_EN
from src.data.translations.hr_tips_ru import TRANSLATIONS as _TIPS_RU


def _merge(ru: dict[str, dict[str, str]], en: dict[str, dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    """ru/en modullarini {id: {maydon: {til: matn}}} shakliga birlashtiradi."""
    merged: dict[str, dict[str, dict[str, str]]] = {}
    ids = set(ru) | set(en)
    for item_id in ids:
        fields = set(ru.get(item_id, {})) | set(en.get(item_id, {}))
        merged[item_id] = {}
        for field in fields:
            lang_map: dict[str, str] = {}
            ru_text = ru.get(item_id, {}).get(field)
            en_text = en.get(item_id, {}).get(field)
            if ru_text:
                lang_map["ru"] = ru_text
            if en_text:
                lang_map["en"] = en_text
            merged[item_id][field] = lang_map
    return merged


TIP_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = _merge(_TIPS_RU, _TIPS_EN)


def _localized(tip_id: str, field: str, uz_value: str) -> LocalizedText:
    value: LocalizedText = {DEFAULT_LANG: uz_value}
    extra = TIP_TRANSLATIONS.get(tip_id, {}).get(field, {})
    for lang in LANGS:
        text = extra.get(lang)
        if isinstance(text, str) and text.strip():
            value[lang] = text
    return value


def _build_tip(source: dict[str, str]) -> HrTip:
    tip_id = source["id"]
    built: dict = {"id": tip_id}
    for field in _PROSE_FIELDS:
        built[field] = _localized(tip_id, field, source[field])
    return built  # type: ignore[return-value]


HR_TIPS: list[HrTip] = [_build_tip(item) for item in _HR_TIPS_UZ]


def pick_text(value: LocalizedText | str, lang: str = DEFAULT_LANG) -> str:
    if isinstance(value, str):
        return value
    normalized = normalize_lang(lang)
    text = value.get(normalized)
    if isinstance(text, str) and text.strip():
        return text
    return value.get(DEFAULT_LANG, "")


def _flatten(tip: HrTip, lang: str) -> HrTipFlat:
    return {
        "id": tip["id"],
        "title": pick_text(tip["title"], lang),
        "summary": pick_text(tip["summary"], lang),
        "full_text": pick_text(tip["full_text"], lang),
    }


def get_tip_by_id(tip_id: str) -> HrTip | None:
    """Backward-compat: ko'p tilli maslahatni id bo'yicha qaytaradi."""
    return next((t for t in HR_TIPS if t["id"] == tip_id), None)


def get_tips(lang: str = DEFAULT_LANG) -> list[HrTipFlat]:
    return [_flatten(t, lang) for t in HR_TIPS]


def get_tip(tip_id: str, lang: str = DEFAULT_LANG) -> HrTipFlat | None:
    tip = get_tip_by_id(tip_id)
    return _flatten(tip, lang) if tip else None
