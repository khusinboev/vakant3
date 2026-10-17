"""Multi-source vacancy store filled by the ingestion loop (``src/ingest/``).

``vacancies`` holds one row per source vacancy, ``uid = "<source>_<source_id>"``
(``osonish_123`` keeps the uid the rest of the product already uses). The
table has an explicit ``id INTEGER PRIMARY KEY`` next to the unique ``uid``:
the FTS5 index is an external-content table keyed by rowid, and SQLite may
renumber the implicit rowid of a table without an INTEGER PRIMARY KEY on
VACUUM, which would silently desynchronise the index.

``vacancies_fts`` indexes title / employer / description_text and is kept in
sync by triggers. ``ingest_cursor`` stores each source's incremental cursor
and the last run's counters.
"""

ID = "m023_vacancy_store"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancies (
            id               INTEGER PRIMARY KEY,
            uid              TEXT NOT NULL UNIQUE,
            source           TEXT NOT NULL,
            source_id        TEXT NOT NULL,
            title            TEXT NOT NULL DEFAULT '',
            employer         TEXT NOT NULL DEFAULT '',
            employer_key     TEXT NOT NULL DEFAULT '',
            salary_min       INTEGER,
            salary_max       INTEGER,
            currency         TEXT,
            salary_gross     INTEGER,
            region_soato     TEXT,
            district_soato   TEXT,
            region_name      TEXT NOT NULL DEFAULT '',
            category         TEXT NOT NULL DEFAULT '',
            experience       TEXT NOT NULL DEFAULT '',
            employment       TEXT NOT NULL DEFAULT '',
            schedule         TEXT NOT NULL DEFAULT '',
            description_text TEXT NOT NULL DEFAULT '',
            skills_json      TEXT NOT NULL DEFAULT '[]',
            contacts_json    TEXT NOT NULL DEFAULT '{}',
            url              TEXT NOT NULL DEFAULT '',
            published_at     INTEGER NOT NULL,
            fetched_at       INTEGER NOT NULL,
            last_seen_at     INTEGER NOT NULL,
            checked_at       INTEGER,
            closed_at        INTEGER,
            close_reason     TEXT,
            status           TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
            quality_score    INTEGER NOT NULL DEFAULT 0,
            dedup_key        TEXT NOT NULL DEFAULT '',
            dedup_group      TEXT,
            dup_of           TEXT,
            raw_json         TEXT NOT NULL DEFAULT '{}',
            UNIQUE (source, source_id)
        )
        """
    )
    for ddl in (
        "CREATE INDEX IF NOT EXISTS idx_vacancies_status_pub ON vacancies(status, published_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_region_pub ON vacancies(region_soato, published_at)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_source_seen ON vacancies(source, last_seen_at)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_dedup_key ON vacancies(dedup_key)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_dedup_group ON vacancies(dedup_group)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_employer_key ON vacancies(employer_key, region_soato)",
        "CREATE INDEX IF NOT EXISTS idx_vacancies_closed_at ON vacancies(closed_at) WHERE closed_at IS NOT NULL",
    ):
        await conn.execute(ddl)

    await conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS vacancies_fts USING fts5(
            title, employer, description_text,
            content='vacancies', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    await conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS vacancies_fts_ai AFTER INSERT ON vacancies BEGIN
            INSERT INTO vacancies_fts (rowid, title, employer, description_text)
            VALUES (new.id, new.title, new.employer, new.description_text);
        END
        """
    )
    await conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS vacancies_fts_ad AFTER DELETE ON vacancies BEGIN
            INSERT INTO vacancies_fts (vacancies_fts, rowid, title, employer, description_text)
            VALUES ('delete', old.id, old.title, old.employer, old.description_text);
        END
        """
    )
    await conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS vacancies_fts_au
        AFTER UPDATE OF title, employer, description_text ON vacancies BEGIN
            INSERT INTO vacancies_fts (vacancies_fts, rowid, title, employer, description_text)
            VALUES ('delete', old.id, old.title, old.employer, old.description_text);
            INSERT INTO vacancies_fts (rowid, title, employer, description_text)
            VALUES (new.id, new.title, new.employer, new.description_text);
        END
        """
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_cursor (
            source      TEXT PRIMARY KEY,
            cursor      TEXT,
            last_run_at INTEGER,
            last_ok_at  INTEGER,
            last_error  TEXT,
            stats_json  TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
