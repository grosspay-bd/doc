#!/usr/bin/env bash
# Usage: ./get-state.sh <payment_id | merchant_ref>
source "$(dirname "$0")/_common.sh"
ID="${1:?usage: $0 <payment_id | merchant_ref>}"
curl -sS "$GROSSPAY_BASE_URL/payments/$ID/state" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" | pp
