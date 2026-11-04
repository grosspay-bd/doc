#!/usr/bin/env bash
# Usage: ./create-deposit.sh [amount] [merchant_ref] [holder_ref]
# Method / network via env vars (defaults: wallet / bkash):
#   ROUTE_KIND=wallet   ROUTE_NETWORK=nagad  HOLDER_ACCOUNT=01812345678 ./create-deposit.sh
#   ROUTE_KIND=banglaqr ROUTE_NETWORK=bkash ./create-deposit.sh
#   ROUTE_KIND=card ./create-deposit.sh               # route_network is not sent for cards
source "$(dirname "$0")/_common.sh"
AMOUNT="${1:-1000.00}"
REF="${2:-order_bd_$(date +%s)}"
HOLDER="${3:-user_bd_001}"
KIND="${ROUTE_KIND:-wallet}"
if [[ "$KIND" == "card" ]]; then NETWORK_LINE=""; else NETWORK_LINE="\"route_network\": \"${ROUTE_NETWORK:-bkash}\","; fi
if [[ -n "${HOLDER_ACCOUNT:-}" ]]; then HOLDER_ACCOUNT_LINE="\"holder_account\": \"$HOLDER_ACCOUNT\","; else HOLDER_ACCOUNT_LINE=""; fi

curl -sS -X POST "$GROSSPAY_BASE_URL/payments/init" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<JSON | pp
{
  "order_amount": "$AMOUNT",
  "order_currency": "BDT",
  "intent": "debit",
  "route_kind": "$KIND",
  $NETWORK_LINE
  $HOLDER_ACCOUNT_LINE
  "merchant_ref": "$REF",
  "holder_ref": "$HOLDER",
  "callback_uri": "${GROSSPAY_CALLBACK_URI:-https://webhook.site/your-uuid}",
  "return_uri": "${GROSSPAY_RETURN_URI:-https://your-site.com/deposit/finished}"
}
JSON
echo "merchant_ref: $REF  → open hosted_url from the response to pay" >&2
