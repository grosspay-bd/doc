#!/usr/bin/env bash
# Sign a sample webhook with YOUR OWN test key pair and send it to a local receiver.
#
# Usage: ./send-test-webhook.sh <url> <posting_state> [client_amount] [amount_posted] [payment_id] [merchant_ref]
# Example (payout 15000, fee 450):
#   ./send-test-webhook.sh http://127.0.0.1:3000/webhooks/grosspay posted 15000.00 15450.00
#
# First run creates test_private.pem / test_public.pem in this folder.
# Start the receiver with GROSSPAY_WEBHOOK_PUBLIC_KEY_FILE=test_public.pem and GROSSPAY_ALLOWED_IPS='*'.
set -euo pipefail
cd "$(dirname "$0")"
URL="${1:?url}"; STATE="${2:?posting_state}"; CLIENT="${3:-}"; POSTED="${4:-$CLIENT}"
PID="${5:-01a15cf5-f7c2-78b1-9276-87ea2c018577}"; REF="${6:-order_bd_0001}"

[[ -f test_private.pem ]] || {
  openssl genrsa -out test_private.pem 2048 2>/dev/null
  openssl rsa -in test_private.pem -pubout -out test_public.pem 2>/dev/null
  echo "generated test_private.pem / test_public.pem" >&2
}

if [[ -n "$CLIENT" ]]; then CA="\"$CLIENT\""; else CA=null; fi
if [[ -n "$POSTED" ]]; then AP="\"$POSTED\""; else AP=null; fi
BODY=$(printf '{"payment_id":"%s","merchant_ref":"%s","posting_state":"%s","amount_posted":%s,"client_amount":%s,"decline_note":null,"order_amount":"1000.00","order_currency":"BDT","booked_at":"2026-10-21T05:36:26.058Z","posted_at":null,"payee_details":null,"valid_through":null}' \
  "$PID" "$REF" "$STATE" "$AP" "$CA")
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -sign test_private.pem | base64 | tr -d '\n')

curl -sS -o /dev/null -w "HTTP %{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "signature-v1: $SIG" \
  --data-binary "$BODY"
