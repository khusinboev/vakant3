# ============================================================
# src/data/law_articles.py
# O'zbekiston Respublikasi mehnat qonunchiligi maqolalari
# Asosiy manbalar:
#   Mehnat Kodeksi (MK): https://lex.uz/uz/docs/5401895
#   Bandlik qonuni (2021): https://lex.uz/uz/docs/6235875
#   Prof. soyuzlar qonuni: https://lex.uz/uz/docs/111711
#   Davlat ijtimoiy sug'urta: https://lex.uz/uz/docs/4256286
#   Mehnat muhofazasi qonuni: https://lex.uz/uz/docs/2712229
#   Pensiya ta'minoti qonuni: https://lex.uz/uz/docs/419121
# ============================================================

from typing import TypedDict

from src.i18n import DEFAULT_LANG, LANGS, normalize_lang

# Ko'p tilli matn: {"uz": ..., "ru": ..., "en": ...}. ru/en bo'lmasa uz ga qaytadi.
LocalizedText = dict[str, str]


class LawArticle(TypedDict):
    """Ko'p tilli maqola (eksport qilinadigan shakl)."""

    id: str
    category: LocalizedText
    category_id: str
    title: LocalizedText
    summary: LocalizedText
    full_text: LocalizedText
    source_url: str
    source_label: LocalizedText


class LawArticleFlat(TypedDict):
    """Bitta til uchun tekislangan maqola (get_articles/get_article qaytaradi)."""

    id: str
    category: str
    category_id: str
    title: str
    summary: str
    full_text: str
    source_url: str
    source_label: str


