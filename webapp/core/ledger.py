"""Wallet ledger: the only place that changes ``users.user_balance``.

Every function here performs the conditional ``UPDATE users ...`` as the FIRST
statement of the transaction and then writes one ``wallet_transactions`` row
with the balance that update produced. Doing the write first matters: a read
taken earlier in the same transaction would pin a WAL snapshot and make the
later write fail with ``SQLITE_BUSY_SNAPSHOT`` instead of waiting for the other
writer, so two concurrent activations would not serialize cleanly.

The caller commits (``await db.commit()``), so the balance change and its
ledger row land atomically; on an exception the caller's rollback drops both.

Invariants (tests/test_ledger.py):
  * ``balance_after`` equals ``users.user_balance`` right after the call;
  * from a zero start, ``SUM(amount)`` per user equals the current balance;
  * a refused change (insufficient funds, unknown user) writes nothing.
"""

from __future__ import annotations

import time
from typing import Any

# Guard rail against a typo'd admin credit or an overflowing price.
MAX_AMOUNT = 100_000_000

KINDS = ("pro_activation", "referral_reward", "admin_credit", "admin_reset", "adjustment")


class LedgerError(Exception):
    """Base class for refusals raised by this module."""


class InsufficientBalance(LedgerError):
    def __init__(self, required: int, balance: int) -> None:
        super().__init__(f"insufficient balance: required {required}, have {balance}")
        self.required = int(required)
        self.balance = int(balance)


class UserNotFound(LedgerError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"user {user_id} not found")
        self.user_id = int(user_id)


class AlreadyPro(LedgerError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"user {user_id} is already pro")
        self.user_id = int(user_id)


def _check_amount(amount: int) -> int:
    amount = int(amount)
    if abs(amount) > MAX_AMOUNT:
        raise ValueError(f"amount out of bounds: {amount}")
    return amount


def _check_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown ledger kind: {kind}")
    return kind


async def _current_balance(db, user_id: int) -> tuple[int, bool] | None:
    cursor = await db.execute(
        "SELECT user_balance, user_pro FROM users WHERE user_id = ?", (int(user_id),)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return int(row[0] or 0), bool(int(row[1] or 0))


async def _insert_tx(
    db,
    *,
    user_id: int,
    kind: str,
    amount: int,
    balance_after: int,
    actor_id: int | None,
    note: str | None,
    price_snapshot: int | None,
) -> int:
    cursor = await db.execute(
        """
        INSERT INTO wallet_transactions
            (user_id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            kind,
            int(amount),
            int(balance_after),
            None if price_snapshot is None else int(price_snapshot),
            None if actor_id is None else int(actor_id),
            None if note is None else str(note)[:500],
            int(time.time()),
        ),
    )
    return int(cursor.lastrowid or 0)


async def apply_balance_change(
    db,
    *,
    user_id: int,
    amount: int,
    kind: str,
    actor_id: int | None = None,
    note: str | None = None,
    price_snapshot: int | None = None,
    require_sufficient: bool = False,
) -> dict[str, Any]:
    """Move ``amount`` (signed) on a user's balance and record it. Caller commits.

    ``require_sufficient`` refuses the change when it would take the balance
    below zero, raising :class:`InsufficientBalance` without touching anything.
    """
    user_id = int(user_id)
    amount = _check_amount(amount)
    kind = _check_kind(kind)

    if require_sufficient and amount < 0:
        cursor = await db.execute(
            """
            UPDATE users SET user_balance = COALESCE(user_balance, 0) + ?
            WHERE user_id = ? AND COALESCE(user_balance, 0) >= ?
            """,
            (amount, user_id, -amount),
        )
    else:
        cursor = await db.execute(
            "UPDATE users SET user_balance = COALESCE(user_balance, 0) + ? WHERE user_id = ?",
            (amount, user_id),
        )

    if not cursor.rowcount:
        state = await _current_balance(db, user_id)
        if state is None:
            raise UserNotFound(user_id)
        raise InsufficientBalance(required=-amount, balance=state[0])

    state = await _current_balance(db, user_id)
    balance_after = state[0] if state else 0
    tx_id = await _insert_tx(
        db,
        user_id=user_id,
        kind=kind,
        amount=amount,
        balance_after=balance_after,
        actor_id=actor_id,
        note=note,
        price_snapshot=price_snapshot,
    )
    return {"balance_after": balance_after, "tx_id": tx_id, "amount": amount}


async def activate_pro(db, user_id: int, price: int) -> dict[str, Any]:
    """Charge ``price`` and flip ``user_pro`` in one conditional update.

    Raises :class:`AlreadyPro` (-> ALREADY_PRO), :class:`InsufficientBalance`
    (-> INSUFFICIENT_BALANCE) or :class:`UserNotFound` (-> NOT_FOUND).
    """
    user_id = int(user_id)
    price = _check_amount(price)
    if price < 0:
        raise ValueError("price must not be negative")

    cursor = await db.execute(
        """
        UPDATE users SET user_balance = COALESCE(user_balance, 0) - ?, user_pro = 1
        WHERE user_id = ?
          AND COALESCE(user_pro, 0) = 0
          AND COALESCE(user_balance, 0) >= ?
        """,
        (price, user_id, price),
    )
    if not cursor.rowcount:
        state = await _current_balance(db, user_id)
        if state is None:
            raise UserNotFound(user_id)
        balance, is_pro = state
        if is_pro:
            raise AlreadyPro(user_id)
        raise InsufficientBalance(required=price, balance=balance)

    state = await _current_balance(db, user_id)
    balance_after = state[0] if state else 0
    tx_id = await _insert_tx(
        db,
        user_id=user_id,
        kind="pro_activation",
        amount=-price,
        balance_after=balance_after,
        actor_id=None,
        note=None,
        price_snapshot=price,
    )
    return {"balance_after": balance_after, "tx_id": tx_id, "amount": -price, "is_pro": True}


async def reset_user(
    db,
    *,
    user_id: int,
    actor_id: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Admin reset: balance -> 0, Pro removed, one ``admin_reset`` row for the delta.

    The update is conditional on the balance we read, so a concurrent change
    cannot be silently swallowed; we re-read and retry a bounded number of times.
    """
    user_id = int(user_id)
    for _ in range(5):
        state = await _current_balance(db, user_id)
        if state is None:
            raise UserNotFound(user_id)
        balance, _is_pro = state
        cursor = await db.execute(
            """
            UPDATE users SET user_balance = 0, user_pro = 0
            WHERE user_id = ? AND COALESCE(user_balance, 0) = ?
            """,
            (user_id, balance),
        )
        if not cursor.rowcount:
            continue
        tx_id = await _insert_tx(
            db,
            user_id=user_id,
            kind="admin_reset",
            amount=_check_amount(-balance),
            balance_after=0,
            actor_id=actor_id,
            note=note,
            price_snapshot=None,
        )
        return {"balance_after": 0, "tx_id": tx_id, "amount": -balance}
    raise LedgerError(f"reset_user: balance for {user_id} kept changing under us")


async def list_transactions(
    db,
    *,
    user_id: int,
    before_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Newest-first page of a user's own ledger rows (cursor = ``before_id``)."""
    limit = max(1, min(int(limit), 50))
    params: list[Any] = [int(user_id)]
    where = "user_id = ?"
    if before_id:
        where += " AND id < ?"
        params.append(int(before_id))
    params.append(limit)
    cursor = await db.execute(
        f"""
        SELECT id, user_id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at
        FROM wallet_transactions
        WHERE {where}
        ORDER BY id DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [dict(row) for row in await cursor.fetchall()]
