#!/usr/bin/env bash
# Assert local payment.v1 matches contracts/payment.v1.PIN.json (export for consumers).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PATH_PAYMENT="backend/contracts/payment.v1.json"
PIN="contracts/payment.v1.PIN.json"
test -f "$PATH_PAYMENT"
test -f "$PIN"
BLOB="$(git hash-object "$PATH_PAYMENT")"
WANT="$(python3 -c "import json;print(json.load(open('$PIN',encoding='utf-8'))['git_blob'])" 2>/dev/null \
  || python -c "import json;print(json.load(open(r'$PIN',encoding='utf-8'))['git_blob'])")"
if [[ "$BLOB" != "$WANT" ]]; then
  echo "::error::payment.v1 PIN drift blob=$BLOB want=$WANT — refresh $PIN after intentional contract bump" >&2
  exit 1
fi
echo "OK payment.v1 pin blob=$BLOB"
