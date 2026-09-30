#!/bin/bash
# Universal review CLI wrapper
# Supports arbitrary meta- prefixes:
#   review artifact
#   meta-review artifact
#   meta-meta-review artifact
#   meta-meta-meta-review artifact
#   ... etc.

set -e

SCRIPT_NAME=$(basename "$0")
ENSEMBLE_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Detect stage count from script name
# review = 1 stage
# meta-review = 2 stages
# meta-meta-review = 3 stages
# etc.

count_metas() {
  local name="$1"
  echo "$name" | grep -o "meta-" | wc -l
}

META_COUNT=$(count_metas "$SCRIPT_NAME")
STAGE_COUNT=$((META_COUNT + 1))

# Pass through to Python CLI
python3 "$ENSEMBLE_ROOT/review/cli.py" --stages "$STAGE_COUNT" "$@"
