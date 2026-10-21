#!/usr/bin/env bash
# Usage: ./create-payout.sh <bkash_number> [amount] [merchant_ref] [holder_ref]
source "$(dirname "$0")/_common.sh"
WALLET="${1:?usage: $0 <bkash_number> [amount] [merchant_ref] [holder_ref]}"
AMOUNT="${2:-1500.00}"
REF="${3:-withdraw_bd_$(date +%s)}"
HOLDER="${4:-user_bd_001}"

curl -sS -X POST "$GROSSPAY_BASE_URL/payments/init" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<JSON | pp
{
  "order_amount": "$AMOUNT",
  "order_currency": "BDT",
  "intent": "credit",
  "route_kind": "wallet",
  "merchant_ref": "$REF",
  "holder_ref": "$HOLDER",
  "callback_uri": "${GROSSPAY_CALLBACK_URI:-https://webhook.site/your-uuid}",
  "credit_details": { "wallet_number": "$WALLET" }
}
JSON
echo "merchant_ref: $REF" >&2
