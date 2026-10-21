#!/usr/bin/env bash
# Shared setup: loads .env next to this script and checks required variables.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$DIR/.env" ]]; then set -a; source "$DIR/.env"; set +a; fi
: "${GROSSPAY_BASE_URL:?set GROSSPAY_BASE_URL (see .env.example)}"
: "${GROSSPAY_API_KEY:?set GROSSPAY_API_KEY (see .env.example)}"
# Pretty-print JSON if jq is installed
pp() { if command -v jq >/dev/null; then jq .; else cat; echo; fi; }
