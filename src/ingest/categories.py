"""Canonical vacancy category for every source (``vacancies.category_id``).

The taxonomy is the Mini App's category filter (``/api/filters/specs``,
``webapp/core/i18n.py:SPECS``): osonish.uz "field" ids, sent as ``spec:<id>``.
Every source is mapped onto these ids so one indexed filter serves the whole
store:

* osonish: its own field id when the payload carries one (``mmk_group_field_ids``,
  a list, in list items and details; singular/nested shapes as fallbacks), else the keyword classifier on the title and the
  osonish position/group names.
* hh.uz: ``professional_roles`` ids through ``HH_ROLE_CATEGORY`` (the
  dictionary at ``api.hh.ru/professional_roles``, every role mapped to the one
  closest category; "Другое" (40) is unmapped), else the keyword classifier on
  the title.
* vacancy.gov.uz: no taxonomy, so the keyword classifier over the position
  name, then the structure and organisation names (a ministry, hokimiyat or
  other state body counts as "finance, economics, management").

Unknown stays ``None``. The classifier is three tiers of word-start stems
(occupations, then sectors/organisation types, then generic roles); within a
tier the first text that hits wins and categories are tried in
``_CATEGORY_ORDER``. Text is lowercased, apostrophes removed and Uzbek
Cyrillic letters folded (``ў->у``, ``қ->к``, ``ғ->г``, ``ҳ->х``), so the stems
cover uz Latin, uz Cyrillic and Russian. A stem ending in ``=`` must be a
whole word.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional

HEALTHCARE = 47
CONSTRUCTION = 41
SALES_MARKETING = 64
AGRICULTURE = 7
IT = 12
EDUCATION_CULTURE_SPORT = 42
TRANSPORT = 36
FINANCE_MANAGEMENT = 1
INDUSTRY = 21
SERVICES = 48

#: The ids behind ``SPECS`` (``spec:<id>``); a test keeps the two in sync.
CANONICAL_IDS: frozenset[int] = frozenset(
    {HEALTHCARE, CONSTRUCTION, SALES_MARKETING, AGRICULTURE, IT, EDUCATION_CULTURE_SPORT, TRANSPORT,
     FINANCE_MANAGEMENT, INDUSTRY, SERVICES}
)

# ----------------------------------------------------------------- hh.uz roles

#: hh ``professional_roles`` id -> canonical id. Roles listed under several hh
#: categories go to the one a job seeker here would look in.
HH_ROLE_CATEGORY: dict[str, int] = {
    # IT
    **{r: IT for r in ("10", "25", "36", "73", "96", "104", "112", "113", "114", "116", "121", "124", "125",
                       "126", "148", "150", "156", "157", "160", "164", "165")},
    # Healthcare / pharmacy
    **{r: HEALTHCARE for r in ("15", "24", "29", "42", "64", "65", "133", "194")},
    # Education, science, culture, media, sport
    **{r: EDUCATION_CULTURE_SPORT for r in ("12", "13", "17", "20", "23", "34", "41", "55", "79", "98", "101",
                                            "103", "132", "138", "139", "167", "168", "181")},
    # Agriculture
    **{r: AGRICULTURE for r in ("7", "19", "43")},
    # Sales, marketing, retail, purchasing
    **{r: SALES_MARKETING for r in ("1", "2", "3", "6", "9", "35", "37", "51", "53", "54", "66", "68", "70",
                                    "71", "77", "83", "97", "99", "105", "106", "119", "122", "123", "127",
                                    "129", "163", "170", "176", "180", "182", "190")},
    # Construction, real estate engineering
    **{r: CONSTRUCTION for r in ("14", "27", "30", "47", "48", "59", "78", "100", "108", "175", "179")},
    # Transport, logistics, warehouse
    **{r: TRANSPORT for r in ("5", "21", "31", "39", "52", "58", "63", "67", "81", "131", "159", "172", "185")},
    # Finance, economics, management, HR, law, office administration
    **{r: FINANCE_MANAGEMENT for r in ("11", "16", "18", "26", "33", "38", "50", "57", "69", "75", "76", "84",
                                       "87", "88", "91", "93", "107", "110", "117", "118", "134", "135", "136",
                                       "137", "142", "145", "146", "147", "153", "154", "155", "158", "161",
                                       "166", "171", "188")},
    # Industry, production, maintenance
    **{r: INDUSTRY for r in ("28", "44", "45", "46", "49", "80", "82", "85", "86", "102", "109", "111", "115",
                             "128", "141", "143", "144", "149", "151", "152", "162", "169", "173", "174", "177",
                             "178", "183", "186", "189", "192", "193")},
    # Services: hospitality, beauty, cleaning, security, post
    **{r: SERVICES for r in ("4", "8", "32", "56", "60", "61", "62", "72", "74", "89", "90", "92", "94", "120",
                             "130", "140", "184", "187", "191")},
}

# --------------------------------------------------------- keyword classifier

#: Agriculture precedes healthcare so a "veterinariya vrachi" is not a doctor.
_CATEGORY_ORDER = (
    IT, AGRICULTURE, HEALTHCARE, EDUCATION_CULTURE_SPORT, FINANCE_MANAGEMENT, SALES_MARKETING, CONSTRUCTION,
    TRANSPORT, SERVICES, INDUSTRY,
)

#: Tier 1: occupations named in a job title.
_OCCUPATIONS: dict[int, tuple[str, ...]] = {
    IT: (
        "dasturchi", "dasturlash", "дастурчи", "programmist", "программист", "разработчик", "developer",
        "frontend", "front-end", "backend", "back-end", "fullstack", "full-stack", "devops", "тестировщик",
        "tester", "qa=", "it=", "it-", "sysadmin", "системный администратор", "tizim administrator",
        "sistem administrator", "сетевой инженер", "tarmoq muhandisi", "data scien", "дата-сайентист",
        "аналитик данных", "bi-аналитик", "android", "ios=", "python", "java=", "javascript", "php=", "golang", "1c=", "1с=",
        "ui/ux", "ux/ui", "web-", "веб-", "web dasturchi", "kiberxavfsizlik", "информационной безопасности",
        "axborot xavfsizligi",
    ),
    HEALTHCARE: (
        "shifokor", "шифокор", "vrach", "врач", "hamshira", "хамшира", "медсестр", "медбрат", "медицинская сестра",
        "медицинский брат", "feldsher", "фельдшер", "farmatsevt", "фармацевт", "provizor", "провизор",
        "stomatolog", "стоматолог", "terapevt", "терапевт", "pediatr", "педиатр", "jarroh", "хирург", "xirurg",
        "akusher", "акушер", "nevrolog", "невролог", "kardiolog", "кардиолог", "rentgen", "рентген", "uzi=",
        "узи=", "doktor", "доктор", "sanitar", "санитар", "ginekolog", "гинеколог", "oftalmolog", "окулист",
        "lor=", "лор=", "anesteziolog", "анестезиолог", "reanimatolog", "реаниматолог", "laborant-tibbiy",
        "tibbiy hamshira", "tish", "massajchi-tibbiy", "dorixona", "аптек", "травматолог", "travmatolog",
        "endokrinolog", "эндокринолог", "urolog", "уролог", "dermatolog", "дерматолог", "onkolog", "онколог",
        "psixiatr", "психиатр", "narkolog", "нарколог", "fizioterapevt", "физиотерапевт", "epidemiolog",
        "эпидемиолог",
    ),
    EDUCATION_CULTURE_SPORT: (
        "oqituvchi", "укитувчи", "учитель", "преподават", "педагог", "pedagog", "tarbiyachi", "тарбиячи",
        "воспитател", "murabbiy", "мураббий", "тренер", "trener", "fitnes", "фитнес", "repetitor", "репетитор",
        "metodist", "методист", "tyutor", "тьютор", "enaga", "няня", "psixolog", "психолог", "logoped",
        "логопед", "defektolog", "дефектолог", "kutubxonachi", "библиотекар", "xoreograf", "хореограф",
        "musiqa", "музык", "aktyor", "актер", "актёр", "artist", "артист", "jurnalist", "журналист",
        "rejissyor", "rejissor", "режиссер", "fotograf", "фотограф", "videooperator", "видеооператор",
        "videomontaj", "видеомонтаж", "dizayner", "дизайнер", "designer", "kopirayter", "копирайтер",
        "muharrir", "редактор", "tadqiqotchi", "исследовател", "ilmiy xodim", "научный сотрудник", "dotsent",
        "доцент", "professor", "профессор", "assistent-oqituvchi", "konsertmeyster", "концертмейстер",
        "rassom", "художник", "instruktor-sport", "sport instruktori", "suzish", "kurash", "boks", "futbol",
        "animator", "аниматор", "boshlovchi", "ведущий", "diktor", "диктор", "ekskursovod", "экскурсовод",
    ),
    AGRICULTURE: (
        "agronom", "агроном", "fermer", "фермер", "zootexnik", "зоотехник", "veterinar", "ветеринар",
        "chorvador", "chorvachi", "животновод", "traktorchi", "тракторист", "bogbon", "боғбон", "садовник",
        "dehqon", "деҳқон", "дехкон", "asalarichi", "пчеловод", "baliqchi", "рыбовод", "mexanizator",
        "механизатор", "доярк", "sut soguvchi", "parrandachi", "птичниц", "cho'pon", "chopon", "чабан",
        "agrotexnik", "агротехник", "selektsioner", "селекционер", "ipakchi", "pillachi",
    ),
    FINANCE_MANAGEMENT: (
        "buxgalter", "бухгалтер", "hisobchi", "iqtisodchi", "иктисодчи", "экономист", "economist",
        "moliyachi", "финансист", "финансовый", "moliya mutaxassis", "auditor", "аудитор", "kaznachey",
        "казначей", "kassir-operator", "кассир-операционист", "kredit", "кредит", "investitsiya", "инвест",
        "soliq", "налог", "yurist", "юрист", "юрисконсульт", "yuriskonsult", "huquqshunos", "хукукшунос",
        "notarius", "нотариус", "advokat", "адвокат", "kadrlar", "кадр", "hr=", "hr-", "rekruter", "рекрутер",
        "менеджер по персоналу", "менеджер по подбору", "xodimlar bolimi", "sekretar", "секретар", "kotib",
        "котиб", "ofis menejer", "ofis-menejer", "офис-менеджер", "office manager", "делопроизвод",
        "ish yurituvchi", "иш юритувчи", "arxivchi", "архивариус", "tarjimon", "таржимон", "переводчик",
        "statistik", "статистик", "aktuariy", "андеррайтер", "baholovchi", "оценщик", "kontroller",
        "контролер-ревизор", "taftishchi", "ревизор", "rejalashtiruvchi", "планов", "omborxona hisobchisi",
    ),
    SALES_MARKETING: (
        "sotuvchi", "сотувчи", "sotuv", "продав", "продаж", "kassir", "кассир", "marketolog", "маркетолог",
        "marketing", "маркетинг", "smm", "реклам", "reklama", "merchandayzer", "мерчандайзер", "promouter",
        "промоутер", "call-центр", "колл-центр", "call center", "call-center", "kontakt markaz",
        "контактного центра", "агент=", "agent=", "sugurta agenti", "страховой агент", "supervayzer",
        "супервайзер", "tovaroved", "товаровед", "закуп", "zakup", "taminotchi", "снабжен", "brend",
        "бренд", "pr-", "pr=", "kontent", "контент", "mijozlar bilan", "по работе с клиентами",
        "торговый представит", "savdo vakili", "savdo agenti", "diler", "дилер", "дистрибьют", "distribyut",
        "realizator", "реализатор", "konsultant", "консультант", "rieltor", "риелтор", "риэлтор",
        "недвижимост", "ko'chmas mulk", "kochmas mulk", "targetolog", "таргетолог", "kategoriya menejeri",
        "категорийный", "marketpleys", "маркетплейс", "mijozlarga xizmat",
    ),
    CONSTRUCTION: (
        "quruvchi", "курувчи", "строител", "gishtchi", "gisht teruvchi", "каменщик", "suvoqchi", "штукатур",
        "malyar", "маляр", "boyoqchi", "armaturachi", "арматурщик", "betonchi", "бетонщик", "prorab",
        "прораб", "arxitektor", "архитектор", "smetchik", "сметчик", "geodezist", "геодезист", "plitkachi",
        "кафельщик", "плиточник", "montajchi", "монтажник", "otdelochnik", "отделочник", "кровельщик",
        "tom yopuvchi", "ekskavatorchi", "экскаваторщик", "kranchi", "крановщик", "kran operatori",
        "инженер-строитель", "muhandis-quruvchi", "qurilish muhandisi", "инженер пто", "инженер-сметчик",
        "инженер строительного", "texnik nazorat", "технадзор", "stropalshik", "грунт", "asfalt", "асфальт",
        "gipsokarton", "гипсокартон", "kafelchi",
    ),
    TRANSPORT: (
        "haydovchi", "хайдовчи", "водител", "shofyor", "шофер", "шофёр", "ekspeditor", "экспедитор",
        "kuryer", "kurer", "курьер", "yetkazib beruvchi", "dostavka", "доставк", "logist", "логист",
        "omborchi", "омборчи", "omborxona", "кладовщик", "yukchi", "yuk tashuvchi", "yuk ortuvchi", "грузчик",
        "dispetcher", "диспетчер", "mashinist", "машинист", "taksi", "такси", "avtobus", "автобус",
        "avtomexanik", "автомеханик", "автослесарь", "avtoslesar", "avtoelektrik", "автоэлектрик",
        "bortprovodnik", "бортпроводник", "стюард", "uchuvchi", "пилот", "pilot", "konduktor", "кондуктор",
        "pochtalon", "почтальон", "ombor mudiri", "начальник склада", "склад", "ombor=", "ombor xodimi",
        "kladovshik", "furachi", "дальнобой", "vagon", "вагон", "lokomotiv", "локомотив", "traktor haydovchi",
    ),
    SERVICES: (
        "oshpaz", "ошпаз", "повар", "ofitsiant", "официант", "barmen", "бармен", "barista", "бариста",
        "farrosh", "фаррош", "уборщ", "tozalovchi", "тозаловчи", "qorovul", "коровул", "охранник", "сторож",
        "qoriqchi", "кўрикчи", "sartarosh", "сартарош", "парикмахер", "kosmetolog", "косметолог", "manikyur",
        "маникюр", "massaj", "массаж", "novvoy", "новвой", "пекар", "konditer", "кондитер", "qandolatchi",
        "idish yuvuvchi", "посудомой", "мойщик", "avtomoyka", "автомойщ", "xostes", "хостес", "gornichnaya",
        "горничн", "dvornik", "дворник", "farrosh-tozalovchi", "kir yuvuvchi", "прачк", 
        "oshxona ishchisi", "povar", "shashlikchi", "кассир-официант", "kosmetik", "vizajist", "визажист",
        "stilist", "стилист", "barber", "барбер", "qassob", "мясник", "обвальщик", "кухонный работник",
        "security", "posbon", "tur menejer", "менеджер по туризму", "turoperator",
        "туроператор", "uy bekasi", "domrabotnitsa", "сиделка",     ),
    INDUSTRY: (
        "payvandchi", "пайвандчи", "сварщик", "svarshik", "elektrosvarshik", "tokar", "токарь", "frezer",
        "фрезеровщ", "slesar", "слесар", "santexnik", "сантехник", "elektrik", "электрик", "elektromontyor",
        "электромонтер", "электромонтёр", "электромонтаж", "elektromontaj", "mehnat muhofazasi", "охране труда", "охрана труда",
        "texnolog=", "технолог=", "operator stanok", "станк", "chpu", "чпу", "tikuvchi",
        "тикувчи", "швея", "bichuvchi", "закройщик", "portnoy", "портн", "mexanik", "механик", "energetik",
        "энергетик", "qadoqlovchi", "упаковщ", "комплектовщ", "duradgor", "дурадгор",
        "столяр", "плотник", "kochegar", "кочегар", "metrolog", "метролог", "tamirlovchi", "ремонтник",
        "kimyogar", "химик", "geolog", "геолог", "shaxtyor", "шахтер", "шахтёр", "gaz payvandchi",
        "оператор производственной", "оператор линии", "liniya operatori",
        "kontrolyor otk", "контролёр отк", "контролер отк", "mebelchi", "мебельщик", "shlifovshik",
        "шлифовщ", "temirchi", "кузнец", "sex boshligi", "начальник цеха", "начальник смены", "smena ustasi",
        "elektrogazsvarshik", "kompressor", "nasos", "насос", "qozonxona", "котельн", "operator kotelnoy",
    ),
}

#: Tier 2: sectors and organisation types (employer names, gov structures).
_SECTORS: dict[int, tuple[str, ...]] = {
    IT: (
        "axborot texnolog", "ахборот технолог", "информационн", "kompyuter", "компьютер", "dasturiy",
        "программн", "it kompaniya", "it-park", "it park", "raqamli texnolog", "цифров", "raqamlashtirish",
    ),
    HEALTHCARE: (
        "tibbiy", "тиббий", "tibbiyot", "тиббиёт", "медицин", "kasalxona", "касалхона", "больниц",
        "поликлиник", "poliklinika", "shifoxona", "шифохона", "sogliqni saqlash", "согликни саклаш",
        "здравоохран", "klinika", "клиник", "sanatoriy", "санатор", "sanitariya-epidemiolog", "санэпид",
        "ambulator", "амбулатор", "dispanser", "диспансер", "tug'ruq", "tugruqxona", "роддом", "farmatsevtika",
        "фармацевт", "qon quyish", "tez tibbiy", "skoraya", "скорой помощи", "oilaviy poliklinika",
        "oilaviy shifokorlik", "sanepid", "sanitariya",
    ),
    EDUCATION_CULTURE_SPORT: (
        "maktab", "мактаб", "школ", "bogcha", "богча", "детский сад", "детсад", "litsey", "лицей", "kollej",
        "колледж", "texnikum", "техникум", "universitet", "университет", "institut", "институт", "oliygoh",
        "talim", "таълим", "образован", "madaniyat", "маданият", "культур", "sport", "спорт", "kutubxona",
        "кутубхона", "библиотек", "muzey", "музей", "teatr", "театр", "akademiya", "академи", "oquv markaz",
        "учебн", "o'quv", "oquv", "bilim yurti", "ilmiy-tadqiqot", "научно-исследоват", "ilm-fan", "наук",
        "san'at", "sanat", "санъат", "искусств", "yoshlar", "molodej", "мусиқа", "teleradio", "телерадио",
        "televideniye", "телевиден", "nashriyot", "издательств", "gazeta", "газет", "jurnal tahririyati",
    ),
    AGRICULTURE: (
        "qishloq xo", "кишлок хужалик", "сельск", "сельхоз", "fermer xo", "agro", "агро", "chorva", "чорва",
        "issiqxona", "иссикхона", "теплиц", "paxta", "пахта", "ipakchilik", "veterinariya", "ветеринар",
        "suv xo", "ирригац", "irrigatsiya", "melioratsiya", "мелиорац", "o'rmon", "ormon xo", "лесхоз",
        "лесн", "bog'dorchilik", "bogdorchilik", "uzumchilik", "parrandachilik", "птицефабрик",
        "baliqchilik", "рыбн хоз",
    ),
    FINANCE_MANAGEMENT: (
        "moliya", "молия", "финанс", "bank", "банк", "soliq", "солик", "налог", "sugurta", "страхов", "audit",
        "аудит", "hokim", "хоким", "vazirlik", "vazirlig", "вазирлиг", "министерств", "qomita", "кумита", "комитет",
        "boshqarma", "бошкарма", "управлени", "inspeksiya", "инспекци", "agentlik", "agentlig", "агентлиг", "агентств",
        "departament", "департамент", "devon", "девон", "adliya", "адлия", "юстиц", "prokuratura", "прокурат",
        "sud=", "суд=", "kengash", "кенгаш", "gaznachilik", "газначилик", "казначейств", "statistika",
        "статистик", "davlat xizmat", "государственн", "markaziy apparat", "apparati", "palata",
        "палата", "senat", "сенат", "majlis", "мажлис", "ombudsman", "fond=", "фонд=", "jamgarma", "жамгарма",
        "byudjet", "бюджет", "iqtisodiyot", "иктисодиёт", "экономик", "investitsiya", "инвестиц", "birja",
        "бирж", "kadastr", "кадастр", "notarial", "нотариал", "mahalla", "махалла", "fuqarolar yigini",
        "prezident", "президент", "vazirlar mahkamasi", "kotibiyat", "секретариат", "huquq", "хукук",
        "ichki ishlar", "ички ишлар", "favqulodda", "bojxona", "божхона", "таможен", "pensiya", "пенсион",
    ),
    SALES_MARKETING: (
        "savdo", "савдо", "торгов", "magazin", "магазин", "dokon", "дўкон", "докон", "supermarket",
        "супермаркет", "gipermarket", "гипермаркет", "bozor", "бозор", "рынок", "реклам", "reklama",
        "ritail", "retail", "ритейл", "marketplace", "маркетплейс", "ulgurji", "оптов", "chakana", "розничн",
        "eksport", "экспорт",
    ),
    CONSTRUCTION: (
        "qurilish", "курилиш", "строительств", "стройк", "arxitektura", "архитектур", "uy-joy", "уй-жой",
        "жилищн", "loyiha-qidiruv", "проектн", "ta'mirlash-qurilish", "tamirlash-qurilish", "ремонтно-строит",
        "yo'l qurilish", "yol qurilish", "дорожн", "ko'prik", "kochmas mulk", "недвижимост",
        "девелопер", "qurilish materiallari", "стройматериал",
    ),
    TRANSPORT: (
        "transport", "транспорт", "logistik", "логистик", "temir yo", "темир йул", "железнодорож",
        "aeroport", "аэропорт", "avia", "авиа", "metropoliten", "метрополитен", "avtobaza", "автобаз",
        "avtokorxona", "автокорхона", "автопарк", "avtopark", "yo'lovchi", "yolovchi", "pochta", "почт",
        "kuryerlik", "курьерск", "yuk tashish", "грузоперевоз", "перевозк", "tashish", "ombor xo", "складск",
        "avtomobil", "автомобил", "avtosalon", "автосалон", "avtoservis", "автосервис", "yetkazib berish",
        "uzbekistan airways", "o'zbekiston temir", "taksopark", "таксопарк",
    ),
    SERVICES: (
        "restoran", "ресторан", "kafe=", "кафе=", "oshxona", "ошхона", "столов", "mehmonxona", "мехмонхона",
        "гостиниц", "отел", "hotel", "turizm", "туризм", "туристи", "salon", "салон", "gozallik", "гўзаллик",
        "красот", "kirxona", "химчист", "xizmat korsatish", "хизмат курсатиш", "обслуживан", "kommunal",
        "коммунал", "obodonlashtirish", "ободонлаштириш", "благоустр", "fast food", "фастфуд", "fastfood",
        "choyxona", "чойхона", "to'yxona", "toyxona", "банкет", "catering", "кейтеринг", "qo'riqlash",
        "qoriqlash", "xavfsizlik xizmati", "служба безопасности", "barbershop", "spa=", "спа=",
        "fitnes klub", "hammom", "сауна", "kir yuvish", "tozalash xizmati", "клининг", "klining",
    ),
    INDUSTRY: (
        "ishlab chiqarish", "ишлаб чикариш", "производств", "zavod", "завод", "fabrika", "фабрик", "sex=",
        "цех", "kombinat", "комбинат", "neft", "нефт", "gaz=", "газ=", "gazli", "энерго", "energetika",
        "энергетик", "elektr tarmoq", "электросет", "elektr stansiya", "электростанц", "issiqlik", "теплоэнерг",
        "kon=", "кон=", "shaxta", "шахт", "metall", "металл", "kimyo", "кимё", "хими", "tikuv", "тикув",
        "швейн", "tekstil", "текстил", "oziq-ovqat", "пищев", "mebel", "мебел", "sement", "цемент",
        "farmatsevtika zavodi", "avtomobilsozlik", "машиностро", "mashinasozlik", "sanoat", "санот", "промышлен",
        "konchilik", "горнодобыв", "geologiya", "геолог", "suv ta'minoti", "suv taminoti", "водоканал",
        "issiqlik ta'minoti", "teplo", "elektr energiya", "hududiy elektr", "paxta tozalash", "ip-yigiruv",
        "yigiruv", "trikotaj", "трикотаж", "poyabzal", "обув", "qandolat", "кондитерск", "non zavodi",
        "хлебозавод", "sut kombinati", "молочн", "go'sht", "мясокомбинат",
    ),
}

#: Tier 3: generic roles, only when nothing more specific matched.
_GENERIC: dict[int, tuple[str, ...]] = {
    FINANCE_MANAGEMENT: (
        "direktor", "директор", "rahbar", "рахбар", "руководител", "boshliq", "boshlig", "бошлик", "начальник",
        "menejer", "менеджер", "manager", "boshqaruvchi", "бошкарувчи", "управляющ", "mutaxassis",
        "мутахассис", "специалист", "inspektor", "инспектор", "ekspert", "эксперт", "mudir", "мудир",
        "заведующ", "rais", "раис", "председател", "orinbosar", "уринбосар", "заместител", "maslahatchi",
        "маслахатчи", "советник", "koordinator", "координатор", "referent", "референт",
    ),
    SERVICES: ("administrator", "администратор", "xizmatchi", "хизматчи"),
    INDUSTRY: (
        "ishchi", "ишчи", "рабоч", "usta", "уста", "мастер", "texnik", "техник", "operator", "оператор",
        "muhandis", "мухандис", "инженер", "engineer", "laborant", "лаборант",
    ),
}

_FOLD = str.maketrans({"ў": "у", "қ": "к", "ғ": "г", "ҳ": "х", "ё": "е", "ʻ": "", "ʼ": "", "'": "", "`": "",
                       "‘": "", "’": "", "´": ""})


def _fold(text: str) -> str:
    return text.lower().translate(_FOLD)


def _compile(table: Mapping[int, Iterable[str]]) -> list[tuple[int, re.Pattern[str]]]:
    out = []
    for category in _CATEGORY_ORDER:
        stems = table.get(category)
        if not stems:
            continue
        parts = []
        for stem in dict.fromkeys(_fold(s) for s in stems):
            whole = stem.endswith("=")
            body = re.escape(stem[:-1] if whole else stem)
            parts.append(body + (r"(?!\w)" if whole else ""))
        out.append((category, re.compile(r"(?<!\w)(?:" + "|".join(parts) + ")", re.UNICODE)))
    return out


_TIERS = (_compile(_OCCUPATIONS), _compile(_SECTORS), _compile(_GENERIC))


def classify_text(*texts: Any) -> Optional[int]:
    """Canonical id for free text, ``texts`` in priority order (title first); ``None`` when nothing hits."""
    folded = [_fold(t) for t in texts if isinstance(t, str) and t.strip()]
    for tier in _TIERS:
        for text in folded:
            for category, pattern in tier:
                if pattern.search(text):
                    return category
    return None


# ----------------------------------------------------------------- per source


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _field_ids(obj: Any, depth: int = 0) -> Iterable[Optional[int]]:
    """Every place an osonish payload may carry its field id (``mmk_group_field_id`` filter).

    Real list items and details carry ``mmk_group_field_ids``, a list (``[3]``); the
    singular keys and nested shapes are fallbacks.
    """
    if not isinstance(obj, Mapping) or depth > 2:
        return
    ids = obj.get("mmk_group_field_ids")
    if isinstance(ids, (list, tuple)):
        for value in ids:
            yield _int(value)
    for key in ("mmk_group_field_id", "group_field_id", "field_id"):
        yield _int(obj.get(key))
    group_field = obj.get("mmk_group_field")
    if isinstance(group_field, Mapping):
        yield _int(group_field.get("id"))
    else:
        yield _int(group_field)
    for key in ("mmk_group", "mmk_position", "group"):
        yield from _field_ids(obj.get(key), depth + 1)


def _names(obj: Any, *keys: str) -> list[str]:
    if not isinstance(obj, Mapping):
        return []
    return [str(obj.get(k)) for k in keys if isinstance(obj.get(k), str)]


def osonish_category(item: Mapping[str, Any], title: str = "") -> Optional[int]:
    """osonish list item / detail -> canonical id (own field id first, then keywords)."""
    if not isinstance(item, Mapping):
        return None
    for field_id in _field_ids(item):
        if field_id in CANONICAL_IDS:
            return field_id
    position = item.get("mmk_position")
    group = item.get("mmk_group") or (position.get("mmk_group") if isinstance(position, Mapping) else None)
    return classify_text(
        title or item.get("title"),
        *_names(position, "position_name", "name", "name_uz", "name_ru"),
        *_names(group, "cat3", "cat2", "cat1", "name_uz", "name", "name_ru"),
    )


def hh_category(item: Mapping[str, Any], title: str = "") -> Optional[int]:
    """hh vacancy -> canonical id (first mapped professional role, then keywords on the title)."""
    if not isinstance(item, Mapping):
        return None
    roles = [r for r in (item.get("professional_roles") or []) if isinstance(r, Mapping)]
    for role in roles:
        category = HH_ROLE_CATEGORY.get(str(role.get("id") or ""))
        if category is not None:
            return category
    return classify_text(title or item.get("name"), *(str(r.get("name") or "") for r in roles))


def vacancy_gov_category(item: Mapping[str, Any], title: str = "") -> Optional[int]:
    """vacancy.gov.uz item -> canonical id (keywords: position, position type, structure, organisation)."""
    if not isinstance(item, Mapping):
        return None
    org = item.get("organizationFull") if isinstance(item.get("organizationFull"), Mapping) else {}
    return classify_text(
        title or item.get("position_name"),
        item.get("position_type"),
        item.get("structure_name"),
        item.get("organization"),
        *_names(org, "name", "name_uz", "name_ru", "full_name"),
    )


_BY_SOURCE = {"osonish": osonish_category, "hh": hh_category, "vacancy_gov": vacancy_gov_category}


def categorize(source: str, raw: Mapping[str, Any] | None, title: str = "", label: str = "") -> Optional[int]:
    """Canonical id for a vacancy of ``source`` (``raw`` = source payload); ``label`` is a free-text fallback."""
    fn = _BY_SOURCE.get(source)
    category = fn(raw or {}, title) if fn else None
    if category is None and (title or label):
        category = classify_text(title, label)
    return category


def spec_to_category(raw_spec: Any) -> Optional[int]:
    """``spec:<id>`` / ``<id>`` (also an int) -> canonical id, ``None`` when it is not one of ours."""
    text = str(raw_spec if raw_spec is not None else "").strip()
    if text.startswith("spec:"):
        text = text[5:]
    value = _int(text)
    return value if value in CANONICAL_IDS else None
