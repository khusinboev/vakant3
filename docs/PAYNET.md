# Paynet provider endpoint (wallet top-ups at a Paynet agent)

Bandlik.uz serves the **provider side** of Paynet's UWS JSON-RPC 2.0 protocol so users can top up the
wallet at a Paynet terminal, kiosk or app. Paynet and SlaydX share ONE Paynet service (one `serviceId`, one
Basic login/password). Paynet calls SlaydX; when the payer id starts with `vk-` (or `vk_`) SlaydX relays the
request here unchanged (same body, `Content-Type`, `Authorization: Basic ...`, plus `X-Forwarded-By: slaydx`)
and returns our JSON to Paynet verbatim. Receipts say "SlaydX" (same as Click, owner-approved).

Code: `webapp/payments/paynet.py` (protocol), `webapp/payments/config.py` (settings), `webapp/payments/service.py`
(`credit_topup`, shared with Click), migration `m027_paynet`, tests `tests/test_payments_paynet.py`.

## Endpoint

`POST https://<bandlik domain>/api/payments/paynet` — JSON-RPC 2.0, UTF-8. Lives under `/api`, next to the Click
callback, so the existing nginx `/api` proxy already routes it. No cookie, no entry gate, no IP filter (all calls
come from SlaydX's server; Paynet's IPs are enforced there; `X-Forwarded-By` can be forged and is ignored).

HTTP is always **200** with a JSON-RPC body, except bad / missing credentials: **401** +
`WWW-Authenticate: Basic realm="paynet"` + error `412`. Any non-POST: `-32300`.

## Environment (names only — the owner writes the values into the server `.env` and restarts `vakant-api`)

| Variable | Meaning |
|---|---|
| `PAYNET_USERNAME` / `PAYNET_PASSWORD` | the same Basic login/password SlaydX uses; empty -> every call is 401 |
| `PAYNET_SERVICE_IDS` | comma list of accepted `serviceId`s (the id SlaydX uses); anything else is error 305 |
| `PAYNET_CLIENT_PARAM` | name of the payer field inside `fields`, default `client_id` |
| `PAYNET_APP_URL` | optional `https://` link for the wallet's "open in the Paynet app" button |

Paynet is "configured" only when username, password and at least one service id are set; the wallet card is shown
only then (`GET /api/payments/paynet/info`).

## Contract

Payer id: `fields.<PAYNET_CLIENT_PARAM>` = `vk-<Bandlik user id>` (`vk_` accepted; case-sensitive; ASCII digits only,
at most 18). Absent -> 411, malformed -> 401, unknown user -> 302, `users.banned` -> 501.
Dates: `YYYY-MM-DD HH:mm:ss`, GMT+5 (no DST). Body cap 64 KB (`-32600`).

| Method | Result / errors |
|---|---|
| `GetInformation` | `{status:"0", timestamp, fields:{name:"Adham B.", balance:<so'm>}}` |
| `PerformTransaction` | `amount` in **tiyin** (positive multiple of 100; so'm below the Click minimum -> 413, above the maximum -> 415). Credits `amount/100` so'm. Result `{timestamp, providerTrnId, fields:{<param>:<as sent>, balance:<new so'm balance>}}`. Duplicate `transactionId` -> **201**, never a second credit. |
| `CheckTransaction` | paid `{transactionState:1, providerTrnId, timestamp}`; unknown `{transactionState:3, providerTrnId:0, timestamp}`; bad `timestamp` -> 414 |
| `CancelTransaction` | **never cancels** (payments are final): found -> 77, unknown -> 203. `timestamp` is required but not format-checked (Paynet's spec sends `DD.MM.YYYY HH:mm:ss` here). |
| `GetStatement` | `{statements:[{amount:<tiyin>, transactionId, providerTrnId, timestamp}]}` — only our PAID Paynet transactions with perform time in `[dateFrom, dateTo]` inclusive (to `dateTo`+999 ms), ordered by time then `transactionId`. Bad / reversed dates -> 414. SlaydX fails the WHOLE merged statement on one malformed row, so a row that would be invalid raises `-32603` instead of being sent. |

Envelope errors: `-32700` invalid JSON (NaN/Infinity count), `-32600` not one object with `jsonrpc:"2.0"`, string
`method`, valid `id`, object `params` (or body too large), `-32601` unknown method (incl. `ChangePassword`),
`-32602` missing / wrong-typed params (incl. a bad `transactionId`), `-32603` internal (never leaks details).
`id` is echoed (string or number) whenever it is valid.

## Money model

* One `BEGIN IMMEDIATE` transaction: duplicate check, payer check, `payment_orders` insert (provider `paynet`,
  state `paid`, `provider_txn` = canonical `transactionId`, times in unix ms, `click_method = 'paynet'`), wallet credit,
  ledger row (`kind topup`, `reference paynet:<transactionId>`) and the payment bonus (`payment_bonus_percent`,
  `payment-bonus:<order id>`) through `service.credit_topup`. A failure anywhere rolls all of it back.
* Idempotency is layered: the write lock serializes callers, the duplicate check answers 201, the unique index
  `(provider, provider_txn)` and the unique ledger reference are the last guards (a lost race still ends as 201).
* `providerTrnId = 1_000_000_000 + payment_orders.seq` — unique, never reused, clear of SlaydX's small integers
  (Paynet sees both statements merged).
* Every authenticated call writes one `payment_events` row (provider `paynet`, params without secrets, response code)
  and one log line (`method`, `service`, `code`, `ms`). The `Authorization` header, password and body are never logged.
* With the payment bonus ON, Paynet's own tester check "balance grew by amount/100" would see the bonus too; run the
  tester with the bonus at 0.

## Verification

`pytest tests/test_payments_paynet.py` (+ `tests/test_payments_click.py`, `tests/test_ledger.py`). Paynet's own tester
(`paynet-tester-linux`, `http://localhost:3000`): Address = local `.../api/payments/paynet`, "Многоразовые",
"CancelTransaction: нет", parameter `client_id`, existing client `vk-<test user id>`, missing client `vk-999999999999`,
amount `100000`, wrong amount `1` — run it against a local dev server with a throw-away DB, never production.
