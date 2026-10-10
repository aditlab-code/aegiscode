#!/usr/bin/env bash
# ==============================================================================
# PreInvocation Hook — Olympus Persona & Skill Context Injector
# ==============================================================================
# Kontrak Antigravity:
# Input: JSON pada stdin (conversationId, workspacePaths, stepIdx, dll.)
# Output: JSON pada stdout ({"injectSteps": [{"ephemeralMessage": "..."}]})
# ==============================================================================

# Zero-Interference Guard: Jika hook eksternal aktif di lingkungan pengembang luar
if [ "${AEGIS_EXTERNAL_HOOKS_ACTIVE:-0}" = "1" ]; then
    echo '{"injectSteps": []}'
    exit 0
fi

# Baca stdin
INPUT_JSON=$(cat)

# Dapatkan direktori root repositori secara dinamis (.agents/hooks -> root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [ ! -d "${REPO_ROOT}/.aegis" ] && [ -d "${SCRIPT_DIR}/.." ]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

# Eksekusi helper python untuk membangun payload injectSteps (mandiri tanpa modul produk)
REPO_ROOT="${REPO_ROOT}" python3 -c "
import json
import os
import sys
from pathlib import Path

repo_root = Path(os.environ.get('REPO_ROOT', '.'))
state_file = repo_root / '.aegis' / 'lifecycle_state.json'

current_phase = 'DEFINE'
active_persona = 'athena-planner'
active_skills = ['interview-me', 'spec-driven-development']

if state_file.is_file():
    try:
        data = json.loads(state_file.read_text(encoding='utf-8'))
        current_phase = data.get('current_phase', 'DEFINE')
        active_persona = data.get('active_persona', 'athena-planner')
        active_skills = data.get('active_skills', [])
    except Exception:
        pass

# Baca petikan ringkas persona dari .agents/agents/
persona_file = repo_root / '.agents' / 'agents' / f'{active_persona}.md'
if not persona_file.is_file():
    persona_file = repo_root / 'agents' / f'{active_persona}.md'
persona_role = 'Olympus Agent'
if persona_file.is_file():
    try:
        content = persona_file.read_text(encoding='utf-8')
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        for line in content.splitlines():
            s = line.strip()
            if s.startswith('#'):
                persona_role = s.lstrip('#').strip()
                break
    except Exception:
        pass

skills_str = ', '.join(active_skills) if active_skills else 'none'

message = (
    f'[OLYMPUS WORKFLOW: PHASE {current_phase} | PERSONA: {active_persona} | ACTIVE SKILLS: {skills_str}]\n'
    f'Peran Aktif: {persona_role}\n'
    f'Direktif Tahapan:\n'
    f'- Anda bertugas menegakkan alur kerja fase {current_phase}.\n'
    f'- Patuhi seluruh kriteria kualitas dan instruksi wajib dari skills: {skills_str}.\n'
    f'- Pastikan stop-gate tahapan terpenuhi sebelum melangkah ke fase berikutnya.'
)

output = {
    'injectSteps': [
        {
            'ephemeralMessage': message
        }
    ]
}

print(json.dumps(output))
"
