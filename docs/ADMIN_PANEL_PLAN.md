# Admin panel v2 — reja

Tuzilgan: 2026-09-21. Manba: joriy kodni 3 ta o'qish-agent tahlili (Admin UI, admin API + ma'lumotlar modeli + masshtab, kirish oqimi).

## 1. Hozirgi holat (qisqa diagnoz)

Hozirgi "admin panel" aslida resume-analitika paneli: 4 tab (Overview, Settings, Analytics, Users), `webapp_admin_settings` singleton qatorini tahrirlaydi, bitta ID bo'yicha balans qo'shish / reset qiladi. Yo'q narsalar:

- Foydalanuvchilar ro'yxati, qidiruv, filtr, detal, harakatlar (Pro berish, bloklash).
- Broadcast (faqat botda, xotirada, restart'da yo'qoladi, 20 xabar/s, 50k user ≈ 42 daqiqa).
- Kanallar boshqaruvi (faqat botda, `channels(id)` jadvalida faqat id).
- Moliya: Pro aktivatsiya va balans o'zgarishlari **hech qayerda yozilmaydi** (ledger yo'q, daromad hisobotini qurib bo'lmaydi).
- Audit log: admin kim nima qilgani yozilmaydi; `add-balance` cheksiz va izsiz.
- Rollar: admin = `ADMIN_IDS` env; yangi admin qo'shish uchun server `.env` + restart.
- Auto-post tarixi (faqat `posted_vacancies`, xatolar JSON blob ichida), referral to'lovlar ko'rinishi, bildirishnoma nazorati.
- Desktop layout (hozirgi UI tor mobil shell).

Kirish oqimi: Mini App'ga BotFather Main App / `t.me/bot/app` / `startapp` havolasi orqali `/start` bosmasdan kirish mumkin, API `initData` bo'lsa foydalanuvchini o'zi yaratadi (`webapp/core/users.py:ensure_user`). Majburiy obuna faqat botdagi `/start` da tekshiriladi, API uni umuman bilmaydi, 30 kunlik sessiya qayta tekshirmaydi.

Masshtab (50k user, 500 parallel): SQLite WAL yetadi, lekin: har so'rovda yangi ulanish + `synchronous=FULL` (get_db da NORMAL o'rnatilmagan), `resume_events` cheksiz o'sadi (retention yo'q), sessiyalar faqat startup'da tozalanadi, bildirishnoma sikli O(users) per-user so'rovlar bilan, broadcast bitta ulanishni butun jarayon davomida ushlab turadi, slowapi limitlari worker'ga bo'linib ketadi, FSM `MemoryStorage`. PostgreSQL'ga o'tish **hozircha shart emas**; belgilar: >200 commit/s, `database is locked` loglarda, ikkinchi API host.

## 2. Tamoyillar

1. Har bir admin harakati serverda tekshiriladi, auditga yoziladi, xavfli harakat tasdiq tokeni bilan.
2. Admin endpoint'lari faqat Bearer sessiya bilan (initData qabul qilinmaydi), rate limit bilan.
3. Foydalanuvchi Mini App'ga faqat bot orqali kiradi: `/start` bosmagan va obuna bo'lmagan user API'da 403 oladi (server gate), UI lock screen faqat ko'rinish.
4. Ko'p userga mo'ljal: yozuvlar batch, fon vazifalar, indekslar, ledger jadvallari. SQLite qoladi, lekin migratsiya yo'li ochiq (ORM yo'q, `?` placeholder).
5. Har bosqich o'zi deploy qilinadigan, testli, orqaga qaytariladigan.

## 3. Bosqichlar

