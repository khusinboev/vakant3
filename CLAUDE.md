# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Bandlik.uz / vakant3: an Uzbek job-vacancy product with three parts that share one SQLite file and one `.env` at the repo root.

| Part | Path | Runs as |
|------|------|---------|
| Telegram bot (aiogram 3, long polling) | `main.py`, `config.py`, `src/` | `python main.py` (prod systemd unit `vakant-bot`) |
| FastAPI backend (Telegram Mini App API) | `webapp/` | uvicorn `webapp.main:app` (prod unit `vakant-api`, port 8001) |
| React 18 + Vite + Tailwind Mini App | `webapp/frontend/` | built to `dist/`, served by nginx in prod (FastAPI also serves it as a fallback) |

Vacancies are not stored as a catalogue: they are scraped live from the osonish.uz API (`src/functions/scraping.py`) and identified everywhere by `uid = "osonish_<id>"`.

The product is trilingual (uz source, ru, en) and has light/dark themes. Uzbek is the source language for every dictionary; ru/en are typed against it.

## Commands

Everything Python runs from the repo root with `.venv` activated. Both the bot and the webapp import `config` and `src` from the root, so the CWD must be the repo root.

```bash
# Bot
python main.py

# API (dev; the Vite proxy expects port 8000, prod uses 8001)
uvicorn webapp.main:app --reload --port 8000
# The API refuses to start with a missing/default WEBAPP_SECRET; for throwaway local runs:
ALLOW_INSECURE_SECRET=1 uvicorn webapp.main:app --reload --port 8000

# Frontend
cd webapp/frontend && npm install && npm run dev      # :5174, proxies /api -> :8000
cd webapp/frontend && npm run lint                    # eslint 9 flat config (react-hooks rules)
cd webapp/frontend && npm run build                   # tsc -b && vite build -> dist/

# Tests (pytest.ini: asyncio_mode=auto, network tests deselected by default)
pytest
pytest tests/test_bot_core.py
pytest tests/test_notifications.py::test_name -v
pytest -m network                                     # live osonish.uz calls, off by default
pytest tests/test_e2e_flow.py                         # boots the real app: gate, admin, ledger, broadcast, content
python ops/loadtest.py --help                         # async load generator (see ops/README.md)
python -m pyflakes main.py config.py src webapp/main.py webapp/core webapp/routers webapp/models webapp/resume tests

# Deploy (build frontend, rsync code + dist, ensure DB_PATH and WEBAPP_SECRET on the server, restart, health check)
bash deploy_safe.sh
```

`tests/conftest.py` pins a temp `DB_PATH` before `.env` is loaded and sets dummy `TOKEN`/`ADMIN_IDS`/`WEBAPP_SECRET`, so tests never touch a real database and do not need `.env`. `deploy.txt` is the Uzbek ops runbook (server paths, systemd, journalctl, DB backup). `ROADMAP.md` describes the five feature sprints; all are implemented.

## Architecture: the coupling you must know

### One SQLite file, two processes, schema split in two places
- Path: `DB_PATH` env, default `src/database/database.sqlite3`. Raw `aiosqlite`, no ORM, WAL mode, `busy_timeout=5000`. The bot opens connections through `src/db/connection.py:connect()` (sets pragmas + Row factory); the API gets one per request via `get_db()` in `webapp/core/database.py` and handlers must `await db.commit()`.
- The bot creates `users`, `channels`, `saves`, `regions`, `districts`, `webapp_sessions`, `bot_handoff_tokens`, `referral_payouts` in `StatsMiddleware.init_db()` (`src/middleware/middlewares.py`) and seeds regions/districts from osonish.
- The API creates everything else in `webapp/core/database.py:init_db()` at lifespan startup: `webapp_admin_settings` (singleton row), `vacancy_cache`, `posted_vacancies`, `notification_settings`, `sent_notifications`, `resume_*`, plus idempotent `ALTER TABLE` migrations (only "duplicate column" errors are swallowed). Adding a column means adding it to the list in `webapp/core/database.py`; the bot's `src/db/settings.py:ensure_settings_columns` mirrors the `webapp_admin_settings` columns it needs (`channel_lang`, `auto_post_scheduled_day`, `last_weekly_stats_week`).
- Everything added since Sept 2026 lives in ordered migrations: `src/db/migrations/mNNN_<slug>.py` (`ID` + `async def apply(conn)`), run by `src/db/migrate.py:run_migrations` from BOTH processes at startup (`schema_migrations` table, `BEGIN IMMEDIATE`, 60 s busy timeout). Add a new `mNNN` file; never edit an applied one. Helper `add_column_if_missing`.
- Connections: the API uses a per-process pool (`webapp/core/database.py`, `DB_POOL_SIZE` default 16, `synchronous=NORMAL`, 503 `SERVER_BUSY` on exhaustion); the bot uses `src/db/connection.py:connect()`. Hourly maintenance in the API lifespan: `retention.purge_expired` + `wal_checkpoint`.
- Consequence: the bot's schedulers read `webapp_admin_settings` and `users.user_pro` but the API creates them, so the API must have started once against a fresh DB.

