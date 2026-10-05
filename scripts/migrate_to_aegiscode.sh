#!/usr/bin/env bash
# ==============================================================================
# Skrip Migrasi Direktori Root: Aether-Agent -> AegisCode
# ==============================================================================
# Skrip ini memindahkan folder fisik repositori dari nama lama (mis. Aether-Agent)
# ke nama kanonik baru (AegisCode) dan memperbarui konfigurasi virtual environment.
#
# Penggunaan:
#   bash scripts/migrate_to_aegiscode.sh
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(dirname "${CURRENT_ROOT}")"
CURRENT_NAME="$(basename "${CURRENT_ROOT}")"
TARGET_NAME="AegisCode"
TARGET_ROOT="${PARENT_DIR}/${TARGET_NAME}"

echo "======================================================================"
echo " AegisCode - Skrip Migrasi Direktori Root"
echo "======================================================================"
echo "Direktori saat ini : ${CURRENT_ROOT}"
echo "Direktori target   : ${TARGET_ROOT}"
echo ""

if [ "${CURRENT_NAME}" = "${TARGET_NAME}" ]; then
    echo "[INFO] Direktori sudah bernama '${TARGET_NAME}'."
    VENV_DIR="${CURRENT_ROOT}/venv"
    if [ -d "${VENV_DIR}/bin" ]; then
        echo "[INFO] Memeriksa dan memperbarui shebang Virtual Environment..."
        python3 -c "
from pathlib import Path
vbin = Path('${VENV_DIR}/bin')
for p in vbin.iterdir():
    if p.is_file() and not p.is_symlink():
        try:
            txt = p.read_text(encoding='utf-8')
            if 'Aether-Agent' in txt:
                p.write_text(txt.replace('Aether-Agent', 'AegisCode'), encoding='utf-8')
        except Exception:
            pass
"
        echo "[INFO] Virtual Environment siap digunakan."
    fi
    exit 0
fi

if [ -e "${TARGET_ROOT}" ]; then
    echo "[GALAT] Target '${TARGET_ROOT}' sudah ada di disk!"
    echo "Harap periksa atau cadangkan folder target sebelum melanjutkan."
    exit 1
fi

echo "[1/3] Memindahkan direktori repositori..."
mv "${CURRENT_ROOT}" "${TARGET_ROOT}"
echo "      Direktori berhasil dipindahkan ke: ${TARGET_ROOT}"

echo "[2/3] Memperbarui jalur konfigurasi Virtual Environment (jika ada)..."
VENV_DIR="${TARGET_ROOT}/venv"
if [ -d "${VENV_DIR}" ]; then
    if [ -f "${VENV_DIR}/bin/activate" ]; then
        sed -i '' "s|${CURRENT_ROOT}|${TARGET_ROOT}|g" "${VENV_DIR}/bin/activate" 2>/dev/null || true
    fi
    python3 -c "
from pathlib import Path
vbin = Path('${VENV_DIR}/bin')
if vbin.is_dir():
    for p in vbin.iterdir():
        if p.is_file() and not p.is_symlink():
            try:
                txt = p.read_text(encoding='utf-8')
                if '${CURRENT_ROOT}' in txt:
                    p.write_text(txt.replace('${CURRENT_ROOT}', '${TARGET_ROOT}'), encoding='utf-8')
            except Exception:
                pass
"
    echo "      Jalur virtual environment berhasil diperbarui."
fi


echo "[3/3] Memvalidasi integritas repositori..."
cd "${TARGET_ROOT}"
python3 scripts/install_aegis.py --check

echo ""
echo "======================================================================"
echo " MIGRASI DIREKTORI BERHASIL!"
echo "======================================================================"
echo "Langkah selanjutnya:"
echo "1. Buka workspace baru di editor/terminal Anda:"
echo "   cd \"${TARGET_ROOT}\""
echo "2. Untuk menjalankan AegisCode Studio:"
echo "   ./run.sh"
echo "======================================================================"
