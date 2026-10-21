# 04 · Payment status

← [Pay-out (credit)](03-pay-out.md) · Next: [Webhooks](05-webhooks.md) →

## Endpoint

`GET /payments/{id}/state`

`{id}` accepts **either**:

| Value | Example |
|---|---|
| GrossPay `payment_id` | `01a15cf5-f7c2-78b1-9276-87ea2c018577` |
| Your `merchant_ref` | `order_bd_0001` |

Looking up by `merchant_ref` is what makes safe retries possible: if `POST /payments/init` timed out and you never received `payment_id`, you can still find out whether the payment was created.

> If your `merchant_ref` can contain characters that are not URL-safe, URL-encode it in the path (`encodeURIComponent` / `urllib.parse.quote(ref, safe="")`). The simplest option is to use only `A–Z a–z 0–9 _ -` in `merchant_ref`.

## Request

```bash
# by payment_id
curl https://api-test.grosspayme.com/v1/payments/01a15cf5-f7c2-78b1-9276-87ea2c018577/state \
  -H "Authorization: Bearer $API_KEY"

# by merchant_ref
curl https://api-test.grosspayme.com/v1/payments/order_bd_0001/state \
  -H "Authorization: Bearer $API_KEY"
```

## Response

The response has **the same structure** as the `POST /payments/init` response and as the webhook body. Example of a completed deposit:

```json
{
  "payment_id": "01a15cf5-f7c2-78b1-9276-87ea2c018577",
  "hosted_url": "https://pay.example/cmvhoj1x300001bo7cdylcnm8",
  "merchant_ref": "order_bd_0001",
  "posting_state": "posted",
  "amount_posted": "1000.00",
  "client_amount": null,
  "decline_note": null,
  "order_amount": "1000.00",
  "order_currency": "BDT",
  "booked_at": "2026-10-21T05:36:26.058Z",
  "posted_at": "2026-10-21T05:41:02.511Z",
  "payee_details": null,
  "valid_through": null
}
```

Field meanings: [Payment object](06-payment-object.md).

## Status is cached — webhooks are the source of truth

The status returned by `GET /state` is **cached on the API side**, so it can lag behind the real state for a short time. Therefore:

| Use `GET /state` for | Do **not** use `GET /state` for |
|---|---|
| Recovering after a timeout on `POST /payments/init` | Tight polling loops (every 1–2 seconds) |
| Reconciling payments that have had no webhook for a long time | Replacing webhooks |
| Support / manual checks | Rejecting or ignoring a webhook because the status call still shows an older state |

### Recommended reconciliation job

Run a background job (e.g. every 10–15 minutes) that picks payments **not final** in your database and older than ~30 minutes, and calls `GET /state` for each. If the API shows a final state that you have not processed, apply it with the same code path you use for webhooks.

```text
SELECT * FROM payments
WHERE posting_state IN ('received', 'queued')
  AND created_at < now() - interval '30 minutes';
-- for each: GET /payments/{payment_id}/state → apply_state(result)
```

Final states: `posted`, `part_posted`, `unposted`, `returned` — but note that `posted` / `part_posted` can still change to `returned` later ([details](06-payment-object.md#lifecycle)).

## Errors

| HTTP | `fault.class` | Typical reason |
|---|---|---|
| `401` / `403` | `unauthorized` | Missing key or missing `Bearer ` prefix |
| `404` | `declined` | No payment with this `payment_id` / `merchant_ref` for your merchant account |
| `5xx` | `server` | Retry with back-off |

Full list: [Errors](07-errors.md).

Next: [Webhooks](05-webhooks.md) →
