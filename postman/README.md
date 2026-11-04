# Postman

## Import

1. In Postman: **Import** → drop all three files:
   - `GrossPay-BD.postman_collection.json`
   - `GrossPay-BD-Test.postman_environment.json`
   - `GrossPay-BD-Production.postman_environment.json`
2. Select the **GrossPay BD — Test** environment (top-right) and fill in:

| Variable | Value |
|---|---|
| `apiKey` | your **test** API key (marked *secret*) |
| `callbackUri` | your webhook endpoint, or a request bin such as `https://webhook.site/<uuid>` to watch webhooks |
| `walletNumber` | bKash number for test payouts (default `01712345678`) |
| `nagadWallet` | Nagad number for test payouts (default `01812345678`) |
| `holderAccount` | Payer's wallet number for the Nagad deposit with `holder_account` |
| `bankCode` | Bank code from the [bank directory](../docs/11-payment-methods.md#bank-directory) — **required** for the bank payout request |
| `bankAccount`, `routingNumber`, `bankPayoutAmount` | Test bank account details for the bank payout |
| `depositAmount` / `payoutAmount` | default `1000.00` / `1500.00` |
| `holderRef`, `returnUri` | optional |

## What's inside

| Folder | Requests |
|---|---|
| **1. Pay-in (debit)** | Create deposit: bKash, Nagad with `holder_account`, BanglaQR, card → Get state by `payment_id` / `merchant_ref` |
| **2. Pay-out (credit)** | Create payout: bKash (local and `+880` formats), Nagad, bank account → Get state |
| **3. Balance** | `GET /partner/ledger_balance` |
| **4. Disputes** | Escalate with receipt (select a file for `file1` in the *Body* tab first) |
| **5. Negative tests** | Invalid bKash / Nagad number and `holder_account` (474), bank payout without `route_network` or `payee_title` (validation), missing `Bearer` (403), invalid key, missing field, short `merchant_ref`, amount below/above limits (475/476), unknown payment (404) |

- `merchant_ref` is generated automatically for each create request (`order_bd_<timestamp>`, `withdraw_bd_<timestamp>`), so you never create duplicates by accident.
- `payment_id`, `merchant_ref` and `hosted_url` are saved to collection variables, so the *Get state* requests work right after *Create*.
- `hosted_url` is printed in the Postman **Console** — open it to pay.
- Every request has tests — see the **Test Results** tab. You can run a whole folder with **Run folder** (Collection Runner).
- A collection-level test fails if the response is not JSON — e.g. a Cloudflare block page. If you see that, send the Cloudflare Ray ID and your server IP to support.

## Notes

- Requests for methods that are not enabled for your account return a validation error with `fault.at: ["route_network"]` — that's expected; ask your manager which methods are enabled.
- **Production** environment sends real money on payouts. Use Test until the [go-live checklist](../docs/10-go-live-checklist.md) is complete.
- Postman can't receive webhooks; use your own endpoint or a request bin.
- Negative tests for limits use `1.00` and `99999999.00` — adjust if your account limits differ.
- Never export or share environments that contain a real `apiKey`.

Alternatively, import [`../openapi/openapi.yaml`](../openapi/openapi.yaml) — Postman builds a collection from the OpenAPI spec (without the tests and auto-saved variables).
