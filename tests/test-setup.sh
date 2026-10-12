#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
help="$("$REPO_ROOT/scripts/setup.sh" --help)"
printf '%s\n' "$help" | grep -q "configuration"
printf '%s\n' "$help" | grep -q -- "--skip-connect"

python_path="$(command -v python3)"
resolved="$(
    DSH_SCNET_PYTHON="$python_path" \
        bash -c 'set -euo pipefail; . "$1/scripts/_common.sh"; resolve_python' _ "$REPO_ROOT"
)"
[ "$resolved" = "$python_path" ]

if DSH_SCNET_PYTHON="$REPO_ROOT/does-not-exist" \
    bash -c 'set -euo pipefail; . "$1/scripts/_common.sh"; resolve_python' _ "$REPO_ROOT"; then
    echo "invalid injected Python path should fail" >&2
    exit 1
fi

echo "setup panel smoke tests passed"
