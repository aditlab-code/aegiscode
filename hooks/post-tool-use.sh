#!/usr/bin/env bash
# ==============================================================================
# PostToolUse Hook — CodeGraph Refresh & Status Sync
# ==============================================================================
# Kontrak Antigravity:
# Input: JSON pada stdin (stepIdx, error, dll.)
# Output: JSON kosong pada stdout ({})
# ==============================================================================

set -euo pipefail

INPUT_JSON=$(cat)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Refresh CodeGraph cache jika script ada
if [ -x "${REPO_ROOT}/hooks/sdd-codegraph-cache.sh" ]; then
    "${REPO_ROOT}/hooks/sdd-codegraph-cache.sh" >/dev/null 2>&1 || true
fi

# Output JSON kosong sesuai kontrak
echo "{}"
