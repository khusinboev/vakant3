"""ops/healthcheck.sh DB checks and ops/restore_check.sh, run as real bash scripts.

Everything points at temp files through the scripts' env overrides; ``curl``,
``systemctl`` and ``df`` are fakes on PATH, so nothing reaches Telegram, the
host services or a real database. User ids are synthetic (900000000000+).
"""
import gzip
import hashlib
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HEALTHCHECK = ROOT / "ops" / "healthcheck.sh"
RESTORE_CHECK = ROOT / "ops" / "restore_check.sh"
BASE = 900_000_000_000
NOW = int(time.time())

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="bash scripts")


def _make_db(path: Path, *, last_attempt_column: bool = True) -> None:
    conn = sqlite3.connect(path)
    target_cols = "broadcast_id INTEGER, user_id INTEGER, status TEXT, sent_at INTEGER, claimed_at INTEGER"
    if last_attempt_column:
        target_cols += ", last_attempt_at INTEGER"
    conn.executescript(
        f"""
        CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER);
        CREATE TABLE schema_migrations (id TEXT PRIMARY KEY, applied_at INTEGER);
        CREATE TABLE broadcasts (id INTEGER PRIMARY KEY, status TEXT, created_at INTEGER, started_at INTEGER);
        CREATE TABLE broadcast_targets ({target_cols});
        CREATE TABLE error_log (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at INTEGER, message TEXT);
        """
    )
    conn.executemany("INSERT INTO users VALUES (?, 0)", [(BASE + i,) for i in range(3)])
    conn.executemany("INSERT INTO schema_migrations VALUES (?, 0)", [("m000",), ("m001",)])
    conn.commit()
    conn.close()


def _sql(path: Path, sql: str, params=()) -> None:
    conn = sqlite3.connect(path)
    if isinstance(params, list):
        conn.executemany(sql, params)
    else:
        conn.execute(sql, params)
    conn.commit()
    conn.close()


