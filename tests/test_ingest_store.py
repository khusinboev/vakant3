"""Vacancy store: migration, FTS sync, upserts, dedup, quality, runner lifecycle and the read API."""
from __future__ import annotations

from dataclasses import replace

import aiosqlite
import pytest

from src.db.connection import apply_pragmas
from src.db.migrate import run_migrations
from src.db.migrations import m023_vacancy_store
from src.ingest import dedup, quality, repo
from src.ingest.base import Batch, NormalizedVacancy, SourceError, new_stats
from src.ingest import runner as runner_mod
from src.ingest.runner import IngestRunner

NOW = 1_792_213_200
DAY = 86_400


@pytest.fixture
async def conn(tmp_path):
    async with aiosqlite.connect(tmp_path / "ingest.sqlite3") as c:
        await apply_pragmas(c)
        await run_migrations(c)
        yield c


def vac(source="hh", sid="1", title="Python developer", employer="Synthetic LLC", region="1726",
        smin=5_000_000, smax=9_000_000, currency="UZS", published=NOW - 3600, desc="", **kw) -> NormalizedVacancy:
    return NormalizedVacancy(
        source=source, source_id=sid, title=title, employer=employer, region_soato=region,
        salary_min=smin, salary_max=smax, currency=currency, published_at=published,
        description_text=desc, url=f"https://example.test/{source}/{sid}", **kw,
    )


async def row(conn, uid):
    cur = await conn.execute("SELECT * FROM vacancies WHERE uid = ?", (uid,))
    return await cur.fetchone()


async def fts_hits(conn, term):
    cur = await conn.execute("SELECT rowid FROM vacancies_fts WHERE vacancies_fts MATCH ?", (repo.fts_query(term),))
    return [r[0] for r in await cur.fetchall()]


# ---------------------------------------------------------------- migration / FTS


async def test_migration_reapply_is_a_noop(conn):
    await repo.upsert_batch(conn, [vac()], NOW)
    assert await run_migrations(conn) == []
    await conn.execute("BEGIN")
    await m023_vacancy_store.apply(conn)  # re-applied by hand: IF NOT EXISTS everywhere
    await conn.commit()
    cur = await conn.execute("SELECT COUNT(*) FROM vacancies")
    assert (await cur.fetchone())[0] == 1
    cur = await conn.execute("SELECT id FROM schema_migrations WHERE id = 'm023_vacancy_store'")
    assert await cur.fetchone() is not None


async def test_fts_follows_insert_update_and_delete(conn):
    await repo.upsert_batch(conn, [vac(title="Python developer")], NOW)
    rid = (await row(conn, "hh_1"))["id"]
    assert await fts_hits(conn, "python") == [rid]
    await repo.apply_detail(conn, vac(title="Golang engineer", desc="Kubernetes va Go"), NOW)
    assert await fts_hits(conn, "python") == []
    assert await fts_hits(conn, "golang") == [rid]
    assert await fts_hits(conn, "kubernetes") == [rid]
    await repo.close(conn, ["hh_1"], "gone", NOW - 61 * DAY)
    assert await repo.purge_closed(conn, NOW - 60 * DAY) == 1
    assert await fts_hits(conn, "golang") == []


# ---------------------------------------------------------------- upserts


async def test_list_resighting_keeps_detail_fields(conn):
    await repo.upsert_batch(conn, [vac(desc="short snippet")], NOW - 100)
    detailed = vac(desc="Full description " * 40, skills=["Python"], contacts={"email": "hr@example.test"})
    await repo.apply_detail(conn, detailed, NOW - 50)
    await repo.upsert_batch(conn, [vac(desc="short snippet", smax=10_000_000)], NOW)
    r = await row(conn, "hh_1")
    assert r["description_text"].startswith("Full description")
    assert r["skills_json"] == '["Python"]' and "hr@example.test" in r["contacts_json"]
    assert r["salary_max"] == 10_000_000 and r["last_seen_at"] == NOW
    assert r["checked_at"] == NOW - 50


async def test_upsert_counts_new_rows_and_reopens_stale(conn):
    assert await repo.upsert_batch(conn, [vac(sid="1"), vac(sid="2", title="QA")], NOW) == 2
    assert await repo.upsert_batch(conn, [vac(sid="1")], NOW) == 0
    await repo.close(conn, ["hh_1"], "stale", NOW)
    assert (await row(conn, "hh_1"))["status"] == "closed"
    await repo.upsert_batch(conn, [vac(sid="1")], NOW + 10)
    r = await row(conn, "hh_1")
    assert r["status"] == "open" and r["closed_at"] is None and r["close_reason"] is None


async def test_source_archived_flag_closes(conn):
    await repo.upsert_batch(conn, [vac(sid="1", is_open=False)], NOW)
    r = await row(conn, "hh_1")
    assert r["status"] == "closed" and r["close_reason"] == "source_closed"


