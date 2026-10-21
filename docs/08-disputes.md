# 08 · Disputes (escalate)

← [Errors](07-errors.md) · Next: [Balance](09-balance.md) →

Open a dispute when the result of a payment doesn't match reality — typically a customer **paid via bKash but the deposit is `unposted`** or stuck, or was booked with the wrong amount.

## Endpoint

`POST /payments/{payment_id}/escalate`

- Content type: **`multipart/form-data`**
- Path parameter: GrossPay `payment_id`

| Form field | Required | Description |
|---|---|---|
| `file1`, `file2`, `file3` | **1 to 3 files** | Evidence: bKash payment receipt / screenshot of the transaction / statement. **PDF, JPEG or PNG**, each **up to 5 MB**. |
| `comment` | no | Free text: what happened, bKash TrxID, amount, payer's wallet number, time of payment |

## Example

```bash
curl -X POST https://api-test.grosspayme.com/v1/payments/01a15cf5-f7c2-78b1-9276-87ea2c018577/escalate \
  -H "Authorization: Bearer $API_KEY" \
  -F "file1=@receipt.jpg" \
  -F "file2=@bkash_statement.pdf" \
  -F "comment=Paid via bKash, TrxID 9A1B2C3D4E, 1000 BDT at 2026-10-21 11:40 BST"
```

Do **not** set `Content-Type` manually — curl / your HTTP library sets `multipart/form-data` with the correct boundary.

Response:

```json
{ "escalated": true }
```

### Python

```python
with open("receipt.jpg", "rb") as f1:
    resp = requests.post(
        f"{BASE_URL}/payments/{payment_id}/escalate",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"file1": ("receipt.jpg", f1, "image/jpeg")},
        data={"comment": "Paid via bKash, TrxID 9A1B2C3D4E"},
        timeout=60,
    )
resp.raise_for_status()
assert resp.json().get("escalated") is True
```

### Node.js (Node 18+)

```js
import { readFile } from 'node:fs/promises';

const form = new FormData();
form.append('file1', new Blob([await readFile('receipt.jpg')], { type: 'image/jpeg' }), 'receipt.jpg');
form.append('comment', 'Paid via bKash, TrxID 9A1B2C3D4E');

const res = await fetch(`${BASE_URL}/payments/${paymentId}/escalate`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${API_KEY}` },   // no Content-Type here
  body: form,
});
```

## What makes a good dispute

- The **bKash TrxID** (10-character transaction ID from the bKash SMS/app) in `comment`.
- A receipt where amount, date/time and recipient number are readable — crop nothing important.
- Exact amount paid and the payer's bKash number.
- One dispute per payment; attach all evidence in one request.

## After escalation

`{"escalated": true}` means the dispute was registered. The outcome arrives as a normal state change of the payment — via [webhook](05-webhooks.md) (e.g. `unposted → posted` with the confirmed `amount_posted`). Your [handler](05-webhooks.md#handler-algorithm) must therefore accept a payment becoming `posted` after it was `unposted`.

## Validation errors

| Problem | Result |
|---|---|
| No files, or more than 3 | `validation` error |
| File larger than 5 MB, or not PDF/JPEG/PNG | `validation` error |
| Unknown `payment_id` | `declined` error |

Next: [Balance](09-balance.md) →
