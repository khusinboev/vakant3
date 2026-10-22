# ============================================================
# src/i18n/ru.py — Русский
# ============================================================

STRINGS: dict[str, str] = {
    # ── Общее ─────────────────────────────────────────────────
    "common.yes": "Да",
    "common.no": "Нет",
    "common.available": "Есть",
    "common.unavailable": "Нет",
    "common.not_available": "Отсутствует",
    "common.back": "Назад",

    # ── Меню пользователя ─────────────────────────────────────
    "menu.laws": "Законодательство",
    "menu.hr": "HR-советы",

    # ── /start ────────────────────────────────────────────────
    "start.loading_vacancy": "{e:hourglass} Загружаем данные вакансии...",
    "start.bad_vacancy_link": "❌ Неверная ссылка на вакансию.",
    "start.vacancy_not_found": "❌ Вакансия не найдена или данные получить не удалось.",
    "start.greeting": (
        "{e:wave} Здравствуйте, <b>{name}</b>!\n\n"
        "В боте Bandlik.uz можно искать и сохранять вакансии и получать уведомления о новых.\n"
        "{e:laws} Трудовое законодательство и {e:tips} HR-советы — в меню ниже."
    ),
    "start.subscribe_prompt": "Чтобы пользоваться ботом, подпишитесь на каналы ниже:",
    "start.btn.open_app": "Открыть в приложении",
    "start.btn.open_in_bot": "Подробнее в боте",
    "start.btn.open_original": "Исходное объявление",
    "bot.menu_button": "Приложение",
    "cmd.start": "Запустить бота",
    "cmd.lang": "Сменить язык",
    "cmd.admin": "Админ-панель",
    "start.btn.jobs": "Поиск работы",
    "start.btn.profile": "Профиль",
    "start.btn.saves": "Избранное",
    "start.btn.subscribed": "Я подписался",
    "start.channel_fallback": "Канал",
    "start.check.ok": "✅ Подтверждено!",
    "start.check.welcome": (
        "{e:party} Добро пожаловать, <b>{name}</b>!\n"
        "Теперь бот доступен вам полностью."
    ),
    "start.check.fail": (
        "❌ Вы подписались не на все каналы!\n"
        "Пожалуйста, подпишитесь на каждый из них."
    ),
    "start.developer": "Разработчик бота @coder_admin_py\n\nPowered by @coder_admin_py",

    # ── Рефералы ──────────────────────────────────────────────
    "referral.reward_notice": (
        "{e:party} По вашей ссылке присоединился новый пользователь!\n"
        "{e:wallet} На ваш баланс зачислено <b>{reward} сум</b>."
    ),
    "referral.gate": (
        "{e:lock} Для доступа к боту включено условие приглашений.\n\n"
        "{e:stats} Прогресс: {current}/{required}\n"
        "{e:group} Сначала пригласите друзей:\n"
        "{link}"
    ),
    "referral.btn.share": "Поделиться с друзьями",
    "referral.share_text": "Bandlik.uz — бот с вакансиями и объявлениями о работе. Присоединяйтесь!",

    # ── Выбор языка ───────────────────────────────────────────
    "lang.choose": "{e:lang} Выберите язык:",
    "lang.saved": "✅ Язык изменён: Русский",
    "lang.name.uz": "🇺🇿 O'zbekcha",
    "lang.name.ru": "🇷🇺 Русский",
    "lang.name.en": "🇬🇧 English",

    # ── Контент: законодательство и HR ────────────────────────
    "content.laws.header": (
        "{e:laws} <b>Трудовой кодекс Узбекистана</b>\n\n"
        "Выберите интересующую статью:"
    ),
    "content.laws.not_found": "Статья не найдена",
    "content.laws.read_more": "Читать на lex.uz",
    "content.truncated": "<i>... (читать полностью)</i>",
    "content.hr.header": (
        "{e:tips} <b>HR-советы</b>\n\n"
        "Практические рекомендации для развития вашей карьеры:"
    ),
    "content.hr.not_found": "Совет не найден",

    # ── Вакансия: зарплата и коды ─────────────────────────────
    "vacancy.title_fallback": "Вакансия",
    "vacancy.salary.range": "{min} – {max} сум",
    "vacancy.salary.from": "от {min} сум",
    "vacancy.salary.upto": "до {max} сум",
    "vacancy.salary.negotiable": "По договорённости",
    "vacancy.salary.unspecified": "Не указана",
    "vacancy.salary.cur_range": "{min} – {max} {cur}",
    "vacancy.salary.cur_from": "от {min} {cur}",
    "vacancy.salary.cur_upto": "до {max} {cur}",
    "vacancy.code_unknown": "Код {code}",

    "vacancy.gender.1": "Мужчина",
    "vacancy.gender.2": "Женщина",
    "vacancy.gender.3": "Не имеет значения",

    "vacancy.work_type.1": "Постоянная работа",
    "vacancy.work_type.2": "Временная работа",
    "vacancy.work_type.3": "Сезонная работа",

    "vacancy.busyness.1": "Полная занятость",
    "vacancy.busyness.2": "Частичная занятость",

    "vacancy.payment.1": "Ежемесячно",
    "vacancy.payment.2": "Ежедневно",
    "vacancy.payment.3": "Почасовая оплата",
    "vacancy.payment.4": "Сдельная оплата",

    "vacancy.education.1": "Среднее общее",
    "vacancy.education.2": "Среднее специальное",
    "vacancy.education.3": "Бакалавр",
    "vacancy.education.4": "Магистр",

    "vacancy.experience.1": "Опыт не требуется",
    "vacancy.experience.2": "До 1 года",
    "vacancy.experience.3": "1–3 года",
    "vacancy.experience.4": "3+ года",

    # hh.uz dictionary ids (experience / employment / schedule)
    "vacancy.hh.experience.noExperience": "Без опыта",
    "vacancy.hh.experience.between1And3": "1–3 года",
    "vacancy.hh.experience.between3And6": "3–6 лет",
    "vacancy.hh.experience.moreThan6": "Более 6 лет",
    "vacancy.hh.employment.full": "Полная занятость",
    "vacancy.hh.employment.part": "Частичная занятость",
    "vacancy.hh.employment.project": "Проектная работа",
    "vacancy.hh.employment.volunteer": "Волонтёрство",
    "vacancy.hh.employment.probation": "Стажировка",
    "vacancy.hh.schedule.fullDay": "Полный день",
    "vacancy.hh.schedule.shift": "Сменный график",
    "vacancy.hh.schedule.flexible": "Гибкий график",
    "vacancy.hh.schedule.remote": "Удалённая работа",
    "vacancy.hh.schedule.flyInFlyOut": "Вахтовый метод",

    # ── Вакансия: подписи полей ───────────────────────────────
    "vacancy.label.company": "Организация",
    "vacancy.label.salary": "Зарплата",
    "vacancy.label.address": "Адрес",
    "vacancy.label.work_type": "Тип работы",
    "vacancy.label.busyness": "Занятость",
    "vacancy.label.payment": "Тип оплаты",
    "vacancy.label.education": "Образование",
    "vacancy.label.experience": "Опыт",
    "vacancy.label.gender": "Пол",
    "vacancy.openings": "Мест: {n}",
    "vacancy.label.count": "Количество мест",
    "vacancy.label.hours": "Рабочее время",
    "vacancy.label.posted": "Дата публикации",
    "vacancy.label.deadline": "Срок",
    "vacancy.label.description": "Описание",
    "vacancy.label.contacts": "Контакты",
    "vacancy.label.source": "Источник",
    "vacancy.label.phone": "Тел",
    "vacancy.label.email": "Email",

    # ── Уведомления ───────────────────────────────────────────
    "notify.header": "{e:bell} <b>Вакансия для вас</b>",
    "notify.details": "Подробнее",

    # ── Админ: кнопки ─────────────────────────────────────────
    "btn.admin.stats": "Статистика",
    "btn.admin.channels": "Каналы",
    "btn.admin.ads": "Рассылка",
    "btn.admin.channel_add": "Добавить канал",
    "btn.admin.channel_del": "Удалить канал",
    "btn.admin.channel_list": "Список каналов",
    "btn.admin.back": "Назад",

    # ── Админ: сообщения ──────────────────────────────────────
    "admin.hello": "{e:admin} Здравствуйте, админ",
    "admin.main_menu": "Главное меню",
    "admin.choose": "Выберите",
    "admin.channel_add_prompt": (
        "Отправьте username канала, который нужно добавить.\nПример: @coder_admin"
    ),
    "admin.channel_del_prompt": (
        "Отправьте username канала, который нужно удалить.\nПример: @coder_admin"
    ),
    "admin.cancelled": "Отменено",
    "admin.text_required": "Пожалуйста, отправьте текстовое сообщение.",
    "admin.channel_bad_format": "Неверный username! Введите в формате @coder_admin",
    "admin.channel_exists": "Этот канал уже добавлен",
    "admin.channel_added": "{e:party} Канал добавлен",
    "admin.channel_missing": "Такого канала нет",
    "admin.channel_deleted": "Канал удалён",
    "admin.channels_empty": "Пока каналов нет",
    "admin.broadcast_menu": "Раздел рассылки сообщений пользователям",
    "admin.progress": (
        "Отправляется... {done}/{total}\n"
        "✅ Успешно: {ok}\n"
        "❌ Ошибок: {fail}"
    ),
    "admin.finished": (
        "✅ Рассылка завершена!\n\n"
        "📊 Всего: {total}\n"
        "✅ Доставлено: {ok}\n"
        "❌ Не доставлено: {fail}"
    ),
    "admin.stats.header": "{e:stats} <b>Статистика пользователей</b>",
    "admin.stats.total": "Всего: {count}",
    "admin.stats.blocked": "🚫 Заблокировали бота: {count}",
    "admin.stats.last3m": "Последние 3 месяца (всего: {count}):",
    "admin.stats.last7d": "Последние 7 дней ({count}):",
    "admin.stats.row": "🔹 {label}: {count}",
    "menu.admin": "Админ",
    "btn.admin.exit": "Главное меню",
    "menu.refreshed": "{e:sparkles} Меню обновлено.",
    "stats2.title": "{e:stats} Статистика",
    "stats2.sec.users": "Пользователи",
    "stats2.sec.pro": "Pro",
    "stats2.sec.payments": "Платежи",
    "stats2.sec.wallet": "Движение по кошелькам (30 дней)",
    "stats2.sec.referrals": "Рефералы",
    "stats2.sec.broadcasts": "Последние рассылки",
    "stats2.users.total": "Всего",
    "stats2.users.today": "Новых сегодня",
    "stats2.users.d7": "Новых за 7 дней",
    "stats2.users.d30": "Новых за 30 дней",
    "stats2.users.active7": "Активных за 7 дней",
    "stats2.users.blocked": "Заблокировали бота",
    "stats2.users.banned": "Забанены",
    "stats2.pro.count": "Pro-пользователи",
    "stats2.pro.act7": "Активаций (7 дней)",
    "stats2.pro.act30": "Активаций (30 дней)",
    "stats2.pay.period": "Период",
    "stats2.pay.paid": "Оплачено",
    "stats2.pay.sum": "Сумма",
    "stats2.period.today": "Сегодня",
    "stats2.period.d7": "7 дней",
    "stats2.period.d30": "30 дней",
    "stats2.period.all": "Всего",
    "stats2.pay.pending": "Ожидают",
    "stats2.pay.cancelled": "Отменены",
    "stats2.pay.by_method": "По способу (всего)",
    "stats2.method.page": "Страница",
    "stats2.method.card": "Карта",
    "stats2.method.phone": "Телефон",
    "stats2.method.app": "Приложение",
    "stats2.method.unknown": "Другое",
    "stats2.wallet.topup": "Пополнения",
    "stats2.wallet.topup_bonus": "Бонусы за пополнение",
    "stats2.wallet.pro_activation": "Активация Pro",
    "stats2.wallet.referral_reward": "Реферальные награды",
    "stats2.ref.new30": "Новых рефералов (30 дней)",
    "stats2.bc.none": "Рассылок ещё не было",
    "stats2.bc.row": "#{id} {status}: отправлено {sent}, ошибок {failed}",
    "stats2.money": "{amount} сум",
    "stats2.col.metric": "Показатель",
    "stats2.col.value": "Значение",
    "admin.channels_status_header": "📊 Состояние каналов:",
    "admin.channels_db_empty": "❌ В базе нет каналов",
    "admin.diag.id": "ID",
    "admin.diag.admin": "Админ",
    "admin.diag.link": "Ссылка",
    "admin.diag.error": "Ошибка",
    "admin.channel_info": (
        "Username канала: {username}\n"
        "Название канала: {title}\n"
        "ID канала: {chat_id}\n"
        "Описание: {about}"
    ),
    "admin.channel_no_admin": "Канал {username} — сделайте бота администратором",
    "admin.channels_none": "Каналов нет",

    # ── Admin: broadcast wizard ───────────────────────────────
    "btn.admin.bc_new": "Новая рассылка",
    "btn.admin.bc_list": "Рассылки",
    "btn.admin.webapp": "Открыть админ-панель",
    "admin.webapp_hint": "{e:app} Расширенное управление — в Mini App:",
    "admin.denied": "⛔ У вас нет прав на это действие.",
    "bc.prompt_content": "Отправьте сообщение для рассылки: текст, фото, видео, документ или GIF.\nФорматирование и эмодзи сохранятся.",
    "bc.bad_content": "Такой тип сообщения не поддерживается. Отправьте текст, фото, видео, документ или GIF.",
    "bc.album_unsupported": "Альбомы (несколько фото или видео) не поддерживаются. Отправьте одно сообщение: одно фото, видео или документ, при необходимости с подписью.",
    "bc.prompt_button": "Чтобы добавить кнопку, отправьте <code>Текст | https://...</code> или нажмите «Пропустить».",
    "bc.bad_button": "Неверный формат кнопки. Пример: <code>Подробнее | https://bandlik.uz</code> (текст до 64 символов, ссылка http или https).",
    "bc.prompt_audience": "{e:group} Кому отправляем?",
    "bc.empty_segment": "В этой аудитории нет получателей. Выберите другую.",
    "bc.preview_card": "👆 Так сообщение увидят пользователи.\n\n👥 Аудитория: {segment}\n📨 Получателей: <b>{count}</b>\n🔘 Кнопка: {button}\n\nПеред отправкой проверьте через «🧪 Тест себе».",
    "bc.no_button": "нет",
    "bc.preview_failed": "Не удалось скопировать сообщение (возможно, оно удалено). Начните заново.",
    "bc.expired": "Это действие устарело. Начните заново.",
    "bc.test_sent": "🧪 Тестовое сообщение отправлено вам",
    "bc.test_failed": "Не удалось отправить тест",
    "bc.already_queued": "Эта рассылка уже в очереди",
    "bc.queued": "✅ В очереди: {total} получателей",
    "bc.card": "📣 <b>Рассылка #{id}</b> · {status}\n👥 {segment}\n\n{body}",
    "bc.status.draft": "📝 черновик",
    "bc.status.queued": "⏳ в очереди",
    "bc.status.running": "🚀 отправляется",
    "bc.status.paused": "⏸ на паузе",
    "bc.status.cancelled": "✖ остановлена",
    "bc.status.done": "✅ завершена",
    "bc.status.failed": "❌ ошибка",
    "bc.state_changed": "Статус: {status}",
    "bc.state_unchanged": "В текущем статусе это действие недоступно",
    "bc.stop_confirm": "\n\n⚠️ Остановить рассылку окончательно? Это нельзя отменить.",
    "bc.list_header": "{e:list} <b>Последние рассылки</b>",
    "bc.list_row": "#{id} · {status} · {done}/{total}",
    "bc.list_empty": "Рассылок пока нет",
    "bc.btn.skip": "Пропустить",
    "bc.btn.cancel": "Отмена",
    "bc.btn.test": "Тест себе",
    "bc.btn.send": "Отправить {count}",
    "bc.btn.pause": "Пауза",
    "bc.btn.resume": "Продолжить",
    "bc.btn.stop": "Стоп",
    "bc.btn.stop_yes": "Да, остановить",
    "bc.btn.stop_no": "Нет",
    "bc.btn.refresh": "Обновить",
    "bc.seg.all": "👥 Все",
    "bc.seg.pro": "⭐ Pro",
    "bc.seg.free": "🆓 Бесплатные",
    "bc.seg.lang_uz": "🇺🇿 Узбекский",
    "bc.seg.lang_ru": "🇷🇺 Русский",
    "bc.seg.lang_en": "🇬🇧 Английский",
    "bc.seg.active_7": "🔥 Активные (7 дней)",
    "bc.seg.active_30": "📆 Активные (30 дней)",
    "bc.seg.test_admins": "🧪 Только админы (тест)",

    # ── Недельная статистика ──────────────────────────────────
    "stats.header": "📊 <b>Статистика за неделю</b> | {label}",
    "stats.users": "👥 <b>Пользователи</b>",
    "stats.users_line": "   +{new} новых (всего: {total})",
    "stats.pro_line": "   💎 Pro: {count}",
    "stats.vacancies": "💼 <b>Вакансии</b>",
    "stats.active_line": "   Активных объявлений: ~{count}",
    "stats.avg_salary_line": "   Средняя зарплата: {amount} сум",
    "stats.top_specs": "🏆 <b>Топ отраслей:</b>",
    "stats.top_regions": "📍 <b>Топ регионов:</b>",
    "stats.top_row": "   {i}. {name} — {count}",
    "stats.resumes": "📄 Создано резюме: {count}",
    "stats.saves": "❤️ В избранном: {count}",
    "stats.week_short": "{day} {month}",
    "stats.week_range_same_month": "{d1}–{d2} {month} {year}",
    "stats.week_range": "{d1} {month1} – {d2} {month2} {year}",

    # ── Названия месяцев (родительный падеж) ──────────────────
    "month.1": "января",
    "month.2": "февраля",
    "month.3": "марта",
    "month.4": "апреля",
    "month.5": "мая",
    "month.6": "июня",
    "month.7": "июля",
    "month.8": "августа",
    "month.9": "сентября",
    "month.10": "октября",
    "month.11": "ноября",
    "month.12": "декабря",

    # ── Chart / grafik ────────────────────────────────────────
    "chart.title": "Статистика за неделю — {label}",
    "chart.top_specs": "Топ отраслей",
    "chart.top_regions": "Топ регионов",
    "chart.new_users": "Новые пользователи по неделям",
    "chart.avg_salary": "Средняя зарплата (сум)",
}
