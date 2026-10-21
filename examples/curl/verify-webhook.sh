#!/usr/bin/env bash
# Verify a saved webhook manually.
# Usage: ./verify-webhook.sh <public.pem> <body.json> <signature-v1 value>
# body.json must contain the raw body exactly as received (no reformatting).
set -euo pipefail
PUB="${1:?public key pem}"; BODY="${2:?raw body file}"; SIG="${3:?signature-v1 header value}"
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
printf '%s' "$SIG" | base64 -d > "$TMP"
openssl dgst -sha256 -verify "$PUB" -signature "$TMP" "$BODY"
