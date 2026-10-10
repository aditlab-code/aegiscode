#!/usr/bin/env bash
# ==============================================================================
# Stop Hook — Olympus Completion Stop-Gate (Prove-It Gatekeeper)
# ==============================================================================
# Kontrak Antigravity:
# Input: JSON pada stdin (executionNum, terminationReason, fullyIdle, dll.)
# Output: JSON pada stdout ({"decision": "allow"|"continue", "reason": "..."})
# ==============================================================================

# Zero-Interference Guard: Jika hook eksternal aktif di lingkungan pengembang luar
if [ "${AEGIS_EXTERNAL_HOOKS_ACTIVE:-0}" = "1" ]; then
    echo '{"decision": "allow"}'
    exit 0
fi

INPUT_JSON=$(cat)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [ ! -d "${REPO_ROOT}/.aegis" ] && [ -d "${SCRIPT_DIR}/.." ]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

REPO_ROOT="${REPO_ROOT}" python3 -c "
import json
import os
import sys
from pathlib import Path

repo_root = Path(os.environ.get('REPO_ROOT', '.'))
state_file = repo_root / '.aegis' / 'lifecycle_state.json'

current_phase = 'DEFINE'
verify_passed = False

if state_file.is_file():
    try:
        data = json.loads(state_file.read_text(encoding='utf-8'))
        current_phase = data.get('current_phase', 'DEFINE')
        gates = data.get('gates', {})
        verify_passed = gates.get('verify_passed', False)
    except Exception:
        pass

# Jika agen ingin berhenti saat berada di fase BUILD dan tes belum diverifikasi
if current_phase == 'BUILD' and not verify_passed:
    output = {
        'decision': 'continue',
        'reason': 'STOP-GATE (Prove-It Pattern): Anda telah melakukan perubahan implementasi (Hephaestus) tetapi belum menjalankan tahap VERIFY (Heracles). Harap jalankan unit test hingga 100% hijau sebelum menutup tugas.'
    }
    print(json.dumps(output))
    sys.exit(0)

# Izinkan stop normal
output = {
    'decision': 'allow'
}
print(json.dumps(output))
"
