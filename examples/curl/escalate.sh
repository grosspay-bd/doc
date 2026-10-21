#!/usr/bin/env bash
# Usage: ./escalate.sh <payment_id> "<comment>" <file1> [file2] [file3]
# Files: 1–3, PDF/JPEG/PNG, up to 5 MB each.
source "$(dirname "$0")/_common.sh"
PID="${1:?usage: $0 <payment_id> \"<comment>\" <file1> [file2] [file3]}"
COMMENT="${2:-}"
shift 2 || true
[[ $# -ge 1 && $# -le 3 ]] || { echo "attach 1 to 3 files" >&2; exit 1; }
ARGS=(); i=1
for f in "$@"; do ARGS+=(-F "file$i=@$f"); i=$((i+1)); done
curl -sS -X POST "$GROSSPAY_BASE_URL/payments/$PID/escalate" \
  -H "Authorization: Bearer $GROSSPAY_API_KEY" \
  "${ARGS[@]}" -F "comment=$COMMENT" | pp
