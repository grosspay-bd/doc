# 03 · Pay-out (credit) — withdrawals to wallets and bank accounts

← [Pay-in (debit)](02-pay-in.md) · Next: [Payment status](04-payment-status.md) →

- [How it works](#how-it-works)
- [Destinations](#destinations)
- [Request](#request)
- [Wallet number rules](#wallet-number-rules)
- [Response](#response)
- [Examples](#examples)
- [Pay-out to a bank account](#pay-out-to-a-bank-account)
- [Final result and customer balance](#final-result-and-customer-balance)
- [Safe retries — avoiding double payouts](#safe-retries--avoiding-double-payouts)

---

## How it works

A payout sends money from your GrossPay balance to a customer's **mobile wallet** (bKash, Nagad, Rocket, Upay) or **bank account**. It is fully server-to-server: there is no payment page and no customer interaction.

1. Reserve (hold) the amount on the customer's balance in **your** system.
2. Call `POST /payments/init` with `intent: "credit"`, the destination (`route_kind` + `route_network`) and the recipient's details.
3. GrossPay returns `payment_id`, `posting_state: "received"`.
4. GrossPay sends the transfer and notifies you via [webhooks](05-webhooks.md).
5. On `posted` — finalise the withdrawal. On `unposted` — release the hold back to the customer.
6. If a payout that was `posted` later becomes `returned` — credit the amount back to the customer.

The payout amount is taken from your merchant balance — check it with [`GET /partner/ledger_balance`](09-balance.md).

---

## Destinations

| Destination | `route_kind` | `route_network` | Recipient details (`credit_details`) |
|---|---|---|---|
| bKash wallet | `wallet` | `bkash` (default if omitted) | `wallet_number` |
| Nagad wallet | `wallet` | `nagad` | `wallet_number` |
| Rocket wallet | `wallet` | `rocket` | `wallet_number` |
| Upay wallet | `wallet` | `upay` | `wallet_number` |
| Bank account | `bank` | bank code, **required** | `account_number`, `payee_title`, `routing_number`* |

\* `routing_number` is required for some banks — see the [bank directory](11-payment-methods.md#bank-directory).

Which destinations are enabled for your account: ask your manager. A destination that is not enabled returns a validation error with `fault.at: ["route_network"]`.

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
| `route_kind` | string | **yes** | `"wallet"` or `"bank"` |
| `route_network` | string | for `bank` | Wallet network (`"bkash"`, `"nagad"`, `"rocket"`, `"upay"`) or bank code. For `wallet` defaults to `"bkash"`. |
| `merchant_ref` | string | **yes** | Your unique withdrawal ID, **5–64 characters**. Idempotency key. |
| `holder_ref` | string | **yes** | ID of the recipient (your customer) in your system |
| `callback_uri` | string (URL) | **yes** | HTTPS URL for [webhooks](05-webhooks.md) |
| `credit_details` | object | **yes** | Recipient details, see below |

`return_uri` is not used for payouts.

### `credit_details` for wallets (`route_kind: "wallet"`)

| Field | Required | Description |
|---|---|---|
| `wallet_number` | **yes** | Recipient's wallet number, see [rules](#wallet-number-rules) |
| `payee_title` | no | Recipient's name, e.g. `"Rahim Uddin"` |

### `credit_details` for bank accounts (`route_kind: "bank"`)

| Field | Required | Description |
|---|---|---|
| `account_number` | **yes** | Digits only; length is checked per bank |
| `payee_title` | **yes** | Account holder name exactly as registered at the bank |
| `routing_number` | depends on the bank | 9 digits; required where the [bank directory](11-payment-methods.md#bank-directory) says so |
| `branch_name` | no | Branch name, free text |

---

## Wallet number rules

GrossPay accepts the number in any of these forms and normalises it:

| You send | Normalised to |
|---|---|
| `01712345678` | `01712345678` |
| `8801712345678` | `01712345678` |
| `+880 1712-345678` | `01712345678` |

After normalisation the number must match the format of the selected network:

| `route_network` | Format | Regular expression |
|---|---|---|
| `bkash`, `nagad`, `upay` | 11 digits, starts with `01`, third digit 3–9 | `^01[3-9]\d{8}$` |
| `rocket` | 12 digits: mobile number + check digit | `^01[3-9]\d{9}$` |

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
const WALLET_RULES = {
  bkash:  /^01[3-9]\d{8}$/,
  nagad:  /^01[3-9]\d{8}$/,
  upay:   /^01[3-9]\d{8}$/,
  rocket: /^01[3-9]\d{9}$/,
};

function normalizeWallet(input, network = 'bkash') {
  let d = String(input).replace(/\D/g, '');   // "+880 1712-345678" -> "8801712345678"
  if (d.startsWith('880')) d = d.slice(2);     // "8801712345678"    -> "01712345678"
  const rule = WALLET_RULES[network];
  return rule && rule.test(d) ? d : null;      // null = invalid
}
```

```python
# Python
import re

WALLET_RULES = {
    "bkash": r"01[3-9]\d{8}",
    "nagad": r"01[3-9]\d{8}",
    "upay": r"01[3-9]\d{8}",
    "rocket": r"01[3-9]\d{9}",
}

def normalize_wallet(value: str, network: str = "bkash") -> str | None:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("880"):
        digits = digits[2:]
    rule = WALLET_RULES.get(network)
    return digits if rule and re.fullmatch(rule, digits) else None
```

```php
// PHP
function normalizeWallet(string $value, string $network = 'bkash'): ?string {
    $rules = [
        'bkash'  => '/^01[3-9]\d{8}$/',
        'nagad'  => '/^01[3-9]\d{8}$/',
        'upay'   => '/^01[3-9]\d{8}$/',
        'rocket' => '/^01[3-9]\d{9}$/',
    ];
    $d = preg_replace('/\D/', '', $value);
    if (str_starts_with($d, '880')) { $d = substr($d, 2); }
    return isset($rules[$network]) && preg_match($rules[$network], $d) ? $d : null;
}
```

> Format validation only proves the number *looks* valid. It does not prove the wallet exists; a payout to such a number fails later and is reported via webhook as `unposted` with the reason in `decline_note`.

---

## Response

Same structure as the deposit response, **without** `hosted_url`. `payee_details` contains the normalised recipient details:

```json
{
  "payment_id": "01a15d02-3b9e-7c11-8a4f-5e2d9c1b7a60",
  "merchant_ref": "withdraw_bd_0002",
  "posting_state": "received",
  "route_kind": "wallet",
  "route_network": "nagad",
  "rail_ref": null,
  "client_amount": null,
  "decline_note": null,
  "order_amount": "1500.00",
  "order_currency": "BDT",
  "booked_at": "2026-10-21T06:02:11.410Z",
  "posted_at": null,
  "payee_details": {
    "wallet_number": "01812345678",
    "payee_title": "Rahim Uddin"
  },
  "valid_through": null
}
```

`payment_id` above is illustrative. Store the returned `payment_id` together with your withdrawal record. After the payout is sent, `rail_ref` contains the wallet transaction ID or the bank reference — keep it for reconciliation and for answering the customer.

---

## Examples

### cURL — bKash payout

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1500.00",
    "order_currency": "BDT",
    "intent": "credit",
    "route_kind": "wallet",
    "route_network": "bkash",
    "merchant_ref": "withdraw_bd_0001",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "credit_details": {
      "wallet_number": "01712345678",
      "payee_title": "Rahim Uddin"
    }
  }'
```

### Nagad payout

Same request, different `route_network`:

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "1500.00",
    "order_currency": "BDT",
    "intent": "credit",
    "route_kind": "wallet",
    "route_network": "nagad",
    "merchant_ref": "withdraw_bd_0002",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "credit_details": {
      "wallet_number": "01812345678",
      "payee_title": "Rahim Uddin"
    }
  }'
```

### Node.js

```js
const network = form.network;                     // 'bkash' | 'nagad' | 'rocket' | 'upay'
const wallet = normalizeWallet(form.wallet, network);
if (!wallet) return badRequest('Enter a valid wallet number, e.g. 01712345678');

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
    route_network: network,
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
        "route_network": "bkash",
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

## Pay-out to a bank account

`route_kind: "bank"`, the bank code in `route_network`, account details in `credit_details`. GrossPay chooses the clearing rail (NPSB or BEFTN) — you don't send it.

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/init \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "order_amount": "25000.00",
    "order_currency": "BDT",
    "intent": "credit",
    "route_kind": "bank",
    "route_network": "<bank_code>",
    "merchant_ref": "withdraw_bd_0003",
    "holder_ref": "user_bd_001",
    "callback_uri": "https://your-site.com/webhooks/grosspay",
    "credit_details": {
      "account_number": "1234567890123",
      "payee_title": "Rahim Uddin",
      "routing_number": "123456789"
    }
  }'
```

Replace `<bank_code>` with a code from the [bank directory](11-payment-methods.md#bank-directory).

**Validation**

| Problem | Result |
|---|---|
| `route_network` missing for `bank` | validation error, `fault.at: ["route_network"]` |
| Bank not enabled for your account | validation error, `fault.at: ["route_network"]` |
| `payee_title` missing | validation error |
| Invalid `account_number` or `routing_number` | business error `474` |

**Timing.** NPSB is online; BEFTN runs in batches on **business days only** (weekends in Bangladesh are **Friday and Saturday**). A bank payout can stay in `queued` until the next business day.

> **⚠️ Never cancel or re-send a bank payout because it is slow.** It is still being processed. Creating a second payout (new `merchant_ref`) can pay the customer twice. Wait for the webhook.

**Returns.** A bank can return a payout that was already credited (wrong or closed account). You receive the usual `posted → returned` transition — give the money back to the customer.

---

## Final result and customer balance

| `posting_state` | Meaning | Customer balance in your system |
|---|---|---|
| `received` | Accepted, waiting to be sent | Keep the hold |
| `queued` | Being processed (bank payouts: may last until the next business day) | Keep the hold |
| `posted` | Sent successfully | Convert the hold into a final debit |
| `part_posted` | Sent partially; actual amount in `amount_posted` | Debit `amount_posted`, release the rest of the hold |
| `unposted` | Not sent (declined, cancelled, expired, wallet/account does not exist) | Release the full hold; reason in `decline_note` |
| `returned` | Was sent, then rolled back (reversal, bank return) | Credit the previously debited amount back to the customer |

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
4. A payout in received/queued is NOT final — never re-send it because it is slow.
```

Next: [Payment status](04-payment-status.md) →
