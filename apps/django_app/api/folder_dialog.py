"""Dialog native OS untuk memilih folder (lintas platform).

Dipakai oleh Gateway (POST /api/projects/pick-folder) agar UI dapat memanggil
dialog Finder / file manager sungguhan dan memperoleh path ABSOLUT. Browser
tidak dapat melakukan ini sendiri (HTML File API hanya memberi path relatif),
sehingga pemilihan folder native adalah tanggung jawab backend.

Kontrak Result (TIDAK pernah melempar ke luar modul ini):
    {"ok": True,  "path": "/abs/path"}                       -> user memilih
    {"ok": False, "reason": "cancelled"}                     -> user membatalkan
    {"ok": False, "reason": "unsupported" | "failed" | "timeout",
     "message": "..."}                                        -> gagal

Catatan keamanan:
    - Semua eksekusi memakai argv list + shell=False (tanpa interpolasi input).
    - Skrip osascript/PowerShell adalah literal statis; TIDAK ada string user.
    - Gateway Aegis terikat ke 127.0.0.1 (single-user local app).
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict

#: Batas tunggu dialog. User interaktif; lebih dari ini dianggap timeout.
PICK_TIMEOUT_SECONDS = 300


def _cancelled(stderr: str) -> bool:
    """True bila osascript/PowerShell dibatalkan user (bukan kegagalan)."""
    # macOS: error -128 = "User canceled"; Windows: exit code tanpa output.
    return "-128" in stderr or "User canceled" in stderr or "canceled by the user" in stderr.lower()


def _pick_darwin(timeout: int) -> Dict[str, Any]:
    """macOS: choose folder via osascript (Finder)."""
    script = (
        'POSIX path of (choose folder with prompt "Pilih workspace project Aegis")'
    )
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout", "message": "Dialog ditutup otomatis (timeout)."}
    except OSError as exc:
        return {"ok": False, "reason": "failed", "message": f"osascript tidak dapat dijalankan: {exc}"}

    if proc.returncode == 0:
        path = (proc.stdout or "").strip()
        # osascript mengembalikan path dengan trailing "/" — normalisasi,
        # kecuali root ("/") yang tetap dipertahankan.
        if len(path) > 1:
            path = path.rstrip("/")
        return {"ok": True, "path": path}

    stderr = proc.stderr or ""
    if _cancelled(stderr):
        return {"ok": False, "reason": "cancelled"}
    return {"ok": False, "reason": "failed", "message": stderr.strip() or "osascript gagal."}


def _pick_windows(timeout: int) -> Dict[str, Any]:
    """Windows: FolderBrowserDialog via PowerShell (GUI native)."""
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$d.Description = 'Pilih workspace project Aegis'; "
        "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout", "message": "Dialog ditutup otomatis (timeout)."}
    except OSError as exc:
        return {"ok": False, "reason": "failed", "message": f"PowerShell tidak dapat dijalankan: {exc}"}

    if proc.returncode == 0:
        path = (proc.stdout or "").strip()
        if path:
            return {"ok": True, "path": path}
        return {"ok": False, "reason": "cancelled"}

    stderr = proc.stderr or ""
    if _cancelled(stderr):
        return {"ok": False, "reason": "cancelled"}
    return {"ok": False, "reason": "failed", "message": stderr.strip() or "FolderBrowserDialog gagal."}


def _pick_linux(timeout: int) -> Dict[str, Any]:
    """Linux: zenity (GNOME) atau kdialog (KDE)."""
    import shutil

    if shutil.which("zenity"):
        argv = ["zenity", "--file-selection", "--directory",
                "--title=Pilih workspace project Aegis"]
    elif shutil.which("kdialog"):
        argv = ["kdialog", "--getexistingdirectory", "/",
                "--title", "Pilih workspace project Aegis"]
    else:
        return {
            "ok": False,
            "reason": "unsupported",
            "message": "Tidak ditemukan zenity/kdialog untuk dialog folder.",
        }

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout", "message": "Dialog ditutup otomatis (timeout)."}
    except OSError as exc:
        return {"ok": False, "reason": "failed", "message": f"Dialog tool gagal dijalankan: {exc}"}

    if proc.returncode == 0:
        path = (proc.stdout or "").strip()
        if path:
            return {"ok": True, "path": path}
        return {"ok": False, "reason": "cancelled"}
    # zenity/kdialog keluar dengan kode 1 saat user membatalkan.
    return {"ok": False, "reason": "cancelled"}


def pick_folder(timeout: int = PICK_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Buka dialog folder native OS. Selalu mengembalikan Result dict.

    Dispatch platform memakai peta strategi (bukan percabangan bertingkat);
    setiap jalur dibungkus try-catch sehingga kegagalan OS tidak pernah
    membocorkan exception ke lapisan HTTP.
    """
    try:
        if sys.platform == "darwin":
            return _pick_darwin(timeout)
        if sys.platform.startswith("win"):
            return _pick_windows(timeout)
        return _pick_linux(timeout)
    except Exception as exc:  # noqa: BLE001 - guard terakhir: Result, jangan 500
        return {"ok": False, "reason": "failed", "message": f"Dialog folder gagal: {exc}"}