# ---------------------------------------------------------------- dedup


async def test_exact_duplicate_across_sources_prefers_hh(conn):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="900000000001")], NOW)
    await repo.upsert_batch(conn, [vac(source="hh", sid="77")], NOW)
    os_row, hh_row = await row(conn, "osonish_900000000001"), await row(conn, "hh_77")
    assert hh_row["dup_of"] is None and hh_row["dedup_group"] == "hh_77"
    assert os_row["dup_of"] == "hh_77" and os_row["dedup_group"] == "hh_77"
    page = await repo.search(conn)
    assert [i["uid"] for i in page["items"]] == ["hh_77"] and page["total"] == 1


async def test_cyrillic_and_latin_titles_share_a_key(conn):
    a = vac(source="hh", sid="1", title="Бухгалтер", employer='ООО "Синтетик"')
    b = vac(source="osonish", sid="2", title="Buxgalter", employer="Sintetik MCHJ")
    assert dedup.dedup_key(a) == dedup.dedup_key(b)


async def test_fuzzy_duplicate_same_employer_region(conn):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1", title="Senior Python developer", smax=5_000_000)],
                            NOW)
    await repo.upsert_batch(conn, [vac(source="hh", sid="2", title="Senior Python developers", smax=15_000_000)],
                            NOW)
    assert dedup.title_ratio("Senior Python developer", "Senior Python developers") >= dedup.FUZZY_RATIO
    assert (await row(conn, "osonish_1"))["dup_of"] == "hh_2"


@pytest.mark.parametrize(
    "other",
    [
        {"employer": "Another Company"},
        {"region": "1703"},
        {"published": NOW - 3600 - 15 * DAY},
        {"title": "Python team lead"},
    ],
)
async def test_fuzzy_negative_cases_stay_separate(conn, other):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1", title="Senior Python developer", smax=5_000_000)],
                            NOW)
    params = {"source": "hh", "sid": "2", "title": "Senior Python developers", "smax": 15_000_000, **other}
    await repo.upsert_batch(conn, [vac(**params)], NOW)
    assert (await row(conn, "osonish_1"))["dup_of"] is None
    assert (await row(conn, "hh_2"))["dup_of"] is None
    assert len((await repo.search(conn))["items"]) == 2


async def test_closing_the_canonical_promotes_a_duplicate(conn):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1"), vac(source="hh", sid="2")], NOW)
    assert (await row(conn, "osonish_1"))["dup_of"] == "hh_2"
    await repo.close(conn, ["hh_2"], "stale", NOW)
    assert (await row(conn, "osonish_1"))["dup_of"] is None
    assert [i["uid"] for i in (await repo.search(conn))["items"]] == ["osonish_1"]
    # hh reappears: it is canonical again.
    await repo.upsert_batch(conn, [vac(source="hh", sid="2")], NOW + 5)
    assert (await row(conn, "osonish_1"))["dup_of"] == "hh_2"
    assert (await row(conn, "hh_2"))["dup_of"] is None


# ---------------------------------------------------------------- quality


def test_quality_orders_complete_over_bare_and_spam():
    complete = vac(desc="x" * 500, published=NOW - 600)
    bare = vac(employer="", smin=None, smax=None, region=None, published=NOW - 10 * DAY)
    bare.url = ""
    spam = replace(complete, title="ЗАРАБОТОК БЕЗ ВЛОЖЕНИЙ!!! 💰💰")
    assert quality.score(complete, NOW) == 100
    assert quality.score(bare, NOW) == 10
    assert quality.score(spam, NOW) == 90
    assert quality.score(complete, NOW) > quality.score(spam, NOW) > quality.score(bare, NOW)
    assert quality.score(vac(published=NOW - 2 * DAY), NOW) < quality.score(vac(published=NOW - 60), NOW)


# ---------------------------------------------------------------- read API


