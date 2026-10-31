"""Vacancy store hardening after the ingestion review.

1. Dedup lookups run inside ``upsert_batch``'s write transaction, so they must
   be index lookups: ``(dedup_key, status, published_at)`` for the exact key
   and ``(employer_key, region_soato, published_at)`` for the fuzzy pass. They
   replace the narrower m023 indexes, which are their prefixes. No ANALYZE:
   the queries in ``src/ingest/dedup.py`` pick these indexes without
   ``sqlite_stat1``, and stats written once would only go stale.
2. ``detail_failures`` / ``recheck_after``: a detail re-check that fails is
   counted and backed off instead of blocking the re-check queue, and a row
   whose last re-check failed is not stale-closed (``src/ingest/runner.py``).
3. Full-text search ignores apostrophe variants (``o'qituvchi`` = ``oʻqituvchi``
   = ``oqituvchi``): the FTS table now reads a view that strips them, the
   triggers index the same stripped text, and the update trigger only fires
   when an indexed column really changed.
"""

from src.db.migrate import add_column_if_missing

ID = "m025_ingest_hardening"

#: Characters removed from indexed text and from queries (``src/ingest/repo.py:fts_query``).
APOSTROPHES = ("ʻ", "ʼ", "'", "`", "‘", "’")


def strip_apostrophes_sql(expr: str) -> str:
    out = expr
    for ch in APOSTROPHES:
        out = f"replace({out}, '{ch.replace(chr(39), chr(39) * 2)}', '')"
    return out


def _cols(prefix: str) -> str:
    return ", ".join(strip_apostrophes_sql(f"{prefix}.{c}") for c in ("title", "employer", "description_text"))


async def apply(conn) -> None:
    for ddl in (
        "DROP INDEX IF EXISTS idx_vacancies_dedup_key",
        "DROP INDEX IF EXISTS idx_vacancies_employer_key",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_dedup ON vacancies(dedup_key, status, published_at)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_employer_region_pub "
        "ON vacancies(employer_key, region_soato, published_at)",
    ):
        await conn.execute(ddl)

    await add_column_if_missing(conn, "vacancies", "detail_failures", "INTEGER NOT NULL DEFAULT 0")
    await add_column_if_missing(conn, "vacancies", "recheck_after", "INTEGER")

    for ddl in (
        "DROP TRIGGER IF EXISTS vacancies_fts_ai",
        "DROP TRIGGER IF EXISTS vacancies_fts_ad",
        "DROP TRIGGER IF EXISTS vacancies_fts_au",
        "DROP TABLE IF EXISTS vacancies_fts",
        "DROP VIEW IF EXISTS vacancies_fts_src",
    ):
        await conn.execute(ddl)
    title, employer, description = (strip_apostrophes_sql(c) for c in ("title", "employer", "description_text"))
    await conn.execute(
        f"""
        CREATE VIEW vacancies_fts_src AS
        SELECT id, {title} AS title, {employer} AS employer, {description} AS description_text FROM vacancies
        """
    )
    await conn.execute(
        """
        CREATE VIRTUAL TABLE vacancies_fts USING fts5(
            title, employer, description_text,
            content='vacancies_fts_src', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    await conn.execute(
        f"""
        CREATE TRIGGER vacancies_fts_ai AFTER INSERT ON vacancies BEGIN
            INSERT INTO vacancies_fts (rowid, title, employer, description_text)
            VALUES (new.id, {_cols('new')});
        END
        """
    )
    await conn.execute(
        f"""
        CREATE TRIGGER vacancies_fts_ad AFTER DELETE ON vacancies BEGIN
            INSERT INTO vacancies_fts (vacancies_fts, rowid, title, employer, description_text)
            VALUES ('delete', old.id, {_cols('old')});
        END
        """
    )
    await conn.execute(
        f"""
        CREATE TRIGGER vacancies_fts_au AFTER UPDATE OF title, employer, description_text ON vacancies
        WHEN old.title IS NOT new.title OR old.employer IS NOT new.employer
             OR old.description_text IS NOT new.description_text
        BEGIN
            INSERT INTO vacancies_fts (vacancies_fts, rowid, title, employer, description_text)
            VALUES ('delete', old.id, {_cols('old')});
            INSERT INTO vacancies_fts (rowid, title, employer, description_text)
            VALUES (new.id, {_cols('new')});
        END
        """
    )
    await conn.execute("INSERT INTO vacancies_fts (vacancies_fts) VALUES ('rebuild')")
