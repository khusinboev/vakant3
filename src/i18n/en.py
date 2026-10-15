# ============================================================
# src/i18n/en.py — English
# ============================================================

STRINGS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────
    "common.yes": "Yes",
    "common.no": "No",
    "common.available": "Yes",
    "common.unavailable": "No",
    "common.not_available": "Not available",
    "common.back": "◀️ Back",

    # ── User menu ─────────────────────────────────────────────
    "menu.laws": "⚖️ Labour law",
    "menu.hr": "💡 HR tips",

    # ── /start ────────────────────────────────────────────────
    "start.loading_vacancy": "⏳ Loading the vacancy details...",
    "start.bad_vacancy_link": "❌ Invalid vacancy link.",
    "start.vacancy_not_found": "❌ Vacancy not found, or the data could not be loaded.",
    "start.extra_sections": "More sections:",
    "start.greeting": (
        "Hello, {name}!\n"
        "Welcome to our bot. Pick the section you need!"
    ),
    "start.subscribe_prompt": "To use the bot, please subscribe to the channels below:",
    "start.btn.jobs": "💼 Find a job",
    "start.btn.profile": "👤 Profile",
    "start.btn.saves": "🗂 Saved",
    "start.btn.subscribed": "✅ I've subscribed",
    "start.channel_fallback": "Channel",
    "start.check.ok": "✅ Confirmed!",
    "start.check.welcome": (
        "Welcome, {name}!\n"
        "You now have full access to the bot."
    ),
    "start.check.fail": (
        "❌ You are not subscribed to all of the channels yet!\n"
        "Please subscribe to every one of them."
    ),
    "start.developer": "Bot developer @coder_admin_py\n\nPowered by @coder_admin_py",

    # ── Referrals ─────────────────────────────────────────────
    "referral.reward_notice": (
        "🎉 A new user joined through your link!\n"
        "<b>{reward} UZS</b> has been added to your balance."
    ),
    "referral.gate": (
        "🔒 Access to the bot requires invitations.\n\n"
        "📊 Progress: {current}/{required}\n"
        "👥 Invite your friends first:\n"
        "{link}"
    ),

    # ── Language ──────────────────────────────────────────────
    "lang.choose": "🌐 Choose your language:",
    "lang.saved": "✅ Language changed: English",
    "lang.name.uz": "🇺🇿 O'zbekcha",
    "lang.name.ru": "🇷🇺 Русский",
    "lang.name.en": "🇬🇧 English",

    # ── Content: labour law and HR ────────────────────────────
    "content.laws.header": (
        "📚 <b>Labour Code of Uzbekistan</b>\n\nPick the article you are interested in:"
    ),
    "content.laws.not_found": "Article not found",
    "content.laws.read_more": "🔗 Read on lex.uz",
    "content.truncated": "<i>... (read the full text)</i>",
    "content.hr.header": (
        "🎯 <b>HR tips</b>\n\nPractical advice to grow your career:"
    ),
    "content.hr.not_found": "Tip not found",

    # ── Vacancy: salary and codes ─────────────────────────────
    "vacancy.title_fallback": "Vacancy",
    "vacancy.salary.range": "{min} – {max} UZS",
    "vacancy.salary.from": "from {min} UZS",
    "vacancy.salary.upto": "up to {max} UZS",
    "vacancy.salary.negotiable": "Negotiable",
    "vacancy.salary.unspecified": "Not specified",
    "vacancy.code_unknown": "Code {code}",

    "vacancy.gender.1": "Male",
    "vacancy.gender.2": "Female",
    "vacancy.gender.3": "Any",

    "vacancy.work_type.1": "Permanent",
    "vacancy.work_type.2": "Temporary",
    "vacancy.work_type.3": "Seasonal",

    "vacancy.busyness.1": "Full-time",
    "vacancy.busyness.2": "Part-time",

    "vacancy.payment.1": "Monthly",
    "vacancy.payment.2": "Daily",
    "vacancy.payment.3": "Hourly",
    "vacancy.payment.4": "Piece rate",

    "vacancy.education.1": "General secondary",
    "vacancy.education.2": "Vocational secondary",
    "vacancy.education.3": "Bachelor's degree",
    "vacancy.education.4": "Master's degree",

    "vacancy.experience.1": "No experience required",
    "vacancy.experience.2": "Up to 1 year",
    "vacancy.experience.3": "1–3 years",
    "vacancy.experience.4": "3+ years",

    # ── Vacancy: field labels ─────────────────────────────────
    "vacancy.label.company": "Company",
    "vacancy.label.salary": "Salary",
    "vacancy.label.address": "Address",
    "vacancy.label.work_type": "Employment type",
    "vacancy.label.busyness": "Workload",
    "vacancy.label.payment": "Payment type",
    "vacancy.label.education": "Education",
    "vacancy.label.experience": "Experience",
    "vacancy.label.gender": "Gender",
    "vacancy.label.count": "Openings",
    "vacancy.label.hours": "Working hours",
    "vacancy.label.posted": "Posted on",
    "vacancy.label.deadline": "Deadline",
    "vacancy.label.description": "Description",
    "vacancy.label.contacts": "Contacts",
    "vacancy.label.source": "Source",
    "vacancy.label.phone": "Phone",
    "vacancy.label.email": "Email",

    # ── Notifications ─────────────────────────────────────────
    "notify.header": "📌 <b>A job pick for you</b>",
    "notify.details": "View details",

    # ── Admin: buttons ────────────────────────────────────────
    "btn.admin.stats": "📊Statistics",
    "btn.admin.channels": "🔧Channels",
    "btn.admin.ads": "📤Broadcast",
    "btn.admin.channel_add": "➕Add channel",
    "btn.admin.channel_del": "❌Remove channel",
    "btn.admin.channel_list": "📋 Channel list",
    "btn.admin.back": "🔙Back",

    # ── Admin: messages ───────────────────────────────────────
    "admin.hello": "Hello, admin",
    "admin.main_menu": "Main menu",
    "admin.choose": "Choose an option",
    "admin.channel_add_prompt": (
        "Send the username of the channel to add.\nExample: @coder_admin"
    ),
    "admin.channel_del_prompt": (
        "Send the username of the channel to remove.\nExample: @coder_admin"
    ),
    "admin.cancelled": "Cancelled",
    "admin.text_required": "Please send a text message.",
    "admin.channel_bad_format": "Invalid channel username! Use the @coder_admin format",
    "admin.channel_exists": "This channel has already been added",
    "admin.channel_added": "Channel added 🎉",
    "admin.channel_missing": "No such channel",
    "admin.channel_deleted": "Channel removed",
    "admin.channels_empty": "No channels yet",
    "admin.broadcast_menu": "Broadcast messages to users",
    "admin.progress": (
        "Sending... {done}/{total}\n"
        "✅ Delivered: {ok}\n"
        "❌ Failed: {fail}"
    ),
    "admin.finished": (
        "✅ Broadcast finished!\n\n"
        "📊 Total: {total}\n"
        "✅ Delivered: {ok}\n"
        "❌ Failed: {fail}"
    ),
    "admin.stats.header": "📊 <b>User statistics</b> 📊",
    "admin.stats.total": "Total: {count}",
    "admin.stats.blocked": "🚫 Blocked the bot: {count}",
    "admin.stats.last3m": "Last 3 months (total: {count}):",
    "admin.stats.last7d": "Last 7 days ({count}):",
    "admin.stats.row": "🔹 {label}: {count}",
    "admin.channels_status_header": "📊 Channel status:",
    "admin.channels_db_empty": "❌ No channels in the database",
    "admin.diag.id": "ID",
    "admin.diag.admin": "Admin",
    "admin.diag.link": "Invite link",
    "admin.diag.error": "Error",
    "admin.channel_info": (
        "Channel username: {username}\n"
        "Channel title: {title}\n"
        "Channel ID: {chat_id}\n"
        "About: {about}"
    ),
    "admin.channel_no_admin": "Channel {username} — make the bot an administrator",
    "admin.channels_none": "There are no channels",

    # ── Admin: broadcast wizard ───────────────────────────────
    "btn.admin.bc_new": "🆕 New broadcast",
    "btn.admin.bc_list": "📋 Broadcasts",
    "btn.admin.webapp": "🖥 Open the admin panel",
    "admin.webapp_hint": "Full controls live in the Mini App:",
    "admin.denied": "⛔ You are not allowed to do this.",
    "bc.prompt_content": "Send the message to broadcast: text, photo, video, document or GIF.\nFormatting and emoji are kept.",
    "bc.bad_content": "This kind of message is not supported. Send text, a photo, video, document or GIF.",
    "bc.album_unsupported": "Albums (several photos or videos) are not supported. Send a single message: one photo, video or document, with a caption if needed.",
    "bc.prompt_button": "To add a button send <code>Text | https://...</code> or tap «Skip».",
    "bc.bad_button": "Invalid button. Example: <code>Details | https://bandlik.uz</code> (text up to 64 characters, an http or https link).",
    "bc.prompt_audience": "👥 Who should receive it?",
    "bc.empty_segment": "Nobody is in this audience. Pick another one.",
    "bc.preview_card": "👆 This is how users will see the message.\n\n👥 Audience: {segment}\n📨 Recipients: <b>{count}</b>\n🔘 Button: {button}\n\nCheck it with «🧪 Test to me» before sending.",
    "bc.no_button": "none",
    "bc.preview_failed": "Could not copy the message (it may have been deleted). Start again.",
    "bc.expired": "This action has expired. Start again.",
    "bc.test_sent": "🧪 Test message sent to you",
    "bc.test_failed": "Could not send the test message",
    "bc.already_queued": "This broadcast is already queued",
    "bc.queued": "✅ Queued for {total} recipients",
    "bc.card": "📣 <b>Broadcast #{id}</b> · {status}\n👥 {segment}\n\n{body}",
    "bc.status.draft": "📝 draft",
    "bc.status.queued": "⏳ queued",
    "bc.status.running": "🚀 sending",
    "bc.status.paused": "⏸ paused",
    "bc.status.cancelled": "✖ stopped",
    "bc.status.done": "✅ finished",
    "bc.status.failed": "❌ failed",
    "bc.state_changed": "Status: {status}",
    "bc.state_unchanged": "Not possible in the current status",
    "bc.stop_confirm": "\n\n⚠️ Stop this broadcast for good? This cannot be undone.",
    "bc.list_header": "📋 <b>Latest broadcasts</b>",
    "bc.list_row": "#{id} · {status} · {done}/{total}",
    "bc.list_empty": "No broadcasts yet",
    "bc.btn.skip": "⏭ Skip",
    "bc.btn.cancel": "✖ Cancel",
    "bc.btn.test": "🧪 Test to me",
    "bc.btn.send": "✅ Send to {count}",
    "bc.btn.pause": "⏸ Pause",
    "bc.btn.resume": "▶ Resume",
    "bc.btn.stop": "✖ Stop",
    "bc.btn.stop_yes": "✅ Yes, stop",
    "bc.btn.stop_no": "◀ No",
    "bc.btn.refresh": "🔄 Refresh",
    "bc.seg.all": "👥 Everyone",
    "bc.seg.pro": "⭐ Pro",
    "bc.seg.free": "🆓 Free",
    "bc.seg.lang_uz": "🇺🇿 Uzbek",
    "bc.seg.lang_ru": "🇷🇺 Russian",
    "bc.seg.lang_en": "🇬🇧 English",
    "bc.seg.active_7": "🔥 Active (7 days)",
    "bc.seg.active_30": "📆 Active (30 days)",
    "bc.seg.test_admins": "🧪 Admins only (dry run)",

    # ── Weekly statistics ─────────────────────────────────────
    "stats.header": "📊 <b>Weekly statistics</b> | {label}",
    "stats.users": "👥 <b>Users</b>",
    "stats.users_line": "   +{new} new (total: {total})",
    "stats.pro_line": "   💎 Pro: {count}",
    "stats.vacancies": "💼 <b>Vacancies</b>",
    "stats.active_line": "   Active postings: ~{count}",
    "stats.avg_salary_line": "   Average salary: {amount} UZS",
    "stats.top_specs": "🏆 <b>Top industries:</b>",
    "stats.top_regions": "📍 <b>Top regions:</b>",
    "stats.top_row": "   {i}. {name} — {count}",
    "stats.resumes": "📄 Resumes created: {count}",
    "stats.saves": "❤️ Saved: {count}",
    "stats.week_short": "{day} {month}",
    "stats.week_range_same_month": "{d1}–{d2} {month} {year}",
    "stats.week_range": "{d1} {month1} – {d2} {month2} {year}",

    # ── Month names ───────────────────────────────────────────
    "month.1": "January",
    "month.2": "February",
    "month.3": "March",
    "month.4": "April",
    "month.5": "May",
    "month.6": "June",
    "month.7": "July",
    "month.8": "August",
    "month.9": "September",
    "month.10": "October",
    "month.11": "November",
    "month.12": "December",

    # ── Chart / grafik ────────────────────────────────────────
    "chart.title": "Weekly statistics — {label}",
    "chart.top_specs": "Top industries",
    "chart.top_regions": "Top regions",
    "chart.new_users": "New users per week",
    "chart.avg_salary": "Average salary (UZS)",
}