async def test_search_fts_filters_and_cursor(conn):
    items = [vac(sid=str(i), title=f"Python dev {i}", employer=f"Emp {i}", published=NOW - i * 60) for i in range(1, 8)]
    items.append(vac(sid="50", title="Oshpaz", employer="Restoran", region="1703"))
    items.append(vac(sid="51", title="Python remote", employer="Abroad", currency="USD", smin=2000, smax=3000))
    await repo.upsert_batch(conn, items, NOW)

    first = await repo.search(conn, query="python", limit=3)
    assert first["total"] == 8 and len(first["items"]) == 3 and first["next_cursor"]
    seen = [i["uid"] for i in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = await repo.search(conn, query="python", limit=3, cursor=cursor)
        assert page["total"] is None
        seen += [i["uid"] for i in page["items"]]
        cursor = page["next_cursor"]
    assert len(seen) == 8 and len(set(seen)) == 8

    assert [i["uid"] for i in (await repo.search(conn, region_soato="1703"))["items"]] == ["hh_50"]
    rich = await repo.search(conn, min_salary=8_000_000)
    assert "hh_51" not in {i["uid"] for i in rich["items"]}  # USD never passes a UZS floor
    assert rich["total"] == 8
    low_floor = await repo.search(conn, min_salary=1_000)
    assert "hh_51" not in {i["uid"] for i in low_floor["items"]} and low_floor["total"] == 8
    assert (await repo.search(conn, source="osonish"))["items"] == []
    assert (await repo.search(conn, cursor="garbage!!"))["items"] == []


@pytest.mark.parametrize("q", ['python" OR "*', "NEAR(a b)", "title:python", "'; DROP TABLE vacancies; --", "***", ""])
async def test_search_query_syntax_is_neutralised(conn, q):
    await repo.upsert_batch(conn, [vac(title="Python developer")], NOW)
    result = await repo.search(conn, query=q)
    assert isinstance(result["items"], list)
    cur = await conn.execute("SELECT COUNT(*) FROM vacancies")
    assert (await cur.fetchone())[0] == 1


async def test_get_returns_decoded_row_in_any_status(conn):
    await repo.upsert_batch(conn, [vac(desc="Ish " * 300, skills=["Excel"])], NOW)
    await repo.close(conn, ["hh_1"], "gone", NOW)
    item = await repo.get(conn, "hh_1")
    assert item["status"] == "closed" and item["skills"] == ["Excel"]
    assert len(item["excerpt"]) <= repo.EXCERPT_LEN and "raw_json" not in item
    assert await repo.get(conn, "hh_404") is None


async def test_freshest_for_post_filters(conn):
    await conn.execute(
        "CREATE TABLE posted_vacancies (vacancy_uid TEXT NOT NULL, channel TEXT NOT NULL, posted_at INTEGER NOT NULL,"
        " PRIMARY KEY (vacancy_uid, channel))"
    )
    await conn.commit()
    await repo.upsert_batch(conn, [
        vac(sid="1", title="Fresh good", employer="A", desc="x" * 500, published=NOW - 600),
        vac(sid="2", title="Old", employer="B", published=NOW - 3 * DAY),
        vac(sid="3", title="Cheap", employer="C", smin=1_000_000, smax=1_500_000, published=NOW - 300),
        vac(sid="4", title="Posted", employer="D", published=NOW - 200),
        vac(sid="5", title="Weak", employer="", smin=None, smax=None, region=None, published=NOW - 100),
    ], NOW)
    await conn.execute("INSERT INTO posted_vacancies VALUES ('hh_4', '@chan', ?)", (NOW,))
    await conn.commit()

    out = await repo.freshest_for_post(conn, since=NOW - DAY, min_quality=50, min_salary=3_000_000, channel="@chan")
    assert [i["uid"] for i in out] == ["hh_1"]
    other_channel = await repo.freshest_for_post(conn, since=NOW - DAY, min_salary=3_000_000, channel="@other")
    assert "hh_4" in {i["uid"] for i in other_channel}
    no_exclude = await repo.freshest_for_post(conn, since=NOW - DAY, exclude_posted=False)
    assert [i["uid"] for i in no_exclude] == ["hh_5", "hh_4", "hh_3", "hh_1"]


async def test_freshest_for_post_without_posted_table(conn):
    await repo.upsert_batch(conn, [vac()], NOW)
    assert len(await repo.freshest_for_post(conn, since=0)) == 1


# ---------------------------------------------------------------- runner


class FakeAdapter:
    interval_seconds = 600
    recheck_per_run = 10
    stale_after_seconds = 7 * DAY

    def __init__(self, name, conn, pages=None, details=None, fail=None, detail_error=False, fail_ids=()):
        self.name = name
        self.conn = conn
        self.pages = pages or []
        self.details = details or {}
        self.fail = fail
        self.detail_error = detail_error
        self.fail_ids = set(fail_ids)
        self.stats = new_stats()
        self.cursors_seen: list = []
        self.detail_calls: list[str] = []

    def enabled(self):
        return True

    async def iter_new(self, cursor, now):
        self.cursors_seen.append(cursor)
        for batch in self.pages:
            assert not self.conn.in_transaction  # never a transaction across "network" I/O
            yield batch
        if self.fail:
            raise self.fail

    async def fetch_detail(self, source_id):
        assert not self.conn.in_transaction
        self.detail_calls.append(source_id)
        if self.detail_error or source_id in self.fail_ids:
            raise SourceError("server_error", 503)
        return self.details.get(source_id)


async def test_runner_stores_rechecks_closes_and_saves_cursor(conn):
    clock = {"t": NOW}
    keep = vac(source="hh", sid="1", title="Kept")
    gone = vac(source="hh", sid="2", title="Gone")
    archived = vac(source="hh", sid="3", title="Archived")
    adapter = FakeAdapter("hh", conn, pages=[Batch([keep, gone], None), Batch([archived], "cur-1")],
                          details={"1": replace(keep, description_text="Full text"),
                                   "3": replace(archived, is_open=False)})
    runner = IngestRunner([adapter], clock=lambda: clock["t"])
    result = await runner.run_once(conn)
    assert result["hh"]["new"] == 3 and result["hh"]["checked"] == 2 and result["hh"]["closed"] == 2
    assert (await row(conn, "hh_1"))["description_text"] == "Full text"
    assert (await row(conn, "hh_2"))["close_reason"] == "gone"
    assert (await row(conn, "hh_3"))["status"] == "closed"
    state = await repo.get_cursor(conn, "hh")
    assert state["cursor"] == "cur-1" and state["last_ok_at"] == NOW and state["last_error"] is None

    # Not due yet: nothing runs.
    clock["t"] = NOW + 60
    assert await runner.run_once(conn) == {}
    # Due: the stored cursor is handed back.
    clock["t"] = NOW + 601
    adapter.pages = []
    await runner.run_once(conn)
    assert adapter.cursors_seen == [None, "cur-1"]


async def test_runner_stale_close_and_purge(conn):
    clock = {"t": NOW}
    await repo.upsert_batch(conn, [vac(sid="old")], NOW - 8 * DAY)
    await repo.upsert_batch(conn, [vac(sid="fresh", title="Fresh one")], NOW - DAY)
    await repo.upsert_batch(conn, [vac(sid="ancient", title="Ancient")], NOW - 100 * DAY)
    await repo.close(conn, ["hh_ancient"], "gone", NOW - 61 * DAY)
    adapter = FakeAdapter("hh", conn)
    adapter.recheck_per_run = 0
    result = await IngestRunner([adapter], clock=lambda: clock["t"]).run_once(conn)
    assert result["hh"]["stale"] == 1
    assert (await row(conn, "hh_old"))["close_reason"] == "stale"
    assert (await row(conn, "hh_fresh"))["status"] == "open"
    assert await row(conn, "hh_ancient") is None


async def test_runner_survives_one_adapter_failing(conn):
    broken = FakeAdapter("hh", conn, pages=[Batch([vac(sid="9")], "half")], fail=SourceError("forbidden", 403))
    healthy = FakeAdapter("osonish", conn, pages=[Batch([vac(source="osonish", sid="1", title="Oshpaz")], "c")])
    result = await IngestRunner([broken, healthy], clock=lambda: NOW).run_once(conn)
    assert "forbidden" in result["hh"]["error"]
    assert result["osonish"]["new"] == 1
    hh_state = await repo.get_cursor(conn, "hh")
    assert "forbidden" in hh_state["last_error"] and hh_state["last_ok_at"] is None
    assert hh_state["cursor"] == "half"  # progress made before the failure is kept
    assert await row(conn, "hh_9") is not None
    assert (await repo.get_cursor(conn, "osonish"))["last_error"] is None


async def test_runner_stops_rechecks_on_outage_without_closing(conn):
    await repo.upsert_batch(conn, [vac(sid=str(i), title=f"Job {i}", employer=f"E{i}") for i in range(1, 6)],
                            NOW - 30 * DAY)
    adapter = FakeAdapter("hh", conn, detail_error=True)
    result = await IngestRunner([adapter], clock=lambda: NOW).run_once(conn)
    # Stops after MAX_CONSECUTIVE_DETAIL_ERRORS failures in a row (an outage), not at the first one.
    assert len(adapter.detail_calls) == runner_mod.MAX_CONSECUTIVE_DETAIL_ERRORS == 3
    assert result["hh"]["closed"] == 0 and result["hh"]["stale"] == 0 and result["hh"]["stale_skipped"] == 1
    cur = await conn.execute("SELECT COUNT(*) FROM vacancies WHERE status = 'open'")
    assert (await cur.fetchone())[0] == 5  # all unseen for 30 days, yet nothing stale-closed during the outage
    assert "recheck" in (await repo.get_cursor(conn, "hh"))["last_error"]


async def test_runner_skips_disabled_adapters(conn):
    adapter = FakeAdapter("hh", conn, pages=[Batch([vac()], "c")])
    adapter.enabled = lambda: False
    assert await IngestRunner([adapter], clock=lambda: NOW).run_once(conn) == {}
    assert await repo.get_cursor(conn, "hh") is None


async def test_recheck_picks_never_checked_first(conn):
    await repo.upsert_batch(conn, [vac(sid="1"), vac(sid="2", title="B"), vac(sid="3", title="C")], NOW)
    await repo.apply_detail(conn, vac(sid="1"), NOW)
    await repo.apply_detail(conn, vac(sid="2", title="B"), NOW - 100)
    assert await repo.pick_for_recheck(conn, "hh", 3) == ["3", "2", "1"]


async def test_runner_end_to_end_with_hh_adapter_and_stub_transport(conn):
    """Real HHAdapter + HHClient over a stub transport: list -> store -> detail re-check -> FTS search."""
    from src.ingest.base import RateLimiter
    from src.ingest.sources.hh import HHAdapter, HHClient, HttpResponse

    item = {
        "id": "4242", "name": "Data analyst", "published_at": "2026-10-17T09:00:00+0500",
        "salary": {"from": 8_000_000, "to": None, "currency": "UZS", "gross": True},
        "area": {"id": "2760", "name": "Самарканд"}, "employer": {"name": "Synthetic Bank"},
        "alternate_url": "https://hh.uz/vacancy/4242", "snippet": {"requirement": "SQL"},
    }

    async def transport(url, params, headers):
        if url.endswith("/vacancies"):
            return HttpResponse(200, {"items": [item], "found": 1, "pages": 1}, {})
        if url.endswith("/vacancies/4242"):
            return HttpResponse(200, {**item, "description": "<p>Power BI va <b>SQL</b></p>"}, {})
        return HttpResponse(404, None, {})

    async def no_sleep(_):
        return None

    client = HHClient("synthetic", transport=transport, rate=RateLimiter(0), sleep=no_sleep)
    adapter = HHAdapter(token="synthetic", client=client)
    result = await IngestRunner([adapter], clock=lambda: NOW).run_once(conn)
    assert result["hh"]["new"] == 1 and result["hh"]["checked"] == 1 and result["hh"]["requests"] == 2
    found = await repo.search(conn, query="power bi", region_soato="1718")
    assert [i["uid"] for i in found["items"]] == ["hh_4242"]
    assert found["items"][0]["description_text"] == "Power BI va SQL"
    assert found["items"][0]["salary_gross"] is True
    assert (await repo.get_cursor(conn, "hh"))["cursor"] == str(NOW)


# ---------------------------------------------------------------- review fixes (m025)


async def _plans_of_traced(conn, action):
    """Run ``action`` with SQL tracing on; return {sql: plan} for every SELECT on ``vacancies`` it ran."""
    seen: list[str] = []
    await conn.set_trace_callback(seen.append)
    try:
        await action()
    finally:
        await conn.set_trace_callback(None)
    plans = {}
    for sql in seen:
        if sql.lstrip().upper().startswith("SELECT") and "FROM vacancies" in sql and sql not in plans:
            cur = await conn.execute("EXPLAIN QUERY PLAN " + sql)
            plans[sql] = " | ".join(str(r[-1]) for r in await cur.fetchall())
    return plans


async def test_dedup_lookups_use_the_m025_indexes(conn):
    await repo.upsert_batch(conn, [vac(sid=str(i), title=f"Job {i}", employer=f"E{i % 3}") for i in range(30)], NOW)
    plans = await _plans_of_traced(
        conn, lambda: repo.upsert_batch(conn, [vac(sid="new", title="Senior Python developer", employer="E1")], NOW)
    )
    exact = [p for s, p in plans.items() if "dedup_key = " in s]
    fuzzy = [p for s, p in plans.items() if "employer_key = " in s]
    assert exact and all("idx_vacancies_dedup " in p for p in exact), exact
    assert fuzzy and all("idx_vacancies_employer_region_pub" in p for p in fuzzy), fuzzy
    assert not any("status_pub" in p or p.startswith("SCAN") for p in plans.values()), plans


async def _seed_bulk(conn, n, *, employers=500, now=NOW):
    """``n`` open rows inserted directly (fast), spread over employers and 10 days, no sqlite_stat1."""
    rows = []
    for i in range(n):
        v = vac(source="osonish", sid=str(900000000000 + i), title=f"Sotuvchi {i % 40}", employer=f"Firma {i % employers}",
                published=now - (i % 10) * DAY, smax=(1 + i % 20) * 500_000)
        rows.append(repo._row_values(v, now))
    await conn.execute("BEGIN")
    await conn.executemany(
        f"INSERT INTO vacancies ({repo._COLUMNS}, dedup_group) VALUES ({repo._PLACEHOLDERS}, NULL)", rows
    )
    await conn.execute("UPDATE vacancies SET dedup_group = uid")
    await conn.commit()


async def test_upsert_batch_lock_stays_short_at_scale(conn):
    import time as _time

    await _seed_bulk(conn, 20_000)
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE name = 'sqlite_stat1'")
    assert await cur.fetchone() is None  # the planner works without statistics, like production
    batch = [vac(source="hh", sid=str(i), title=f"Sotuvchi {i % 40}", employer=f"Firma {i % 500}",
                 published=NOW - DAY) for i in range(50)]
    started = _time.perf_counter()
    await repo.upsert_batch(conn, batch, NOW)
    elapsed = _time.perf_counter() - started
    assert elapsed < 0.2, f"50-row batch took {elapsed:.3f}s at 20k rows"


async def test_failed_recheck_is_backed_off_and_the_queue_moves_on(conn):
    """probe3: a permanently failing detail must not starve the queue nor let healthy rows go stale."""
    await repo.upsert_batch(
        conn, [vac(sid=str(i), title=f"Job {i}", employer=f"E{i}", published=NOW - (1 if i == 1 else 2) * DAY)
               for i in range(1, 6)], NOW,
    )
    clock = {"t": NOW}
    adapter = FakeAdapter("hh", conn, details={str(i): vac(sid=str(i), title=f"Job {i}", employer=f"E{i}")
                                               for i in range(2, 6)}, fail_ids={"1"})
    adapter.stale_after_seconds = 21 * DAY
    runner = IngestRunner([adapter], clock=lambda: clock["t"])
    await runner.run_once(conn)
    assert sorted(adapter.detail_calls) == ["1", "2", "3", "4", "5"]  # the failure did not stop the run
    r1 = await row(conn, "hh_1")
    assert r1["detail_failures"] == 1 and r1["recheck_after"] == NOW + repo.DETAIL_BACKOFF_BASE
    assert r1["status"] == "open"
    # Backed off: the next run (10 min later) leaves hh_1 alone.
    adapter.detail_calls.clear()
    clock["t"] = NOW + 601
    await runner.run_once(conn)
    assert "1" not in adapter.detail_calls
    # 22 days on, never re-sighted in a list: healthy rows are confirmed by detail, the failing one is kept.
    clock["t"] = NOW + 22 * DAY
    await runner.run_once(conn, force=True)
    cur = await conn.execute("SELECT uid, status FROM vacancies ORDER BY uid")
    assert {r[0]: r[1] for r in await cur.fetchall()} == {f"hh_{i}": "open" for i in range(1, 6)}
    assert (await row(conn, "hh_1"))["detail_failures"] == 2
    # A success resets the counter.
    adapter.fail_ids = set()
    adapter.details["1"] = vac(sid="1", title="Job 1", employer="E1")
    clock["t"] = NOW + 30 * DAY
    await runner.run_once(conn, force=True)
    r1 = await row(conn, "hh_1")
    assert r1["detail_failures"] == 0 and r1["recheck_after"] is None


async def test_close_stale_skips_rows_whose_recheck_failed_until_give_up(conn):
    await repo.upsert_batch(conn, [vac(sid="1"), vac(sid="2", title="Other", employer="X")], NOW - 30 * DAY)
    await repo.record_detail_failure(conn, "hh_1", NOW)
    assert await repo.close_stale(conn, "hh", NOW - 21 * DAY, NOW) == 1  # only hh_2
    assert (await row(conn, "hh_1"))["status"] == "open"
    await conn.execute("UPDATE vacancies SET detail_failures = ? WHERE uid = 'hh_1'", (repo.DETAIL_FAILURE_GIVE_UP,))
    await conn.commit()
    assert await repo.close_stale(conn, "hh", NOW - 21 * DAY, NOW) == 1


async def test_recheck_backoff_grows_and_is_capped(conn):
    await repo.upsert_batch(conn, [vac()], NOW)
    waits = []
    for _ in range(8):
        await repo.record_detail_failure(conn, "hh_1", NOW)
        waits.append((await row(conn, "hh_1"))["recheck_after"] - NOW)
    assert waits[:3] == [3600, 7200, 14400] and max(waits) == repo.DETAIL_BACKOFF_MAX
    assert await repo.pick_for_recheck(conn, "hh", 5, now=NOW) == []
    assert await repo.pick_for_recheck(conn, "hh", 5, now=NOW + repo.DETAIL_BACKOFF_MAX) == ["1"]


async def test_unparseable_detail_only_rotates_the_row(conn):
    from src.ingest.base import RateLimiter
    from src.ingest.sources.osonish import OsonishAdapter

    await repo.upsert_batch(conn, [vac(source="osonish", sid="900000000001", title="Oshpaz")], NOW)

    async def no_pages(page, per_page):
        return [], 1

    async def detail(vacancy_id):
        return {"id": vacancy_id, "title": "Oshpaz", "created_at": "17.10.2026 10:00"}  # unparseable date

    adapter = OsonishAdapter(no_pages, detail, rate=RateLimiter(0))
    result = await IngestRunner([adapter], clock=lambda: NOW + 60).run_once(conn, force=True)
    r = await row(conn, "osonish_900000000001")
    assert r["status"] == "open" and r["close_reason"] is None
    assert r["checked_at"] == NOW + 60 and r["detail_failures"] == 0
    assert result["osonish"]["detail_unusable"] == 1 and result["osonish"]["closed"] == 0


@pytest.mark.parametrize(
    "first, second",
    [
        # No employer: identical title/region/salary is not enough.
        ({"employer": ""}, {"employer": ""}),
        # A short distinguishing token.
        ({"title": "Haydovchi B"}, {"title": "Haydovchi C"}),
        ({"title": "Kassir 1-smena"}, {"title": "Kassir 2-smena"}),
        # Two different known districts.
        ({"district_soato": "1726262"}, {"district_soato": "1726269"}),
        # Same exact key, but more than 14 days apart.
        ({"published": NOW - 20 * DAY}, {"published": NOW}),
    ],
)
async def test_dedup_does_not_merge_unrelated_jobs(conn, first, second):
    base = {"title": "Sotuvchi", "employer": "Korzinka MCHJ", "smax": 3_000_000}
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1", **{**base, **first})], NOW)
    await repo.upsert_batch(conn, [vac(source="hh", sid="2", **{**base, **second})], NOW)
    assert (await row(conn, "osonish_1"))["dup_of"] is None
    assert (await row(conn, "hh_2"))["dup_of"] is None


async def test_dedup_still_merges_across_sources_when_one_district_is_unknown(conn):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1", district_soato="1726262")], NOW)
    await repo.upsert_batch(conn, [vac(source="hh", sid="2")], NOW)
    assert (await row(conn, "osonish_1"))["dup_of"] == "hh_2"


async def test_a_duplicate_that_diverges_is_split_out_again(conn):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1", title="Sotuvchi", employer="Korzinka"),
                                   vac(source="osonish", sid="2", title="Sotuvchi", employer="Korzinka")], NOW)
    assert len((await repo.search(conn))["items"]) == 1
    await repo.upsert_batch(conn, [vac(source="osonish", sid="2", title="Bosh buxgalter", employer="Korzinka",
                                       smax=9_000_000)], NOW + 10)
    assert sorted(i["uid"] for i in (await repo.search(conn))["items"]) == ["osonish_1", "osonish_2"]
    assert (await row(conn, "osonish_2"))["dedup_group"] == "osonish_2"