### Bosqich 0 — Poydevor va xavfsizlik (prereq)  ~2 kun
| # | Ish | Hajm | Agent/model |
|---|---|---|---|
| 0.1 | `synchronous=NORMAL` har ulanishda; per-process ulanish pool (API `get_db`, bot `connect()`); WAL checkpoint soatlik; `journal_size_limit` | S | opus (DB) |
| 0.2 | Indekslar: `users(date)`, `users(user_pro)`, `resume_events(created_at)`, `resume_exports(created_at)`, `notification_settings(enabled)`, `posted_vacancies(channel,posted_at)`, `referral_payouts(ts)` | S | (0.1 bilan) |
| 0.3 | Fon retention (soatlik): sessiyalar, `resume_events` 90 kun, idempotency, WAL checkpoint | S | (0.1 bilan) |
| 0.4 | `admins(user_id PK, role, added_by, added_at, disabled)` jadvali; rollar `owner/admin/moderator/viewer`; `ADMIN_IDS` faqat bootstrap (owner). `require_admin(role=...)` | M | opus (auth) |
| 0.5 | `admin_audit_log(id, actor, action, target_type, target_id, payload_json, ip, created_at)` + `log_admin_action` dependency har mutatsiya route'ida | M | (0.4 bilan) |
| 0.6 | Admin auth qattiqlashtirish: `/api/admin/*` va `/api/wallet/admin/*` faqat Bearer; initData oynasi 1 soat → 5 daqiqa; rate limit; CORS `allow_credentials=False`; tasdiq tokeni (60 s, actor+action+params hash) balans/reset/broadcast uchun | M | (0.4 bilan) |
| 0.7 | `wallet_transactions(id, user_id, kind[pro_activation|referral_reward|admin_credit|admin_reset], amount, balance_after, price_snapshot, actor, note, created_at)`; `activate_pro`, `admin_add_balance`, referral payout shu ledger orqali | M | opus (wallet) |
| 0.8 | Settings: bitta UPDATE, `version` ustuni (optimistic), o'zgarish tarixi auditga; bot TTL keshini yozuvda invalidatsiya (`settings_version`) | S | (0.7 bilan) |
| 0.9 | Redis: slowapi `storage_uri`, aiogram `RedisStorage` (REDIS_URL bor, fallback memory) | S | sonnet |
| 0.10 | Test: barcha `/api/admin*` va `/api/wallet/admin*` route'lari `require_admin` ga bog'liqligini avtomatik tekshiruvchi test | S | (0.4 bilan) |

### Bosqich 1 — Kirish nazorati: bot orqali + majburiy obuna  ~1.5 kun
| # | Ish | Hajm |
|---|---|---|
| 1.1 | `users.started_at` (bot `/start` yozadi), bir martalik backfill `started_at = date` | S |
| 1.2 | `subscription_checks(user_id PK, checked_at, ok, missing_json)`; `webapp/core/subscription.py`: httpx `getChatMember`, TTL ok=10 min / yo'q=60 s, fail-open faqat 5xx/tarmoqda, bot kanalda admin bo'lmasa kanal o'tkazib yuboriladi | M |
| 1.3 | `webapp/core/entry_gate.py`: `require_entry` dependency; tartib `BOT_START_REQUIRED` → `SUBSCRIPTION_REQUIRED{channels}` → `REFERRAL_LOCKED`; adminlar bypass (webapp referral gate'ga ham bypass qo'shiladi); jobs/saves/profile/resume/wallet/notifications router'lariga ulanadi | M |
| 1.4 | `GET /api/auth/gate` (bitta chaqiriq: bot_started, subscribed, channels[{id,title,invite_link}], referral), `POST /api/auth/gate/recheck` (6/min) | S |
| 1.5 | `channels` jadvali kengayadi: `title, username, invite_link, added_by, added_at, enabled`; `getChat` bilan tekshiruv; `GET/POST/DELETE /api/admin/channels`; bot va API bir jadvalni ishlatadi | M |
| 1.6 | Frontend: `EntryLockScreen` (Botni ochish / Obuna bo'lish tugmalari / Qayta tekshirish), App.tsx dagi referral gate shu bilan birlashadi; i18n uz/ru/en | M |
| 1.7 | `bot_handoff_tokens` o'lik jadvali olib tashlanadi | S |
| 1.8 | BotFather: Main App o'chiriladi (qo'lda, siz), bot tugmalari `WEBAPP_URL` bilan qoladi | — |

