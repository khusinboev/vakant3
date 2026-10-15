"""Click wallet top-ups, ported from SlaydX (``lib/server/payments.ts`` and friends).

Money rule: a balance changes ONLY in :func:`webapp.payments.service.settle_order`,
called by the Click Shop API ``Complete`` callback, through
``webapp.core.ledger.apply_balance_change``. The Merchant API calls (card token,
SMS, invoice) merely START a payment.
"""