async def test_the_canonical_diverging_unhides_its_duplicates(conn):
    await repo.upsert_batch(conn, [vac(source="osonish", sid="1"), vac(source="osonish", sid="3"),
                                   vac(source="hh", sid="2")], NOW)
    assert (await row(conn, "osonish_1"))["dup_of"] == "hh_2"
    await repo.apply_detail(conn, vac(source="hh", sid="2", title="Golang engineer", smax=20_000_000), NOW + 10)
    hh, os1, os3 = await row(conn, "hh_2"), await row(conn, "osonish_1"), await row(conn, "osonish_3")
    assert hh["dup_of"] is None and hh["dedup_group"] == "hh_2"
    # The remaining two still match each other: one group of their own, one of them visible.
    assert os1["dedup_group"] == os3["dedup_group"] != "hh_2"
    assert sorted(i["uid"] for i in (await repo.search(conn))["items"]) == ["hh_2", os1["dedup_group"]]


def test_raw_json_drops_descriptions_and_fits_the_cap():
    raw = {"id": 1, "hr": {"name": "A"}, "info": "<p>" + "x" * 3000 + "</p>", "requirements": "y" * 3000,
           "title": "T", "company": {"about": "z" * 5000}}
    text = repo._raw_json(raw)
    assert len(text) <= repo._RAW_MAX
    import json as _json

    slim = _json.loads(text)
    assert slim == {"id": 1, "hr": {"name": "A"}, "title": "T"}  # largest non-kept value went first
    assert repo._raw_json({"id": 1, "hr": {"x": "q" * 9000}}) == "{}"