# O'zbekcha manba matnlar. Tarjimalar ARTICLE_TRANSLATIONS da saqlanadi.
_ARTICLES_UZ: list[dict[str, str]] = [
    {
        "id": "worktime-norm",
        "category": "Ish vaqti",
        "title": "Kunlik va haftalik ish vaqti me'yori",
        "summary": "Oddiy ish rejimida haftalik 40 soat, kuniga 8 soat. Ayrim toifalar uchun qisqartirilgan me'yorlar belgilangan.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 116–117-moddalar</b>\n\n"
            "<b>Oddiy ish vaqti me'yori:</b>\n"
            "Haftalik ish vaqti <b>40 soatdan</b> oshmasligi kerak. 5 kunlik ish haftasida kunlik ish vaqti <b>8 soat</b>, 6 kunlik ish haftasida esa <b>7 soat</b> (shanba kuni — 5 soat).\n\n"
            "<b>Qisqartirilgan ish vaqti (116-modda):</b>\n"
            "• 16 yoshgacha bo'lganlar — <b>24 soat/hafta</b>\n"
            "• 16–18 yoshlilar — <b>36 soat/hafta</b>\n"
            "• I va II guruh nogironlar — <b>36 soat/hafta</b>\n"
            "• Zararli yoki og'ir sharoitlarda ishlaydigan xodimlar — <b>36 soat/hafta</b>\n\n"
            "<b>Yarim stavkali ish:</b>\n"
            "Ish beruvchi va xodim kelishuvi asosida yarim kunlik yoki yarim haftalik ish tartibi belgilanishi mumkin. Bu holda ish haqi haqiqatda ishlangan vaqt uchun to'lanadi.\n\n"
            "<b>Muhim:</b> Qisqartirilgan ish vaqtida to'liq ish vaqtidek ish haqi to'lanadi (nogironlar va yoshlar uchun)."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-116",
        "source_label": "Mehnat Kodeksi, 116–117-moddalar",
    },
    {
        "id": "overtime",
        "category": "Ish vaqti",
        "title": "Ortiqcha ish vaqti va unga haq to'lash",
        "summary": "Kuniga 2 soatdan, yilda 120 soatdan oshmasligi kerak. Ortiqcha soatlar 1.5–2 barobar haq bilan to'lanadi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 120–121, 157-moddalar</b>\n\n"
            "<b>Ortiqcha ish vaqtining cheklovlari:</b>\n"
            "• Har bir xodim uchun kuniga <b>2 soatdan</b> ko'p bo'lmasligi kerak\n"
            "• Bir yil davomida <b>120 soatdan</b> oshmasligi kerak\n"
            "• Ketma-ket ikki kun ortiqcha ishlash man etiladi\n\n"
            "<b>Kimlar ortiqcha ishlata olmaydi:</b>\n"
            "• 18 yoshgacha bo'lganlar\n"
            "• Homilador ayollar\n"
            "• Uch yoshgacha bola tarbiyalayotgan onalar\n"
            "• I va II guruh nogironlar (agar tibbiy ruxsat bo'lmasa)\n\n"
            "<b>To'lov tartibi (157-modda):</b>\n"
            "• Dam olish kunlarida yoki bayram kunlarida ishlash — <b>ikki barobar</b> haq\n"
            "• Doimiy ish vaqtidan keyin birinchi <b>2 soat</b> — kamida <b>1.5 barobar</b>\n"
            "• Keyingi soatlar — kamida <b>2 barobar</b>\n\n"
            "<b>Muhim:</b> Xodim ortiqcha ishlash o'rniga boshqa kunlarda dam olish talab qilishi ham mumkin (qo'shimcha dam olish kuni)."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-120",
        "source_label": "Mehnat Kodeksi, 120–121, 157-moddalar",
    },
    {
        "id": "annual-leave",
        "category": "Ta'til",
        "title": "Yillik ta'til: muddati va to'lov tartibi",
        "summary": "Asosiy ta'til kamida 15 ish kuni. Ayrim toifalar (pedagog, tibbiyot, nogironlar) uchun 18–30 ish kunigacha uzaytirilgan ta'til.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 134–136-moddalar</b>\n\n"
            "<b>Asosiy ta'til muddati:</b>\n"
            "Barcha xodimlar uchun yillik asosiy ta'til kamida <b>15 ish kuni</b>. Ko'pchilik korxonalarda mehnat shartnomasi yoki jamoa shartnomasi bilan 18–21 ish kunicha belgilanadi.\n\n"
            "<b>Uzaytirilgan asosiy ta'til (135-modda):</b>\n"
            "• Pedagog xodimlar — <b>30 ish kuni</b>\n"
            "• Tibbiyot xodimlari — <b>18–30 ish kuni</b> (mutaxassislik bo'yicha)\n"
            "• I va II guruh nogironlar — <b>30 ish kuni</b>\n"
            "• Yoshlar (18 yoshgacha) — <b>30 ish kuni</b>\n\n"
            "<b>Qo'shimcha ta'til:</b>\n"
            "• Zararli yoki og'ir ish sharoiti — <b>kamida 6 qo'shimcha kun</b>\n"
            "• Ko'p smenali ish — alohida tartib\n"
            "• Uzoq xizmat staji uchun — jamoa shartnomasi asosida\n\n"
            "<b>Ta'til haqi:</b>\n"
            "Ta'til oldidan o'rtacha kunlik ish haqiga asoslanib, <b>ta'til boshlanishidan 3 kun oldin</b> to'liq to'lanishi shart.\n\n"
            "<b>Muhim:</b> Ta'tilni pul bilan almashtirishga <b>faqat ishdan bo'shaganda</b> ruxsat etiladi. Ish paytida ta'tilni pulga o'xshatish qonunga ziddir."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-134",
        "source_label": "Mehnat Kodeksi, 134–136-moddalar",
    },
    {
        "id": "sick-leave",
        "category": "Ijtimoiy kafolatlar",
        "title": "Kasallik varaqasi: to'lash tartibi va miqdori",
        "summary": "Kasallik varaqasi to'lovlari xizmat muddatiga qarab 60%–100% orasida. Ijtimoiy sug'urta fondi to'laydi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 280–281-moddalar va «Davlat ijtimoiy sug'urtasi» qonuni</b>\n\n"
            "<b>Kim to'laydi:</b>\n"
            "Kasallik varaqasi bo'yicha nafaqa <b>davlat ijtimoiy sug'urta fondidan</b> to'lanadi, ish beruvchi emas. Ish beruvchi faqat fond qo'shimcha to'lamagan hollarda farqni to'laydi (ichki qoidaga ko'ra).\n\n"
            "<b>To'lov foizi (xizmat muddatiga qarab):</b>\n"
            "• Xizmat muddati <b>5 yilgacha</b> — o'rtacha ish haqining <b>60%</b>\n"
            "• <b>5 yildan 8 yilgacha</b> — <b>80%</b>\n"
            "• <b>8 yil va undan ko'p</b> — <b>100%</b>\n\n"
            "<b>Maxsus holatlarda 100% to'lov:</b>\n"
            "• Mehnat shikastlanishi yoki kasb kasalligi\n"
            "• 3 va undan ko'p farzand tarbiyalayotgan ota-onalar\n"
            "• I va II guruh nogironlar\n"
            "• Harbiy xizmat o'taganlarga (veteran guvohnomasi bo'lsa)\n\n"
            "<b>Vaqt chegaralari:</b>\n"
            "• Oddiy kasallik: <b>30 kungacha</b> (kerak bo'lsa uzaytiriladi)\n"
            "• Davolash muassasasida yotqizib davolash: cheklovsiz\n\n"
            "<b>Muhim:</b> Kasallik varaqasini qo'lga kiritgandan so'ng <b>6 oy ichida</b> ish beruvchiga topshirish kerak."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-280",
        "source_label": "Mehnat Kodeksi, 280–281-moddalar",
    },
    {
        "id": "labor-contract",
        "category": "Mehnat shartnomasi",
        "title": "Mehnat shartnomasi tuzish: majburiy shartlar",
        "summary": "Mehnat shartnomasi yozma shaklda tuzilishi shart. Majburiy shartlar: ish joyi, lavozim, maosh miqdori, ish vaqti.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 74–77-moddalar</b>\n\n"
            "<b>Shartnoma shakli:</b>\n"
            "Mehnat shartnomasi <b>yozma shaklda</b> tuziladi. Og'zaki kelishuv qonuniy kuchga ega emas. Shartnoma ikki nusxada imzolanadi: biri xodimda, biri ish beruvchida saqlanadi.\n\n"
            "<b>Majburiy shartlar (76-modda):</b>\n"
            "1. Ish joyi (korxona nomi va manzili)\n"
            "2. Xodimning lavozimi yoki kasbi\n"
            "3. Mehnat faoliyati boshlanadigan sana\n"
            "4. Ish haqi miqdori va to'lash muddati\n"
            "5. Ish vaqti va dam olish tartibi\n"
            "6. Ijtimoiy sug'urta shartlari\n\n"
            "<b>Shartnoma muddati:</b>\n"
            "• <b>Muddatsiz</b> — asosiy tur (afzalroq)\n"
            "• <b>Muddatli</b> — maksimal <b>5 yil</b>; faqat qonunda ko'rsatilgan asoslarda tuziladi (masalan, mavsumiy ish, loyiha)\n\n"
            "<b>Sinov muddati:</b>\n"
            "Shartnomada sinov muddati ko'rsatilishi mumkin — maksimal <b>3 oy</b> (rahbar lavozimlar uchun <b>6 oy</b>).\n\n"
            "<b>Muhim:</b> Agar xodim ish boshlab ketsa, lekin shartnoma imzolanmagan bo'lsa — bu <b>ish beruvchi uchun ma'muriy javobgarlik</b> sababi. Xodimning huquqlari baribir himoyalanadi."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-74",
        "source_label": "Mehnat Kodeksi, 74–77-moddalar",
    },
    {
        "id": "probation",
        "category": "Mehnat shartnomasi",
        "title": "Sinov muddati: qoidalar va cheklovlar",
        "summary": "Sinov muddati odatda 3 oy, rahbarlar uchun 6 oy. Yoshlar, homiladorlar va boshqa toifalar uchun sinov muddat belgilanmaydi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 84-modda</b>\n\n"
            "<b>Sinov muddat chegaralari:</b>\n"
            "• Oddiy xodimlar uchun — <b>3 oygacha</b>\n"
            "• Rahbar lavozimlar (direktor, bosh buxgalter, filial mudiri) — <b>6 oygacha</b>\n"
            "• Mavsumiy ish (6 oydan kam) — <b>2 haftadan oshmasligi</b> kerak\n\n"
            "<b>Sinov muddat belgilanmaydi (84-modda 2-qismi):</b>\n"
            "• 18 yoshgacha bo'lganlar\n"
            "• Homilador ayollar va 3 yoshgacha bola bilan onalar\n"
            "• Kasbiy musobaqa (konkurs) asosida qabul qilinganlar\n"
            "• Boshqa korxonadan o'tkazish yo'li bilan kelganlar\n"
            "• O'quv muassasasini tamomlaganlar — birinchi ish joylari uchun\n"
            "• Nogironlar (tibbiy ko'rsatma bo'lsa)\n\n"
            "<b>Sinov davrida xodim huquqlari:</b>\n"
            "Sinov muddati davomida xodim to'liq mehnat qonunchiligi himoyasidan foydalanadi. Ish haqi, ta'til, kasallik varaqasi — barchasi oddiy tartibda.\n\n"
            "<b>Sinov muvaffaqiyatsiz tugasa:</b>\n"
            "Ish beruvchi <b>3 kun oldin yozma ogohlantirish</b> berishi shart. Xodim bu qarorga <b>sud orqali ijaroz bildirishi</b> mumkin."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-84",
        "source_label": "Mehnat Kodeksi, 84-modda",
    },
    {
        "id": "dismissal",
        "category": "Ishdan bo'shatish",
        "title": "Ishdan bo'shatish: asoslar va tartib",
        "summary": "Xodim ixtiyoriy ketishda 2 hafta oldin ogohlantiradi. Ish beruvchi tomonidan bo'shatishda qat'iy tartib va qonuniy asoslar talab etiladi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 100–104-moddalar</b>\n\n"
            "<b>Xodimning o'z ixtiyori bilan ketishi:</b>\n"
            "Xodim istagan vaqtda shartnomani bekor qilishi mumkin — buning uchun <b>14 kun oldin yozma ariza</b> beradi. Ish beruvchi kelishilgan holda bu muddatni qisqartirishi mumkin.\n\n"
            "<b>Ish beruvchi tomonidan bo'shatish asoslari (100-modda):</b>\n"
            "• Korxona tugatilishi yoki shtatlar qisqarishi\n"
            "• Xodim lavozimiga mos kelmasligi (attestatsiya orqali isbotlangan)\n"
            "• Tartib-intizom buzilishi (oldindan ogohlantirish bo'lgan holda)\n"
            "• Ishga kelmay qolish (sababsiz, 3 soatdan ko'p)\n"
            "• Ishda mast holda kelish\n"
            "• Maxfiy ma'lumotni oshkor etish\n\n"
            "<b>Ogohlantiruv muddati (shtatlar qisqarishi uchun):</b>\n"
            "Kamida <b>2 oy oldin</b> yozma ogohlantirish berilishi va boshqa ish taklif etilishi shart.\n\n"
            "<b>Kim bo'shatilmaydi:</b>\n"
            "• <b>Homilador ayollar</b> — hech qanday asosda bo'shatilmaydi\n"
            "• <b>3 yoshgacha bola bilan onalar</b> — shtatlar qisqarishida bo'shatilmaydi\n"
            "• <b>Ta'tildagi xodimlar</b> — ta'til davomida bo'shatilmaydi\n"
            "• <b>Kasallik varaqasidagilar</b> — kasallik vaqtida bo'shatilmaydi\n\n"
            "<b>Muhim:</b> Nohaq bo'shatilgan xodim <b>1 oy ichida</b> sudga murojaat qilib, <b>ishga qayta tiklanish va o'tkazib yuborilgan vaqt uchun ish haqi</b> talab qilishi mumkin."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-100",
        "source_label": "Mehnat Kodeksi, 100–104-moddalar",
    },
    {
        "id": "min-wage",
        "category": "Ish haqi",
        "title": "Eng kam ish haqi (MROT) va uning ta'siri",
        "summary": "O'zbekistonda eng kam ish haqi (MROT) Hukumat qarori bilan belgilanadi va har yili oshirib boriladi. 2025 yil uchun MROT — 980 000 so'm/oy.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 153-modda va Hukumat qarorlari</b>\n\n"
            "<b>Hozirgi holat (2025 yil):</b>\n"
            "O'zbekiston Respublikasi Vazirlar Mahkamasining qarori bilan eng kam ish haqi (MROT) <b>980 000 so'm/oy</b> etib belgilangan.\n\n"
            "<b>MROT qayerda qo'llanadi:</b>\n"
            "• Hech bir xodim ish haqini MROTdan past olmaydi (to'liq stavkada)\n"
            "• Agar ish haqi MROT dan past bo'lsa — bu <b>ma'muriy huquqbuzarlik</b>\n"
            "• Nafaqalar va kompensatsiyalar hisoblashda asosiy ko'rsatkich sifatida ishlatiladi\n\n"
            "<b>Amaliy ma'lumot:</b>\n"
            "• MROT — bu faqat minimal chegara. Ish beruvchi har qanday yuqori miqdorni to'lashi mumkin\n"
            "• Jamoa shartnomasida MROT dan yuqori minimal ish haqi belgilanishi mumkin\n"
            "• Yarim stavkada ishlayotganlarga MROT ning yarmi to'lanadi\n\n"
            "<b>Soliq imtiyozlari:</b>\n"
            "Bazaviy hisoblash miqdori (BHM) — bu MROTning 10%i bo'lib, daromad solig'i chegirmalarini hisoblashda ishlatiladi.\n\n"
            "<b>Muhim:</b> MROT har yili qayta ko'rib chiqiladi. Eng yangi rasmiy qiymat uchun: stat.uz yoki lex.uz saytlarini kuzatib boring."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-153",
        "source_label": "Mehnat Kodeksi, 153-modda",
    },
    {
        "id": "maternity",
        "category": "Ijtimoiy kafolatlar",
        "title": "Homilador ayollar va yosh onalar huquqlari",
        "summary": "Homilador ayollar ishdan bo'shatilmaydi, tunda ishlatilmaydi. Dekret ta'tili 132 kun. Bola 3 yoshgacha ixtiyoriy ta'til bilan ish joyi saqlanadi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 225–228-moddalar</b>\n\n"
            "<b>Himoya (225-modda):</b>\n"
            "• Homiladorligi ma'lum bo'lgan ayolni <b>hech qanday asosda ishdan bo'shatish man etiladi</b>\n"
            "• Ularni tunda (22:00–06:00) ishlashga majbur etish mumkin emas\n"
            "• Ortiqcha ish, xizmat safari, zararli ish — faqat yozma rozilik bilan\n\n"
            "<b>Dekret ta'tili (227-modda):</b>\n"
            "• Oddiy tug'ruq — <b>70 kun oldin + 70 kun keyin = 140 kun</b>\n"
            "• Murakab tug'ruq — <b>70 kun oldin + 86 kun keyin = 156 kun</b>\n"
            "• Ko'p tug'ilish (egizak va h.) — <b>84 kun oldin + 110 kun keyin = 194 kun</b>\n"
            "• Dekret nafaqasi — o'rtacha ish haqining <b>100%</b>\n\n"
            "<b>Bola parvarishi ta'tili (228-modda):</b>\n"
            "• Bola <b>3 yoshga</b> to'lguncha ixtiyoriy ta'til olish mumkin\n"
            "• Bu vaqtda <b>ish joyi va lavozim saqlanadi</b>\n"
            "• Xizmat stajiga hisoblanadi\n"
            "• Nafaqa — minimal ish haqi asosida (ijtimoiy sug'urta fondidan)\n\n"
            "<b>Muhim:</b> Ota ham (yoki boshqa qarindosh) bola parvarishi ta'tilini olishi mumkin. Bu faqat onaning huquqi emas."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-225",
        "source_label": "Mehnat Kodeksi, 225–228-moddalar",
    },
    {
        "id": "wage-delay",
        "category": "Ish haqi",
        "title": "Ish haqi kechiktirilganda xodim huquqlari",
        "summary": "Ish haqi oyda kamida 2 marta to'lanishi shart. Kechiktirish uchun ish beruvchi peniya to'laydi va ma'muriy javobgarlikka tortiladi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 164–166-moddalar</b>\n\n"
            "<b>To'lash muddati (164-modda):</b>\n"
            "Ish haqi <b>oyda kamida 2 marta</b> to'lanishi shart. Aniq sanalar mehnat yoki jamoa shartnomasida ko'rsatiladi. Ta'til va bayram kunlarida to'lov muddati oldinroq ko'chadi.\n\n"
            "<b>Kechiktirilganda peniya:</b>\n"
            "Har bir kechiktirilgan kun uchun: O'zbekiston Markaziy banki qayta moliyalash stavkasining <b>1/300 qismi</b> miqdorida peniya to'lanadi.\n\n"
            "<b>Xodimning harakatlari:</b>\n"
            "1. Ish beruvchiga yozma murojaat\n"
            "2. Mehnat inspeksiyasiga shikoyat (ish joyidagi yoki hududiy)\n"
            "3. Prokuraturaga murojaat\n"
            "4. Sudga da'vo (3 yillik muddatlama doirasida)\n\n"
            "<b>Ish beruvchi uchun javobgarlik:</b>\n"
            "• Ma'muriy: 5 BHMdan 20 BHMgacha jarima\n"
            "• Qasddan 3 oydan ko'proq kechiktirish — <b>jinoiy javobgarlik</b> (3 yilgacha ozodlikdan mahrum etish)\n\n"
            "<b>Muhim:</b> Ish beruvchi ish haqini naqd pul o'rniga tovar yoki xizmatlar bilan to'lashga haqli emas — bu qonunga zid."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-164",
        "source_label": "Mehnat Kodeksi, 164–166-moddalar",
    },
    {
        "id": "holidays",
        "category": "Ish vaqti",
        "title": "Dam olish kunlari va davlat bayramlari",
        "summary": "Haftalik dam olish: shanba va yakshanba. 9 ta rasmiy bayram kuni. Bayram kunida ishlash 2 barobar yoki qo'shimcha dam olish bilan kompensatsiya qilinadi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 146–149-moddalar</b>\n\n"
            "<b>Haftalik dam olish (146-modda):</b>\n"
            "5 kunlik ish haftasida — <b>shanba va yakshanba</b>. 6 kunlik haftada — <b>yakshanba</b>. Ish beruvchi muayyan kunda dam olishni o'zgartirishi mumkin (masalan, sanoat korxonalari), lekin xodim roziligisiz emas.\n\n"
            "<b>Rasmiy bayram kunlari O'zbekistonda:</b>\n"
            "• 1–2 yanvar — Yangi yil\n"
            "• 8 mart — Xalqaro xotin-qizlar kuni\n"
            "• 21–23 mart — Navro'z bayrami\n"
            "• 9 may — Xotira va qadrlash kuni\n"
            "• 1 sentyabr — Mustaqillik kuni\n"
            "• 1 oktyabr — O'qituvchi va murabbiylar kuni\n"
            "• 8 dekabr — O'zbekiston Konstitutsiyasi kuni\n"
            "• Ramazon hayiti (2 kun)\n"
            "• Qurbon hayiti (2 kun)\n\n"
            "<b>Bayram kunida ishlash (157-modda):</b>\n"
            "• <b>2 barobar</b> ish haqi yoki\n"
            "• Oddiy ish haqi + <b>boshqa kunda dam olish</b> (xodim tanloviga ko'ra)\n\n"
            "<b>Muhim:</b> Bayram kuni boshqa ish kuniga to'g'ri kelsa (du–juma), u avvalgi yoki keyingi ish kuniga ko'chiriladi — bu Vazirlar Mahkamasi qarori bilan e'lon qilinadi."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-146",
        "source_label": "Mehnat Kodeksi, 146–149-moddalar",
    },
    {
        "id": "labor-dispute",
        "category": "Mehnat nizolari",
        "title": "Mehnat nizolarini hal qilish tartibi",
        "summary": "Individual nizo avval mehnat nizolari komissiyasida, so'ng sudda ko'riladi. Nohaq bo'shatish bo'yicha sudga 1 oy ichida murojaat etiladi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 271–275-moddalar</b>\n\n"
            "<b>Nizo turlari:</b>\n"
            "• <b>Individual nizo</b> — bitta xodim va ish beruvchi o'rtasidagi kelishmovchilik\n"
            "• <b>Jamoaviy nizo</b> — kasaba uyushmasi yoki xodimlar guruhi ishtirokida\n\n"
            "<b>Individual nizo ko'rish tartibi:</b>\n\n"
            "<b>1-bosqich: Mehnat nizolari komissiyasi (MNK)</b>\n"
            "• Korxona ichida tashkil etiladi (agar 15+ xodim bo'lsa)\n"
            "• Ariza berilgandan so'ng <b>10 kun ichida</b> ko'rib chiqiladi\n"
            "• Qaror bajarilishi — <b>10 kun ichida</b>\n\n"
            "<b>2-bosqich: Sud</b>\n"
            "• MNK qaroriga rozi bo'lmaslik yoki MNK yo'qligi holatida\n"
            "• Nohaq bo'shatish bo'yicha — ariza <b>1 oy ichida</b> berilishi shart\n"
            "• Ish haqi bo'yicha da'vo — <b>3 yil ichida</b>\n"
            "• Boshqa nizolar — <b>3 oy ichida</b>\n\n"
            "<b>Sud qarorini bajarish:</b>\n"
            "Ishga qayta tiklash haqidagi sud qaroriga — ish beruvchi <b>zudlik bilan</b> (keyingi ish kuniyoq) bajarishga majbur.\n\n"
            "<b>Mehnat inspeksiyasi:</b>\n"
            "Har qanday vaqtda <b>mehnat inspeksiyasiga</b> murojaat qilish mumkin — ular tekshiruv o'tkazib, jarima belgilaydi. Bu sud jarayoniga muqobil emas, paralel ravishda amalga oshiriladi."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-271",
        "source_label": "Mehnat Kodeksi, 271–275-moddalar",
    },
    # ── Qo'shimcha maqolalar: boshqa rasmiy hujjatlar ──────────────────
    {
        "id": "collective-agreement",
        "category": "Jamoa shartnomasi",
        "title": "Jamoa shartnomasi: nima va nima uchun",
        "summary": "Jamoa shartnomasi ish beruvchi bilan kasaba uyushma (yoki vakil xodimlar) o'rtasidagi bitim. Mehnat shartlarini yaxshilash, qo'shimcha imtiyozlar belgilash imkonini beradi.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 45–50-moddalar</b>\n\n"
            "<b>Nima bu:</b>\n"
            "Jamoa shartnomasi — ish beruvchi va xodimlar vakili (kasaba uyushma yoki vakillar kengashi) o'rtasida tuziladigan yozma bitim. Unda qonunda belgilangandan <b>yaxshiroq</b> mehnat shartlari nazarda tutiladi.\n\n"
            "<b>Nima bo'lishi mumkin:</b>\n"
            "• Yuqori ish haqi minimumi (qonundagi MROTdan yuqori)\n"
            "• Qo'shimcha ta'til kunlari\n"
            "• Ovqatlanish, transport yoki turar-joy imtiyozlari\n"
            "• Sog'liqni saqlash yoki malaka oshirish to'lovlari\n"
            "• Ishdan bo'shatilganda katta kompensatsiya\n\n"
            "<b>Tuzish tartibi (47-modda):</b>\n"
            "1. Xodimlar yoki kasaba uyushma muzokaralar boshlanishini talab qiladi\n"
            "2. Muzokaralar <b>3 oy</b> ichida yakunlanadi\n"
            "3. Shartnoma imzolangach <b>7 kun ichida</b> mehnat organlari bilan ro'yxatdan o'tkaziladi\n"
            "4. Amal qilish muddati — odatda <b>1–3 yil</b>\n\n"
            "<b>Kimga tegishli:</b>\n"
            "Jamoa shartnomasi imzolangan korxonadagi <b>barcha</b> xodimlarga tegishli — kasaba uyushma a'zolari bo'lmasalar ham.\n\n"
            "<b>Muhim:</b> Jamoa shartnomasidagi shartlar mehnat shartnomasidagi shartlardan yaxshiroq bo'lishi shart; aks holda ariza komissiya orqali hal qilinadi."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-45",
        "source_label": "Mehnat Kodeksi, 45–50-moddalar",
    },
    {
        "id": "labor-safety",
        "category": "Mehnat muhofazasi",
        "title": "Mehnat muhofazasi: ish beruvchi majburiyatlari",
        "summary": "Ish beruvchi xodimlar uchun xavfsiz ish sharoiti yaratishi, himoya vositalarini bepul berishi va xodimlarni yo'riqnoma bilan o'tkazishi shart.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 215–220-moddalar va «Mehnat muhofazasi» qonuni (2015)</b>\n\n"
            "<b>Ish beruvchining asosiy majburiyatlari (MK 215-mod):</b>\n"
            "• Xavfsiz ish joylari va asbob-uskunalarni ta'minlash\n"
            "• Shaxsiy himoya vositalarini (kiyim, quloq, ko'z himoyasi) <b>bepul</b> berish\n"
            "• Yangi qabul qilingan xodimlarni <b>mehnat muhofazasi bo'yicha yo'riqnoma bilan o'tkazish</b>\n"
            "• Zararli omillar haqida xodimlarni xabardor qilish\n"
            "• Tibbiy ko'rikni tashkil etish (zararli ishlar uchun)\n\n"
            "<b>Xodimning huquqlari (216-modda):</b>\n"
            "• Xavfsiz ish sharoitida ishlash huquqi\n"
            "• Xavf-xatarli ish topshirig'ini <b>rad etish huquqi</b>\n"
            "• Shikastlanish yoki kasallik bo'lsa kompensatsiya olish\n"
            "• Mehnat muhofazasi holatini tekshirish bo'yicha murojaat qilish\n\n"
            "<b>Mehnat shikastlanishi (218-modda):</b>\n"
            "Ish paytida jarohatlanganda:\n"
            "1. Ish beruvchi darhol tergov komisiyasi tuzadi\n"
            "2. H-1 shaklidagi dalolatnoma rasmiylashtiriladi (<b>3 kun ichida</b>)\n"
            "3. Jabrlanuvchi <b>ijtimoiy sug'urta fondidan</b> bir martalik va oylik nafaqalar oladi\n\n"
            "<b>Davlat nazorati:</b>\n"
            "Mehnat inspektorlari korxonalarda rejalashtirilmagan tekshiruvlar o'tkazishi mumkin. Buzilish aniqlanganda jarima va faoliyatni to'xtatish chorasi ko'rilishi mumkin."
        ),
        "source_url": "https://lex.uz/uz/docs/2712229",
        "source_label": "Mehnat muhofazasi qonuni, 2015 + MK 215–220-moddalar",
    },
    {
        "id": "employment-guarantees",
        "category": "Bandlik",
        "title": "Bandlik kafolatlari va ishsizlik nafaqasi",
        "summary": "Davlat rasmiy ishsizlarga nafaqa, kasbiy tayyorgarlik va yangi ish joylari orqali yordam beradi. Bandlik markaziga ro'yxatdan o'tish — asosiy shart.",
        "full_text": (
            "📋 <b>«Aholini bandlik sohasida davlat tomonidan qo'llab-quvvatlash» qonuni (2021)</b>\n\n"
            "<b>Davlat kafolatlari:</b>\n"
            "• Ishga joylashishda bepul yordam (bandlik markazlari orqali)\n"
            "• Kasbiy tayyorgarlik va qayta tayyorlash kurslari — <b>bepul</b>\n"
            "• Vaqtinchalik ish o'rinlarini tashkil etish\n"
            "• Ishsizlik nafaqasi (ro'yxatdan o'tganlar uchun)\n\n"
            "<b>Ishsizlik nafaqasi:</b>\n"
            "• Bandlik markazida ro'yxatdan o'tganlar oladi\n"
            "• Miqdori: oxirgi ish haqiga qarab, kamida <b>MROT</b> darajasida\n"
            "• Muddati: odatda <b>6 oygacha</b> (alohida hollarda 12 oy)\n"
            "• Nafaqa vaqtida aktiv ish qidirish talab etiladi\n\n"
            "<b>Bandlik markaziga murojaat:</b>\n"
            "1. Pasport va mehnat daftarchasi bilan murojaat\n"
            "2. <b>10 kun</b> ichida birinchi ish taklif etiladi\n"
            "3. Uch bor taklifni rad etish — nafaqadan mahrum etiladi\n\n"
            "<b>Imtiyozli toifalar (ustuvor yordam):</b>\n"
            "• Nogironlar\n"
            "• Yosh mutaxassislar (25 yoshgacha)\n"
            "• Uch va undan ko'p farzandli ota-onalar\n"
            "• Qamoqdan qaytganlar va boshqalar\n\n"
            "<b>Muhim:</b> Bandlik markazlari hozir «Mehnat» portali orqali onlayn ham xizmat ko'rsatadi: <b>mehnat.uz</b>"
        ),
        "source_url": "https://lex.uz/uz/docs/6235875",
        "source_label": "Bandlik qonuni, 2021 + Mehnat Kodeksi",
    },
    {
        "id": "trade-unions",
        "category": "Kasaba uyushmalari",
        "title": "Kasaba uyushmalari va xodimlar vakilligi huquqlari",
        "summary": "Xodimlar kasaba uyushmasiga erkin kirish va chiqish huquqiga ega. Kasaba uyushma a'zolarini ishdan bo'shatish cheklangan.",
        "full_text": (
            "📋 <b>«Professional soyuzlar» qonuni (1992, yangilangan)</b>\n\n"
            "<b>Kasaba uyushmasi nima:</b>\n"
            "Kasaba uyushma (KU) — xodimlarning ixtiyoriy uyushmasi bo'lib, ularning iqtisodiy va mehnat huquqlarini himoya qiladi.\n\n"
            "<b>Xodimlarning asosiy huquqlari (Qonun 5-modda):</b>\n"
            "• Kasaba uyushmasiga <b>erkin kirish va chiqish</b>\n"
            "• Kasaba uyushma faoliyati uchun ish haqi ushlanmaslik\n"
            "• Ish vaqtida KU vakilining muammolarni hal qilish uchun vaqt ajratish\n\n"
            "<b>Kasaba uyushma huquqlari:</b>\n"
            "• Jamoa shartnomasi tuzish va imzolash\n"
            "• Mehnat qonunchiligi buzilishlarini tekshirish\n"
            "• Ish beruvchi bilan muzokaralar olib borish\n"
            "• Ish tashlashni uyushtirish (qonunda belgilangan tartibda)\n"
            "• Xodimlar nomidan sudga murojaat qilish\n\n"
            "<b>Ish tashlash huquqi (Mehnat Kodeksi 257-modda):</b>\n"
            "• Ish tashlashni boshlamasdan avval — muzokaralar, mediatsiya\n"
            "• Rasm ish tashlash uchun — oldindan <b>7 kun</b> ogohlantirish\n"
            "• Tibbiyot, atom elektr stansiyasi, temir yo'l — ish tashlash cheklangan\n\n"
            "<b>Kasaba uyushma a'zosini ishdan bo'shatish:</b>\n"
            "KU rahbarlarini va faollarini bo'shatishda ish beruvchi kasaba uyushmasining <b>roziligini</b> olishi shart (MK 101-modda).\n\n"
            "<b>Muhim:</b> Kasaba uyushmasiga a'zo bo'lmaganlarga ham xuddi shu jamoaviy shartnoma shartlari qo'llaniladi."
        ),
        "source_url": "https://lex.uz/uz/docs/111711",
        "source_label": "Professional soyuzlar qonuni, 1992 (yangilangan)",
    },
    {
        "id": "social-insurance",
        "category": "Ijtimoiy kafolatlar",
        "title": "Davlat ijtimoiy sug'urtasi: kim to'laydi, kim oladi",
        "summary": "Ish beruvchi har bir rasmiy xodim uchun ijtimoiy sug'urta badali to'laydi. Xodim kasallik, shikastlanish, homiladorlik va pensiya nafaqalarini shu fonddan oladi.",
        "full_text": (
            "📋 <b>«Davlat ijtimoiy sug'urtasi» qonuni</b>\n\n"
            "<b>Sug'urta turlari:</b>\n"
            "• Vaqtinchalik mehnatga layoqatsizlik (kasallik varaqasi)\n"
            "• Homiladorlik va tug'ruq nafaqasi\n"
            "• Bola parvarishi nafaqasi (3 yoshgacha)\n"
            "• Mehnat shikastlanishi va kasb kasalligi nafaqasi\n"
            "• Pensiya (keksalik, nogironlik, boqimanda)\n\n"
            "<b>Badal to'lash (ish beruvchi majburiyati):</b>\n"
            "• Rasmiy ish haqining muayyan foizida hisoblangan badal har oy Ijtimoiy sug'urta fondiga o'tkaziladi\n"
            "• Xodimning qo'li sug'urta badalini to'lashda ishtirok etmaydi (ish beruvchi to'liq to'laydi)\n"
            "• Norasmiy ish — sug'urta himoyasi yo'q\n\n"
            "<b>Nafaqalar miqdori:</b>\n"
            "Kasallik yoki shikastlanish nafaqasi xizmat stajiga qarab:\n"
            "• 5 yilgacha — ish haqining <b>60%</b>\n"
            "• 5–8 yil — <b>80%</b>\n"
            "• 8 yildan ko'p — <b>100%</b>\n\n"
            "<b>Norasmiy ishning xavfi:</b>\n"
            "Norasmiy (qora) ishlovchilarda:\n"
            "• Kasallik varaqasi bo'yicha nafaqa yo'q\n"
            "• Mehnat shikastlanishida kompensatsiya cheklangan\n"
            "• Pensiya stajiga qo'shilmaydi\n"
            "• Ishdan bo'shatilganda huquqiy himoya yo'q\n\n"
            "<b>Muhim:</b> Ish beruvchi xodimni rasmiy ro'yxatdan o'tkazmasa — bu <b>ma'muriy va jinoiy javobgarlik</b> sababi."
        ),
        "source_url": "https://lex.uz/uz/docs/4256286",
        "source_label": "Davlat ijtimoiy sug'urtasi qonuni",
    },
    {
        "id": "pension-basics",
        "category": "Pensiya",
        "title": "Pensiya ta'minoti: yoshlar va miqdori",
        "summary": "Ayollar 55, erkaklar 60 yoshda pensiyaga chiqadi. Pensiya miqdori ish staji va ish haqiga bog'liq. Minimal pensiya belgilangan.",
        "full_text": (
            "📋 <b>«Pensiya ta'minoti to'g'risida» qonuni (O'RQ-783, 2023)</b>\n\n"
            "<b>Pensiyaga chiqish yoshi:</b>\n"
            "• Erkaklar — <b>60 yosh</b>\n"
            "• Ayollar — <b>55 yosh</b>\n"
            "• Erta pensiya imkoniyati: ayrim kasb egalari (shaxta, zararli ish) uchun 5–10 yil erta\n\n"
            "<b>Minimal staj:</b>\n"
            "Oddiy pensiya uchun kamida <b>25 yil ish staji</b> talab etiladi (ayollar — 20 yil).\n"
            "Staj yetarli bo'lmagan hollarda — ijtimoiy pensiya (kamroq miqdorda) beriladi.\n\n"
            "<b>Pensiya miqdori qanday hisoblanadi:</b>\n"
            "• Bazaviy qism + stajga qarab qo'shimcha\n"
            "• Har yilgi staj uchun ish haqining ma'lum foizi qo'shiladi\n"
            "• So'nggi 3–5 yillik o'rtacha ish haqi asosida hisoblanadi\n\n"
            "<b>Ijtimoiy pensiya (staj yetmasa):</b>\n"
            "Staj to'liq bo'lmagan fuqarolar ham pensiya oladi — minimal belgilangan miqdorda.\n\n"
            "<b>Norasmiy ish va pensiya:</b>\n"
            "Norasmiy ishlagan yillar stajga qo'shilmaydi — bu kelajakda kichik pensiyaga olib keladi.\n\n"
            "<b>Pensiya olish uchun murojaat:</b>\n"
            "Pensiya yoshiga yetgach, <b>Ijtimoiy xizmat markazlariga</b> yoki «My.gov.uz» portali orqali murojaat qiling."
        ),
        "source_url": "https://lex.uz/uz/docs/419121",
        "source_label": "Pensiya ta'minoti qonuni (O'RQ-783, 2023)",
    },
    {
        "id": "labor-migration",
        "category": "Bandlik",
        "title": "Xorijda ishlash: huquqlar va muhim ogohlantirishlar",
        "summary": "O'zbekistondagi rasmiy organlar orqali chet elga chiqish xavfsiz. Norasmiy broker orqali ketish — savdo-odam xavfiga olib kelishi mumkin.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi 10-mod va «Mehnat migratsiyasi» qonuni</b>\n\n"
            "<b>Rasmiy xorijiy ishga joylashish:</b>\n"
            "• O'zbekiston Bandlik va mehnat vazirligi tasdiqlagan litsenziyali agentliklar orqali\n"
            "• «Xalqaro mehnat migratsiyasi» agentligi (AMIR) orqali\n"
            "• Xorijdagi O'zbekiston elchixonasi yordamida\n\n"
            "<b>Rasmiy shartnoma majburiy (MK 10-modda):</b>\n"
            "Xorijda ishlash uchun:\n"
            "1. Ish beruvchi bilan rasmiy mehnat shartnomasi (o'zbekcha va xorijiy tilda)\n"
            "2. Shartnomada: ish joyi, maosh, viza, uy-joy va qaytish kafolati ko'rsatilishi shart\n"
            "3. O'zbekiston elchixonasiga ro'yxatdan o'tish\n\n"
            "<b>Xavf belgilari (insonlar savdosi):</b>\n"
            "🔴 Pasportni tortib oladigan ish beruvchi\n"
            "🔴 Shartnomada ko'rsatilganidan boshqa ish\n"
            "🔴 Vaʼda qilingan maoshni to'lamaslik\n"
            "🔴 Ozodlikni cheklash yoki uyga qaytishga yo'l qo'ymaslik\n\n"
            "<b>Murojaat qayerga:</b>\n"
            "• O'zbekiston elchixonasi yoki konsulligi\n"
            "• «1404» — ishonch telefoni (O'zbekiston)\n"
            "• IOM (Xalqaro migratsiya tashkiloti)\n\n"
            "<b>Muhim:</b> Biror hujjatni imzolashdan oldin rasmiy tarjima va mustaqil maslahat oling."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-10",
        "source_label": "Mehnat Kodeksi, 10-modda + Mehnat migratsiyasi qonuni",
    },
    {
        "id": "labor-inspection",
        "category": "Mehnat muhofazasi",
        "title": "Mehnat inspeksiyasi: tekshiruv va shikoyat berish",
        "summary": "Mehnat inspektorlari korxonalarda rejali va rejasiz tekshiruv o'tkazadi. Har qanday xodim yozma shikoyat berishi mumkin.",
        "full_text": (
            "📋 <b>Mehnat Kodeksi, 285–289-moddalar va «Inspeksiya» qoidalari</b>\n\n"
            "<b>Davlat mehnat inspeksiyasi vazifasi:</b>\n"
            "• Mehnat qonunchiligi va mehnat muhofazasi talablariga rioya etilishini nazorat qilish\n"
            "• Xodimlarga mehnat huquqlarini tushuntirish\n"
            "• Qonun buzilishi aniqlanganda jarima tayinlash\n\n"
            "<b>Xodim shikoyat berishi uchun:</b>\n"
            "1. <b>Yozma ariza</b> — hududiy mehnat inspeksiyasiga shaxsan yoki pochta orqali\n"
            "2. <b>Onlayn</b> — «mehnat.uz» yoki «my.gov.uz» portali orqali\n"
            "3. <b>Telefon</b> — 1088 (Mehnat vazirligi ishonch liniyasi)\n\n"
            "<b>Tekshiruv natijasida nima bo'ladi:</b>\n"
            "• Inspektor korxonaga keladi, hujjatlarni tekshiradi\n"
            "• Buzilish aniqlansa — <b>yo'riqnoma</b> beriladi (muddatli bajarish uchun)\n"
            "• Jarima: yuridik shaxslar uchun <b>100–500 BHM</b> gacha\n"
            "• Bir xil buzilishni qaytarish — <b>faoliyatni to'xtatish</b> chorasi\n\n"
            "<b>Shikoyat beruvchi himoyasi:</b>\n"
            "Ish beruvchi shikoyat bergan xodimga nisbatan qasos chorasi ko'rsa — bu <b>alohida javobgarlik</b> sababi (MK 285-modda).\n\n"
            "<b>Muhim:</b> Inspeksiyaga murojaat qilish bepul va anonimlik so'rab ham bo'ladi."
        ),
        "source_url": "https://lex.uz/uz/docs/5401895#5401895-285",
        "source_label": "Mehnat Kodeksi, 285–289-moddalar",
    },
]

