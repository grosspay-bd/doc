# 07 · Errors

← [Payment object & lifecycle](06-payment-object.md) · Next: [Disputes](08-disputes.md) →

- [Error envelope](#error-envelope)
- [`fault.class`](#faultclass)
- [Business error codes](#business-error-codes)
- [Retry policy](#retry-policy)
- [Examples](#examples)

---

## Error envelope

Any request that fails returns a non-`2xx` HTTP status and this body:

```json
{
  "ok": false,
  "fault": {
    "class": "declined",
    "code": "474",
    "detail": "Invalid bKash wallet number (0171234), expected format: 01XXXXXXXXX",
    "at": null
  }
}
```

| Field | Type | Description |
|---|---|---|
| `ok` | boolean | Always `false` for errors |
| `fault.class` | string | Error category — drives your handling logic, see below |
| `fault.code` | string | Machine-readable code (a **string**, e.g. `"474"`) |
| `fault.detail` | string | Human-readable description. For logs and support — don't parse it. |
| `fault.at` | array \| null | For `validation` errors: the fields that failed. Otherwise `null`. |

**How to detect an error:** HTTP status is not `2xx` **or** the body has `"ok": false`. Successful responses are the plain [payment object](06-payment-object.md) (no `ok` wrapper).

---

## `fault.class`

| `fault.class` | HTTP status | When | Retry? |
|---|---|---|---|
| `validation` | `400`, `422` | Malformed JSON, missing or invalid fields. `fault.at` lists the fields. | **No** — fix the request |
| `unauthorized` | `401`, `403` | Wrong, empty or revoked API key; `Authorization` header without `Bearer ` prefix | **No** — fix credentials |
| `declined` | other `4xx` | Business refusal — see codes below | **No**, except `477` |
| `server` | `5xx` | Error on GrossPay side | **Yes**, with back-off (see [retry policy](#retry-policy)) |

---

## Business error codes

| `fault.code` | Meaning | What to do |
|---|---|---|
| `470` | The payer (`holder_ref`) already has an active payment | Don't create another one. For a deposit, send the customer back to the existing `hosted_url`, or wait until the previous payment is final. |
| `471` | Merchant limit exceeded | Stop and alert your team; contact your manager to review limits. Show the customer a generic "try later" message. |
| `474` | Invalid payment details (e.g. bKash number) | Ask the customer to correct the details. See [number rules](03-pay-out.md#bkash-wallet-number-rules). |
| `475` | Amount is below the minimum | Show the minimum amount to the customer |
| `476` | Amount is above the maximum | Show the maximum amount to the customer |
| `477` | Temporary — repeat the request later | Retry later with the **same** `merchant_ref` |

> Ask your manager for the current minimum/maximum amounts and merchant limits for your account and validate them in your UI before calling the API.

---

## Retry policy

| Situation | Safe to retry? | How |
|---|---|---|
| `validation`, `unauthorized`, `declined` (except `477`) | ❌ | Retrying the same request returns the same error |
| `477` | ✅ | Same request, same `merchant_ref`, after a delay (e.g. 30 s → 1 min → 5 min) |
| `5xx` / timeout / connection reset on `POST /payments/init` | ⚠️ Only after checking | First `GET /payments/{merchant_ref}/state`. Exists → use it. Not found → repeat the POST with the same `merchant_ref`. |
| `5xx` / timeout on `GET` endpoints | ✅ | Exponential back-off: 1 s, 2 s, 4 s, 8 s … (cap at ~60 s) |

**Golden rule:** a retry of the same business operation always uses the **same `merchant_ref`**. A new `merchant_ref` means a new payment — for payouts that can mean paying twice.

Recommended HTTP client timeouts: connect 5–10 s, read 30 s.

---

## Examples

### Validation error

```json
{
  "ok": false,
  "fault": {
    "class": "validation",
    "code": "400",
    "detail": "order_currency must be BDT",
    "at": ["order_currency"]
  }
}
```

### Missing `Bearer ` prefix

```http
HTTP/1.1 403 Forbidden
```

```json
{
  "ok": false,
  "fault": { "class": "unauthorized", "code": "403", "detail": "Unauthorized", "at": null }
}
```

### Active payment already exists

```json
{
  "ok": false,
  "fault": { "class": "declined", "code": "470", "detail": "Payer already has an active payment", "at": null }
}
```

*The `detail` texts and `code` values in the validation/unauthorized/470 examples are illustrative; rely on `fault.class` and `fault.code`, not on `detail`.*

### Handling errors in code

```js
async function grosspay(method, path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { Authorization: `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30_000),
  });
  const data = await res.json().catch(() => ({}));
  if (res.ok && data.ok !== false) return data;

  const fault = data.fault ?? { class: res.status >= 500 ? 'server' : 'unknown', code: String(res.status) };
  const err = new Error(`GrossPay ${res.status} ${fault.class}/${fault.code}: ${fault.detail ?? ''}`);
  err.fault = fault;
  err.retryable = fault.class === 'server' || fault.code === '477';
  throw err;
}
```

Next: [Disputes](08-disputes.md) →