async def test_list_resighting_does_not_reopen_a_row_detail_found_gone(conn):
    await repo.upsert_batch(conn, [vac()], NOW)
    await repo.close(conn, ["hh_1"], "gone", NOW)
    await repo.upsert_batch(conn, [vac()], NOW + 10)
    r = await row(conn, "hh_1")
    assert r["status"] == "closed" and r["close_reason"] == "gone" and r["last_seen_at"] == NOW + 10
    await repo.apply_detail(conn, vac(), NOW + 20)  # the detail endpoint is the authority
    assert (await row(conn, "hh_1"))["status"] == "open"


async def _fts_snapshot(conn):
    cur = await conn.execute("SELECT group_concat(id || ':' || hex(block)) FROM vacancies_fts_data")
    return (await cur.fetchone())[0]


async def test_fts_update_trigger_skips_unchanged_rows(conn):
    await repo.upsert_batch(conn, [vac()], NOW)
    before = await _fts_snapshot(conn)
    await repo.upsert_batch(conn, [vac(smax=12_000_000)], NOW + 10)  # title / employer / description unchanged
    assert (await row(conn, "hh_1"))["salary_max"] == 12_000_000
    assert await _fts_snapshot(conn) == before  # no FTS delete + insert
    await repo.upsert_batch(conn, [vac(title="Go developer")], NOW + 20)
    assert await _fts_snapshot(conn) != before
    assert await fts_hits(conn, "go") == [(await row(conn, "hh_1"))["id"]]


