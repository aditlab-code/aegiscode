#!/usr/bin/env bash
# Session Start Hook for Olympus Agent Framework & CodeGraph
set -euo pipefail

# Zero-Interference Guard: Jika hook eksternal aktif di lingkungan pengembang luar
if [ "${AEGIS_EXTERNAL_HOOKS_ACTIVE:-0}" = "1" ]; then
    exit 0
fi

# 1. Pastikan RTK tersedia
if command -v rtk >/dev/null 2>&1; then
    echo "[Olympus Hook] RTK utility detected at $(which rtk)"
else
    echo "[Olympus Hook] Warning: RTK utility not in PATH. Fallback to native tools (rg, find, git)."
fi

# 2. Pastikan direktori .aegis/ dan data/ ada
mkdir -p .aegis/cache
mkdir -p data

# 3. Validasi kesiapan CodeGraph store dan inisialisasi state lifecycle secara pasif
if [ -f "data/aegis.db" ] || [ -d ".aegis" ]; then
    echo "[Olympus Hook] CodeGraph storage ready."
fi

# Inisialisasi state mandiri tanpa mengimpor runtime agent_ai
python3 -c "
import json
from pathlib import Path
state_file = Path('.aegis/lifecycle_state.json')
if not state_file.is_file():
    state_file.parent.mkdir(parents=True, exist_ok=True)
    default_state = {
        'version': '1.0',
        'current_phase': 'DEFINE',
        'active_persona': 'athena-planner',
        'active_skills': ['interview-me', 'spec-driven-development'],
        'gates': {'define_passed': False, 'plan_passed': False, 'build_passed': False, 'verify_passed': False, 'review_passed': False, 'ship_passed': False}
    }
    state_file.write_text(json.dumps(default_state, indent=2), encoding='utf-8')
" >/dev/null 2>&1 || true

echo "[Olympus Hook] Olympus Agent Framework initialized. Active personas: zeus, athena, hermes, hephaestus, heracles, themis."
exit 0
