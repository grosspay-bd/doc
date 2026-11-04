#!/usr/bin/env bash
# Payout to a mobile wallet.
# Usage: ./create-payout.sh <wallet_number> [amount] [merchant_ref] [holder_ref]
# Network via env var (default bkash): ROUTE_NETWORK=nagad ./create-payout.sh 01812345678
source "$(dirname "$0")/_common.sh"
WALLET="${1:?usage: $0 <wallet_number> [amount] [merchant_ref] [holder_ref]}"
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
  "route_network": "${ROUTE_NETWORK:-bkash}",
  "merchant_ref": "$REF",
  "holder_ref": "$HOLDER",
  "callback_uri": "${GROSSPAY_CALLBACK_URI:-https://webhook.site/your-uuid}",
  "credit_details": { "wallet_number": "$WALLET" }
}
JSON
echo "merchant_ref: $REF" >&2