@pytest.mark.parametrize("query", ["o'qituvchi", "oʻqituvchi", "o‘qituvchi", "o’qituvchi", "oqituvchi", "O`QITUVCHI"])
async def test_search_ignores_apostrophe_variants(conn, query):
    await repo.upsert_batch(conn, [vac(sid="1", title="Boshlang'ich sinf oʻqituvchisi", employer="Maktab")], NOW)
    await repo.upsert_batch(conn, [vac(sid="2", title="Ingliz tili o'qituvchi", employer="Litsey")], NOW)
    found = await repo.search(conn, query=query)
    assert sorted(i["uid"] for i in found["items"]) == ["hh_1", "hh_2"]


async def test_fts_index_stays_consistent_and_m025_reapply_rebuilds(conn):
    from src.db.migrations import m025_ingest_hardening

    await repo.upsert_batch(conn, [vac(sid="1", title="Oʻqituvchi"), vac(sid="2", title="Kassir", employer="K")], NOW)
    await repo.apply_detail(conn, vac(sid="1", title="Katta oʻqituvchi", desc="Ingliz tili’ni"), NOW + 1)
    await repo.close(conn, ["hh_2"], "gone", NOW - 61 * DAY)
    await repo.purge_closed(conn, NOW - 60 * DAY)
    await conn.execute("INSERT INTO vacancies_fts (vacancies_fts) VALUES ('integrity-check')")
    await conn.commit()
    await conn.execute("BEGIN")
    await m025_ingest_hardening.apply(conn)
    await conn.commit()
    await conn.execute("INSERT INTO vacancies_fts (vacancies_fts) VALUES ('integrity-check')")
    assert [i["uid"] for i in (await repo.search(conn, query="o'qituvchi"))["items"]] == ["hh_1"]
    assert (await repo.search(conn, query="tilini"))["total"] == 1