### Cross-package imports
- webapp -> bot: `webapp/routers/{jobs,saves,filters}.py` import `src.functions.{cache,scraping,functions,vacancy_format}`; the content seed migration imports `src.data.law_articles` / `hr_tips`. The API never imports the aiogram `bot` object.
- bot -> webapp: none. The bot reads `webapp_admin_settings` directly through `src/db/settings.py:get_admin_settings` (60 s TTL cache).
- `config.BASE_DIR` is the DB file path. `webapp.core.config.BASE_DIR` is the repo root. Same name, different meaning.

### Admin-configured behaviour lives in the DB, not env
The `webapp_admin_settings` row (edited via `PATCH /api/admin/state` and the Admin page) drives: auto-post channel/salary floor/posts-per-day/`channel_lang`, referral gate on/off and required count, Pro price and referral reward, resume KPI targets. There are no scheduler env vars.

### Bot process
- `config.py` holds module-level `bot` and `dp` singletons (HTML parse mode, `MemoryStorage`). Routers `start`, `admin`, `content` are included in `main.py`.
- `StatsMiddleware` runs on `dp.message` and `dp.callback_query`: it captures `/start ref_<id>` before inserting a new user (so `users.ref_by` is set exactly once and the reward is paid once via `referral_payouts`), normalizes `users.lang`, and injects `lang` and `is_new_user` into handler kwargs. Handlers take `lang: str`.
- i18n: `src/i18n/` (`uz.py`, `ru.py`, `en.py`, `t(lang, key, **kw)`, `normalize_lang`). Reply-keyboard labels are built per language and routed by key with `src/filters/text_key.py:TextKey("menu.laws")`, never by literal text. `/lang` and the first `/start` offer a language picker.
- Admin = `ADMIN_IDS` env via `src/filters/admin.py:IsAdmin` applied to the admin router.
- Background loops in `main.py`: auto-post, notifications (scale-safe: 6 fixed queries per tick, bounded concurrent sends), weekly stats, `broadcast_worker_loop` (job tables `broadcasts`/`broadcast_targets`, claims batches with `UPDATE ... RETURNING`, 25 msg/s, resumable, cancel-aware, marks `users.blocked`), `bot_jobs_loop` (generic `bot_jobs` queue, handlers registered in `src/functions/bot_jobs.py:JOB_HANDLERS`, e.g. `auto_post.post_now`), `daily_rollup_loop` (`daily_stats` at 00:10). Each tick opens its own connection and reads admin settings through the TTL cache (invalidated by `webapp_admin_settings.version`). Weekly stats persist `last_weekly_stats_week`; auto-post persists `auto_post_scheduled_day` so slots are generated once per day and stale slots are closed unsent. Channel posts use `channel_lang`; notifications use the user's `lang`.
- All user/API text placed into HTML messages goes through `html.escape`. Time handling uses `src/core/timeutil.py` (`Asia/Tashkent`, `now_tz`, `day_key`, `week_key`).
- Bot web-app buttons use `WEBAPP_URL` (default `https://abitur24.uz/app`).