# ============================================================
# Ko'p tillilik qatlami
# ============================================================

# Proza maydonlari — ularning har biri LocalizedText ga aylanadi.
_PROSE_FIELDS: tuple[str, ...] = ("category", "title", "summary", "full_text", "source_label")

# Tarjimalar shu yerga qo'shiladi: article_id -> {maydon: {til: matn}}.
# ru/en tarjimalari src/data/translations/law_articles_{ru,en}.py da saqlanadi
# (har biri article_id -> {maydon: matn} shaklida); shu yerda ular
# {article_id: {maydon: {til: matn}}} shakliga birlashtiriladi.
from src.data.translations.law_articles_en import TRANSLATIONS as _ARTICLES_EN
from src.data.translations.law_articles_ru import TRANSLATIONS as _ARTICLES_RU


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


ARTICLE_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = _merge(_ARTICLES_RU, _ARTICLES_EN)

# Kategoriya nomi (uz) -> barqaror id
CATEGORY_IDS: dict[str, str] = {
    "Bandlik": "employment",
    "Ijtimoiy kafolatlar": "social-guarantees",
    "Ish haqi": "wages",
    "Ish vaqti": "work-time",
    "Ishdan bo'shatish": "dismissal",
    "Jamoa shartnomasi": "collective-agreement",
    "Kasaba uyushmalari": "trade-unions",
    "Mehnat muhofazasi": "labor-protection",
    "Mehnat nizolari": "labor-disputes",
    "Mehnat shartnomasi": "labor-contract",
    "Pensiya": "pension",
    "Ta'til": "leave",
}

