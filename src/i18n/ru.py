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
    "common.back": "◀️ Назад",

    # ── Меню пользователя ─────────────────────────────────────
    "menu.laws": "⚖️ Законодательство",
    "menu.hr": "💡 HR-советы",

    # ── /start ────────────────────────────────────────────────
    "start.loading_vacancy": "⏳ Загружаем данные вакансии...",
    "start.bad_vacancy_link": "❌ Неверная ссылка на вакансию.",
    "start.vacancy_not_found": "❌ Вакансия не найдена или данные получить не удалось.",
    "start.extra_sections": "Дополнительные разделы:",
    "start.greeting": (
        "Здравствуйте, {name}!\n"
        "Добро пожаловать в наш бот. Выберите нужный раздел!"
    ),
    "start.subscribe_prompt": "Чтобы пользоваться ботом, подпишитесь на каналы ниже:",
    "start.btn.jobs": "💼 Поиск работы",
    "start.btn.profile": "👤 Профиль",
    "start.btn.saves": "🗂 Избранное",
    "start.btn.subscribed": "✅ Я подписался",
    "start.channel_fallback": "Канал",
    "start.check.ok": "✅ Подтверждено!",
    "start.check.welcome": (
        "Добро пожаловать, {name}!\n"
        "Теперь бот доступен вам полностью."
    ),
    "start.check.fail": (
        "❌ Вы подписались не на все каналы!\n"
        "Пожалуйста, подпишитесь на каждый из них."
    ),
    "start.developer": "Разработчик бота @coder_admin_py\n\nPowered by @coder_admin_py",

    # ── Рефералы ──────────────────────────────────────────────
    "referral.reward_notice": (
        "🎉 По вашей ссылке присоединился новый пользователь!\n"
        "На ваш баланс зачислено <b>{reward} сум</b>."
    ),
    "referral.gate": (
        "🔒 Для доступа к боту включено условие приглашений.\n\n"
        "📊 Прогресс: {current}/{required}\n"
        "👥 Сначала пригласите друзей:\n"
        "{link}"
    ),

    # ── Выбор языка ───────────────────────────────────────────
    "lang.choose": "🌐 Выберите язык:",
    "lang.saved": "✅ Язык изменён: Русский",
    "lang.name.uz": "🇺🇿 O'zbekcha",
    "lang.name.ru": "🇷🇺 Русский",
    "lang.name.en": "🇬🇧 English",

    # ── Контент: законодательство и HR ────────────────────────
    "content.laws.header": (
        "📚 <b>Трудовой кодекс Узбекистана</b>\n\nВыберите интересующую статью:"
    ),
    "content.laws.not_found": "Статья не найдена",
    "content.laws.read_more": "🔗 Читать на lex.uz",
    "content.truncated": "<i>... (читать полностью)</i>",
    "content.hr.header": (
        "🎯 <b>HR-советы</b>\n\nПрактические рекомендации для развития вашей карьеры:"
    ),
    "content.hr.not_found": "Совет не найден",

    # ── Вакансия: зарплата и коды ─────────────────────────────
    "vacancy.title_fallback": "Вакансия",
    "vacancy.salary.range": "{min} – {max} сум",
    "vacancy.salary.from": "от {min} сум",
    "vacancy.salary.upto": "до {max} сум",
    "vacancy.salary.negotiable": "По договорённости",
    "vacancy.salary.unspecified": "Не указана",
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
    "notify.header": "📌 <b>Вакансия для вас</b>",
    "notify.details": "Подробнее",

    # ── Админ: кнопки ─────────────────────────────────────────
    "btn.admin.stats": "📊Статистика",
    "btn.admin.channels": "🔧Каналы",
    "btn.admin.ads": "📤Рассылка",
    "btn.admin.channel_add": "➕Добавить канал",
    "btn.admin.channel_del": "❌Удалить канал",
    "btn.admin.channel_list": "📋 Список каналов",
    "btn.admin.back": "🔙Назад",
    "btn.admin.forward": "📨Переслать сообщение",
    "btn.admin.copy": "📬Обычное сообщение",

    # ── Админ: сообщения ──────────────────────────────────────
    "admin.hello": "Здравствуйте, админ",
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
    "admin.channel_added": "Канал добавлен 🎉",
    "admin.channel_missing": "Такого канала нет",
    "admin.channel_deleted": "Канал удалён",
    "admin.channels_empty": "Пока каналов нет",
    "admin.broadcast_menu": "Раздел рассылки сообщений пользователям",
    "admin.forward_prompt": "Отправьте сообщение, которое нужно переслать",
    "admin.copy_prompt": "Отправьте сообщение для рассылки",
    "admin.sending": "Отправляется... {done}/{total}",
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
    "admin.stats.header": "📊 <b>Статистика пользователей</b> 📊",
    "admin.stats.total": "Всего: {count}",
    "admin.stats.blocked": "🚫 Заблокировали бота: {count}",
    "admin.stats.last3m": "Последние 3 месяца (всего: {count}):",
    "admin.stats.last7d": "Последние 7 дней ({count}):",
    "admin.stats.row": "🔹 {label}: {count}",
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
