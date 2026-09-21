#!/usr/bin/env python3
"""HTTP load generator for the vakant3 Mini App API (webapp/).

Usage (against a local dev API, see ops/README.md for the full recipe)::

    ALLOW_INSECURE_SECRET=1 uvicorn webapp.main:app --port 8000 &
    python ops/loadtest.py --seed-sessions 50 --db-path /tmp/loadtest.sqlite3 \\
        --bearer-file /tmp/bearer.txt
    python ops/loadtest.py --base-url http://localhost:8000 --users 50 \\
        --duration 30 --scenario mixed --bearer-file /tmp/bearer.txt

Only httpx (already a project dependency) is used for HTTP; no extra
third-party packages are required beyond requirements.txt.

Never point this at a production host. The acceptance target (docs/
ADMIN_PANEL_PLAN.md Bosqich 4/5) is 200 concurrent virtual users with
p95 < 500 ms and zero "database is locked" errors.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import math
import os
import random
import secrets
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = REPO_ROOT / "ops" / "loadtest-results"

SCENARIOS = ("jobs", "saves", "resume", "mixed")
MIXED_WEIGHTS = {"jobs": 50, "saves": 30, "resume": 20}

# Reserved fake Telegram ids for seeded load-test users so they never collide
# with a real account. Telegram user ids in production are well below this.
DEFAULT_SEED_USER_BASE = 900_000_000_000


# ---------------------------------------------------------------------------
# Percentile / histogram helpers (pure, unit-tested without any network I/O)
# ---------------------------------------------------------------------------


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile of ``values`` (0..100). Empty -> 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    rank = (len(ordered) - 1) * (pct / 100.0)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[int(rank)]
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


@dataclasses.dataclass
class EndpointStats:
    """Latency histogram + status/error breakdown for one logical endpoint."""

    name: str
    latencies_ms: list[float] = dataclasses.field(default_factory=list)
    status_counts: Counter = dataclasses.field(default_factory=Counter)
    error_codes: Counter = dataclasses.field(default_factory=Counter)

    def add(self, latency_ms: float, status_code: int, error_code: str | None = None) -> None:
        self.latencies_ms.append(latency_ms)
        self.status_counts[status_code] += 1
        if error_code:
            self.error_codes[error_code] += 1

    @property
    def count(self) -> int:
        return len(self.latencies_ms)

    @property
    def error_count(self) -> int:
        return sum(n for status, n in self.status_counts.items() if status == 0 or status >= 400)

    @property
    def rate_limited_count(self) -> int:
        return self.status_counts.get(429, 0)

    def summary(self) -> dict[str, Any]:
        lat = self.latencies_ms
        return {
            "endpoint": self.name,
            "count": self.count,
            "errors": self.error_count,
            "rate_limited_429": self.rate_limited_count,
            "status_counts": dict(sorted(self.status_counts.items())),
            "error_codes": dict(self.error_codes),
            "p50_ms": round(percentile(lat, 50), 1),
            "p95_ms": round(percentile(lat, 95), 1),
            "p99_ms": round(percentile(lat, 99), 1),
            "max_ms": round(max(lat), 1) if lat else 0.0,
            "mean_ms": round(sum(lat) / len(lat), 1) if lat else 0.0,
        }


StatsMap = dict[str, EndpointStats]


def record(stats: StatsMap, name: str, latency_ms: float, status_code: int, error_code: str | None = None) -> None:
    bucket = stats.get(name)
    if bucket is None:
        bucket = EndpointStats(name)
        stats[name] = bucket
    bucket.add(latency_ms, status_code, error_code)


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loadtest.py",
        description="Concurrent load generator for the vakant3 Mini App API.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL (dev default port 8000).")
    parser.add_argument("--users", type=int, default=50, help="Concurrent virtual users.")
    parser.add_argument("--duration", type=float, default=30.0, help="Run length in seconds.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="mixed", help="Which flow virtual users run.")
    parser.add_argument(
        "--init-data-file",
        help="File with one valid Telegram initData string per line; cycled across virtual users.",
    )
    parser.add_argument(
        "--bearer-file",
        help="File with one session bearer token per line; cycled across virtual users. "
        "Also used as the output path when --seed-sessions is given.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_RESULTS_DIR), help="Where the JSON report is written.")
    parser.add_argument("--request-timeout", type=float, default=15.0, help="Per-request httpx timeout (seconds).")

    seed = parser.add_argument_group("--seed-sessions mode (no load generated, just DB setup)")
    seed.add_argument(
        "--seed-sessions",
        type=int,
        default=None,
        help="Create N test users + webapp_sessions rows directly in --db-path and exit.",
    )
    seed.add_argument("--db-path", help="SQLite file to seed into (required with --seed-sessions).")
    seed.add_argument(
        "--seed-user-base",
        type=int,
        default=DEFAULT_SEED_USER_BASE,
        help="First fake user_id; subsequent seeded users increment from here.",
    )
    seed.add_argument(
        "--session-ttl-seconds",
        type=int,
        default=30 * 24 * 60 * 60,
        help="Lifetime of seeded sessions (matches SESSION_TTL_SECONDS default).",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.seed_sessions is not None:
        if args.seed_sessions <= 0:
            parser.error("--seed-sessions must be a positive integer")
        if not args.db_path:
            parser.error("--seed-sessions requires --db-path")
    else:
        if not args.init_data_file and not args.bearer_file:
            parser.error(
                "one of --init-data-file or --bearer-file is required "
                "(or run with --seed-sessions/--db-path first to create one)"
            )
        if args.users <= 0:
            parser.error("--users must be a positive integer")
        if args.duration <= 0:
            parser.error("--duration must be positive")
    return args


def load_credentials(path: str) -> list[str]:
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if value and not value.startswith("#"):
            lines.append(value)
    if not lines:
        raise SystemExit(f"{path} has no usable credential lines")
    return lines


# ---------------------------------------------------------------------------
# Seeding: create fake users + signed sessions directly in a local sqlite DB
# ---------------------------------------------------------------------------


def _mint_session_token(sid: str, exp: int) -> str:
    """Sign {"sid", "exp"} the same way webapp.core.session.sign_session_payload does."""
    from jose import jws

    secret = os.environ.get("WEBAPP_SECRET", "change-me")
    return jws.sign({"sid": sid, "exp": exp}, secret, algorithm="HS256")


async def _create_session_row(db: Any, user_id: int, ttl_seconds: int) -> str:
    """Insert a webapp_sessions row and return the bearer token for it.

    Prefers the real ``webapp.core.session`` helpers (so the token format can
    never drift from what the API actually verifies); falls back to minting
    the JWS by hand if that module cannot be imported (e.g. run outside the
    repo root, or pydantic-settings unavailable).
    """
    os.environ.setdefault("ALLOW_INSECURE_SECRET", "1")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from webapp.core.session import create_session  # type: ignore

        token, _exp = await create_session(db, user_id)
        return token
    except Exception:
        now = int(time.time())
        exp = now + ttl_seconds
        sid = secrets.token_urlsafe(32)
        await db.execute(
            "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (sid, user_id, now, exp),
        )
        return _mint_session_token(sid, exp)


async def _ensure_seed_schema(db: Any) -> None:
    """Match the users/webapp_sessions schema owned by the bot (src/middleware/middlewares.py)
    and mirrored by the API (webapp/core/database.py). Idempotent."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            date INTEGER,
            lang TEXT,
            region TEXT,
            district TEXT,
            specs TEXT,
            money INTEGER
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS webapp_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    await db.commit()


