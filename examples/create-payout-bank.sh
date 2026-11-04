#!/usr/bin/env bash
# Payout to a bank account.
# Usage: ./create-payout-bank.sh <bank_code> <account_number> "<payee_title>" [routing_number] [amount] [merchant_ref]
# bank_code: see docs/11-payment-methods.md#bank-directory. payee_title must match the bank records.
source "$(dirname "$0")/_common.sh"
BANK="${1:?usage: $0 <bank_code> <account_number> \"<payee_title>\" [routing_number] [amount] [merchant_ref]}"
ACCOUNT="${2:?account_number required}"
TITLE="${3:?payee_title required}"
ROUTING="${4:-}"
AMOUNT="${5:-25000.00}"
REF="${6:-withdraw_bd_$(date +%s)}"
if [[ -n "$ROUTING" ]]; then ROUTING_LINE=", \"routing_number\": \"$ROUTING\""; else ROUTING_LINE=""; fi

curl -sS -X POST "$GROSSPAY_BASE_URL/payments/init" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<JSON | pp
{
  "order_amount": "$AMOUNT",
  "order_currency": "BDT",
  "intent": "credit",
  "route_kind": "bank",
  "route_network": "$BANK",
  "merchant_ref": "$REF",
  "holder_ref": "${HOLDER_REF:-user_bd_001}",
  "callback_uri": "${GROSSPAY_CALLBACK_URI:-https://webhook.site/your-uuid}",
  "credit_details": { "account_number": "$ACCOUNT", "payee_title": "$TITLE"$ROUTING_LINE }
}
JSON
echo "merchant_ref: $REF  (bank payouts may stay 'queued' until the next business day — do not re-send)" >&2
