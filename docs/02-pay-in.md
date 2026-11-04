# 02 · Pay-in (debit) — deposits

← [Getting started](01-getting-started.md) · Next: [Pay-out (credit)](03-pay-out.md) →

- [How it works](#how-it-works)
- [Methods](#methods)
- [Request](#request)
- [Response](#response)
- [Examples](#examples)
- [Redirecting the payer](#redirecting-the-payer)
- [Final result](#final-result)
- [Implementation notes](#implementation-notes)

---

## How it works

A deposit is created with `intent: "debit"` and is completed **only on the GrossPay hosted payment page**:

1. Your backend calls `POST /payments/init` with the method (`route_kind`) and network (`route_network`) you want the customer to pay with.
2. GrossPay returns `payment_id` and `hosted_url`, `posting_state: "received"`.
3. You redirect the customer to `hosted_url`.
4. The page shows payment instructions for exactly that method — the customer doesn't choose anything. For a wallet transfer the customer pays in the wallet app and enters the **TrxID** (transaction ID from the confirmation SMS / app, e.g. `9A1B2C3D4E`).
5. GrossPay confirms the payment, sends you webhooks, and returns the customer to your `return_uri`.
6. You credit the customer **only** after a verified webhook (or status) with `posting_state` `posted` / `part_posted`, using `amount_posted`.

Host-to-host (`silent_mode`) is **not available** for Bangladesh.

---

## Methods

| `route_kind` | `route_network` | What the customer does on the page |
|---|---|---|
| `wallet` | `bkash` (default), `nagad`, `rocket`, `upay` | Sends money from the wallet app and enters the TrxID |
| `banglaqr` | `bkash`, `nagad` | Scans the BanglaQR code with the wallet app |
| `card` | — (don't send) | Pays by card |

Which pairs are enabled for your account: ask your manager. Full matrix: [Payment methods & networks](11-payment-methods.md).

---

## Request

`POST /payments/init`

Headers:

```http
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

### Body fields

| Field | Type | Required | Description |
|---|---|---|---|
| `order_amount` | string | **yes** | Amount to pay, decimal string with 2 decimals: `"1000.00"` |
| `order_currency` | string | **yes** | Always `"BDT"` |
| `intent` | string | **yes** | Always `"debit"` for deposits |
| `route_kind` | string | **yes** | Payment method: `"wallet"`, `"banglaqr"` or `"card"` |
| `route_network` | string | depends | Network: `"bkash"`, `"nagad"`, `"rocket"`, `"upay"`. For `wallet` it defaults to `"bkash"` if omitted; for `banglaqr` send it; for `card` don't send it. |
| `merchant_ref` | string | **yes** | Your unique order ID, **5–64 characters**. Idempotency key — never reuse it for a different payment. |
| `holder_ref` | string | **yes** | ID of the payer in your system, **up to 128 characters**. Keep it stable per customer. |
| `holder_name` | string | no | Payer's name, e.g. `"Rahim Uddin"` |
| `holder_account` | string | no | The wallet number the payer will pay **from**, if you know it. See [below](#holder_account--payers-wallet-number). |
| `callback_uri` | string (URL) | **yes** | HTTPS URL that will receive [webhooks](05-webhooks.md) |
| `return_uri` | string (URL) | **yes** | Where the payer is sent after leaving the payment page |

Do **not** send `silent_mode`.

### `holder_account` — payer's wallet number

Optional. Send it when you know which wallet the customer will pay from (e.g. it's saved in their profile).

- **Not sent** — the payment is created as usual.
- **Sent** — normalised by the network's rules (`8801712345678` → `01712345678`, see [number formats](11-payment-methods.md#wallet-number-formats)). An invalid format is rejected with error **`474`**.
- It speeds up automatic matching of the incoming transfer, helps fraud checks and is used in disputes.
- It is returned in the payment object as `holder_account` — possibly **masked**, and after payment it may show the account the customer actually paid from.

> Don't confuse it with `holder_ref`: `holder_ref` is **your customer ID** (required); `holder_account` is a **wallet number** (optional).

### Minimal valid body (bKash)

```json
{
  "order_amount": "1000.00",
  "order_currency": "BDT",
  "intent": "debit",
  "route_kind": "wallet",
  "route_network": "bkash",
  "merchant_ref": "order_bd_0001",
  "holder_ref": "user_bd_001",
  "callback_uri": "https://your-site.com/webhooks/grosspay",
  "return_uri": "https://your-site.com/deposit/finished"
}
```

Replace every `your-site.com` URL with your own endpoints. Requests without `route_network` (`"route_kind": "wallet"` only) keep working and are processed as bKash.

---

## Response

```json
{
  "payment_id": "01a15cf5-f7c2-78b1-9276-87ea2c018577",
  "hosted_url": "https://pay.example/cmvhoj1x300001bo7cdylcnm8",
  "merchant_ref": "order_bd_0001",
  "posting_state": "received",
  "route_kind": "wallet",
  "route_network": "bkash",
  "holder_account": null,
  "rail_ref": null,
  "client_amount": null,
  "decline_note": null,
  "order_amount": "1000.00",
  "order_currency": "BDT",
  "booked_at": "2026-10-21T05:36:26.058Z",
  "posted_at": null,
  "payee_details": null,
  "valid_through": "2026-10-21T05:41:26.058Z"
}
```

> The host of `hosted_url` is shown here as a placeholder. Always use the URL **exactly as returned**; never build or modify it yourself.

| Field | What to do with it |
|---|---|
| `payment_id` | **Store it** next to your order. Needed for disputes and support. |
| `hosted_url` | Redirect the payer here. |
| `posting_state` | `received` — waiting for the payer. Do **not** credit anything yet. |
| `route_kind` / `route_network` | Echo of the method and network. |
| `valid_through` | Deadline to pay. After it the payment ends as `unposted` (`decline_note`: e.g. *Expired by timeout*). May be `null`. |
| `holder_account` | Payer's wallet, if you sent it (may be masked). |
| `rail_ref` | `null` now; after payment — the wallet TrxID. Store it for reconciliation and disputes. |
| `order_amount` / `order_currency` | Echo of what you requested. |
| `booked_at` | When the payment was created (UTC). |
| `client_amount`, `decline_note`, `posted_at`, `payee_details` | `null` at this stage. See [Payment object](06-payment-object.md). |

Once the payment is booked, the object gains the field **`amount_posted`** — the amount that was actually paid and booked. This is the number you credit.

The full field reference is in [Payment object & lifecycle](06-payment-object.md).

---

## Examples

The language examples below create a bKash deposit; requests for other methods differ only in `route_kind` / `route_network` (and optional `holder_account`) — see [Other methods](#other-methods).

### cURL

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1000.00",
    "order_currency": "BDT",
    "intent": "debit",
    "route_kind": "wallet",
    "route_network": "bkash",
    "merchant_ref": "order_bd_0001",
    "holder_ref": "user_bd_001",
    "holder_name": "Rahim Uddin",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "return_uri": "https://your-site.com/deposit/finished"
  }'
```

### Node.js (fetch, Node 18+)

```js
const res = await fetch(`${process.env.GROSSPAY_BASE_URL}/payments/init`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.GROSSPAY_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    order_amount: '1000.00',            // string, not number
    order_currency: 'BDT',
    intent: 'debit',
    route_kind: 'wallet',
    route_network: 'bkash',
    merchant_ref: order.id,             // 5–64 chars, unique
    holder_ref: user.id,
    holder_name: user.fullName,
    callback_uri: 'https://your-site.com/webhooks/grosspay',
    return_uri: `https://your-site.com/deposit/finished?order=${order.id}`,
  }),
});

const data = await res.json();
if (!res.ok || data.ok === false) {
  throw new Error(`GrossPay ${res.status}: ${data.fault?.code} ${data.fault?.detail}`);
}
await db.orders.update(order.id, { payment_id: data.payment_id, state: data.posting_state });
return redirect(data.hosted_url);
```

### Python (requests)

```python
import os, requests

resp = requests.post(
    f"{os.environ['GROSSPAY_BASE_URL']}/payments/init",
    headers={"Authorization": f"Bearer {os.environ['GROSSPAY_API_KEY']}"},
    json={
        "order_amount": "1000.00",
        "order_currency": "BDT",
        "intent": "debit",
        "route_kind": "wallet",
        "route_network": "bkash",
        "merchant_ref": "order_bd_0001",
        "holder_ref": "user_bd_001",
        "holder_name": "Rahim Uddin",
        "callback_uri": "https://your-site.com/webhooks/grosspay",
        "return_uri": "https://your-site.com/deposit/finished",
    },
    timeout=30,
)
data = resp.json()
if not resp.ok or data.get("ok") is False:
    raise RuntimeError(f"GrossPay {resp.status_code}: {data.get('fault')}")
payment_id, hosted_url = data["payment_id"], data["hosted_url"]
```

### PHP (cURL)

```php
<?php
$payload = [
    'order_amount'   => '1000.00',
    'order_currency' => 'BDT',
    'intent'         => 'debit',
    'route_kind'     => 'wallet',
    'route_network'  => 'bkash',
    'merchant_ref'   => 'order_bd_0001',
    'holder_ref'     => 'user_bd_001',
    'callback_uri'   => 'https://your-site.com/webhooks/grosspay',
    'return_uri'     => 'https://your-site.com/deposit/finished',
];

$ch = curl_init(getenv('GROSSPAY_BASE_URL') . '/payments/init');
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 30,
    CURLOPT_HTTPHEADER     => [
        'Authorization: Bearer ' . getenv('GROSSPAY_API_KEY'),
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS     => json_encode($payload),
]);
$body   = curl_exec($ch);
$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

$data = json_decode($body, true);
if ($status >= 300 || ($data['ok'] ?? true) === false) {
    throw new RuntimeException("GrossPay $status: " . json_encode($data['fault'] ?? $data));
}
header('Location: ' . $data['hosted_url'], true, 302);
```

---

### Other methods

#### Nagad deposit with `holder_account`

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1000.00",
    "order_currency": "BDT",
    "intent": "debit",
    "route_kind": "wallet",
    "route_network": "nagad",
    "holder_account": "01812345678",
    "merchant_ref": "order_bd_0002",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "return_uri": "https://your-site.com/deposit/finished"
  }'
```

#### BanglaQR deposit

The page shows a BanglaQR code; the customer scans it with the bKash or Nagad app.

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1000.00",
    "order_currency": "BDT",
    "intent": "debit",
    "route_kind": "banglaqr",
    "route_network": "bkash",
    "merchant_ref": "order_bd_0003",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "return_uri": "https://your-site.com/deposit/finished"
  }'
```

#### Card deposit

`route_network` is not sent for cards.

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1000.00",
    "order_currency": "BDT",
    "intent": "debit",
    "route_kind": "card",
    "merchant_ref": "order_bd_0004",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "return_uri": "https://your-site.com/deposit/finished"
  }'
```

---

## Redirecting the payer

- Redirect with a normal `302` or open `hosted_url` in the same tab. In mobile apps, open it in the system browser or an in-app browser that can switch to the bKash app.
- Do not embed the page in an `<iframe>` — app switching and some browsers' cookie rules can break the flow.
- `return_uri` is a **UX redirect only**. Reaching it does **not** mean the payment succeeded (the payer can come back after cancelling, or before the payment is confirmed). On the return page, show "Payment is being processed" and read the result from your own database, which is updated by webhooks.

---

## Final result

| `posting_state` | Meaning | What you do |
|---|---|---|
| `received` | Waiting for the payer | Nothing; show "pending" |
| `queued` | Payment confirmed, being booked | Nothing yet; show "processing" |
| `posted` | Fully paid and booked | Credit **`amount_posted`** |
| `part_posted` | Partially paid | Credit **`amount_posted`** (it is lower than `order_amount`) |
| `unposted` | Declined, cancelled or expired | Mark the order failed; nothing to credit. Reason in `decline_note`. |
| `returned` | Previously booked money was rolled back (reversal, refund, chargeback) | **Debit back** what you credited for this payment |

> **Always credit `amount_posted`, never `order_amount`.** The payer may pay a different amount than requested; `amount_posted` is what was actually booked.

See [Payment object & lifecycle](06-payment-object.md#how-to-book-balances) for the full accounting rules.

---

## Implementation notes

- **One active deposit per customer.** If the same `holder_ref` already has an active payment, `POST /payments/init` returns business error `470`. Reuse the existing `hosted_url` for that customer instead of creating a new payment, or wait until the previous one becomes final.
- **Idempotency.** `merchant_ref` is the idempotency key. If `POST /payments/init` times out or returns `5xx`, first call `GET /payments/{merchant_ref}/state`: if the payment exists, continue with it; if it does not, repeat the create request with the **same** `merchant_ref`. Never generate a new `merchant_ref` for a retry of the same order. Details: [Errors → retry policy](07-errors.md#retry-policy).
- **Limits.** Amounts outside your configured minimum/maximum return `475` / `476`; exceeding the merchant limit returns `471`. Ask your manager for the current limits and validate amounts in your UI before calling the API.
- **Payment deadline.** A deposit that is not paid before `valid_through` ends as `unposted` (e.g. *Expired by timeout*). Redirect the customer to `hosted_url` right away, and create a new payment (new `merchant_ref`) if they come back later.
- **Method not enabled.** A `route_kind` + `route_network` pair that is not enabled for your account returns a validation error with `fault.at: ["route_network"]`. Show only the methods that are enabled for you.
- **Amounts as strings.** Send `"1000.00"`, not `1000` or `1000.0`.
- **Do not trust the browser.** Never credit based on the customer reaching `return_uri`, query parameters or front-end callbacks — only on a webhook with a valid signature or a server-side status call.

Next: [Pay-out (credit)](03-pay-out.md) →
