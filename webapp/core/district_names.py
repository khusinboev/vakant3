"""Russian and English names for Uzbekistan's 205 districts / cities (tumanlar, shaharlar).

Keyed by SOATO code (the ``districts.soato`` column). Uzbek names come from the DB
(``districts.name_uz``); this module only supplies the "ru" and "en" translations,
mirroring the pattern used for regions in :mod:`webapp.core.i18n` (``REGION_NAMES``).
"""

DISTRICT_NAMES: dict[str, dict[str, str]] = {
    "1703202": {"ru": "Алтынкульский район", "en": "Oltinkoʻl District"},  # Oltinko'l tumani
    "1703203": {"ru": "Андижанский район", "en": "Andijan District"},  # Andijon tumani
    "1703206": {"ru": "Балыкчинский район", "en": "Baliqchi District"},  # Baliqchi tumani
    "1703209": {"ru": "Бустонский район", "en": "Boʻston District"},  # Bo'ston tumani
    "1703210": {"ru": "Булакбашинский район", "en": "Buloqboshi District"},  # Buloqboshi tumani
    "1703211": {"ru": "Джалакудукский район", "en": "Jalaquduq District"},  # Jalaquduq tumani
    "1703214": {"ru": "Избасканский район", "en": "Izboskan District"},  # Izboskan tumani
    "1703217": {"ru": "Улугнорский район", "en": "Ulugʻnor District"},  # Ulug'nor tumani
    "1703220": {"ru": "Кургантепинский район", "en": "Qoʻrgʻontepa District"},  # Qo'rg'ontepa tumani
    "1703224": {"ru": "Асакинский район", "en": "Asaka District"},  # Asaka tumani
    "1703227": {"ru": "Мархаматский район", "en": "Marxamat District"},  # Marxamat tumani
    "1703230": {"ru": "Шахриханский район", "en": "Shaxrixon District"},  # Shaxrixon tumani
    "1703232": {"ru": "Пахтаабадский район", "en": "Paxtaobod District"},  # Paxtaobod tumani
    "1703236": {"ru": "Ходжаабадский район", "en": "Xoʻjaobod District"},  # Xo'jaobod tumani
    "1703401": {"ru": "город Андижан", "en": "Andijan City"},  # Andijon
    "1703408": {"ru": "город Ханабад", "en": "Xonobod City"},  # Xonobod
    "1706204": {"ru": "Алатский район", "en": "Olot District"},  # Olot tumani
    "1706207": {"ru": "Бухарский район", "en": "Buxoro District"},  # Buxoro tumani
    "1706212": {"ru": "Вабкентский район", "en": "Vobkent District"},  # Vobkent tumani
    "1706215": {"ru": "Гиждуванский район", "en": "Gʻijduvon District"},  # G'ijduvon tumani
    "1706219": {"ru": "Каганский район", "en": "Kogon District"},  # Kogon tumani
    "1706230": {"ru": "Каракульский район", "en": "Qorakoʻl District"},  # Qorako'l tumani
    "1706232": {"ru": "Караулбазарский район", "en": "Qorovulbozor District"},  # Qorovulbozor tumani
    "1706240": {"ru": "Пешкунский район", "en": "Peshku District"},  # Peshku tumani
    "1706242": {"ru": "Ромитанский район", "en": "Romitan District"},  # Romitan tumani
    "1706246": {"ru": "Жондорский район", "en": "Jondor District"},  # Jondor tumani
    "1706258": {"ru": "Шафирканский район", "en": "Shofirkon District"},  # Shofirkon tumani
    "1706401": {"ru": "город Бухара", "en": "Bukhara City"},  # Buxoro
    "1706403": {"ru": "город Каган", "en": "Kogon City"},  # Kogon
    "1708201": {"ru": "Арнасайский район", "en": "Arnasoy District"},  # Arnasoy tumani
    "1708204": {"ru": "Бахмальский район", "en": "Baxmal District"},  # Baxmal tumani
    "1708209": {"ru": "Галляаральский район", "en": "Gʻallaorol District"},  # G'allaorol tumani
    "1708212": {"ru": "район Шарофа Рашидова", "en": "Sharof Rashidov District"},  # Sharof Rashidov tumani
    "1708215": {"ru": "Дустликский район", "en": "Doʻstlik District"},  # Do'stlik tumani
    "1708218": {"ru": "Зааминский район", "en": "Zomin District"},  # Zomin tumani
    "1708220": {"ru": "Зарбдарский район", "en": "Zarbdor District"},  # Zarbdor tumani
    "1708223": {"ru": "Мирзачульский район", "en": "Mirzachoʻl District"},  # Mirzacho'l tumani
    "1708225": {"ru": "Зафарабадский район", "en": "Zafarobod District"},  # Zafarobod tumani
    "1708228": {"ru": "Пахтакорский район", "en": "Paxtakor District"},  # Paxtakor tumani
    "1708235": {"ru": "Фаришский район", "en": "Forish District"},  # Forish tumani
    "1708237": {"ru": "Янгиабадский район", "en": "Yangiobod District"},  # Yangiobod tumani
    "1708401": {"ru": "город Джизак", "en": "Jizzakh City"},  # Jizzax
    "1710207": {"ru": "Гузарский район", "en": "Gʻuzor District"},  # G'uzor tumani
    "1710212": {"ru": "Дехканабадский район", "en": "Dehqonobod District"},  # Dehqonobod tumani
    "1710220": {"ru": "Камашинский район", "en": "Qamashi District"},  # Qamashi tumani
    "1710224": {"ru": "Каршинский район", "en": "Qarshi District"},  # Qarshi tumani
    "1710229": {"ru": "Касанский район", "en": "Koson District"},  # Koson tumani
    "1710232": {"ru": "Китабский район", "en": "Kitob District"},  # Kitob tumani
    "1710233": {"ru": "Миришкорский район", "en": "Mirishkor District"},  # Mirishkor tumani
    "1710234": {"ru": "Мубарекский район", "en": "Muborak District"},  # Muborak tumani
    "1710235": {"ru": "Нишанский район", "en": "Nishon District"},  # Nishon tumani
    "1710237": {"ru": "Касбийский район", "en": "Kasbi District"},  # Kasbi tumani
    "1710242": {"ru": "Чиракчинский район", "en": "Chiroqchi District"},  # Chiroqchi tumani
    "1710245": {"ru": "Шахрисабзский район", "en": "Shahrisabz District"},  # Shahrisabz tumani
    "1710250": {"ru": "Яккабагский район", "en": "Yakkabogʻ District"},  # Yakkabog' tumani
    "1710401": {"ru": "город Карши", "en": "Qarshi City"},  # Qarshi
    "1710405": {"ru": "город Шахрисабз", "en": "Shahrisabz City"},  # Shahrisabz
    "1712211": {"ru": "Канимехский район", "en": "Konimex District"},  # Konimex tumani
    "1712216": {"ru": "Кызылтепинский район", "en": "Qiziltepa District"},  # Qiziltepa tumani
    "1712230": {"ru": "Навбахорский район", "en": "Navbahor District"},  # Navbahor tumani
    "1712234": {"ru": "Кармининский район", "en": "Karmana District"},  # Karmana tumani
    "1712238": {"ru": "Нуратинский район", "en": "Nurota District"},  # Nurota tumani
    "1712244": {"ru": "Тамдынский район", "en": "Tomdi District"},  # Tomdi tumani
    "1712248": {"ru": "Учкудукский район", "en": "Uchquduq District"},  # Uchquduq tumani
    "1712251": {"ru": "Хатырчинский район", "en": "Xatirchi District"},  # Xatirchi tumani
    "1712401": {"ru": "город Навои", "en": "Navoiy City"},  # Navoiy
    "1712408": {"ru": "город Зарафшан", "en": "Zarafshon City"},  # Zarafshon
    "1712412": {"ru": "город Газган", "en": "Gʻozgʻon City"},  # G'ozg'on
    "1714204": {"ru": "Мингбулакский район", "en": "Mingbuloq District"},  # Mingbuloq tumani
    "1714207": {"ru": "Касансайский район", "en": "Kosonsoy District"},  # Kosonsoy tumani
    "1714212": {"ru": "Наманганский район", "en": "Namangan District"},  # Namangan tumani
    "1714216": {"ru": "Наринский район", "en": "Norin District"},  # Norin tumani
    "1714219": {"ru": "Папский район", "en": "Pop District"},  # Pop tumani
    "1714224": {"ru": "Туракурганский район", "en": "Toʻraqoʻrgʻon District"},  # To'raqo'rg'on tumani
    "1714229": {"ru": "Уйчинский район", "en": "Uychi District"},  # Uychi tumani
    "1714234": {"ru": "Учкурганский район", "en": "Uchqoʻrgʻon District"},  # Uchqo'rg'on tumani
    "1714236": {"ru": "Чартакский район", "en": "Chortoq District"},  # Chortoq tumani
    "1714237": {"ru": "Чустский район", "en": "Chust District"},  # Chust tumani
    "1714242": {"ru": "Янгикурганский район", "en": "Yangiqoʻrgʻon District"},  # Yangiqo'rg'on tumani
    "1714401": {"ru": "город Наманган", "en": "Namangan City"},  # Namangan
    "1718203": {"ru": "Акдарьинский район", "en": "Oqdaryo District"},  # Oqdaryo tumani
    "1718206": {"ru": "Булунгурский район", "en": "Bulungʻur District"},  # Bulung'ur tumani
    "1718209": {"ru": "Джамбайский район", "en": "Jomboy District"},  # Jomboy tumani
    "1718212": {"ru": "Иштыханский район", "en": "Ishtixon District"},  # Ishtixon tumani
    "1718215": {"ru": "Каттакурганский район", "en": "Kattaqoʻrgʻon District"},  # Kattaqo'rg'on tumani
    "1718216": {"ru": "Кошрабадский район", "en": "Qoʻshrabot District"},  # Qo'shrabot tumani
    "1718218": {"ru": "Нарпайский район", "en": "Narpay District"},  # Narpay tumani
    "1718224": {"ru": "Пайарыкский район", "en": "Payariq District"},  # Payariq tumani
    "1718227": {"ru": "Пастдаргомский район", "en": "Pastdargʻom District"},  # Pastdarg'om tumani
    "1718230": {"ru": "Пахтачийский район", "en": "Paxtachi District"},  # Paxtachi tumani
    "1718233": {"ru": "Самаркандский район", "en": "Samarqand District"},  # Samarqand tumani
    "1718235": {"ru": "Нурабадский район", "en": "Nurobod District"},  # Nurobod tumani
    "1718236": {"ru": "Ургутский район", "en": "Urgut District"},  # Urgut tumani
    "1718238": {"ru": "Тайлякский район", "en": "Tayloq District"},  # Tayloq tumani
    "1718401": {"ru": "город Самарканд", "en": "Samarkand City"},  # Samarqand
    "1718406": {"ru": "город Каттакурган", "en": "Kattaqoʻrgʻon City"},  # Kattaqo'rg'on
    "1722201": {"ru": "Алтынсайский район", "en": "Oltinsoy District"},  # Oltinsoy tumani
    "1722202": {"ru": "Ангорский район", "en": "Angor District"},  # Angor tumani
    "1722203": {"ru": "Бандиханский район", "en": "Bandixon District"},  # Bandixon tumani
    "1722204": {"ru": "Байсунский район", "en": "Boysun District"},  # Boysun tumani
    "1722207": {"ru": "Музрабадский район", "en": "Muzrabot District"},  # Muzrabot tumani
    "1722210": {"ru": "Денауский район", "en": "Denov District"},  # Denov tumani
    "1722212": {"ru": "Джаркурганский район", "en": "Jarqoʻrgʻon District"},  # Jarqo'rg'on tumani
    "1722214": {"ru": "Кумкурганский район", "en": "Qumqoʻrgʻon District"},  # Qumqo'rg'on tumani
    "1722215": {"ru": "Кызырыкский район", "en": "Qiziriq District"},  # Qiziriq tumani
    "1722217": {"ru": "Сариасийский район", "en": "Sariosiyo District"},  # Sariosiyo tumani
    "1722220": {"ru": "Термезский район", "en": "Termiz District"},  # Termiz tumani
    "1722221": {"ru": "Узунский район", "en": "Uzun District"},  # Uzun tumani
    "1722223": {"ru": "Шерабадский район", "en": "Sherobod District"},  # Sherobod tumani
    "1722226": {"ru": "Шурчинский район", "en": "Shoʻrchi District"},  # Sho'rchi tumani
    "1722401": {"ru": "город Термез", "en": "Termez City"},  # Termiz
    "1724206": {"ru": "Акалтынский район", "en": "Oqoltin District"},  # Oqoltin tumani
    "1724212": {"ru": "Баяутский район", "en": "Boyovut District"},  # Boyovut tumani
    "1724216": {"ru": "Сайхунабадский район", "en": "Sayxunobod District"},  # Sayxunobod tumani
    "1724220": {"ru": "Гулистанский район", "en": "Guliston District"},  # Guliston tumani
    "1724226": {"ru": "Сардобинский район", "en": "Sardoba District"},  # Sardoba tumani
    "1724228": {"ru": "Мирзаабадский район", "en": "Mirzaobod District"},  # Mirzaobod tumani
    "1724231": {"ru": "Сырдарьинский район", "en": "Sirdaryo District"},  # Sirdaryo tumani
    "1724235": {"ru": "Хавастский район", "en": "Xovos District"},  # Xovos tumani
    "1724401": {"ru": "город Гулистан", "en": "Guliston City"},  # Guliston
    "1724410": {"ru": "город Ширин", "en": "Shirin City"},  # Shirin
    "1724413": {"ru": "город Янгиер", "en": "Yangiyer City"},  # Yangiyer
    "1726262": {"ru": "Учтепинский район", "en": "Uchtepa District"},  # Uchtepa tumani
    "1726264": {"ru": "Бектемирский район", "en": "Bektemir District"},  # Bektemir tumani
    "1726266": {"ru": "Юнусабадский район", "en": "Yunusobod District"},  # Yunusobod tumani
    "1726269": {"ru": "Мирзо-Улугбекский район", "en": "Mirzo Ulugʻbek District"},  # Mirzo Ulug'bek tumani
    "1726273": {"ru": "Мирабадский район", "en": "Mirobod District"},  # Mirobod tumani
    "1726277": {"ru": "Шайхантахурский район", "en": "Shayxontoxur District"},  # Shayxontoxur tumani
    "1726280": {"ru": "Алмазарский район", "en": "Olmazor District"},  # Olmazor tumani
    "1726283": {"ru": "Сергелийский район", "en": "Sirgʻali District"},  # Sirg'ali tumani
    "1726287": {"ru": "Яккасарайский район", "en": "Yakkasaroy District"},  # Yakkasaroy tumani
    "1726290": {"ru": "Яшнабадский район", "en": "Yashnobod District"},  # Yashnobod tumani
    "1726292": {"ru": "Янгихаётский район", "en": "Yangihayot District"},  # Yangihayot tumani
    "1726294": {"ru": "Чиланзарский район", "en": "Chilonzor District"},  # Chilonzor tumani
    "1727206": {"ru": "Аккурганский район", "en": "Oqqoʻrgʻon District"},  # Oqqo'rg'on tumani
    "1727212": {"ru": "Ахангаранский район", "en": "Ohangaron District"},  # Ohangaron tumani
    "1727220": {"ru": "Бекабадский район", "en": "Bekobod District"},  # Bekobod tumani
    "1727224": {"ru": "Бостанлыкский район", "en": "Boʻstonliq District"},  # Bo'stonliq tumani
    "1727228": {"ru": "Букинский район", "en": "Boʻka District"},  # Bo'ka tumani
    "1727233": {"ru": "Нижнечирчикский район", "en": "Quyi Chirchiq District"},  # Quyichirchiq tumani
    "1727237": {"ru": "Зангиатинский район", "en": "Zangiota District"},  # Zangiota tumani
    "1727239": {"ru": "Верхнечирчикский район", "en": "Yuqori Chirchiq District"},  # Yuqorichirchiq tumani
    "1727248": {"ru": "Кибрайский район", "en": "Qibray District"},  # Qibray tumani
    "1727249": {"ru": "Паркентский район", "en": "Parkent District"},  # Parkent tumani
    "1727250": {"ru": "Пскентский район", "en": "Pskent District"},  # Pskent tumani
    "1727253": {"ru": "Среднечирчикский район", "en": "Oʻrta Chirchiq District"},  # O'rtachirchiq tumani
    "1727256": {"ru": "Чиназский район", "en": "Chinoz District"},  # Chinoz tumani
    "1727259": {"ru": "Янгиюльский район", "en": "Yangiyoʻl District"},  # Yangiyo'l tumani
    "1727265": {"ru": "Ташкентский район", "en": "Toshkent District"},  # Toshkent tumani
    "1727401": {"ru": "город Нурафшан", "en": "Nurafshon City"},  # Nurafshon
    "1727404": {"ru": "город Алмалык", "en": "Olmaliq City"},  # Olmaliq
    "1727407": {"ru": "город Ангрен", "en": "Angren City"},  # Angren
    "1727413": {"ru": "город Бекабад", "en": "Bekobod City"},  # Bekobod
    "1727415": {"ru": "город Ахангаран", "en": "Ohangaron City"},  # Ohangaron
    "1727419": {"ru": "город Чирчик", "en": "Chirchiq City"},  # Chirchiq
    "1727424": {"ru": "город Янгиюль", "en": "Yangiyoʻl City"},  # Yangiyo'l
    "1730203": {"ru": "Алтыарыкский район", "en": "Oltiariq District"},  # Oltiariq tumani
    "1730206": {"ru": "Куштепинский район", "en": "Qoʻshtepa District"},  # Qo'shtepa tumani
    "1730209": {"ru": "Багдадский район", "en": "Bogʻdod District"},  # Bog'dod tumani
    "1730212": {"ru": "Бувайдинский район", "en": "Buvayda District"},  # Buvayda tumani
    "1730215": {"ru": "Бешарыкский район", "en": "Beshariq District"},  # Beshariq tumani
    "1730218": {"ru": "Кувинский район", "en": "Quva District"},  # Quva tumani
    "1730221": {"ru": "Учкуприкский район", "en": "Uchkoʻprik District"},  # Uchko'prik tumani
    "1730224": {"ru": "Риштанский район", "en": "Rishton District"},  # Rishton tumani
    "1730226": {"ru": "Сохский район", "en": "Soʻx District"},  # So'x tumani
    "1730227": {"ru": "Ташлакский район", "en": "Toshloq District"},  # Toshloq tumani
    "1730230": {"ru": "Узбекистанский район", "en": "Oʻzbekiston District"},  # O'zbekiston tumani
    "1730233": {"ru": "Ферганский район", "en": "Fargʻona District"},  # Farg'ona tumani
    "1730236": {"ru": "Дангаринский район", "en": "Dangʻara District"},  # Dang'ara tumani
    "1730238": {"ru": "Фуркатский район", "en": "Furqat District"},  # Furqat tumani
    "1730242": {"ru": "Языованский район", "en": "Yozyovon District"},  # Yozyovon tumani
    "1730401": {"ru": "город Фергана", "en": "Fergana City"},  # Farg'ona
    "1730405": {"ru": "город Коканд", "en": "Kokand City"},  # Qo'qon
    "1730408": {"ru": "город Кувасай", "en": "Quvasoy City"},  # Quvasoy
    "1730412": {"ru": "город Маргилан", "en": "Margilan City"},  # Marg'ilon
    "1733217": {"ru": "Ургенчский район", "en": "Urganch District"},  # Urganch tumani
    "1733204": {"ru": "Багатский район", "en": "Bogʻot District"},  # Bog'ot tumani
    "1733208": {"ru": "Гурленский район", "en": "Gurlan District"},  # Gurlan tumani
    "1733212": {"ru": "Кошкупырский район", "en": "Qoʻshkoʻpir District"},  # Qo'shko'pir tumani
    "1733220": {"ru": "Хазараспский район", "en": "Xazorasp District"},  # Xazorasp tumani
    "1733221": {"ru": "Тупроккалинский район", "en": "Tuproqqalʼa District"},  # Tuproqqal'a tumani
    "1733223": {"ru": "Ханкинский район", "en": "Xonqa District"},  # Xonqa tumani
    "1733226": {"ru": "Хивинский район", "en": "Xiva District"},  # Xiva tumani
    "1733230": {"ru": "Шаватский район", "en": "Shovot District"},  # Shovot tumani
    "1733233": {"ru": "Янгиарыкский район", "en": "Yangiariq District"},  # Yangiariq tumani
    "1733236": {"ru": "Янгибазарский район", "en": "Yangibozor District"},  # Yangibozor tumani
    "1733401": {"ru": "город Ургенч", "en": "Urgench City"},  # Urganch
    "1733406": {"ru": "город Хива", "en": "Khiva City"},  # Xiva
    "1735204": {"ru": "Амударьинский район", "en": "Amudaryo District"},  # Amudaryo tumani
    "1735207": {"ru": "Берунийский район", "en": "Beruniy District"},  # Beruniy tumani
    "1735209": {"ru": "район Бозатов", "en": "Boʻzatov District"},  # Bo'zatov tumani
    "1735211": {"ru": "Караузякский район", "en": "Qoraoʻzak District"},  # Qorao'zak tumani
    "1735212": {"ru": "Кегейлийский район", "en": "Kegeyli District"},  # Kegeyli tumani
    "1735215": {"ru": "Кунградский район", "en": "Qoʻngʻirot District"},  # Qo'ng'irot tumani
    "1735218": {"ru": "Канлыкульский район", "en": "Qanlikoʻl District"},  # Qanliko'l tumani
    "1735222": {"ru": "Муйнакский район", "en": "Moʻynoq District"},  # Mo'ynoq tumani
    "1735225": {"ru": "Нукусский район", "en": "Nukus District"},  # Nukus tumani
    "1735228": {"ru": "Тахиаташский район", "en": "Taxiatosh District"},  # Taxiatosh tumani
    "1735230": {"ru": "Тахтакупырский район", "en": "Taxtakoʻpir District"},  # Taxtako'pir tumani
    "1735233": {"ru": "Турткульский район", "en": "Toʻrtkoʻl District"},  # To'rtko'l tumani
    "1735236": {"ru": "Ходжейлийский район", "en": "Xoʻjayli District"},  # Xo'jayli tumani
    "1735240": {"ru": "Чимбайский район", "en": "Chimboy District"},  # Chimboy tumani
    "1735243": {"ru": "Шуманайский район", "en": "Shumanay District"},  # Shumanay tumani
    "1735250": {"ru": "Эллик-Калинский район", "en": "Ellikkala District"},  # Ellikkala tumani
    "1735401": {"ru": "город Нукус", "en": "Nukus City"},  # Nukus
}
