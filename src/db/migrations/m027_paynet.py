"""Paynet top-ups: ``payment_orders`` / ``payment_events`` accept provider ``paynet``.

m020 created both tables with ``provider IN ('click')`` (and ``payment_orders``
with ``click_method IN ('page','card','phone','app')``). SQLite cannot alter a
CHECK constraint, so each table is rebuilt once, the way m020 rebuilds
``wallet_transactions``: new table, copy every row with its ``seq``/``id``,
drop, rename, recreate the indexes, and keep the AUTOINCREMENT high-water mark
(an id that ever existed is never handed out again).

A Paynet top-up is a normal ``payment_orders`` row (provider ``paynet``,
``provider_txn`` = Paynet's ``transactionId``, state ``paid`` from the start,
``click_method`` = ``paynet`` so the admin lists show where it came from).
The existing unique index ``(provider, provider_txn)`` is the idempotency
guard. Our ``providerTrnId`` is ``1_000_000_000 + seq``: ``seq`` is unique and
never reused, and the offset keeps it clear of SlaydX's small integers (the two
statements are merged on Paynet's side).

New index ``idx_payment_orders_paynet_perform`` serves ``GetStatement``.
"""

ID = "m027_paynet"


async def _table_sql(conn, name: str) -> str | None:
    cursor = await conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    )
    row = await cursor.fetchone()
    return None if row is None else str(row[0] or "")


async def _high_water(conn, name: str):
    cursor = await conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (name,))
    row = await cursor.fetchone()
    return None if row is None or row[0] is None else int(row[0])


async def _restore_high_water(conn, name: str, seq: int | None) -> None:
    if seq is None:
        return
    # The copy already moved the counter to MAX(copied id); only ever raise it.
    cursor = await conn.execute("SELECT 1 FROM sqlite_sequence WHERE name = ?", (name,))
    if await cursor.fetchone():
        await conn.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?", (seq, name))
    else:
        await conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (name, seq))


_ORDERS_DDL = """
    CREATE TABLE {name} (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        provider TEXT NOT NULL DEFAULT 'click' CHECK (provider IN ('click', 'paynet')),
        purpose TEXT NOT NULL DEFAULT 'topup' CHECK (purpose IN ('topup')),
        amount_soum INTEGER NOT NULL CHECK (amount_soum > 0),
        state TEXT NOT NULL DEFAULT 'created'
            CHECK (state IN ('created', 'pending', 'paid', 'cancelled')),
        provider_txn TEXT,
        prepare_id INTEGER UNIQUE,
        create_time INTEGER NOT NULL DEFAULT 0,
        perform_time INTEGER NOT NULL DEFAULT 0,
        cancel_time INTEGER NOT NULL DEFAULT 0,
        cancel_reason INTEGER,
        click_method TEXT CHECK (click_method IN ('page', 'card', 'phone', 'app', 'paynet')),
        click_invoice_id INTEGER,
        click_card_token TEXT,
        click_payment_id INTEGER,
        bonus_percent INTEGER NOT NULL DEFAULT 0,
        bonus_amount INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
"""

_ORDER_COLUMNS = (
    "seq, id, user_id, provider, purpose, amount_soum, state, provider_txn, prepare_id, "
    "create_time, perform_time, cancel_time, cancel_reason, click_method, click_invoice_id, "
    "click_card_token, click_payment_id, bonus_percent, bonus_amount, created_at, updated_at"
)

_ORDER_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created "
    "ON payment_orders (user_id, created_at DESC)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_orders_txn "
    "ON payment_orders (provider, provider_txn) WHERE provider_txn IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_payment_orders_state_created ON payment_orders (state, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_payment_orders_created ON payment_orders (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_payment_orders_card_token "
    "ON payment_orders (updated_at) WHERE click_card_token IS NOT NULL",
    # GetStatement: paid Paynet orders by perform time (unix ms).
    "CREATE INDEX IF NOT EXISTS idx_payment_orders_paynet_perform "
    "ON payment_orders (perform_time, seq) WHERE provider = 'paynet' AND state = 'paid'",
)

_EVENTS_DDL = """
    CREATE TABLE {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL CHECK (provider IN ('click', 'paynet')),
        method TEXT NOT NULL,
        order_id TEXT,
        provider_txn TEXT,
        payload TEXT NOT NULL,
        response_code INTEGER,
        received_at INTEGER NOT NULL
    )
"""

_EVENT_COLUMNS = "id, provider, method, order_id, provider_txn, payload, response_code, received_at"

_EVENT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_payment_events_order ON payment_events (order_id, received_at)",
    "CREATE INDEX IF NOT EXISTS idx_payment_events_txn ON payment_events (provider, provider_txn)",
    "CREATE INDEX IF NOT EXISTS idx_payment_events_received ON payment_events (received_at)",
)


async def _rebuild(conn, table: str, ddl: str, columns: str, indexes: tuple[str, ...]) -> None:
    current = await _table_sql(conn, table)
    if current is None:
        # m020 always runs first; this only covers a hand-built database.
        await conn.execute(ddl.format(name=table))
    elif "'paynet'" not in current:
        high_water = await _high_water(conn, table)
        tmp = f"{table}_m027"
        await conn.execute(f"DROP TABLE IF EXISTS {tmp}")
        await conn.execute(ddl.format(name=tmp))
        await conn.execute(f"INSERT INTO {tmp} ({columns}) SELECT {columns} FROM {table}")
        await conn.execute(f"DROP TABLE {table}")
        await conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
        await _restore_high_water(conn, table, high_water)
    for statement in indexes:
        await conn.execute(statement)


async def apply(conn) -> None:
    await _rebuild(conn, "payment_orders", _ORDERS_DDL, _ORDER_COLUMNS, _ORDER_INDEXES)
    await _rebuild(conn, "payment_events", _EVENTS_DDL, _EVENT_COLUMNS, _EVENT_INDEXES)
