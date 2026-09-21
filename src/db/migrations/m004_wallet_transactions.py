"""Wallet ledger: every balance change gets an immutable row.

``amount`` is signed (credit > 0, debit < 0) and ``balance_after`` is the
``users.user_balance`` value the same transaction wrote, so the ledger can be
replayed and reconciled against the users table.
"""

ID = "m004_wallet_transactions"

KINDS = ("pro_activation", "referral_reward", "admin_credit", "admin_reset", "adjustment")


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN (
                'pro_activation', 'referral_reward', 'admin_credit', 'admin_reset', 'adjustment'
            )),
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            price_snapshot INTEGER,
            actor_id INTEGER,
            note TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallet_tx_user_created "
        "ON wallet_transactions (user_id, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallet_tx_created ON wallet_transactions (created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wallet_tx_kind_created "
        "ON wallet_transactions (kind, created_at)"
    )
