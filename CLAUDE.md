# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Hard rules (read first)

- **Production is one shared server** (address only in `deploy_safe.sh` `SERVER` and the `deploy.txt` runbook; never copy it anywhere else). It also runs SlaydX (docker), ~20 other bots/APIs under `/home/*`, host PostgreSQL/Redis and one nginx for all sites. Touch only `/home/vakant` and the `vakant-api`/`vakant-bot` units. Never restart/reload nginx, docker, redis or postgres, never `docker ... prune`, never build on the server (4 vCPU, ~8 GB RAM shared). Details: `.claude/deploy.md`.
- **Production DB** `/home/vakant/data/database.sqlite3` is excluded from `deploy_safe.sh` and must never be overwritten, deleted or restored without the owner's explicit go. Both deploy paths back it up first (`data/backups/predeploy_*` by `ops/auto_deploy.sh`, `backup_db.sh` by `deploy_safe.sh`); for any manual server work run `/home/vakant/backup_db.sh` first.
- **Ship policy:** after each logical step run the relevant tests and commit (conventional commits) without asking, then continue. When a task is finished and verified (`pytest`, `npm run lint`, `npm run build` green), push to `master` without asking, watch CI and the auto-deploy, check `/api/health` and the journals, and report. Ask first only for: destroying/restoring prod data, server-wide changes (nginx, other units, packages, cron, firewall), and product/money *values* (Pro price, rewards, gate thresholds).
- **`git push` to `master` = production.** CI (`.github/workflows/ci.yml`) tests it and, if green, force-pushes a release (tree + built `dist` + `RELEASE` sha) to the `deploy` branch; the server's `ops/auto_deploy.sh` (cron, 2 min) ships it with snapshot, DB backup, health check and automatic rollback, and alerts `ADMIN_IDS`. Never push to `deploy` by hand. Kill switch: `touch /home/vakant/.deploy/auto-deploy.disabled`. `bash deploy_safe.sh` is the manual fallback (clean tree only). Details: `.claude/deploy.md`.
- **Real Telegram side effects:** tests use a dummy `TOKEN` and never reach Telegram. Never run the bot locally with the production token (it would answer real users and make the prod bot's long polling fail with `Conflict`); never trigger a broadcast or channel post against real users from local code.
- Nothing is "done" without evidence: the exact command plus pass/fail counts. Tests are never weakened, skipped or deleted to go green.
- Secrets: `.env` values and tokens never go into commits, logs or docs (variable names only); server addresses stay in the two files above. Personal data in tests and fixtures is synthetic (e.g. user ids from 900000000000, as in `ops/loadtest.py`).
- Languages: talk to the owner in Uzbek; code, comments, commits, CLAUDE.md and `.claude/*.md` in English (except `.claude/holat.md`, Uzbek for `/holat`); `deploy.txt` stays the Uzbek runbook. UI text: uz is the source, every key also in ru and en.

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

# Tests (pytest.ini: asyncio_mode=auto, pythonpath=., network tests deselected by default; ~600 tests)
pytest                                                # full suite: run via scripts/heavy.sh (see "Heavy commands")
pytest tests/test_bot_core.py
pytest tests/test_notifications.py::test_name -v
pytest -m network                                     # live osonish.uz calls, off by default
pytest tests/test_e2e_flow.py                         # boots the real app: gate, admin, ledger, broadcast, content
python ops/loadtest.py --help                         # async load generator (see ops/README.md)
python -m pyflakes main.py config.py src webapp/main.py webapp/core webapp/routers webapp/models webapp/resume tests

# Deploy: `git push origin master` (CI + auto-deploy). Manual fallback from a clean tree:
bash deploy_safe.sh
```

`tests/conftest.py` is hermetic: it never reads `.env` (`PYTHON_DOTENV_DISABLED=1`) and forces a temp `DB_PATH`, a dummy but well-formed `TOKEN`, `ADMIN_IDS=1`, a test `WEBAPP_SECRET` and `REDIS_URL=""` (in-memory cache/limiter), so tests never touch a real database, bot or Redis. A new env variable read at import time must get a test value there too. `deploy.txt` is the Uzbek ops runbook (server paths, systemd, journalctl, DB backup). `ROADMAP.md` describes the five feature sprints; all are implemented.

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
- `users.last_seen_at` is stamped from `webapp/core/auth.py` (once per request, from the row the identity lookup already loaded) and from the bot's `StatsMiddleware.resolve_user`, throttled to one write per 10 min per user (`webapp/core/users.py:touch_last_seen`, `src/middleware/middlewares.py:touch_last_seen`). It is what makes the admin Users `sort=last_seen` and the `active_days` broadcast segment meaningful.
- `resume_events` are not written per request: `webapp/core/event_queue.py` buffers them in memory and a lifespan task writes one `executemany` every 2 s or 200 events on its own `open_connection()`, drains on shutdown and drops above 10k. `POST /api/resume/events` enqueues and touches no connection; admin analytics still read the table directly. `PUT /api/resume/profile` skips the `resume_idempotency` row when the `X-Idempotency-Key` starts with `resume_autosave:` (the Mini App's 15 s timer, never retried); `resume_save:` keys still get one.
- `webapp/core/retention.py:purge_expired` runs at startup (sessions, idempotency keys, old notifications, stale vacancy cache).

### Referral gate
`src/functions/referral_gate.py:compute_referral_state(conn, user_id)` is the single rule implementation; the bot wrapper adds the admin bypass and message, `webapp/core/referral_gate.py` raises `REFERRAL_LOCKED`.

### Vacancy ingestion
- `src/ingest/` stores vacancies from every source in our DB (migration `m023_vacancy_store`): table `vacancies` (`uid = "<source>_<source_id>"`, explicit `id` rowid for the external-content FTS5 table `vacancies_fts` synced by triggers, `status` open/closed, `quality_score`, `dedup_group`/`dup_of`) and `ingest_cursor` (per-source cursor, last run/error, stats). Description is stored as sanitized plain text (`text.py`), still `html.escape` it on output; the UI shows an excerpt plus the source link.
- Adapters in `sources/` (`osonish.py` always on; `hh.py` = official API `api.hh.ru` with `host=hh.uz`, on only when `HH_APP_TOKEN` is set, `HH_USER_AGENT`, `HH_RATE_PER_SECOND`, 429/5xx backoff, >2000-result windows split by date). `regions.py` maps hh cities to our region SOATO; `dedup.py` (exact key + difflib fuzzy, canonical hh > osonish); `quality.py` (0-100).
- `runner.py:ingest_loop` is a bot background task (tick 60 s, each source every 10 min, `INGEST_ENABLED=0` turns it off): list -> batched upserts, detail re-check (fills descriptions, closes 404/archived), stale close after 21 days unconfirmed, purge closed > 60 days. Never a transaction across network I/O. All SQL is in `repo.py`; read API for consumers: `search`, `get`, `freshest_for_post`. Tests stub all HTTP.

### Vacancy formatting is shared
`src/functions/vacancy_format.py`: `normalize_vacancy_detail(uid, detail, lang)` (localized labels plus `codes`), `format_vacancy_message_html(uid, detail, lang, compact)` used by the bot deeplink, auto-post, notifications and `webapp/routers/jobs.py`. Integer code -> label maps live in the i18n dictionaries on both sides (`src/i18n/*.py` and `webapp/frontend/src/i18n/*/vacancy.ts`); keep the code numbers in sync.

### Frontend
- Routing in `App.tsx`: `/app` is the entry and dispatches to Home/Profile/Saves via `?go=` or Telegram `start_param`. Outside Telegram only `Landing` renders. `ErrorBoundary` wraps the routes; `ToastHost` is mounted once.
- Big pages are directories: `src/pages/ResumeStudio/` (index, `useResumeDraft`, `useResumeSync`, `steps/`, `TemplatePreview`) and `src/pages/Admin/`. Typed client in `src/api/admin.ts` (+ `adminTypes.ts`, `gate.ts`); recharts is the lazy `vendor-charts` chunk. The "Admin panel" entry appears only when `/auth/gate` reports a role.

#### Admin panel (v3, mobile-first — rules in `docs/ADMIN_UI_V3_SPEC.md`)
- `/admin/*` renders **without** the app `Layout` (no app header, no BottomNav): the panel owns the viewport. Chrome is one 40px header plus one 44px bottom bar (`layout/AdminShell.tsx`, `AdminBar.tsx`); on ≥1024px a 56px `Rail` replaces the bar. Pages never draw an `<h1>` — they declare the header with `useAdminHeader({title|titleKey, back, primary, menu})`. The single `primary` action is a compact button in the header on every size; Telegram's `MainButton` is deliberately unused (it draws a second full-width bar under our own) and the shell hides it on mount. `hooks/haptics.ts:haptic()` gives feedback on confirm/failure. The header starts below `--admin-top-inset` so Telegram's floating fullscreen controls never cover it.
- **Every overlay is a history entry.** Sheets open with `useHistorySheet(name)` (pushes the same location with the sheet name on `location.state.sheets`) or as a route (`/admin/users/:id/action/:action`). Telegram BackButton, the browser back gesture, `Esc` and the header's ‹ all funnel into `hooks/useAdminBack.ts` and close exactly one level; at the panel root back leaves to `/app`. Filters, sub-tabs, periods and accordion sections live in the URL (`useAdminFilters`, `useQueryState`, `useUrlTabs`, `Accordion queryKey`) but REPLACE history, so they survive reload without growing the back stack.
- Density scale (enforced by review): 13px body / 11px meta (nothing smaller), 32px buttons, 40px rows, 56px two-line rows, `p-3`/`rounded-xl`, no card inside card. Banned in `src/pages/Admin`: `text-base`, `text-lg`, `text-[9px]`, `text-[10px]`, `p-4`+, `rounded-2xl`, `h-11`, `h-12`, `tap-target`. Utilities live under `.admin-root` in `index.css`.
- Kit in `src/pages/Admin/ui/` (`Button`, `Chip`, `StatusChip`, `StatTile`, `KeyValue`, `List`/`ListRow`, `SearchBar`, `FilterChips`+`FilterSheet`, `Accordion`, `Tabs`, `SegmentedControl`, `Toolbar`, `ActionBar`, `Sheet`, `Skeleton`, `EmptyState`, `JsonDetails`, `PeriodSelector`, `ProgressBar`) — use it instead of new one-off components; `ui/KitPage.tsx` is a dev-only gallery at `/admin/_kit`. Pages are `pages/<Name>Page.tsx` plus one folder each (users, broadcasts, channels, content, finance, system, autopost, analytics, views/Overview+Settings); `registry.ts` maps ids, paths, child routes and `minRole`. Generic inputs live in `src/components/ui/` (`BottomSheet`, `Field`, `StyledSelect`, `MonthYearPicker`, `TagInput`, `WizardProgress`).
- i18n: `src/i18n/` with per-namespace dictionaries (`common`, `vacancy`, `resume`, `admin`, `adminUsers`, `adminBroadcasts`, `adminChannels`, `adminContent`, `adminFinance`, `adminSystem`, `adminAutopost`) per language (a new namespace = a file per language + one import line in `src/i18n/index.ts` and in `ru/index.ts`, `en/index.ts`); uz is eager and the type source, ru/en are lazy chunks loaded by `ensureDictionary`. Use `useT()` (`t(key, vars)`), `useLocale()` for numbers/dates, `useVacancyCodeLabel()` for codes. A missing ru/en key is a compile error. Language state is `src/store/lang.ts` (localStorage -> `/auth/me` -> Telegram `language_code` -> uz), synced with `PATCH /api/profile/lang`.
- Theme: tailwind `darkMode: 'class'` with semantic tokens (`bg`, `surface`, `surfaceAlt`, `text`, `muted`, `border`, `primary`, `primaryFg`, `success`, `warning`, `danger`) defined as CSS variables in `index.css`; `src/store/theme.ts` + `useTheme()` (modes `telegram`/`system`/`light`/`dark`). Never use raw slate/gray/white classes except in resume previews (they depict a printed page) and brand gradients. Language and theme switchers are in the Profile "Settings" card.
- Data: react-query hooks in `src/hooks/` (`useJobs` list key `["jobs","list",params]`, `useJobDetail` `["jobs","detail",uid]`, `useSaves` with keyed optimistic rollback, `useStaticList` for regions/districts/specs). Errors go through `src/lib/parseApiError.ts` and `useToast().apiError`.
- Back is hierarchical, not history replay: `src/lib/nav/parents.ts` declares each screen's parent (`/app` is the only root; `state.navParent` overrides), `src/hooks/useAppBack.ts` `backAction` pops an open overlay first, then runs the page interceptor, then goes to the parent (replace unless the entry below is the parent). Tab switches replace history. Telegram BackButton and the admin back both use it; never add `navigate(-1)` except to pop an overlay. `node webapp/frontend/scripts/nav-check.mjs` checks the parent map.
- Telegram viewport handling is the fragile area. `useTelegramWebApp` computes `--bottom-safe` in JS because fullscreen zeroes `contentSafeAreaInset`; `BottomNav` returns `null` while `useKeyboardOpen()` is true and that hook must be called before any early return. `useBackInterceptor` lets pages capture the Telegram BackButton.

## Conventions
- Commit messages follow conventional commits with optional scope: `feat(resume): ...`, `fix: ...`, `chore(deploy): ...`.
- `src/buttons/buttuns.py` is misspelled; import it as-is.
- New env variables must also be added by hand to the server `.env` (it is not synced by deploy); `deploy_safe.sh` bootstraps `DB_PATH` and `WEBAPP_SECRET` if missing; both deploy paths run `pip install` only when `requirements.txt` changed.
- Broadcast media is stored under `<DB dir>/uploads/`; never served by the API, sent to Telegram by the bot.
- `docs/ADMIN_PANEL_PLAN.md` records the admin v2 design decisions; `ops/` holds the server backup/logrotate scripts and the load test.

## Working agreement (for the AI — binding)

**Roles**
- **Lead / PM** (main session): reads the code, splits big work into disjoint packages, reviews every diff itself, talks to the owner, merges. Large work is delegated, not typed by hand; the lead supervises.
- **Builder agents**: each in its own git worktree + branch, only its own files ("one file, one package"), a commit after every logical step, never push to `master`. Brief: `.claude/agent-brief.md`, included in every agent prompt. Natural packages here: bot (`main.py`, `src/`), API (`webapp/core`, `webapp/routers`, `webapp/resume`), frontend (`webapp/frontend/src`), ops (`ops/`, `deploy_safe.sh`).
- **Independent reviewer**: a separate read-only agent. Verdict APPROVE / APPROVE WITH FIXES / CHANGES REQUESTED; findings MAJOR / MINOR / NIT, each with file:line and proof. Auth, entry gate, confirm tokens, ledger/wallet and migrations get the strongest model.
- **Models**: mechanical/doc/table work — light model (haiku/sonnet); algorithms, integration, complex UI — opus; security, money, auth and independent review — the strongest. A package that needs real tests or mutation checks never goes to a light model.
- **Limits**: ≤ 3–4 agents at a time, ≤ 2 heavy processes (agents count). One file, one agent.

**Flow**
1. Read the code, then ask the owner ALL open questions ONCE (`AskUserQuestion`, recommendation first).
2. After the answers, run to the end without asking: code → tests → independent review → merge → push → deploy → verify → tell the owner (see "Ship policy").
3. Take small technical decisions yourself and list them in the report; ask only about product, money values, server-wide or irreversible decisions.
4. If the owner says stop, stop immediately and do nothing more.
5. Long work is tracked in `.claude/holat.md` (read it at session start); `/holat` reads, `/holats` stops everything and saves.

**Evidence**
- "Done" only with a command plus pass/fail counts. Never trust an agent report blindly: rerun on the merged tree.
- New important assertion → mutation check: break the code on purpose, watch that test fail there, restore.
- Say explicitly what was not verified.

**Safety**
- Before an irreversible or outward-facing action, confirm unless the ship policy above covers it; approval in one context does not carry over to another.
- If a permission is denied, do not route around it; report it.

## Testing standard

- Backend (bot + API): `pytest` on a temp SQLite (`tests/conftest.py`). Every behaviour change needs a test in the matching `tests/test_*.py`; money, auth, gate and migration changes also need a negative test (wrong role, insufficient balance, replayed confirm token, re-applied migration).
- `tests/test_e2e_flow.py` boots the real app (gate, admin, ledger, broadcast, content): run it for any change under `webapp/core` or the admin routers.
- `pytest -m network` hits live osonish.uz: run only when `src/functions/scraping.py` or vacancy formatting changes, never in a loop.
- Frontend has no unit tests: `npm run lint` and `npm run build` (includes `tsc -b`) are mandatory for any frontend change. Outside Telegram the app renders only `Landing`, so real UI checks happen in the Telegram Mini App after deploy; state what was checked there and what was not.
- Before a deploy: full `pytest`, `python -m pyflakes ...` (command above), `npm run lint`, `npm run build`, all green.

## Heavy commands

The dev machine has 14 GB RAM shared with the editor, agents and other projects. Full `pytest`, `npm run build`, `tsc -b` and `ops/loadtest.py` run only through `scripts/heavy.sh` (cgroup `vakant3-heavy.slice`: 4G total, 3G and 900 s per command; `-m`/`-t` override). Prefer single test files while iterating; at most 2 heavy commands at a time.

## Deploy

Normal path: push `master` → CI (`backend` ‖ `frontend` → `ci-ok` → `release`) → `deploy` branch → server cron `ops/auto_deploy.sh` (live within ~2–5 min of a green CI; state in `/home/vakant/.deploy/`, log `/var/log/vakant-deploy.log`). Fallback: `bash deploy_safe.sh` (builds locally, rsyncs, pre-deploy backup, pip only when `requirements.txt` changed, restart, health). Neither deletes server files. Rollback, kill switch and server layout: `.claude/deploy.md`; Uzbek runbook: `deploy.txt` §11.

## State and memory

Long-running work state — `.claude/holat.md` (`/holat`, `/holats`); action log — `.claude/actions/`; directory map — `.claude/structure.md`. `.claude/` is git-ignored (local only). To refresh these rules: `/sozlash yangila`.
