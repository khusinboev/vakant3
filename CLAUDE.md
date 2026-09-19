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
python -m pyflakes main.py config.py src webapp/main.py webapp/core webapp/routers webapp/models webapp/resume tests

# Deploy (build frontend, rsync code + dist, ensure DB_PATH and WEBAPP_SECRET on the server, restart, health check)
bash deploy_safe.sh
```

`tests/conftest.py` sets a dummy `TOKEN`/`ADMIN_IDS`, so tests do not need `.env`. `deploy.txt` is the Uzbek ops runbook (server paths, systemd, journalctl, DB backup). `ROADMAP.md` describes the five feature sprints; all are implemented.

## Architecture: the coupling you must know

### One SQLite file, two processes, schema split in two places
- Path: `DB_PATH` env, default `src/database/database.sqlite3`. Raw `aiosqlite`, no ORM, WAL mode, `busy_timeout=5000`. The bot opens connections through `src/db/connection.py:connect()` (sets pragmas + Row factory); the API gets one per request via `get_db()` in `webapp/core/database.py` and handlers must `await db.commit()`.
- The bot creates `users`, `channels`, `saves`, `regions`, `districts`, `webapp_sessions`, `bot_handoff_tokens`, `referral_payouts` in `StatsMiddleware.init_db()` (`src/middleware/middlewares.py`) and seeds regions/districts from osonish.
- The API creates everything else in `webapp/core/database.py:init_db()` at lifespan startup: `webapp_admin_settings` (singleton row), `vacancy_cache`, `posted_vacancies`, `notification_settings`, `sent_notifications`, `resume_*`, plus idempotent `ALTER TABLE` migrations (only "duplicate column" errors are swallowed). Adding a column means adding it to the list in `webapp/core/database.py`; the bot's `src/db/settings.py:ensure_settings_columns` mirrors the `webapp_admin_settings` columns it needs (`channel_lang`, `auto_post_scheduled_day`, `last_weekly_stats_week`).
- Consequence: the bot's schedulers read `webapp_admin_settings` and `users.user_pro` but the API creates them, so the API must have started once against a fresh DB.

### Cross-package imports
- webapp -> bot: `webapp/routers/{jobs,saves,filters}.py` import `src.functions.{cache,scraping,functions,vacancy_format}`; `webapp/routers/content.py` imports `src.data.law_articles`. The API never imports the aiogram `bot` object.
- bot -> webapp: none. The bot reads `webapp_admin_settings` directly through `src/db/settings.py:get_admin_settings` (60 s TTL cache).
- `config.BASE_DIR` is the DB file path. `webapp.core.config.BASE_DIR` is the repo root. Same name, different meaning.

### Admin-configured behaviour lives in the DB, not env
The `webapp_admin_settings` row (edited via `PATCH /api/admin/state` and the Admin page) drives: auto-post channel/salary floor/posts-per-day/`channel_lang`, referral gate on/off and required count, Pro price and referral reward, resume KPI targets. There are no scheduler env vars.

### Bot process
- `config.py` holds module-level `bot` and `dp` singletons (HTML parse mode, `MemoryStorage`). Routers `start`, `admin`, `content` are included in `main.py`.
- `StatsMiddleware` runs on `dp.message` and `dp.callback_query`: it captures `/start ref_<id>` before inserting a new user (so `users.ref_by` is set exactly once and the reward is paid once via `referral_payouts`), normalizes `users.lang`, and injects `lang` and `is_new_user` into handler kwargs. Handlers take `lang: str`.
- i18n: `src/i18n/` (`uz.py`, `ru.py`, `en.py`, `t(lang, key, **kw)`, `normalize_lang`). Reply-keyboard labels are built per language and routed by key with `src/filters/text_key.py:TextKey("menu.laws")`, never by literal text. `/lang` and the first `/start` offer a language picker.
- Admin = `ADMIN_IDS` env via `src/filters/admin.py:IsAdmin` applied to the admin router.
- Three background loops in `main.py` (auto-post, notifications, weekly stats) each open their own connection per tick and read admin settings through the TTL cache. Weekly stats persist `last_weekly_stats_week`; auto-post persists `auto_post_scheduled_day` so slots are generated once per day and stale slots are closed unsent. Channel posts use `channel_lang`; notifications use the user's `lang`.
- All user/API text placed into HTML messages goes through `html.escape`. Time handling uses `src/core/timeutil.py` (`Asia/Tashkent`, `now_tz`, `day_key`, `week_key`).
- Bot web-app buttons use `WEBAPP_URL` (default `https://abitur24.uz/app`).