### Bosqich 2 — Admin API v2  ~3 kun (parallel 4 agent)
| Modul | Endpoint'lar | Hajm |
|---|---|---|
| Users | `GET /admin/users?q&pro&blocked&lang&region&from&to&sort&page` (cursor), `GET /admin/users/{id}` (profil, saves, referral, ledger, resume, notif), `POST /admin/users/{id}/pro` (grant/revoke, muddat ixtiyoriy), `POST .../balance` (amount, note, confirm_token), `POST .../ban` (yangi `users.banned`, blocked'dan farqli), `POST .../message` (bitta xabar) | L |
| Broadcast | `broadcasts(id, actor, status, kind[text|photo|forward], payload_json, target_json, total, sent, failed, created_at, started_at, finished_at)` + `broadcast_targets(broadcast_id, user_id, status, error)`; bot ichida worker sikl (25 msg/s token bucket, resumable, cancel); `POST /admin/broadcasts` (targeting: all / pro / lang / region / faol 30 kun / test faqat adminlarga), `GET /admin/broadcasts`, `GET .../{id}`, `POST .../{id}/cancel`; rasm yuklash `sendPhoto` orqali | L |
| Auto-post | `auto_post_log(id, uid, channel, message_id, status, error, posted_at)` (JSON blob o'rniga); `GET /admin/auto-post/history`, `POST /admin/auto-post/post-now` (bot navbatiga so'rov: `bot_commands` jadvali yoki Redis pub/sub) | M |
| Finance | `GET /admin/finance/summary` (kunlik/haftalik Pro aktivatsiya, balans kiritish, referral to'lovlar), `GET /admin/finance/transactions` (filtr, cursor), `GET /admin/referrals` (kim kimni, to'langan/to'lanmagan) | M |
| Analytics | `daily_stats` rollup jadvali (kunlik: yangi user, faol, Pro, saves, resume ok/err, posts, notif); bot tungi job to'ldiradi; dashboard so'rovlari rollup'dan; `resume-*` mavjud endpoint'lar qoladi | M |
| System | `GET /admin/system` (DB hajmi, WAL hajmi, sessiya soni, scheduler oxirgi ishlash vaqtlari, broadcast navbati, Redis holati, oxirgi 50 xato `error_log` jadvalidan), `GET /admin/audit` (cursor, filtr) | M |
| Content | Boshlang'ich: `GET /admin/content` (maqolalar/tips ro'yxati faqat o'qish). DB'ga ko'chirish keyingi iteratsiya | S |

### Bosqich 3 — Admin UI v2  ~3 kun (parallel 3 agent)
- **Layout:** `/admin` marshruti Telegram Desktop va telefon uchun responsive: ≥1024px da chap sidebar + jadval, mobil'da pastki tablar. Alohida brauzer auth kiritilmaydi (bitta auth tizimi qoladi), admin Telegram Desktop orqali kiradi.
- **Sahifalar:** Dashboard (rollup KPI + sparkline), Users (jadval, qidiruv, filtr, cursor pagination, detal drawer, harakatlar tasdiq bilan), Broadcasts (compose, targeting, prognoz soni, progress, tarix, cancel), Channels (majburiy obuna kanallari + auto-post kanali, tekshiruv holati), Auto-post (sozlama + tarix + "hozir yubor"), Finance (ledger, grafiklar), Referrals, Settings (versiya, tarix), Audit, System.
- **Umumiy komponentlar:** `DataTable` (cursor, sort, bo'sh/xato holatlar), `ConfirmDialog` (tasdiq tokeni bilan), `FilterBar`, `StatCard`.
- Rollar UI'da: viewer faqat o'qiydi, moderator user harakatlari, admin hammasi, owner adminlarni boshqaradi.
- i18n `admin` namespace kengayadi; tokenlar bilan tun rejimi.

### Bosqich 4 — Masshtab ishlari  ~1.5 kun
- Bildirishnoma sikli: gruppalangan so'rovlar, nomzodlar to'plami bir marta, cheklangan parallel yuborish.
- `resume_events` batch yozuv (asyncio queue + `executemany`), autosave'da idempotency qatori yo'q.
- Sessiya: launch'da mavjud tirik sessiya qayta ishlatiladi.
- Yuk testi skripti (`ops/loadtest.py`, httpx, 200 parallel: jobs/search, saves, resume autosave) va natijalar `docs/` ga.

### Bosqich 5 — Sifat va chiqarish  ~1 kun
- Test: gate matritsasi (start yo'q / obuna yo'q / referral / admin bypass / fail-open), broadcast worker (resume, cancel, blocked), ledger invariantlari (balance_after = oldingi + amount), audit har mutatsiyada, rollar.
- Xavfsizlik ro'yxati: initData oynasi, Bearer-only, rate limit, tasdiq tokeni, upper bound'lar (`pro_price`, `amount`), kanal formati.
- Deploy: backup → deploy → migratsiya tekshiruvi → smoke. `CLAUDE.md` va `deploy.txt` yangilanadi.

## 4. Agentlar va modellar (token tejash)
- Har agent faqat o'z fayllariga egalik qiladi; umumiy shartnoma (`CONTRACT`) oldindan yoziladi: jadval sxemalari, endpoint shakllari, xato kodlari, i18n kalit prefikslari.
- Katta/xavfli qismlar (auth, ledger, gate, broadcast worker, DB pool) — **opus**; UI sahifalari va oddiy CRUD — **sonnet**; inventar/grep/tarjima — **haiku/sonnet**.
- Bosqich 0 (3 agent parallel) → 1 (2 agent) → 2 (4 agent) → 3 (3 agent) → 4 (2 agent) → 5 (2 agent). Jami ~16 agent chaqiruvi, har biri chegaralangan brifing bilan. O'qish-audit takrorlanmaydi: shu hujjat va agent hisobotlari brifing sifatida beriladi.

## 5. Qabul mezonlari
- Adminsiz user hech bir `/api/admin*` ni ko'ra olmaydi (avtomatik test); har mutatsiya audit qatoriga ega.
- `/start` bosmagan user Mini App'da lock screen ko'radi, API 403 `BOT_START_REQUIRED`; obuna bo'lmagan user `SUBSCRIPTION_REQUIRED` va kanallar ro'yxati; Telegram 5xx da hech kim qulflanmaydi.
- Broadcast 50k userga ≈ 35 daqiqada, restart'dan keyin davom etadi, progress UI'da.
- Yuk testi: 200 parallel so'rovda p95 < 500 ms, `database is locked` yo'q.
- Ledger yig'indisi = balanslar (invariant testi).

## 6. Qabul qilingan qarorlar (2026-09-21)
1. Admin panel faqat Telegram Mini App ichida; user bot orqali avtomatik login bo'ladi (initData → user_id), adminlar `admins` jadvali orqali aniqlanadi, Mini App'da "Admin panel" tugmasi chiqadi; owner yangi adminlarni paneldan qo'shadi.
2. Majburiy obuna kanallari admin paneldan qo'shiladi; havola kiritilganda darhol `getChat` + bot a'zoligi tekshiriladi va natija ko'rsatiladi.
3. Broadcast: matn + media (rasm/video/hujjat) + inline tugmalar.
4. Kontent (qonun maqolalari, HR maslahatlar) DB'ga ko'chadi va admin paneldan tahrirlanadi; kod ichidagi fayllar boshlang'ich seed bo'lib qoladi.
5. BotFather Main App o'chirilmaydi: nazorat serverda (1-bosqich), Main App orqali kirgan user lock screen ko'radi.

## 7. Bajarilish holati (2026-09-21)
Bosqich 0–5 barchasi bajarildi (26 agent, parallel). Natija: 15 migratsiya (m000–m015), 94 API route, 580 test (e2e oqim va xavfsizlik testlari bilan), admin UI 8 sahifa + shell. Xavfsizlik tekshiruvi 3 High / 4 Medium / 7 Low topdi, hammasi tuzatildi (rate-limit kaliti tekshirilgan identifikatsiya bo'yicha, `href` sxemasi tekshiruvi, X-Real-IP, queue uchun tasdiq tokeni, upload hajmi Content-Length bo'yicha, migratsiya busy_timeout, cheklangan COUNT'lar).
Deploy'dan keyin qo'lda: kanallarni Channels sahifasida qo'shish, auto-post kanalini tekshirish, BotFather Main App qoladi.
Keyingi iteratsiya g'oyalari: `users.last_seen_at` ni auth'da yangilash, admin uchun brauzer login (Login Widget), yuk testi natijalarini `docs/` ga yozish, monitoring/alert.
