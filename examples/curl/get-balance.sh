#!/usr/bin/env bash
# Usage: ./get-balance.sh
source "$(dirname "$0")/_common.sh"
curl -sS "$GROSSPAY_BASE_URL/partner/ledger_balance" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" | pp
