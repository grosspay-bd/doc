# 11 · Payment methods & networks

← [Go-live checklist](10-go-live-checklist.md) · [Back to README](../README.md)

Every payment is routed by two fields you send in `POST /payments/init`:

| Field | Meaning | Example |
|---|---|---|
| `route_kind` | **Payment method** | `wallet`, `banglaqr`, `card`, `bank` |
| `route_network` | **Network** — the wallet or the bank | `bkash`, `nagad`, a bank code |

You choose the method and network on your side and send them in the request. **The customer does not choose anything on the payment page.**

- [Supported combinations](#supported-combinations)
- [Backward compatibility](#backward-compatibility)
- [Which combinations are enabled for you](#which-combinations-are-enabled-for-you)
- [Wallet number formats](#wallet-number-formats)
- [Bank directory](#bank-directory)
- [Bank payout timing](#bank-payout-timing)

---

## Supported combinations

| `route_kind` | Pay-in (`intent: debit`) | Pay-out (`intent: credit`) | `route_network` |
|---|---|---|---|
| `wallet` | Transfer from a mobile wallet, hosted page | To a wallet number | `bkash`, `nagad`, `rocket`, `upay` |
| `banglaqr` | Customer scans a BanglaQR code in the wallet app, hosted page | — | `bkash`, `nagad` |
| `card` | Card payment, hosted page | — | **not sent** |
| `bank` | — | To a bank account | **required**, bank code from the [bank directory](#bank-directory) |

All pay-ins go through the hosted payment page (`hosted_url`). Host-to-host (`silent_mode`) is not available.

Rules:

- Values are **lowercase**.
- New networks and banks may be added to these lists without a new API version — don't hard-code a closed list in validation that rejects unknown values coming *back* from GrossPay.
- `rocket` and `upay` are enabled per merchant — check with your manager before using them.

### Quick reference — request examples

| Scenario | `intent` | `route_kind` | `route_network` | Example |
|---|---|---|---|---|
| Deposit via bKash | `debit` | `wallet` | `bkash` (or omit) | [Pay-in](02-pay-in.md#examples) |
| Deposit via Nagad | `debit` | `wallet` | `nagad` | [Pay-in → Nagad](02-pay-in.md#nagad-deposit-with-holder_account) |
| Deposit via BanglaQR | `debit` | `banglaqr` | `bkash` / `nagad` | [Pay-in → BanglaQR](02-pay-in.md#banglaqr-deposit) |
| Deposit by card | `debit` | `card` | — | [Pay-in → card](02-pay-in.md#card-deposit) |
| Payout to bKash | `credit` | `wallet` | `bkash` (or omit) | [Pay-out](03-pay-out.md#examples) |
| Payout to Nagad | `credit` | `wallet` | `nagad` | [Pay-out → Nagad](03-pay-out.md#nagad-payout) |
| Payout to a bank account | `credit` | `bank` | bank code | [Pay-out → bank](03-pay-out.md#pay-out-to-a-bank-account) |

---

## Backward compatibility

- `route_kind: "wallet"` **without** `route_network` is treated as `bkash`. Existing bKash integrations keep working with no changes.
- For `route_kind: "bank"`, `route_network` is **required**.
- We still recommend sending `route_network` explicitly for every request — it makes logs and reconciliation unambiguous.

---

## Which combinations are enabled for you

The `route_kind` + `route_network` pairs available to your account are configured by GrossPay, separately for pay-ins and pay-outs. Ask your manager which pairs are enabled.

A request with a pair that is not enabled for your account is rejected with a **validation error**:

```json
{
  "ok": false,
  "fault": {
    "class": "validation",
    "code": "400",
    "detail": "route_network nagad is not enabled for this merchant",
    "at": ["route_network"]
  }
}
```

*`code` and `detail` are illustrative — rely on `fault.class` and `fault.at`.*

---

## Wallet number formats

Applies to `credit_details.wallet_number` (pay-outs) and `holder_account` (pay-ins). GrossPay strips everything except digits and the `880` / `+880` country prefix, then checks the result by network:

| `route_network` | Format after normalisation | Regular expression | Example |
|---|---|---|---|
| `bkash` | 11-digit mobile number | `^01[3-9]\d{8}$` | `01712345678` |
| `nagad` | 11-digit mobile number | `^01[3-9]\d{8}$` | `01812345678` |
| `upay` | 11-digit mobile number | `^01[3-9]\d{8}$` | `01912345678` |
| `rocket` | 12 digits: mobile number + check digit | `^01[3-9]\d{9}$` | `017123456781` |

Accepted input forms: `01712345678`, `8801712345678`, `+880 1712-345678`.

An invalid number for the selected network is rejected with business error **`474`**. A valid format does not prove that the wallet exists: a payout to a non-existent wallet ends as `unposted` with the reason in `decline_note`.

Reference normaliser (JavaScript):

```js
const WALLET_RULES = {
  bkash:  /^01[3-9]\d{8}$/,
  nagad:  /^01[3-9]\d{8}$/,
  upay:   /^01[3-9]\d{8}$/,
  rocket: /^01[3-9]\d{9}$/,
};

function normalizeWallet(input, network = 'bkash') {
  let d = String(input).replace(/\D/g, '');
  if (d.startsWith('880')) d = d.slice(2);
  const rule = WALLET_RULES[network];
  return rule && rule.test(d) ? d : null;   // null = invalid
}
```

Python and PHP versions: [`examples/python-client`](../examples/python-client/grosspay_bd.py), [Pay-out → number rules](03-pay-out.md#wallet-number-rules).

---

## Bank directory

Use the **code** as `route_network` for `route_kind: "bank"` pay-outs.

| Code (`route_network`) | Bank | `routing_number` required |
|---|---|---|
| `<bank_code>` | *Bank name* | yes / no |

<!-- TODO before publishing: fill in the list of supported banks and their codes. Keep codes lowercase. -->

If your target bank is not in the list, contact your manager.

Bank account fields for the payout (`credit_details`):

| Field | Required | Format |
|---|---|---|
| `account_number` | **yes** | Digits only; length is checked per bank |
| `payee_title` | **yes** | Account holder name exactly as registered at the bank |
| `routing_number` | depends on the bank (see table) | 9 digits |
| `branch_name` | no | Free text |

Details and examples: [Pay-out → bank account](03-pay-out.md#pay-out-to-a-bank-account).

---

## Bank payout timing

GrossPay chooses the clearing rail itself — you don't send it:

| Rail | Speed |
|---|---|
| **NPSB** | Online, usually within minutes |
| **BEFTN** | Batches, **business days only** |

Weekends in Bangladesh are **Friday and Saturday**. A bank payout can therefore stay in `queued` until the next business day.

> **Do not cancel or retry a bank payout because it is "taking too long".** The payout is still in progress; a second payout with a new `merchant_ref` can pay the customer twice. Wait for the webhook.

A bank can return a payout that was already `posted` (wrong or closed account). This arrives as the usual `posted → returned` transition — give the money back to the customer. See [Payment object → lifecycle](06-payment-object.md#lifecycle).
