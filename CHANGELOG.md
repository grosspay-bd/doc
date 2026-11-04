# Changelog

## 2026-11-04

New payment methods and networks. **Backward compatible** — existing bKash integrations work without changes.

- `route_kind` now selects the payment method: `wallet`, `banglaqr`, `card` (pay-in), `bank` (pay-out).
- `route_network` selects the network: `bkash`, `nagad`, `rocket`, `upay`, or a bank code. `wallet` without `route_network` = `bkash`.
- Pay-in: Nagad wallet transfer, BanglaQR (bKash / Nagad), card.
- Pay-in: new optional field `holder_account` — payer's wallet number.
- Pay-out: Nagad, Rocket, Upay wallets; bank accounts (`credit_details.account_number`, `payee_title`, `routing_number`, `branch_name`).
- Payment object: new fields `route_kind`, `route_network`, `rail_ref`, `holder_account`; `payee_details` now filled for pay-outs; `valid_through` filled for pay-ins.
- Webhooks: only final states are guaranteed; `received` / `queued` webhooks may be skipped.
- Errors: no new codes. Invalid number/account of any network → `474`; method or network not enabled → validation error with `fault.at: ["route_network"]`.
- New section [11 · Payment methods & networks](docs/11-payment-methods.md); go-live scenarios T13–T17; OpenAPI, Postman, curl and Python client updated.

## 2026-10-21

- Initial release of the Bangladesh (BDT · bKash) integration guide.
- Endpoints: `POST /payments/init` (debit / credit), `GET /payments/{id}/state`, `GET /partner/ledger_balance`, `POST /payments/{payment_id}/escalate`.
- Webhooks signed with RSA-SHA256 (`signature-v1`), sender IP `136.148.218.118`.
- OpenAPI 3.0 specification, Postman collection, curl scripts, webhook receivers (Node.js, Python, PHP), Python client.