# ---------------------------------------------------------------- openings (collapsed duplicates)


async def _same_position(conn, n, *, source="osonish", employer="Shifoxona"):
    await repo.upsert_batch(
        conn, [vac(source=source, sid=str(900000000100 + i), title="Sanitarka", employer=employer) for i in range(n)], NOW
    )


async def test_openings_counts_open_rows_of_the_canonical_group(conn):
    await _same_position(conn, 4)
    await repo.upsert_batch(conn, [vac(sid="solo", title="Kassir", employer="Boshqa")], NOW)
    page = await repo.search(conn)
    by_title = {i["title"]: i for i in page["items"]}
    assert len(page["items"]) == 2  # four duplicates collapsed into one card
    assert by_title["Sanitarka"]["openings"] == 4
    assert by_title["Kassir"]["openings"] == 1  # a row in its own (single-member) group
    canonical = by_title["Sanitarka"]["uid"]
    assert (await repo.get(conn, canonical))["openings"] == 4
    # A collapsed duplicate reports its group's count too.
    dup = next(u for u in (f"osonish_{900000000100 + i}" for i in range(4)) if u != canonical)
    assert (await repo.get(conn, dup))["openings"] == 4


async def test_openings_ignores_closed_members_and_ungrouped_rows(conn):
    await _same_position(conn, 3)
    page = await repo.search(conn)
    canonical = page["items"][0]["uid"]
    closed = next(f"osonish_{900000000100 + i}" for i in range(3) if f"osonish_{900000000100 + i}" != canonical)
    await repo.close(conn, [closed], "gone", NOW)
    assert (await repo.search(conn))["items"][0]["openings"] == 2
    # No group at all (legacy row): exactly one opening.
    await conn.execute("UPDATE vacancies SET dedup_group = NULL, dup_of = NULL WHERE uid = ?", (canonical,))
    await conn.commit()
    assert (await repo.get(conn, canonical))["openings"] == 1


async def test_openings_is_one_indexed_query_for_a_page(conn):
    for k in range(5):
        await _same_position(conn, 3, employer=f"Org {k}")
    plans = await _plans_of_traced(conn, lambda: repo.search(conn, limit=5))
    grouped = [(s, p) for s, p in plans.items() if "GROUP BY dedup_group" in s]
    assert len(grouped) == 1, list(plans)
    assert "idx_vacancies_dedup_group" in grouped[0][1], grouped[0][1]
    assert all(i["openings"] == 3 for i in (await repo.search(conn, limit=5))["items"])