### API process
- Routers mount under `/api` with their own prefix (`/auth`, `/jobs`, `/saves`, `/profile`, `/referral`, `/admin`, `/wallet`, `/resume`, `/content`, `/notifications`, `/filters`). Unknown `/api/*` paths return 404 JSON; the SPA catch-all is registered last.
- One auth mechanism: `webapp/core/auth.py` dependencies `current_user`, `optional_user`, `require_admin`. Order: Bearer session token (JWS over a `webapp_sessions` row, identity taken from the row) then `X-Telegram-Init-Data` (HMAC-verified, auto-provisions the user). Admin is `user_id in settings.admin_ids_set`; no DB flag. The frontend sends Bearer, init-data and `Accept-Language` on every request.
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
- Big pages are directories: `src/pages/ResumeStudio/` (index, `useResumeDraft`, `useResumeSync`, `steps/`, `TemplatePreview`) and `src/pages/Admin/` (index, `tabs/`, `components/`, `useAdminQueries`); the recharts tab is lazy. Generic inputs live in `src/components/ui/` (`BottomSheet`, `Field`, `StyledSelect`, `MonthYearPicker`, `TagInput`, `WizardProgress`).
- i18n: `src/i18n/` with per-namespace dictionaries (`common`, `vacancy`, `resume`, `admin`) per language; uz is eager and the type source, ru/en are lazy chunks loaded by `ensureDictionary`. Use `useT()` (`t(key, vars)`), `useLocale()` for numbers/dates, `useVacancyCodeLabel()` for codes. A missing ru/en key is a compile error. Language state is `src/store/lang.ts` (localStorage -> `/auth/me` -> Telegram `language_code` -> uz), synced with `PATCH /api/profile/lang`.
- Theme: tailwind `darkMode: 'class'` with semantic tokens (`bg`, `surface`, `surfaceAlt`, `text`, `muted`, `border`, `primary`, `primaryFg`, `success`, `warning`, `danger`) defined as CSS variables in `index.css`; `src/store/theme.ts` + `useTheme()` (modes `telegram`/`system`/`light`/`dark`). Never use raw slate/gray/white classes except in resume previews (they depict a printed page) and brand gradients. Language and theme switchers are in the Profile "Settings" card.
- Data: react-query hooks in `src/hooks/` (`useJobs` list key `["jobs","list",params]`, `useJobDetail` `["jobs","detail",uid]`, `useSaves` with keyed optimistic rollback, `useStaticList` for regions/districts/specs). Errors go through `src/lib/parseApiError.ts` and `useToast().apiError`.
- Telegram viewport handling is the fragile area. `useTelegramWebApp` computes `--bottom-safe` in JS because fullscreen zeroes `contentSafeAreaInset`; `BottomNav` returns `null` while `useKeyboardOpen()` is true and that hook must be called before any early return. `useBackInterceptor` lets pages capture the Telegram BackButton.

## Conventions
- Commit messages follow conventional commits with optional scope: `feat(resume): ...`, `fix: ...`, `chore(deploy): ...`.
- `src/buttons/buttuns.py` is misspelled; import it as-is.
- The production DB at `/home/vakant/data/database.sqlite3` is excluded from `deploy_safe.sh` and must never be overwritten or deleted.
- New env variables must also be added by hand to the server `.env` (it is not synced by deploy); `deploy_safe.sh` bootstraps `DB_PATH` and `WEBAPP_SECRET` if missing.
