#!/usr/bin/env bash
# ==============================================================================
# PostToolUse Hook — CodeGraph Refresh & Status Sync
# ==============================================================================
# Kontrak Antigravity:
# Input: JSON pada stdin (stepIdx, error, dll.)
# Output: JSON kosong pada stdout ({})
# ==============================================================================

# Zero-Interference Guard: Jika hook eksternal aktif di lingkungan pengembang luar
if [ "${AEGIS_EXTERNAL_HOOKS_ACTIVE:-0}" = "1" ]; then
    echo "{}"
    exit 0
fi

INPUT_JSON=$(cat)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [ ! -d "${REPO_ROOT}/.aegis" ] && [ -d "${SCRIPT_DIR}/.." ]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

# Refresh CodeGraph cache jika script ada
if [ -x "${SCRIPT_DIR}/sdd-codegraph-cache.sh" ]; then
    "${SCRIPT_DIR}/sdd-codegraph-cache.sh" >/dev/null 2>&1 || true
fi

# Output JSON kosong sesuai kontrak
echo "{}"
