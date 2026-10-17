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
    await repo.close(conn, ["hh_2"], "gone", NOW)
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

    def __init__(self, name, conn, pages=None, details=None, fail=None, detail_error=False):
        self.name = name
        self.conn = conn
        self.pages = pages or []
        self.details = details or {}
        self.fail = fail
        self.detail_error = detail_error
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
        if self.detail_error:
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
    await repo.upsert_batch(conn, [vac(sid="1"), vac(sid="2", title="Other")], NOW)
    adapter = FakeAdapter("hh", conn, detail_error=True)
    result = await IngestRunner([adapter], clock=lambda: NOW).run_once(conn)
    assert len(adapter.detail_calls) == 1  # stops at the first outage
    assert result["hh"]["closed"] == 0
    assert (await row(conn, "hh_1"))["status"] == "open"
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