# Kategoriya yorliqlari — qisqa UI matnlari, uchala tilda.
CATEGORY_TRANSLATIONS: dict[str, dict[str, str]] = {
    "employment": {"uz": "Bandlik", "ru": "Занятость", "en": "Employment"},
    "social-guarantees": {
        "uz": "Ijtimoiy kafolatlar",
        "ru": "Социальные гарантии",
        "en": "Social guarantees",
    },
    "wages": {"uz": "Ish haqi", "ru": "Заработная плата", "en": "Wages"},
    "work-time": {"uz": "Ish vaqti", "ru": "Рабочее время", "en": "Working time"},
    "dismissal": {"uz": "Ishdan bo'shatish", "ru": "Увольнение", "en": "Dismissal"},
    "collective-agreement": {
        "uz": "Jamoa shartnomasi",
        "ru": "Коллективный договор",
        "en": "Collective agreement",
    },
    "trade-unions": {"uz": "Kasaba uyushmalari", "ru": "Профсоюзы", "en": "Trade unions"},
    "labor-protection": {
        "uz": "Mehnat muhofazasi",
        "ru": "Охрана труда",
        "en": "Occupational safety",
    },
    "labor-disputes": {
        "uz": "Mehnat nizolari",
        "ru": "Трудовые споры",
        "en": "Labour disputes",
    },
    "labor-contract": {
        "uz": "Mehnat shartnomasi",
        "ru": "Трудовой договор",
        "en": "Employment contract",
    },
    "pension": {"uz": "Pensiya", "ru": "Пенсия", "en": "Pension"},
    "leave": {"uz": "Ta'til", "ru": "Отпуск", "en": "Leave"},
}


