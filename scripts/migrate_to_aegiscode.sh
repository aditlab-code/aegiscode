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
    echo "[INFO] Direktori sudah bernama '${TARGET_NAME}'. Tidak ada pemindahan nama direktori yang diperlukan."
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
    # Perbarui VIRTUAL_ENV path pada activate scripts jika ada
    if [ -f "${VENV_DIR}/bin/activate" ]; then
        sed -i '' "s|${CURRENT_ROOT}|${TARGET_ROOT}|g" "${VENV_DIR}/bin/activate" 2>/dev/null || true
    fi
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
