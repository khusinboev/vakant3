# ops/

Operational scripts. `backup_db.sh` and `logrotate-vakant-bot` run on the
production server (see `deploy.txt`). `loadtest.py` is a local-only tool —
it is never run against production and never reads the server `.env`.

## loadtest.py

A load generator for the Mini App API (`webapp/`), built for the Bosqich 4/5
acceptance target in `docs/ADMIN_PANEL_PLAN.md` §3: **200 concurrent
requests, p95 < 500 ms, no "database is locked" errors.**

It only uses `httpx` (already in `requirements.txt`) plus the standard
library — nothing extra to install.

**Never run this against `abitur24.uz` or any production host.** It is a
local/dev-only tool: point `--base-url` at a `uvicorn` process on your own
machine, backed by a throwaway SQLite file (never `/home/vakant/data/database.sqlite3`
and never a copy of it that you intend to deploy from).

### 1. Start a local API

```bash
cd /path/to/vakant3
DB_PATH=/tmp/loadtest.sqlite3 \
ALLOW_INSECURE_SECRET=1 \
  .venv/bin/uvicorn webapp.main:app --port 8000
```

`ALLOW_INSECURE_SECRET=1` lets the API boot with the default `WEBAPP_SECRET`
(`change-me`) instead of refusing to start. `loadtest.py`'s seed mode signs
tokens with the same default secret, so **both processes must see the same
`WEBAPP_SECRET`** — either leave it unset in both (default `change-me`) or
export the same explicit value to both shells.

A brand new `DB_PATH` only gets `webapp_admin_settings`, `resume_*`,
`vacancy_cache`, etc. from the API's own `init_db()` — the `users`,
`regions`, `districts` and `webapp_sessions` tables are normally created by
the **bot's** `StatsMiddleware.init_db()` (see CLAUDE.md). For a pure
load-test DB you don't need the bot at all: `loadtest.py --seed-sessions`
creates the minimal `users` + `webapp_sessions` schema itself. `regions`
will not exist unless you also run the bot once against that DB path — that
only matters for the `region_soato` filter in the `jobs` scenario, which the
script treats as optional and silently skips if `/api/filters/regions`
errors.

### 2. Create test users + sessions

```bash
.venv/bin/python ops/loadtest.py \
  --seed-sessions 200 \
  --db-path /tmp/loadtest.sqlite3 \
  --bearer-file /tmp/loadtest-bearer.txt
```

This inserts 200 fake users (`user_id` starting at 900000000000, override
with `--seed-user-base`) directly into `/tmp/loadtest.sqlite3`, mints a
signed session per user the same way `POST /api/auth/tg-webapp` would
(`webapp.core.session.create_session`, imported directly with
`ALLOW_INSECURE_SECRET=1`; if that import fails for any reason the script
falls back to minting the JWS by hand with `python-jose`, reading
`WEBAPP_SECRET` from the environment), and writes one bearer token per line
to `/tmp/loadtest-bearer.txt`.

You can also point `--init-data-file` at real (or bot-issued) Telegram
`initData` strings instead — one per line — if you'd rather exercise the
`X-Telegram-Init-Data` auth path.

### 3. Run the load test

```bash
.venv/bin/python ops/loadtest.py \
  --base-url http://localhost:8000 \
  --users 200 \
  --duration 60 \
  --scenario mixed \
  --bearer-file /tmp/loadtest-bearer.txt
```

Each virtual user loops for `--duration` seconds. Credentials are cycled
(`user_index % len(credentials)`), so 200 users with 200 seeded sessions
means one session per user; fewer seeded sessions just means some sessions
are shared by several concurrent virtual users (still realistic — the API
doesn't care how many browser tabs use one session).

`--scenario`:
- `jobs` — `GET /api/jobs/search` (random page 1-5, random region if
  `/api/filters/regions` returned any) then `GET /api/jobs/{uid}` for a
  random result.
- `saves` — the `jobs` flow, plus `GET /api/saves`, plus a 10% chance to
  `POST /api/saves/{uid}` (and a 50% chance to immediately `DELETE` it
  again).
- `resume` — `GET /api/resume/profile` then `PUT /api/resume/profile` with
  a minimal autosave-style body.
- `mixed` (default) — each iteration randomly picks jobs/saves/resume with
  weights 50/30/20, matching the plan's "jobs/search, saves, resume
  autosave" scenario list.

A `429` response is recorded like any other status but the script then
sleeps 1-2s before that virtual user's next request, so a real rate limit
doesn't turn into a request storm.

### 4. Read the numbers

The script prints a table to stdout and writes the full JSON to
`ops/loadtest-results/<unix-timestamp>.json` (create your own `--output-dir`
if you don't want it under the repo). Per endpoint you get `count`, `errors`
(any status `>= 400` or a transport failure), `rate_limited_429`,
`status_counts`, `error_codes` (the API's `detail.code`, e.g.
`REFERRAL_LOCKED`, `SAVE_LIMIT_REACHED`), and `p50_ms`/`p95_ms`/`p99_ms`/
`max_ms`/`mean_ms` latency.

The acceptance check from the plan is printed as one line:

```
Acceptance (p95<500ms, no 'database is locked'): PASS
```

`PASS` means: the overall p95 across all endpoints is under 500 ms **and**
no endpoint's `error_codes` contains anything with "locked" in it (an
aiosqlite `database is locked` exception surfaces as a transport error whose
`error_codes` key is the exception class name, e.g. `OperationalError`, if
it isn't caught server-side — check the API's own logs too, since some
"database is locked" occurrences are logged and swallowed rather than
returned to the client).

Any `4xx`/`5xx` count that isn't `429` is worth reading the `error_codes`
for before blaming the DB — a freshly seeded user with no referrals will get
`REFERRAL_LOCKED` on `jobs`/`saves` endpoints if the target DB's
`webapp_admin_settings.referral_enabled` is `1` (it defaults to `0` on a
brand new DB, so a from-scratch `--db-path` is unaffected).

### CLI reference

```
--base-url URL           default http://localhost:8000
--users N                concurrent virtual users, default 50
--duration S              run length in seconds, default 30
--scenario {jobs,saves,resume,mixed}   default mixed
--init-data-file FILE     one Telegram initData string per line
--bearer-file FILE        one session bearer token per line
                          (also the seed-mode output path)
--output-dir DIR          default ops/loadtest-results
--request-timeout S       per-request httpx timeout, default 15

--seed-sessions N         create N users+sessions in --db-path and exit
--db-path FILE            sqlite file to seed into
--seed-user-base ID       first fake user_id, default 900000000000
--session-ttl-seconds S   seeded session lifetime, default 30 days
```