@pytest.fixture
def env(tmp_path):
    """Script environment with fake curl/systemctl/df; the curl log records Telegram sends."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "telegram.log"
    (bin_dir / "curl").write_text(
        "#!/usr/bin/env bash\n"
        'case "$*" in *api.telegram.org*) echo "$*" >> "$CURL_LOG"; exit 0;; esac\n'
        'exit "${FAKE_HEALTH_RC:-0}"\n'
    )
    (bin_dir / "systemctl").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "df").write_text("#!/usr/bin/env bash\necho 'Use%'\necho ' 10%'\n")
    for name in ("curl", "systemctl", "df"):
        (bin_dir / name).chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text("TOKEN=123456:TEST\nADMIN_IDS=900000000001,900000000002\n")
    db = tmp_path / "database.sqlite3"
    _make_db(db)
    return {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "VAKANT_ENV": str(env_file),
        "VAKANT_HEALTH_STATE": str(tmp_path / ".health_state"),
        "VAKANT_DB": str(db),
        "VAKANT_PY": sys.executable,
        "CURL_LOG": str(log),
    }


def _run(script: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *args], env=env, capture_output=True, text=True, timeout=60
    )


def _db_problems(env: dict, **overrides) -> str:
    result = _run(HEALTHCHECK, {**env, **overrides}, "--db-only")
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _sends(env: dict) -> list[str]:
    log = Path(env["CURL_LOG"])
    return log.read_text().splitlines() if log.exists() else []


# ─── healthcheck: DB checks ─────────────────────────────────────────────────

def test_healthy_db_reports_nothing_and_is_not_modified(env):
    db = Path(env["VAKANT_DB"])
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert _db_problems(env) == ""
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in db.parent.glob("database.sqlite3*")) == ["database.sqlite3"]


def test_running_broadcast_without_progress_for_30_min_is_reported(env):
    db = Path(env["VAKANT_DB"])
    _sql(db, "INSERT INTO broadcasts VALUES (7, 'running', ?, ?)", (NOW - 7200, NOW - 7200))
    _sql(db, "INSERT INTO broadcast_targets VALUES (7, ?, 'failed', NULL, NULL, ?)", (BASE + 1, NOW - 31 * 60))
    assert _db_problems(env).startswith("broadcast_7_stalled_")
    # Any recent progress mark (here a failure stamped a minute ago) clears it.
    _sql(db, "INSERT INTO broadcast_targets VALUES (7, ?, 'failed', NULL, NULL, ?)", (BASE + 2, NOW - 60))
    assert _db_problems(env) == ""


def test_only_running_broadcasts_count(env):
    db = Path(env["VAKANT_DB"])
    for bid, status in ((1, "paused"), (2, "done"), (3, "queued")):
        _sql(db, "INSERT INTO broadcasts VALUES (?, ?, ?, ?)", (bid, status, NOW - 9999, NOW - 9999))
    assert _db_problems(env) == ""


def test_stall_check_works_before_m019(tmp_path, env):
    db = tmp_path / "legacy.sqlite3"
    _make_db(db, last_attempt_column=False)
    _sql(db, "INSERT INTO broadcasts VALUES (3, 'running', ?, ?)", (NOW - 3600, NOW - 3600))
    _sql(db, "INSERT INTO broadcast_targets VALUES (3, ?, 'sent', ?, NULL)", (BASE + 1, NOW - 3000))
    assert _db_problems(env, VAKANT_DB=str(db)).startswith("broadcast_3_stalled_")
    _sql(db, "INSERT INTO broadcast_targets VALUES (3, ?, 'sending', NULL, ?)", (BASE + 2, NOW - 30))
    assert _db_problems(env, VAKANT_DB=str(db)) == ""


def test_more_than_50_errors_in_10_minutes(env):
    db = Path(env["VAKANT_DB"])
    _sql(db, "INSERT INTO error_log (created_at, message) VALUES (?, 'x')", [(NOW - 30,)] * 50)
    _sql(db, "INSERT INTO error_log (created_at, message) VALUES (?, 'old')", [(NOW - 700,)] * 100)
    assert _db_problems(env) == ""  # exactly 50 recent: not more than the limit
    _sql(db, "INSERT INTO error_log (created_at, message) VALUES (?, 'x')", (NOW - 5,))
    assert _db_problems(env) == "errors_51_in_10min"


def test_db_size_limit(env):
    assert _db_problems(env, HC_DB_MAX_BYTES="1") == "db_size_0MB"
    assert _db_problems(env, HC_DB_MAX_BYTES=str(1024**3)) == ""


def test_missing_db_is_reported(env, tmp_path):
    assert _db_problems(env, VAKANT_DB=str(tmp_path / "nope.sqlite3")) == "db_missing"


# ─── healthcheck: alert once, recover once ──────────────────────────────────

def test_db_problem_alerts_once_and_recovery_is_announced_once(env):
    db = Path(env["VAKANT_DB"])
    _sql(db, "INSERT INTO error_log (created_at, message) VALUES (?, 'x')", [(NOW - 5,)] * 60)

    assert _run(HEALTHCHECK, env).returncode == 0
    sends = _sends(env)
    assert len(sends) == 2  # one per admin
    assert all("errors_60_in_10min" in line for line in sends)
    assert {"chat_id=900000000001", "chat_id=900000000002"} <= {
        part for line in sends for part in line.split()
    }

    _run(HEALTHCHECK, env)  # still bad: no second alert
    assert len(_sends(env)) == 2

    _sql(db, "DELETE FROM error_log")
    _run(HEALTHCHECK, env)
    sends = _sends(env)
    assert len(sends) == 4 and all("tiklandi" in line for line in sends[2:])
    _run(HEALTHCHECK, env)  # healthy again: silence
    assert len(_sends(env)) == 4
    assert Path(env["VAKANT_HEALTH_STATE"]).read_text().strip() == "ok"


def test_existing_checks_still_alert(env):
    _run(HEALTHCHECK, {**env, "FAKE_HEALTH_RC": "7"})
    sends = _sends(env)
    assert len(sends) == 2 and all("api_health" in line for line in sends)


# ─── restore_check ──────────────────────────────────────────────────────────

def _backup(db: Path, dest: Path, mtime: int) -> Path:
    dest.write_bytes(gzip.compress(db.read_bytes()))
    os.utime(dest, (mtime, mtime))
    return dest


def test_restore_check_ok_on_the_newest_backup_and_cleans_up(env, tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    db = Path(env["VAKANT_DB"])
    old = tmp_path / "old.sqlite3"
    _make_db(old)
    _sql(old, "DELETE FROM users")
    _backup(old, backups / "database_20261001.sqlite3.gz", NOW - 86400)
    newest = _backup(db, backups / "predeploy_x.sqlite3.gz", NOW - 60)
    work_env = {**env, "VAKANT_BACKUP_DIR": str(backups)}

    result = _run(RESTORE_CHECK, work_env)
    assert result.returncode == 0, result.stdout + result.stderr
    line = result.stdout.strip()
    assert line.startswith("OK restore_check: ") and str(newest) in line
    assert "integrity=ok users=3 schema_migrations=2" in line
    assert not list(tmp_path.glob("vakant-restore.*"))  # temp copy removed


def test_restore_check_fails_on_a_corrupt_or_missing_backup(env, tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    work_env = {**env, "VAKANT_BACKUP_DIR": str(backups)}

    empty = _run(RESTORE_CHECK, work_env)
    assert empty.returncode == 1 and empty.stdout.startswith("FAIL restore_check: no ")

    (backups / "database_bad.sqlite3.gz").write_bytes(b"not gzip at all")
    bad = _run(RESTORE_CHECK, work_env)
    assert bad.returncode == 1 and "does not gunzip" in bad.stdout

    (backups / "database_bad.sqlite3.gz").write_bytes(gzip.compress(b"SQLite format 3\x00" + b"\x01" * 5000))
    garbage = _run(RESTORE_CHECK, work_env)
    assert garbage.returncode == 1 and garbage.stdout.startswith("FAIL restore_check: ")
    assert not list(tmp_path.glob("vakant-restore.*"))


def test_restore_check_fails_when_integrity_check_finds_damage(env, tmp_path):
    """A backup that opens and answers COUNT(*) but whose b-trees are damaged."""
    backups = tmp_path / "backups"
    backups.mkdir()
    db = Path(env["VAKANT_DB"])
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE junk (a TEXT)")
    conn.execute("CREATE INDEX idx_junk ON junk(a)")
    conn.executemany("INSERT INTO junk VALUES (?)", [(f"v{i}",) for i in range(50)])
    conn.commit()
    # Point the index at another index's b-tree: rows go "missing from index".
    conn.execute("PRAGMA writable_schema=ON")
    conn.execute(
        "UPDATE sqlite_master SET rootpage = (SELECT rootpage FROM sqlite_master "
        "WHERE name = 'sqlite_autoindex_schema_migrations_1') WHERE name = 'idx_junk'"
    )
    conn.commit()
    conn.close()
    _backup(db, backups / "database_1.sqlite3.gz", NOW)
    result = _run(RESTORE_CHECK, {**env, "VAKANT_BACKUP_DIR": str(backups)})
    assert result.returncode == 1, result.stdout
    assert "integrity_check=" in result.stdout and "missing from index" in result.stdout


def test_restore_check_fails_without_migrations(env, tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    db = Path(env["VAKANT_DB"])
    _sql(db, "DELETE FROM schema_migrations")
    _backup(db, backups / "database_1.sqlite3.gz", NOW)
    result = _run(RESTORE_CHECK, {**env, "VAKANT_BACKUP_DIR": str(backups)})
    assert result.returncode == 1 and "schema_migrations is empty" in result.stdout