def _localized(article_id: str, field: str, uz_value: str) -> LocalizedText:
    """uz manba + mavjud tarjimalardan LocalizedText yig'adi."""
    value: LocalizedText = {DEFAULT_LANG: uz_value}
    extra = ARTICLE_TRANSLATIONS.get(article_id, {}).get(field, {})
    for lang in LANGS:
        text = extra.get(lang)
        if isinstance(text, str) and text.strip():
            value[lang] = text
    return value


def _build_article(source: dict[str, str]) -> LawArticle:
    article_id = source["id"]
    category_uz = source["category"]
    category_id = CATEGORY_IDS.get(category_uz, category_uz)

    category = dict(CATEGORY_TRANSLATIONS.get(category_id) or {DEFAULT_LANG: category_uz})
    category.setdefault(DEFAULT_LANG, category_uz)

    built: dict = {
        "id": article_id,
        "category_id": category_id,
        "category": category,
        "source_url": source["source_url"],
    }
    for field in _PROSE_FIELDS:
        if field == "category":
            continue
        built[field] = _localized(article_id, field, source[field])
    return built  # type: ignore[return-value]


ARTICLES: list[LawArticle] = [_build_article(item) for item in _ARTICLES_UZ]

# Backward-compat: o'zbekcha kategoriya nomlari ro'yxati.
CATEGORIES: list[str] = sorted({a["category"] for a in _ARTICLES_UZ})