async def seed_sessions(args: argparse.Namespace) -> Path:
    import aiosqlite

    now = int(time.time())
    tokens: list[str] = []
    async with aiosqlite.connect(args.db_path) as db:
        await _ensure_seed_schema(db)
        for i in range(args.seed_sessions):
            user_id = args.seed_user_base + i
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
                (user_id, now, "uz"),
            )
            await db.commit()
            token = await _create_session_row(db, user_id, args.session_ttl_seconds)
            await db.commit()
            tokens.append(token)

    out_path = Path(args.bearer_file or (DEFAULT_RESULTS_DIR / "seeded-bearer-tokens.txt"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(tokens) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def _error_code_from_response(resp: httpx.Response) -> str | None:
    try:
        detail = resp.json().get("detail")
    except Exception:
        return None
    if isinstance(detail, dict):
        return str(detail.get("code") or "")
    return None


async def _timed_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    stats: StatsMap,
    name: str,
    **kwargs: Any,
) -> httpx.Response | None:
    start = time.perf_counter()
    try:
        resp = await client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        record(stats, name, elapsed_ms, 0, type(exc).__name__)
        return None
    elapsed_ms = (time.perf_counter() - start) * 1000
    error_code = _error_code_from_response(resp) if resp.status_code >= 400 else None
    record(stats, name, elapsed_ms, resp.status_code, error_code)
    if resp.status_code == 429:
        # Respect rate limits: back off before the caller's next request
        # instead of hammering the same bucket again immediately.
        await asyncio.sleep(random.uniform(1.0, 2.0))
    return resp


async def _prime_regions(client: httpx.AsyncClient, headers: dict[str, str]) -> list[str]:
    """Best-effort: fetch region codes once so /jobs/search filters realistically."""
    try:
        resp = await client.get("/api/filters/regions", headers=headers, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            return [str(item["soato"]) for item in data if isinstance(item, dict) and item.get("soato")]
    except Exception:
        pass
    return []


async def _do_jobs(
    client: httpx.AsyncClient, headers: dict[str, str], stats: StatsMap, rng: random.Random, regions: list[str]
) -> str | None:
    params: dict[str, Any] = {"page": rng.randint(1, 5)}
    if regions:
        params["region_soato"] = rng.choice(regions)
    resp = await _timed_request(client, "GET", "/api/jobs/search", headers, stats, "GET /jobs/search", params=params)
    uid = None
    if resp is not None and resp.status_code == 200:
        try:
            vacancies = resp.json().get("vacancies") or []
            if vacancies:
                uid = rng.choice(vacancies).get("uid")
        except ValueError:
            uid = None
    if uid:
        await _timed_request(client, "GET", f"/api/jobs/{uid}", headers, stats, "GET /jobs/{uid}")
    return uid


async def _do_saves(
    client: httpx.AsyncClient, headers: dict[str, str], stats: StatsMap, rng: random.Random, regions: list[str]
) -> None:
    uid = await _do_jobs(client, headers, stats, rng, regions)
    await _timed_request(
        client, "GET", "/api/saves", headers, stats, "GET /saves", params={"page": 1, "limit": 10}
    )
    if uid and rng.random() < 0.10:
        await _timed_request(client, "POST", f"/api/saves/{uid}", headers, stats, "POST /saves/{uid}")
        if rng.random() < 0.5:
            await _timed_request(client, "DELETE", f"/api/saves/{uid}", headers, stats, "DELETE /saves/{uid}")


async def _do_resume(client: httpx.AsyncClient, headers: dict[str, str], stats: StatsMap, rng: random.Random) -> None:
    await _timed_request(client, "GET", "/api/resume/profile", headers, stats, "GET /resume/profile")
    body = {"profile": {"full_name": f"Load Test {rng.randint(1, 10_000)}"}, "selected_template": "clean"}
    await _timed_request(client, "PUT", "/api/resume/profile", headers, stats, "PUT /resume/profile", json=body)


async def virtual_user(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    scenario: str,
    stats: StatsMap,
    stop_at: float,
    rng: random.Random,
    regions: list[str],
) -> None:
    scenario_names = list(MIXED_WEIGHTS.keys())
    scenario_weights = list(MIXED_WEIGHTS.values())
    while time.monotonic() < stop_at:
        scen = scenario if scenario != "mixed" else rng.choices(scenario_names, weights=scenario_weights)[0]
        if scen == "jobs":
            await _do_jobs(client, headers, stats, rng, regions)
        elif scen == "saves":
            await _do_saves(client, headers, stats, rng, regions)
        elif scen == "resume":
            await _do_resume(client, headers, stats, rng)
        await asyncio.sleep(rng.uniform(0.05, 0.3))


# ---------------------------------------------------------------------------
# Orchestration + reporting
# ---------------------------------------------------------------------------


async def run_loadtest(args: argparse.Namespace) -> dict[str, Any]:
    if args.bearer_file:
        creds = load_credentials(args.bearer_file)
        cred_kind = "bearer"
    else:
        creds = load_credentials(args.init_data_file)
        cred_kind = "init-data"

    stats: StatsMap = {}
    limits = httpx.Limits(max_connections=args.users * 2, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.request_timeout, limits=limits) as client:
        primer_headers = _headers_for(creds[0], cred_kind)
        regions = await _prime_regions(client, primer_headers)

        stop_at = time.monotonic() + args.duration
        start_wall = time.time()
        tasks = []
        for i in range(args.users):
            headers = _headers_for(creds[i % len(creds)], cred_kind)
            rng = random.Random(1000 + i)
            tasks.append(
                asyncio.create_task(virtual_user(client, headers, args.scenario, stats, stop_at, rng, regions))
            )
        await asyncio.gather(*tasks)
        elapsed = max(time.time() - start_wall, 1e-6)

    return build_report(stats, args, elapsed)


def _headers_for(cred: str, cred_kind: str) -> dict[str, str]:
    if cred_kind == "bearer":
        return {"Authorization": f"Bearer {cred}"}
    return {"X-Telegram-Init-Data": cred}


def build_report(stats: StatsMap, args: argparse.Namespace, elapsed_seconds: float) -> dict[str, Any]:
    endpoints = [stats[name].summary() for name in sorted(stats)]
    total_requests = sum(e["count"] for e in endpoints)
    total_errors = sum(e["errors"] for e in endpoints)
    total_429 = sum(e["rate_limited_429"] for e in endpoints)
    all_latencies = [lat for bucket in stats.values() for lat in bucket.latencies_ms]
    return {
        "meta": {
            "base_url": args.base_url,
            "users": args.users,
            "duration_requested_s": args.duration,
            "duration_actual_s": round(elapsed_seconds, 2),
            "scenario": args.scenario,
            "timestamp": int(time.time()),
        },
        "totals": {
            "requests": total_requests,
            "errors": total_errors,
            "rate_limited_429": total_429,
            "requests_per_sec": round(total_requests / elapsed_seconds, 2),
            "p50_ms": round(percentile(all_latencies, 50), 1),
            "p95_ms": round(percentile(all_latencies, 95), 1),
            "p99_ms": round(percentile(all_latencies, 99), 1),
        },
        "endpoints": endpoints,
    }


def print_report(report: dict[str, Any]) -> None:
    meta = report["meta"]
    totals = report["totals"]
    print(
        f"\nLoad test: {meta['users']} users, scenario={meta['scenario']}, "
        f"base_url={meta['base_url']}, duration={meta['duration_actual_s']}s"
    )
    print(
        f"Totals: {totals['requests']} requests, {totals['errors']} errors, "
        f"{totals['rate_limited_429']} rate-limited (429), "
        f"{totals['requests_per_sec']} req/s | "
        f"p50={totals['p50_ms']}ms p95={totals['p95_ms']}ms p99={totals['p99_ms']}ms"
    )
    header = f"{'endpoint':<28}{'count':>8}{'errors':>8}{'429':>6}{'p50':>8}{'p95':>8}{'p99':>8}{'max':>9}"
    print(header)
    print("-" * len(header))
    for ep in report["endpoints"]:
        print(
            f"{ep['endpoint']:<28}{ep['count']:>8}{ep['errors']:>8}{ep['rate_limited_429']:>6}"
            f"{ep['p50_ms']:>8.1f}{ep['p95_ms']:>8.1f}{ep['p99_ms']:>8.1f}{ep['max_ms']:>9.1f}"
        )
        if ep["error_codes"]:
            print(f"    error codes: {ep['error_codes']}")
    gate = "PASS" if totals["p95_ms"] < 500 and _no_locked_db(report) else "CHECK"
    print(f"\nAcceptance (p95<500ms, no 'database is locked'): {gate}")


def _no_locked_db(report: dict[str, Any]) -> bool:
    for ep in report["endpoints"]:
        for code in ep["error_codes"]:
            if "locked" in code.lower():
                return False
    return True


def write_report(report: dict[str, Any], output_dir: str) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{report['meta']['timestamp']}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.seed_sessions is not None:
        out_path = asyncio.run(seed_sessions(args))
        print(f"Seeded {args.seed_sessions} users/sessions into {args.db_path} -> bearer tokens at {out_path}")
        return

    report = asyncio.run(run_loadtest(args))
    print_report(report)
    out_path = write_report(report, args.output_dir)
    print(f"\nFull JSON report: {out_path}")


if __name__ == "__main__":
    main()
