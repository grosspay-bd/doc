#!/usr/bin/env bash
# Usage: ./create-deposit.sh [amount] [merchant_ref] [holder_ref]
source "$(dirname "$0")/_common.sh"
AMOUNT="${1:-1000.00}"
REF="${2:-order_bd_$(date +%s)}"
HOLDER="${3:-user_bd_001}"

curl -sS -X POST "$GROSSPAY_BASE_URL/payments/init" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<JSON | pp
{
  "order_amount": "$AMOUNT",
  "order_currency": "BDT",
  "intent": "debit",
  "route_kind": "wallet",
  "merchant_ref": "$REF",
  "holder_ref": "$HOLDER",
  "callback_uri": "${GROSSPAY_CALLBACK_URI:-https://webhook.site/your-uuid}",
  "return_uri": "${GROSSPAY_RETURN_URI:-https://your-site.com/deposit/finished}"
}
JSON
echo "merchant_ref: $REF  → open hosted_url from the response to pay" >&2
