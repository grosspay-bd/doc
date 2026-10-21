# 03 · Pay-out (credit) — withdrawal to bKash

← [Pay-in (debit)](02-pay-in.md) · Next: [Payment status](04-payment-status.md) →

- [How it works](#how-it-works)
- [Request](#request)
- [bKash wallet number rules](#bkash-wallet-number-rules)
- [Response](#response)
- [Examples](#examples)
- [Final result and customer balance](#final-result-and-customer-balance)
- [Safe retries — avoiding double payouts](#safe-retries--avoiding-double-payouts)

---

## How it works

A payout sends money from your GrossPay balance to a customer's **personal bKash wallet**. It is fully server-to-server: there is no payment page and no customer interaction.

1. Reserve (hold) the amount on the customer's balance in **your** system.
2. Call `POST /payments/init` with `intent: "credit"` and the recipient's bKash number.
3. GrossPay returns `payment_id`, `posting_state: "received"`.
4. GrossPay sends the transfer and notifies you via [webhooks](05-webhooks.md).
5. On `posted` — finalise the withdrawal. On `unposted` — release the hold back to the customer.
6. If a payout that was `posted` later becomes `returned` — credit the amount back to the customer.

The payout amount is taken from your merchant balance — check it with [`GET /partner/ledger_balance`](09-balance.md).

---

## Request

`POST /payments/init`

```http
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

### Body fields

| Field | Type | Required | Description |
|---|---|---|---|
| `order_amount` | string | **yes** | Amount to send, decimal string: `"1500.00"` |
| `order_currency` | string | **yes** | Always `"BDT"` |
| `intent` | string | **yes** | Always `"credit"` for payouts |
| `route_kind` | string | **yes** | Always `"wallet"` |
| `merchant_ref` | string | **yes** | Your unique withdrawal ID, **5–64 characters**. Idempotency key. |
| `holder_ref` | string | **yes** | ID of the recipient (your customer) in your system |
| `callback_uri` | string (URL) | **yes** | HTTPS URL for [webhooks](05-webhooks.md) |
| `credit_details` | object | **yes** | Recipient details, see below |
| `credit_details.wallet_number` | string | **yes** | Recipient's bKash number, see [rules](#bkash-wallet-number-rules) |
| `credit_details.payee_title` | string | no | Recipient's name, e.g. `"Rahim Uddin"` |

`return_uri` is not used for payouts. Do not send `route_network`.

---

## bKash wallet number rules

GrossPay accepts the number in any of these forms and normalises it:

| You send | Normalised to |
|---|---|
| `01712345678` | `01712345678` |
| `8801712345678` | `01712345678` |
| `+880 1712-345678` | `01712345678` |

After normalisation the number **must** match `01XXXXXXXXX`:

- exactly **11 digits**,
- starts with `01`,
- the **third digit is 3–9** (mobile operator prefix).

Regular expression for the normalised value:

```regex
^01[3-9]\d{8}$
```

An invalid number is rejected with business error **`474`**:

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

**Validate in your UI before the API call** so the customer can fix a typo immediately. Reference implementations:

```js
// JavaScript
function normalizeBkash(input) {
  let d = String(input).replace(/\D/g, '');          // keep digits only: "+880 1712-345678" -> "8801712345678"
  if (d.startsWith('880')) d = d.slice(2);            // "8801712345678" -> "01712345678"
  return /^01[3-9]\d{8}$/.test(d) ? d : null;         // null = invalid
}
```

```python
# Python
import re

def normalize_bkash(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("880"):
        digits = digits[2:]
    return digits if re.fullmatch(r"01[3-9]\d{8}", digits) else None
```

```php
// PHP
function normalizeBkash(string $value): ?string {
    $d = preg_replace('/\D/', '', $value);
    if (str_starts_with($d, '880')) { $d = substr($d, 2); }
    return preg_match('/^01[3-9]\d{8}$/', $d) ? $d : null;
}
```

> Format validation only proves the number *looks* valid. It does not prove the number has an active bKash personal account; a payout to such a number fails later and is reported via webhook as `unposted`.

---

## Response

Same structure as the deposit response, **without** `hosted_url`:

```json
{
  "payment_id": "01a15d02-3b9e-7c11-8a4f-5e2d9c1b7a60",
  "merchant_ref": "withdraw_bd_0001",
  "posting_state": "received",
  "client_amount": null,
  "decline_note": null,
  "order_amount": "1500.00",
  "order_currency": "BDT",
  "booked_at": "2026-10-21T06:02:11.410Z",
  "posted_at": null,
  "payee_details": null,
  "valid_through": null
}
```

`payment_id` above is illustrative. Store the returned `payment_id` together with your withdrawal record.

---

## Examples

### cURL

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1500.00",
    "order_currency": "BDT",
    "intent": "credit",
    "route_kind": "wallet",
    "merchant_ref": "withdraw_bd_0001",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "credit_details": {
      "wallet_number": "01712345678",
      "payee_title": "Rahim Uddin"
    }
  }'
```

### Node.js

```js
const wallet = normalizeBkash(form.wallet);
if (!wallet) return badRequest('Enter a valid bKash number, e.g. 01712345678');

await db.tx(async (t) => {
  await t.balances.hold(user.id, '1500.00', withdrawal.id);   // reserve first
  await t.withdrawals.insert({ id: withdrawal.id, status: 'pending' });
});

const res = await fetch(`${process.env.GROSSPAY_BASE_URL}/payments/init`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.GROSSPAY_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    order_amount: '1500.00',
    order_currency: 'BDT',
    intent: 'credit',
    route_kind: 'wallet',
    merchant_ref: withdrawal.id,
    holder_ref: user.id,
    callback_uri: 'https://your-site.com/webhooks/grosspay',
    credit_details: { wallet_number: wallet, payee_title: user.fullName },
  }),
});
```

### Python

```python
resp = requests.post(
    f"{BASE_URL}/payments/init",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "order_amount": "1500.00",
        "order_currency": "BDT",
        "intent": "credit",
        "route_kind": "wallet",
        "merchant_ref": "withdraw_bd_0001",
        "holder_ref": "user_bd_001",
        "callback_uri": "https://your-site.com/webhooks/grosspay",
        "credit_details": {"wallet_number": "01712345678", "payee_title": "Rahim Uddin"},
    },
    timeout=30,
)
```

A complete client is in [`examples/python-client`](../examples/python-client).

---

## Final result and customer balance

| `posting_state` | Meaning | Customer balance in your system |
|---|---|---|
| `received` | Accepted, waiting to be sent | Keep the hold |
| `queued` | Being processed | Keep the hold |
| `posted` | Sent successfully | Convert the hold into a final debit |
| `part_posted` | Sent partially; actual amount in `amount_posted` | Debit `amount_posted`, release the rest of the hold |
| `unposted` | Not sent (declined, cancelled or expired) | Release the full hold; reason in `decline_note` |
| `returned` | Was sent, then rolled back (reversal, refund) | Credit the previously debited amount back to the customer |

> **⚠️ A successful payout can still come back.** A payout may first reach `posted` and later be reported as `returned`. Your webhook handler must support this transition and give the money back to the customer. See [Payment object → lifecycle](06-payment-object.md#lifecycle).

---

## Safe retries — avoiding double payouts

Network timeouts on payouts are the most expensive bug in a payment integration. Follow this algorithm:

```text
1. Generate merchant_ref ONCE per withdrawal and persist it before calling the API.
2. POST /payments/init
   ├─ 2xx                         → store payment_id, wait for webhooks
   ├─ 4xx business error (47x)    → final error, release the hold (except 477, see below)
   ├─ 477 "retry later"           → retry later with the SAME merchant_ref
   └─ timeout / connection error / 5xx
        → GET /payments/{merchant_ref}/state
            ├─ found     → payment exists, continue with it (do NOT create again)
            └─ not found → retry POST with the SAME merchant_ref
3. Never create a "new" payout with a NEW merchant_ref for the same withdrawal
   unless the previous one is in a final state (unposted).
```

Next: [Payment status](04-payment-status.md) →
