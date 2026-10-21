# 10 · Go-live checklist

← [Balance](09-balance.md) · [Back to README](../README.md)

Complete every item in the **Test** environment (`api-test.grosspayme.com`) before requesting Production credentials. Copy this file into your ticket and tick the boxes.

## 1. Configuration

- [ ] API key stored in a secret store / environment variable, not in code or Git
- [ ] Base URL, API key and webhook public key are configured **per environment** and cannot be mixed
- [ ] `Authorization: Bearer <API_KEY>` is sent on every request (with the `Bearer ` prefix)
- [ ] `callback_uri` is public HTTPS with a valid certificate
- [ ] `136.148.218.118` is allow-listed on the webhook endpoint (firewall / WAF / proxy)
- [ ] The webhook route accepts `POST` (and never answers `405` by framework default)
- [ ] HTTP client timeouts set (connect 5–10 s, read ~30 s)

## 2. Pay-in (debit)

- [ ] Amounts sent as strings with two decimals (`"1000.00"`)
- [ ] `merchant_ref` unique per payment, 5–64 chars, generated once and stored before the API call
- [ ] `holder_ref` is a stable ID of the customer
- [ ] `payment_id` stored with the order
- [ ] Customer is redirected to `hosted_url` exactly as returned
- [ ] Return page does **not** credit; it shows the state from your DB
- [ ] Error `470` handled (existing active payment)
- [ ] Errors `475` / `476` shown to the customer as min/max amount messages

## 3. Pay-out (credit)

- [ ] bKash number normalised and validated (`^01[3-9]\d{8}$`) before the call
- [ ] Customer funds held **before** the payout request
- [ ] Hold released on `unposted`
- [ ] Money returned to the customer on `posted → returned`
- [ ] Timeout handling uses `GET /payments/{merchant_ref}/state` before retrying — no new `merchant_ref` for a retry
- [ ] Error `474` shown as "invalid bKash number"

## 4. Webhooks

- [ ] Signature verified on the **raw body** with the correct environment's public key
- [ ] Invalid / missing signature → nothing changes, response `401`/`403`
- [ ] Handler is idempotent (duplicates do not double-credit)
- [ ] Out-of-order events handled (late `queued` after `posted` is ignored)
- [ ] Amounts booked from `amount_posted`, never from `order_amount`
- [ ] `returned` reverses previous credit/debit
- [ ] `unposted → posted` (late confirmation) is accepted
- [ ] Response `200` within a few seconds; heavy work is async
- [ ] Raw webhook bodies are logged (audit trail) — without API keys
- [ ] `405` is returned **only** by explicit business logic

## 5. Operations

- [ ] Reconciliation job for payments stuck in `received` / `queued` (`GET /state`)
- [ ] Balance monitoring with alert threshold (`GET /partner/ledger_balance`)
- [ ] Dispute flow for customers who paid but weren't credited (`POST /escalate`)
- [ ] Logs include `payment_id`, `merchant_ref`, HTTP status, `fault.code` for every API call
- [ ] Support team knows where to find a payment by `merchant_ref` / `payment_id` in the [merchant cabinet](https://cabinet.grosspayme.com)

## Test scenarios

Run each scenario in Test and record the `payment_id`. Scenarios that depend on the payment outcome (T4, T10) may need to be triggered by GrossPay support in Test — ask your manager, or cover them with signed test webhooks (W-scenarios below).

| # | Scenario | Expected result in your system |
|---|---|---|
| T1 | Deposit 1000.00, pay in full | Webhook `posted`, customer +1000.00 |
| T2 | Deposit, payer abandons the page | Webhook `unposted`, no credit, order failed |
| T3 | Deposit, payer returns to `return_uri` before paying | Order still pending, no credit |
| T4 | Deposit, payer pays less than requested | `part_posted`, credit = `amount_posted` |
| T5 | Second deposit for same `holder_ref` while T-payment active | `470` handled gracefully |
| T6 | Deposit with amount below min / above max | `475` / `476` message to customer |
| T7 | Request without `Bearer ` prefix | `403`, alert in logs |
| T8 | Payout 1500.00 to a valid number | Hold → `posted` → final debit |
| T9 | Payout to `0171234` (invalid) | `474`, hold released / not created |
| T10 | Payout `posted`, then `returned` | Customer gets 1500.00 back |
| T11 | `POST /payments/init` timeout simulated (kill connection) | Recovery via `GET /payments/{merchant_ref}/state`, single payment |
| T12 | Escalate a payment with 1 receipt | `{"escalated": true}` |

### Webhook scenarios

Simulate with your own key pair ([how](05-webhooks.md#testing-webhooks)):

| # | Scenario | Expected |
|---|---|---|
| W1 | Same `posted` webhook delivered 3 times | Credited once, `200` each time |
| W2 | `posted` arrives, then a late `queued` | State stays `posted`, `200` |
| W3 | Body changed by 1 byte after signing | Rejected, nothing changes |
| W4 | Valid signature, Production key used in Test | Rejected → fix configuration |
| W5 | Webhook for unknown `payment_id` | `503`, logged, retried |
| W6 | Your DB unavailable | `5xx`; after recovery the retry is processed once |
| W7 | `unposted` → later `posted` | Credit applied once |

When all boxes are ticked, send the list of test `payment_id`s to your GrossPay manager to request Production access.