### API process
- Routers mount under `/api` with their own prefix (`/auth`, `/jobs`, `/saves`, `/profile`, `/referral`, `/admin`, `/wallet`, `/resume`, `/content`, `/notifications`, `/filters`). Admin v2 routers are separate files registered in `webapp/main.py`: `admin_admins` (owner: admins CRUD), `admin_users`, `admin_broadcasts` (+ `/admin/uploads`), `admin_channels`, `admin_content`, `admin_autopost`, `admin_finance`, `admin_analytics`, `admin_system` (system/audit/errors). Cursor pagination everywhere: `?limit&cursor` → `{items, next_cursor, total|null}`. Unknown `/api/*` paths return 404 JSON; unhandled exceptions are logged to `error_log` and return `INTERNAL_ERROR{request_id}`; the SPA catch-all is registered last.
- Content (law articles / HR tips / categories) lives in DB tables `content_*` seeded once from `src/data/law_articles.py` and `hr_tips.py` (migration m007); public `/api/content/*` and the bot read the DB (`webapp/core/content_repo.py`, `src/data/content_repo.py`); admins edit via `/api/admin/content/*` (HTML allowlist `<b><i><u><a href><code><br>`, href schemes http/https/tg/mailto).
- One auth mechanism: `webapp/core/auth.py` dependencies `current_user`, `optional_user`, `require_admin`, `require_role(min_role)`. Order: Bearer session token (JWS over a `webapp_sessions` row, identity taken from the row) then `X-Telegram-Init-Data` (HMAC-verified, 300 s window, auto-provisions the user). Admin routes are Bearer-only. Admin identity comes from the `admins` table (roles `owner > admin > moderator > viewer`); `ADMIN_IDS` only bootstraps the first owner. The frontend sends Bearer, init-data and `Accept-Language` on every request.
- Entry gate (`webapp/core/entry_gate.py:require_entry`, router-level on jobs/saves/profile/resume/wallet/notifications/referral): banned → `USER_BANNED`; no `users.started_at` (set by bot `/start`) → `BOT_START_REQUIRED`; required channels not joined → `SUBSCRIPTION_REQUIRED{channels}` (Telegram `getChatMember` cached in `subscription_checks`, 10 min ok / 60 s not-ok, fail-open on Telegram 5xx, channels where the bot is not admin are skipped); then the referral gate. Admins bypass. `GET /api/auth/gate` + `POST /api/auth/gate/recheck` (6/min) feed the frontend `EntryLockScreen`.
- Admin mutations: every one writes `admin_audit_log` via `webapp/core/audit.py:log_admin_action` inside the mutation's transaction; money/destructive/broadcast actions additionally need a confirm token (`POST /api/admin/confirm` → `X-Confirm-Token`, HMAC over actor+action+params, 60 s; dependency `webapp/core/confirm.py:require_confirmation(action, param_keys)` reads the params from the JSON body). Settings PATCH is one UPDATE with `version`/`expected_version` → 409 `SETTINGS_CONFLICT`.
- Money only moves through `webapp/core/ledger.py:apply_balance_change` (conditional UPDATE first in the transaction + `wallet_transactions` row; kinds pro_activation/referral_reward/admin_credit/admin_reset/adjustment). The bot's referral payout writes the same ledger row in plain SQL.
- Rate limiting keys on the verified identity (`request.state.user_id`, else HMAC-verified token/init-data, else client IP from `webapp/core/request_ip.py` = `X-Real-IP` or last `X-Forwarded-For` hop). Admin routes: 60/min reads, 10/min mutations.
- Errors: always `HTTPException(detail={"code": UPPER_SNAKE, ...params})` built with `webapp/core/errors.py:api_error`. Codes include AUTH_REQUIRED, ADMIN_REQUIRED, REFERRAL_LOCKED{count,required}, PRO_REQUIRED, SAVE_LIMIT_REACHED{limit,current}, PREMIUM_TEMPLATE, INSUFFICIENT_BALANCE{required,balance}, ALREADY_PRO, NOT_FOUND{resource}, VALIDATION_ERROR{field}, TELEGRAM_SEND_FAILED, UPSTREAM_ERROR, PDF_RENDER_FAILED. No prose in `detail`; the frontend translates codes.
- Language per request: `webapp/core/i18n.py:get_lang` (`?lang` > `users.lang` > `Accept-Language` > uz). Localized responses: `/content/laws*`, `/filters/specs` (`{id,key,label}`), `/filters/regions` (`name`), `/jobs/*` salary text and `normalized` labels plus raw `codes`, `/resume/templates`, PDF headings. `PATCH /api/profile/lang` persists the preference.
- Rate limiting is slowapi keyed on the resolved user id (else forwarded IP), in-memory per worker. Any `@limiter.limit` endpoint must take `request: Request`.
- `src/functions/cache.py` is a Redis-or-in-memory cache (`REDIS_URL`, 30 min TTL) used only by API routers. The `vacancy_cache` table is a separate 4 h cache written by the auto-post scheduler.
- Wallet updates are conditional atomic `UPDATE ... WHERE user_balance >= ?` with rowcount checks.
- Resume builder lives in the `webapp/resume/` package (`router.py`, `schemas.py` incl. localized `TEMPLATES` and the allowlisted event names, `normalize.py`, `photos.py` (async fetch, host allowlist), `repository.py`, `i18n.py`, `render/pdf.py` + `render/templates/*.py`, fpdf2 with DejaVu from `/usr/share/fonts/truetype/dejavu/`, rendered in a threadpool). `webapp/routers/resume.py` only re-exports the router. Free templates are `clean`, `modern`, `compact`; others return `PREMIUM_TEMPLATE` for non-Pro.
- `webapp/core/retention.py:purge_expired` runs at startup (sessions, idempotency keys, old notifications, stale vacancy cache).

