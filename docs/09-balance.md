# 09 · Balance

← [Disputes](08-disputes.md) · Next: [Go-live checklist](10-go-live-checklist.md) →

## Endpoint

`GET /partner/ledger_balance`

Returns the balance of your merchant account.

```bash
curl https://api-test.grosspayme.com/v1/partner/ledger_balance \
  -H "Authorization: Bearer $API_KEY"
```

## Response

```json
{
  "available_balance": "0.00",
  "curr_alpha": "BDT"
}
```

| Field | Type | Description |
|---|---|---|
| `available_balance` | string (decimal) | Funds available on your merchant account |
| `curr_alpha` | string | Currency code (ISO 4217 alpha), `"BDT"` |

## Typical uses

- **Before a payout batch** — make sure `available_balance` covers the sum of the payouts you are about to send, otherwise some of them will be rejected.
- **Monitoring** — poll every few minutes and alert your finance team when the balance falls below a threshold, so payouts don't stop.
- **Reconciliation** — compare with your internal ledger daily.

Don't call it before every single payout in a tight loop; cache the value for a short time (e.g. 30–60 s) and rely on error handling for the rare race.

Next: [Go-live checklist](10-go-live-checklist.md) →
