#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
help="$("$REPO_ROOT/scripts/setup.sh" --help)"
printf '%s\n' "$help" | grep -q "first-use"
printf '%s\n' "$help" | grep -q -- "--skip-connect"

echo "setup panel smoke tests passed"