def pick_text(value: LocalizedText | str, lang: str = DEFAULT_LANG) -> str:
    """LocalizedText dan tilni tanlaydi, yo'q bo'lsa uz ga qaytadi."""
    if isinstance(value, str):
        return value
    normalized = normalize_lang(lang)
    text = value.get(normalized)
    if isinstance(text, str) and text.strip():
        return text
    return value.get(DEFAULT_LANG, "")


def _flatten(article: LawArticle, lang: str) -> LawArticleFlat:
    return {
        "id": article["id"],
        "category_id": article["category_id"],
        "category": pick_text(article["category"], lang),
        "title": pick_text(article["title"], lang),
        "summary": pick_text(article["summary"], lang),
        "full_text": pick_text(article["full_text"], lang),
        "source_url": article["source_url"],
        "source_label": pick_text(article["source_label"], lang),
    }


def get_article_by_id(article_id: str) -> LawArticle | None:
    """Backward-compat: ko'p tilli maqolani id bo'yicha qaytaradi."""
    return next((a for a in ARTICLES if a["id"] == article_id), None)


def get_articles(lang: str = DEFAULT_LANG) -> list[LawArticleFlat]:
    """Barcha maqolalar, tanlangan tilda tekislangan holda."""
    return [_flatten(a, lang) for a in ARTICLES]


def get_article(article_id: str, lang: str = DEFAULT_LANG) -> LawArticleFlat | None:
    """Bitta maqola, tanlangan tilda tekislangan holda."""
    article = get_article_by_id(article_id)
    return _flatten(article, lang) if article else None


def get_categories(lang: str = DEFAULT_LANG) -> list[dict[str, str]]:
    """Maqolalarda uchraydigan kategoriyalar: [{"id": ..., "name": ...}]."""
    seen: list[str] = []
    for article in ARTICLES:
        category_id = article["category_id"]
        if category_id not in seen:
            seen.append(category_id)
    items = [
        {
            "id": category_id,
            "name": pick_text(
                CATEGORY_TRANSLATIONS.get(category_id, {DEFAULT_LANG: category_id}), lang
            ),
        }
        for category_id in seen
    ]
    return sorted(items, key=lambda item: item["name"])