### Referral gate
`src/functions/referral_gate.py:compute_referral_state(conn, user_id)` is the single rule implementation; the bot wrapper adds the admin bypass and message, `webapp/core/referral_gate.py` raises `REFERRAL_LOCKED`.

### Vacancy formatting is shared
`src/functions/vacancy_format.py`: `normalize_vacancy_detail(uid, detail, lang)` (localized labels plus `codes`), `format_vacancy_message_html(uid, detail, lang, compact)` used by the bot deeplink, auto-post, notifications and `webapp/routers/jobs.py`. Integer code -> label maps live in the i18n dictionaries on both sides (`src/i18n/*.py` and `webapp/frontend/src/i18n/*/vacancy.ts`); keep the code numbers in sync.

### Frontend
- Routing in `App.tsx`: `/app` is the entry and dispatches to Home/Profile/Saves via `?go=` or Telegram `start_param`. Outside Telegram only `Landing` renders. `ErrorBoundary` wraps the routes; `ToastHost` is mounted once.
- Big pages are directories: `src/pages/ResumeStudio/` (index, `useResumeDraft`, `useResumeSync`, `steps/`, `TemplatePreview`) and `src/pages/Admin/` (responsive shell: `layout/` sidebar ≥1024px / bottom tabs, `registry.ts` page table with `minRole`, `pages/<Name>Page.tsx` + one folder per page: users, broadcasts, channels, content, finance, system, autopost, analytics; shared `components/` DataTable/ConfirmDialog/FilterBar/StatCard/RoleGate and `hooks/` useCursorQuery/useConfirmedMutation/useAdminRole). Typed client in `src/api/admin.ts` (+ `adminTypes.ts`, `gate.ts`); recharts is the lazy `vendor-charts` chunk. Admin pages are reached at `/admin/<id>`; the "Admin panel" entry appears only when `/auth/gate` reports a role. Generic inputs live in `src/components/ui/` (`BottomSheet`, `Field`, `StyledSelect`, `MonthYearPicker`, `TagInput`, `WizardProgress`).
- i18n: `src/i18n/` with per-namespace dictionaries (`common`, `vacancy`, `resume`, `admin`, `adminUsers`, `adminBroadcasts`, `adminChannels`, `adminContent`, `adminFinance`, `adminSystem`, `adminAutopost`) per language (a new namespace = a file per language + one import line in `src/i18n/index.ts` and in `ru/index.ts`, `en/index.ts`); uz is eager and the type source, ru/en are lazy chunks loaded by `ensureDictionary`. Use `useT()` (`t(key, vars)`), `useLocale()` for numbers/dates, `useVacancyCodeLabel()` for codes. A missing ru/en key is a compile error. Language state is `src/store/lang.ts` (localStorage -> `/auth/me` -> Telegram `language_code` -> uz), synced with `PATCH /api/profile/lang`.
- Theme: tailwind `darkMode: 'class'` with semantic tokens (`bg`, `surface`, `surfaceAlt`, `text`, `muted`, `border`, `primary`, `primaryFg`, `success`, `warning`, `danger`) defined as CSS variables in `index.css`; `src/store/theme.ts` + `useTheme()` (modes `telegram`/`system`/`light`/`dark`). Never use raw slate/gray/white classes except in resume previews (they depict a printed page) and brand gradients. Language and theme switchers are in the Profile "Settings" card.
- Data: react-query hooks in `src/hooks/` (`useJobs` list key `["jobs","list",params]`, `useJobDetail` `["jobs","detail",uid]`, `useSaves` with keyed optimistic rollback, `useStaticList` for regions/districts/specs). Errors go through `src/lib/parseApiError.ts` and `useToast().apiError`.
- Telegram viewport handling is the fragile area. `useTelegramWebApp` computes `--bottom-safe` in JS because fullscreen zeroes `contentSafeAreaInset`; `BottomNav` returns `null` while `useKeyboardOpen()` is true and that hook must be called before any early return. `useBackInterceptor` lets pages capture the Telegram BackButton.

## Conventions
- Commit messages follow conventional commits with optional scope: `feat(resume): ...`, `fix: ...`, `chore(deploy): ...`.
- `src/buttons/buttuns.py` is misspelled; import it as-is.
- The production DB at `/home/vakant/data/database.sqlite3` is excluded from `deploy_safe.sh` and must never be overwritten or deleted.
- New env variables must also be added by hand to the server `.env` (it is not synced by deploy); `deploy_safe.sh` bootstraps `DB_PATH` and `WEBAPP_SECRET` if missing and runs `pip install`.
- Broadcast media is stored under `<DB dir>/uploads/`; never served by the API, sent to Telegram by the bot.
- `docs/ADMIN_PANEL_PLAN.md` records the admin v2 design decisions; `ops/` holds the server backup/logrotate scripts and the load test.
