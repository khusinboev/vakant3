"""Click wallet top-ups: orders, the raw webhook trail, abuse counters, ledger kinds.

Ported from SlaydX (``001_init.sql`` payment_orders, ``005_payment_times``,
``025_payment_events``, ``048_click_direct``), adapted to SQLite:

``payment_orders``
    One row per top-up attempt. ``id`` is a UUID string; Click sees it as
    ``merchant_trans_id = "vk-<id>"`` (the shared Click service forwards every
    ``vk-`` request from SlaydX to us). ``seq`` is the integer Click needs as
    ``merchant_prepare_id``: it is copied into ``prepare_id`` on the first
    Prepare, so an order that was never prepared has no prepare id. Times
    (``create_time``/``perform_time``/``cancel_time``) are unix **ms** like the
    provider protocol; ``created_at``/``updated_at`` are unix seconds like the
    rest of vakant3. ``click_card_token`` holds a one-time card token only
    between "SMS sent" and "payment submitted"; the card number, expiry and
    SMS code are never stored.

``payment_events``
    Every signed Click Prepare/Complete (repeats included) with our answer
    code; ``sign_string`` is redacted before the insert. No FK: a request for
    an unknown order still leaves a trace.

``payment_rate_limits``
    Fixed-window counters for the Merchant API calls (they cost SMS and can
    probe cards). In the database, not in the per-worker slowapi memory, so
    the caps hold across uvicorn workers.

``wallet_transactions``
    SQLite cannot alter a CHECK constraint, so the table is rebuilt once to
    accept the kinds ``topup`` and ``topup_bonus`` and to gain ``reference``
    with a partial UNIQUE index on ``(kind, reference)``: a top-up is written
    with ``click:<click_trans_id>`` and its bonus with
    ``payment-bonus:<order id>``, the second guard (after the order's
    ``state`` transition) against crediting one payment twice. Ids and the
    AUTOINCREMENT high-water mark are preserved.

``webapp_admin_settings.payment_bonus_percent``
    0–50, default 0 (off): N % of every paid top-up is credited as a bonus.
"""

from src.db.migrate import add_column_if_missing

ID = "m020_click_payments"

LEDGER_KINDS = (
    "pro_activation",
    "referral_reward",
    "admin_credit",
    "admin_reset",
    "adjustment",
    "topup",
    "topup_bonus",
)

_LEDGER_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_wallet_tx_user_created ON wallet_transactions (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_tx_created ON wallet_transactions (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_tx_kind_created ON wallet_transactions (kind, created_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_tx_kind_reference "
    "ON wallet_transactions (kind, reference) WHERE reference IS NOT NULL",
)


async def _table_sql(conn, name: str) -> str | None:
    cursor = await conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    )
    row = await cursor.fetchone()
    return None if row is None else str(row[0] or "")


async def _rebuild_wallet_transactions(conn) -> None:
    kinds_sql = ", ".join(f"'{kind}'" for kind in LEDGER_KINDS)
    ddl = f"""
        CREATE TABLE {{name}} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ({kinds_sql})),
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            price_snapshot INTEGER,
            actor_id INTEGER,
            note TEXT,
            created_at INTEGER NOT NULL,
            reference TEXT
        )
    """
    current = await _table_sql(conn, "wallet_transactions")
    if current is None:
        # m004 always runs first; this only covers a hand-built database.
        await conn.execute(ddl.format(name="wallet_transactions"))
    elif "'topup'" not in current:
        cursor = await conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'wallet_transactions'"
        )
        seq_row = await cursor.fetchone()
        await conn.execute("DROP TABLE IF EXISTS wallet_transactions_m020")
        await conn.execute(ddl.format(name="wallet_transactions_m020"))
        await conn.execute(
            """
            INSERT INTO wallet_transactions_m020
                (id, user_id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at)
            SELECT id, user_id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at
            FROM wallet_transactions
            """
        )
        await conn.execute("DROP TABLE wallet_transactions")
        await conn.execute("ALTER TABLE wallet_transactions_m020 RENAME TO wallet_transactions")
        if seq_row is not None and seq_row[0] is not None:
            # Never hand out an id that an old (even a deleted) row once had.
            await conn.execute(
                "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'wallet_transactions'",
                (int(seq_row[0]),),
            )
    for statement in _LEDGER_INDEXES:
        await conn.execute(statement)


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_orders (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL DEFAULT 'click' CHECK (provider IN ('click')),
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
            click_method TEXT CHECK (click_method IN ('page', 'card', 'phone', 'app')),
            click_invoice_id INTEGER,
            click_card_token TEXT,
            click_payment_id INTEGER,
            bonus_percent INTEGER NOT NULL DEFAULT 0,
            bonus_amount INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created "
        "ON payment_orders (user_id, created_at DESC)"
    )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_orders_txn "
        "ON payment_orders (provider, provider_txn) WHERE provider_txn IS NOT NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_orders_state_created "
        "ON payment_orders (state, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_orders_created ON payment_orders (created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_orders_card_token "
        "ON payment_orders (updated_at) WHERE click_card_token IS NOT NULL"
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL CHECK (provider IN ('click')),
            method TEXT NOT NULL,
            order_id TEXT,
            provider_txn TEXT,
            payload TEXT NOT NULL,
            response_code INTEGER,
            received_at INTEGER NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_events_order ON payment_events (order_id, received_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_events_txn ON payment_events (provider, provider_txn)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_events_received ON payment_events (received_at)"
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_rate_limits (
            bucket TEXT NOT NULL,
            window_start INTEGER NOT NULL,
            hits INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (bucket, window_start)
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_rate_limits_window "
        "ON payment_rate_limits (window_start)"
    )

    await _rebuild_wallet_transactions(conn)

    if await _table_sql(conn, "webapp_admin_settings") is not None:
        await add_column_if_missing(
            conn, "webapp_admin_settings", "payment_bonus_percent", "INTEGER NOT NULL DEFAULT 0"
        )
