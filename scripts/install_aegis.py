#!/usr/bin/env python
"""AETHER installer + bootstrap resmi (helper untuk run.bat).

Skrip ini HANYA memakai standard library sehingga dapat dijalankan SEBELUM
dependency AETHER terpasang. Tujuannya membuat distribusi AETHER ramah-user:
cukup jalankan run.bat, sisanya (venv, dependency, frontend build) disiapkan
di sini secara otomatis.

Tanggung jawab:
    1. Verifikasi prasyarat (Python >= 3.10, git tersedia).
    2. Siapkan virtual environment portable di <root>/venv.
    3. Pastikan dependency runtime terpasang (pip install -r requirements.txt).
    4. Pastikan file konfigurasi .env ada (disalin dari template; TANPA credential).
    5. Pastikan frontend production build ada (web/frontend/dist), build bila perlu.
    6. Jalankan AETHER (Django Gateway) pada port yang dibaca dari
       `<root>/data/settings.json` -> `port` (fallback ke port lain yang bebas
       bila port tersebut sedang dipakai; default 8000 bila tidak dikonfigurasi).

Sifat IDEMPOTENT: aman dijalankan berulang. Langkah yang sudah selesai
dilewati (dicek dulu), sehingga menjalankan ulang tidak merusak instalasi.

MODE SIMULASI (--simulate): dry-run OFFLINE. Seluruh alur dicetak sebagai
rencana berpenanda state (SKIP / AKAN) TANPA efek samping apa pun: tidak
menjalankan git clone, `python -m venv`, `pip install`, `npm install`,
`vite build`, maupun `manage.py runserver`; tidak membuka browser; dan tidak
menulis/menyalin file apa pun (termasuk .env). Mode ini hanya membaca state
(keberadaan file/folder, `shutil.which`, `sys.version_info`, cek port via
socket) sehingga aman dijalankan di lingkungan tanpa koneksi internet.
Kapitalisasi flag ditoleransi (mis. `--SIMULATE`), karena gate simulasi di
run.bat mencocokkan argumen secara case-insensitive.

Batasan arsitektur yang dipertahankan:
    - Entry backend tetap web/django_app/manage.py.
    - Frontend tetap dibangun dari web/frontend memakai Vite; build memakai
      `node node_modules/vite/bin/vite.js build` (tidak bergantung pada npm
      script) sesuai konvensi proyek.
    - Tidak ada credential yang ditulis ke file mana pun.
    - Tidak meng-install Python/Node secara otomatis; hanya memberi pesan jelas.
    - Tidak ada path machine-specific (semua path relatif ke root instalasi).

Jalankan (biasanya lewat run.bat):
    python scripts/install_aether.py
    python scripts/install_aether.py --check          # verifikasi saja
    python scripts/install_aether.py --no-launch      # setup saja
    python scripts/install_aether.py --simulate       # dry-run offline (tanpa unduhan/mutasi)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Konstanta (portable; JANGAN hardcode path mesin)
# ---------------------------------------------------------------------------
MIN_PYTHON = (3, 10)
REPO_URL = "https://github.com/aditlab-code/aegiscode.git"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
LOG_PREFIX = "[AegisCode]"


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def info(message: str) -> None:
    print(f"{LOG_PREFIX} {message}", flush=True)


def warn(message: str) -> None:
    print(f"{LOG_PREFIX} WARNING: {message}", flush=True)


def error(message: str) -> None:
    print(f"{LOG_PREFIX} ERROR: {message}", flush=True)


# ---------------------------------------------------------------------------
# Path helpers (semua relatif ke root instalasi)
# ---------------------------------------------------------------------------
def project_root_default() -> Path:
    """Root AETHER = parent dari folder scripts/ (lokasi file ini)."""
    return Path(__file__).resolve().parent.parent


def venv_dir(root: Path) -> Path:
    return root / "venv"


def venv_python(root: Path) -> Path:
    """Path python di dalam venv (Windows: Scripts, POSIX: bin)."""
    win_python = venv_dir(root) / "Scripts" / "python.exe"
    if win_python.exists():
        return win_python
    posix_python = venv_dir(root) / "bin" / "python"
    if posix_python.exists():
        return posix_python
    # Belum dibuat: default Windows.
    return win_python


def requirements_file(root: Path) -> Path:
    return root / "requirements.txt"


def frontend_dir(root: Path) -> Path:
    return root / "web" / "frontend"


def frontend_dist_index(root: Path) -> Path:
    return frontend_dir(root) / "dist" / "index.html"


def django_app_dir(root: Path) -> Path:
    return root / "web" / "django_app"


def settings_file(root: Path) -> Path:
    """File konfigurasi global AETHER (`<root>/data/settings.json`).

    Satu-satunya sumber konfigurasi global (termasuk `port`); installer TIDAK
    membuat/menulis file ini, hanya membacanya (read-only).
    """
    return root / "data" / "settings.json"


def _deps_stamp(venv: Path) -> Path:
    stamp = venv / ".aegis_deps_stamp"
    if not stamp.exists() and (venv / ".aether_deps_stamp").exists():
        return venv / ".aether_deps_stamp"
    return stamp


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------
def _run_command(argv: list[str], cwd: Path | None = None, env: dict | None = None):
    """Jalankan executable. Batch/CMD script di Windows dirutekan lewat cmd.exe.

    hal ini diperlukan karena CreateProcess tidak dapat mengeksekusi file
    .cmd/.bat secara langsung (mis. npm.CMD).
    """
    exe = argv[0]
    suffix = Path(exe).suffix.lower()
    if os.name == "nt" and suffix in (".cmd", ".bat"):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return subprocess.run([comspec, "/c", exe, *argv[1:]], cwd=str(cwd) if cwd else None, env=env)
    return subprocess.run(argv, cwd=str(cwd) if cwd else None, env=env)


# ---------------------------------------------------------------------------
# 1) Prasyarat
# ---------------------------------------------------------------------------
def verify_python() -> bool:
    """Validasi interpreter yang sedang berjalan (dipakai run.bat untuk bootstrap)."""
    version = sys.version_info
    if (version.major, version.minor) < MIN_PYTHON:
        error(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ wajib, terdeteksi "
            f"{version.major}.{version.minor}.{version.micro}."
        )
        error("Instal Python 3.10+ (https://www.python.org/downloads/windows/) lalu jalankan ulang run.bat.")
        return False
    info(f"Python {version.major}.{version.minor}.{version.micro} OK ({sys.executable})")
    return True


def verify_git() -> bool:
    """git diperlukan untuk bootstrap (clone) dan oleh Agent. Wajib ada."""
    git = shutil.which("git")
    if not git:
        error("git tidak ditemukan di PATH.")
        error("Instal Git for Windows (https://git-scm.com/download/win) lalu jalankan ulang run.bat.")
        return False
    try:
        result = subprocess.run([git, "--version"], capture_output=True, text=True)
    except OSError as exc:  # pragma: no cover - sangat jarang
        error(f"gagal menjalankan git: {exc}")
        return False
    version = (result.stdout or result.stderr).strip() or "git"
    info(f"{version} OK")
    return True


# ---------------------------------------------------------------------------
# 2) Virtual environment
# ---------------------------------------------------------------------------
def ensure_venv(root: Path) -> Path | None:
    python = venv_python(root)
    if python.exists():
        info(f"Virtual environment OK ({python})")
        return python

    info("Membuat virtual environment (venv)...")
    try:
        result = _run_command([sys.executable, "-m", "venv", str(venv_dir(root))])
    except OSError as exc:
        error(f"gagal membuat venv: {exc}")
        return None
    if result.returncode != 0 or not venv_python(root).exists():
        error("gagal membuat virtual environment. Pastikan modul 'venv' tersedia pada Python Anda.")
        return None
    info(f"Virtual environment dibuat ({venv_python(root)})")
    return venv_python(root)


# ---------------------------------------------------------------------------
# 3) Dependency runtime
# ---------------------------------------------------------------------------
def _requirements_hash(root: Path) -> str | None:
    req = requirements_file(root)
    if not req.exists():
        return None
    return hashlib.sha256(req.read_bytes()).hexdigest()


def deps_satisfied(root: Path, python: Path) -> bool:
    """Cek stamp hash requirements + import nyata; idempotensi & cepat."""
    expected = _requirements_hash(root)
    if expected is None:
        return False
    stamp = _deps_stamp(venv_dir(root))
    if not stamp.exists():
        return False
    try:
        if stamp.read_text(encoding="utf-8").strip() != expected:
            return False
    except OSError:
        return False
    try:
        probe = subprocess.run(
            [str(python), "-c", "import django, dotenv, requests, PIL"],
            capture_output=True,
        )
    except OSError:
        return False
    return probe.returncode == 0


def install_deps(root: Path, python: Path, force: bool = False) -> bool:
    if not requirements_file(root).exists():
        warn("requirements.txt tidak ditemukan; melewati instalasi dependency.")
        return True
    if not force and deps_satisfied(root, python):
        info("Dependency runtime sudah terpasang (skip).")
        return True

    info("Memasang dependency runtime (pip install -r requirements.txt)...")
    argv = [
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(requirements_file(root)),
    ]
    try:
        result = _run_command(argv)
    except OSError as exc:
        error(f"gagal menjalankan pip: {exc}")
        return False
    if result.returncode != 0:
        error("instalasi dependency gagal (pip). Periksa koneksi internet lalu jalankan ulang run.bat.")
        return False

    try:
        _deps_stamp(venv_dir(root)).write_text(_requirements_hash(root) or "", encoding="utf-8")
    except OSError:  # pragma: no cover - stamp hanya optimasi
        pass
    info("Dependency runtime terpasang.")
    return True


# ---------------------------------------------------------------------------
# 4) Konfigurasi .env (tanpa credential)
# ---------------------------------------------------------------------------
def ensure_env_file(root: Path) -> bool:
    env_file = root / ".env"
    if env_file.exists():
        info("Konfigurasi .env ditemukan (tidak diubah).")
        return True
    for candidate in ("deployment.template", ".env.example"):
        source = root / candidate
        if source.exists():
            try:
                shutil.copyfile(source, env_file)
            except OSError as exc:
                warn(f"gagal menyalin {candidate} ke .env: {exc}")
                return True
            info(f"Konfigurasi .env dibuat dari {candidate} (isi API key hanya bila diperlukan).")
            return True
    warn("template konfigurasi tidak ditemukan (.env.example / deployment.template); .env dilewati.")
    return True


# ---------------------------------------------------------------------------
# 5) Frontend production build
# ---------------------------------------------------------------------------
def ensure_frontend(root: Path, force: bool = False) -> bool:
    frontend = frontend_dir(root)
    dist_index = frontend_dist_index(root)

    if not frontend.exists():
        error(f"folder frontend tidak ditemukan ({frontend}).")
        return False

    if dist_index.exists() and not force:
        info("Frontend production build sudah ada (skip).")
        return True

    node = shutil.which("node")
    if not node:
        error("Node.js diperlukan untuk build frontend, tetapi 'node' tidak ditemukan di PATH.")
        error("Instal Node.js LTS (https://nodejs.org) lalu jalankan ulang run.bat.")
        error("AETHER TIDAK meng-install Node secara otomatis (butuh persetujuan Anda).")
        return False

    node_modules = frontend / "node_modules"
    if not node_modules.exists():
        npm = shutil.which("npm")
        if not npm:
            error("'npm' tidak ditemukan di PATH; dibutuhkan untuk 'npm install' di web/frontend.")
            error("Instal Node.js LTS (yang menyertakan npm) lalu jalankan ulang run.bat.")
            return False
        info("Memasang dependency frontend (npm install)...")
        result = _run_command([npm, "install"], cwd=frontend)
        if result.returncode != 0:
            error("'npm install' gagal. Periksa koneksi internet lalu jalankan ulang run.bat.")
            return False

    vite = node_modules / "vite" / "bin" / "vite.js"
    if not vite.exists():
        error("vite tidak ditemukan di node_modules. Hapus web/frontend/node_modules lalu jalankan ulang run.bat.")
        return False

    info("Membangun frontend production build (vite build)...")
    result = _run_command([node, str(vite), "build"], cwd=frontend)
    if result.returncode != 0 or not dist_index.exists():
        error("build frontend gagal. Periksa pesan di atas lalu jalankan ulang run.bat.")
        return False
    info("Frontend production build siap (web/frontend/dist).")
    return True


# ---------------------------------------------------------------------------
# 6) Jalankan AETHER (Django Gateway)
# ---------------------------------------------------------------------------
def _open_browser_later(url: str, delay: float = 3.0) -> None:
    """Buka browser setelah delay singkat agar server sempat siap."""

    def _open() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - pembukaan browser bersifat best-effort
            pass

    threading.Thread(target=_open, daemon=True).start()


def terminate_process_tree(proc: subprocess.Popen, timeout: float = 3.0) -> None:
    """Hentikan pohon proses secara deterministik (Zero-Zombie process tree kill).

    Sesuai docs/ruleset.md Bagian 4:
    1. Mengirim sinyal SIGTERM ke seluruh sub-proses anak.
    2. Memberi batas waktu aman (grace period) 3 detik untuk terminasi bersih.
    3. Mengeksekusi SIGKILL (atau taskkill /F /T di Windows) bila proses belum berhenti.
    """
    if proc.poll() is not None:
        return

    pid = proc.pid
    # 1. Tahap SIGTERM lembut
    if os.name == "nt":
        try:
            proc.terminate()
        except Exception:
            pass
    else:
        try:
            pgid = os.getpgid(pid)
            if pgid != os.getpgid(0):
                os.killpg(pgid, signal.SIGTERM)
            else:
                proc.terminate()
        except (ProcessLookupError, OSError):
            try:
                proc.terminate()
            except Exception:
                pass

    # Tunggu bounded hingga batas waktu aman (grace period 3.0 detik)
    deadline = time.time() + max(0.1, float(timeout))
    while time.time() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)

    # 2. Eskalasi ke SIGKILL bila belum berhenti dalam batas waktu
    if proc.poll() is None:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=3.0,
                    shell=False,
                )
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            try:
                pgid = os.getpgid(pid)
                if pgid != os.getpgid(0):
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    proc.kill()
            except (ProcessLookupError, OSError):
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=1.0)
            except Exception:
                pass


def _kill_process_by_port(port: int) -> bool:
    """Cari PID yang menahan port dan hentikan seluruh pohon prosesnya."""
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=3.0,
            ).stdout
            pids = set()
            for line in out.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pids.add(parts[-1])
            for pid in pids:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", pid],
                    capture_output=True,
                    timeout=3.0,
                )
            return bool(pids)
        except Exception:
            return False
    else:
        try:
            res = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            pids = [p.strip() for p in res.stdout.splitlines() if p.strip()]
            for pid in pids:
                try:
                    ipid = int(pid)
                    try:
                        pgid = os.getpgid(ipid)
                        os.killpg(pgid, signal.SIGKILL)
                    except Exception:
                        os.kill(ipid, signal.SIGKILL)
                except Exception:
                    pass
            return bool(pids)
        except Exception:
            return False


def terminate_running_server(host: str, port: int, timeout: float = 3.0) -> bool:
    """Hentikan server AegisCode yang sedang berjalan pada host dan port tertentu (Zero-Zombie)."""
    if not port_in_use(host, port):
        info(f"Tidak ada server yang sedang berjalan pada {host}:{port}.")
        return True

    # 1. Coba hentikan secara aman melalui endpoint HTTP POST /api/server/terminate
    target_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    url = f"http://{target_host}:{port}/api/server/terminate"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"force": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                info(f"Sinyal terminasi berhasil dikirim ke server pada {url}.")
    except Exception as exc:
        warn(f"Panggilan API terminasi ({url}) tidak dapat diselesaikan: {exc}")

    # 2. Tunggu pelepasan port hingga batas waktu (3 detik)
    deadline = time.time() + max(1.0, float(timeout))
    while time.time() < deadline:
        if not port_in_use(host, port):
            info(f"Port {port} telah bebas.")
            return True
        time.sleep(0.2)

    # 3. Fallback OS-level tree-kill bila port masih tertahan
    warn(f"Server masih menahan port {port} setelah {timeout} detik. Menjalankan process tree-kill paksa...")
    _kill_process_by_port(port)
    time.sleep(0.5)

    if not port_in_use(host, port):
        info(f"Port {port} berhasil dilepaskan melalui process tree-kill.")
        return True

    error(f"Gagal membebaskan port {port}.")
    return False


def launch(root: Path, python: Path, host: str, port: int | None = None, open_browser: bool = True) -> int:
    app_dir = django_app_dir(root)
    if not (app_dir / "manage.py").exists():
        error(f"manage.py tidak ditemukan di {app_dir}.")
        return 1

    # Port AKTUAL: port dari `data/settings.json` (bila CLI tidak menentukan),
    # dengan fallback otomatis ke port bebas berikutnya.
    actual_port, fallback = resolve_port(root, host, port)

    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    env.setdefault("DJANGO_ALLOWED_HOSTS", f"{host},localhost")

    url = f"http://{host}:{actual_port}/"
    info(f"Port konfigurasi (data/settings.json): {port_from_settings(root)}")
    if fallback:
        warn(
            f"port {port if port is not None else port_from_settings(root)} sedang dipakai; "
            f"AegisCode memakai port alternatif {actual_port}."
        )
    info("Backend started")
    info("Frontend ready")
    info(f"URL: {url}")
    info("Tekan Ctrl+C di jendela ini untuk menghentikan AegisCode.")

    if open_browser:
        _open_browser_later(url)

    argv = [str(python), "manage.py", "runserver", f"{host}:{actual_port}"]

    popen_kwargs: dict[str, Any] = {
        "cwd": str(app_dir),
        "env": env,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(argv, **popen_kwargs)
    except Exception as exc:
        error(f"Gagal menjalankan server: {exc}")
        return 1

    interrupted = False

    def _sig_handler(signum: int, frame: Any) -> None:
        nonlocal interrupted
        interrupted = True
        info("Sinyal penghentian diterima. Menjalankan process tree-kill...")
        terminate_process_tree(proc, timeout=3.0)

    old_sigint = signal.signal(signal.SIGINT, _sig_handler)
    old_sigterm = signal.signal(signal.SIGTERM, _sig_handler)
    old_sighup = None
    if hasattr(signal, "SIGHUP"):
        old_sighup = signal.signal(signal.SIGHUP, _sig_handler)

    try:
        while proc.poll() is None and not interrupted:
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        interrupted = True
        info("Ctrl+C terdeteksi. Menghentikan seluruh proses anak...")
    finally:
        terminate_process_tree(proc, timeout=3.0)
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
        if old_sighup is not None:
            signal.signal(signal.SIGHUP, old_sighup)

    info("AegisCode server telah berhenti (Zero-Zombie exit).")
    return 0


# ---------------------------------------------------------------------------
# 7) Mode SIMULASI (dry-run, offline, tanpa mutasi)
# ---------------------------------------------------------------------------
def _aegis_markers(root: Path) -> list[str]:
    """Marker yang menandai sebuah folder sebagai instalasi AegisCode (read-only)."""
    found: list[str] = []
    if (root / "pyproject.toml").exists():
        found.append("pyproject.toml")
    if (django_app_dir(root) / "manage.py").exists():
        found.append("web/django_app/manage.py")
    if (frontend_dir(root) / "package.json").exists():
        found.append("web/frontend/package.json")
    return found


_aether_markers = _aegis_markers


def looks_like_aegis(root: Path) -> bool:
    """True bila root memuat marker instalasi AegisCode (tanpa efek samping)."""
    markers = _aegis_markers(root)
    return "pyproject.toml" in markers or "web/django_app/manage.py" in markers


looks_like_aether = looks_like_aegis


def port_in_use(host: str, port: int) -> bool:
    """Cek apakah port sudah terpakai — read-only, TIDAK menjalankan server."""
    target = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((target, port)) == 0
    except OSError:
        return False


def port_from_settings(root: Path) -> int:
    """Baca `port` dari `<root>/data/settings.json` (default aman `DEFAULT_PORT`).

    Read-only: installer TIDAK pernah menulis file konfigurasi global. Nilai
    non-angka atau di luar rentang port valid (1..65535) jatuh ke `DEFAULT_PORT`
    sehingga AETHER tetap dapat dijalankan. Fungsi ini TIDAK pernah melempar.
    """
    try:
        data = json.loads(settings_file(root).read_text(encoding="utf-8"))
        raw = data.get("port", DEFAULT_PORT)
    except Exception:  # noqa: BLE001 - absent/korup -> default aman
        return DEFAULT_PORT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PORT
    if not (1 <= value <= 65535):
        return DEFAULT_PORT
    return value


#: Jumlah port berurutan yang dicoba saat port konfigurasi sedang dipakai.
PORT_FALLBACK_ATTEMPTS = 50


def resolve_port(root: Path, host: str, port: int | None = None) -> tuple[int, bool]:
    """Tentukan port AKTUAL untuk runserver (port BEBAS pertama).

    Port dasar (base) ditentukan berurutan: `port` eksplisit (mis. dari CLI
    `--port`), lalu `port` dari `<root>/data/settings.json`, lalu `DEFAULT_PORT`.
    Bila port dasar sedang dipakai, fungsi mencari port BERIKUTNYA yang bebas
    sehingga mekanisme fallback ke port lain tetap terjaga.

    Returns:
        `(port_aktual, fallback_dipakai)` — `fallback_dipakai` True bila port
        dasar tidak dapat dipakai dan AETHER pindah ke port lain.
    """
    preferred = port if port is not None else port_from_settings(root)
    if not (1 <= preferred <= 65535):
        preferred = DEFAULT_PORT
    if not port_in_use(host, preferred):
        return preferred, False
    for offset in range(1, PORT_FALLBACK_ATTEMPTS + 1):
        candidate = preferred + offset
        if candidate > 65535:
            candidate = 1 + (candidate - 65536)
        if candidate == preferred:
            break
        if not port_in_use(host, candidate):
            return candidate, True
    # Tidak ada port bebas ditemukan -> pakai port dasar agar konflik dilaporkan
    # eksplisit oleh runserver (tidak menyembunyikan masalah).
    return preferred, False


def deps_stamp_state(root: Path) -> tuple[str, str]:
    """Status dependency TANPA menjalankan proses apa pun (dipakai mode simulasi)."""
    expected = _requirements_hash(root)
    if expected is None:
        return "skip", "requirements.txt tidak ditemukan"
    stamp = _deps_stamp(venv_dir(root))
    if not stamp.exists():
        return "install", "stamp dependency belum ada"
    try:
        if stamp.read_text(encoding="utf-8").strip() != expected:
            return "install", "requirements.txt berubah sejak instalasi terakhir"
    except OSError:
        return "install", "stamp dependency tidak dapat dibaca"
    return "skip", "stamp cocok dengan requirements.txt"


def run_simulation(
    root: Path,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    *,
    skip_frontend: bool = False,
    rebuild_frontend: bool = False,
) -> int:
    """Cetak rencana instalasi (dry-run) tanpa unduhan/mutasi apa pun.

    Hanya operasi read-only: `shutil.which`, `Path.exists`, `sys.version_info`,
    dan cek port via socket. Tidak ada subprocess = tidak ada git clone / pip /
    npm / vite / runserver, dan tidak ada file yang ditulis.
    """
    counters = {"koneksi": 0, "lokal": 0, "skip": 0}

    # Port EFEKTIF untuk rencana: eksplisit (CLI) atau dari data/settings.json.
    # Mode simulasi TIDAK mencari fallback (read-only plan); ia hanya melaporkan
    # port yang akan dipakai beserta status bebas/terpakai.
    effective_port = port if port is not None else port_from_settings(root)

    info("[SIMULATE] Mode simulasi (dry-run, offline) — tidak ada unduhan/mutasi dijalankan.")

    # --- DETEKSI ----------------------------------------------------------
    info(f"[DETEKSI] root: {root}")
    markers = _aether_markers(root)
    if markers:
        info(f"[DETEKSI] marker AETHER: DITEMUKAN ({', '.join(markers)})")
    else:
        info("[DETEKSI] marker AETHER: TIDAK DITEMUKAN (root belum ada / bukan instalasi AETHER)")

    version = sys.version_info
    if (version.major, version.minor) < MIN_PYTHON:
        warn(
            f"[DETEKSI] Python {version.major}.{version.minor}.{version.micro} < "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}; instalasi nyata akan berhenti."
        )
    else:
        info(f"[DETEKSI] Python {version.major}.{version.minor}.{version.micro} OK ({sys.executable})")

    git = shutil.which("git")
    node = shutil.which("node")
    npm = shutil.which("npm")
    info(f"[DETEKSI] git: {'ADA (' + git + ')' if git else 'TIDAK DITEMUKAN'}")
    info(f"[DETEKSI] Node.js: {'ADA (' + node + ')' if node else 'TIDAK DITEMUKAN'}")
    info(f"[DETEKSI] npm: {'ADA (' + npm + ')' if npm else 'TIDAK DITEMUKAN'}")

    # --- CLONE (dieksekusi oleh run.bat, bukan oleh installer) -------------
    if looks_like_aether(root):
        info("[CLONE] SKIP (instalasi AETHER sudah ada di root; git clone tidak diperlukan)")
        counters["skip"] += 1
    else:
        info(
            f"[CLONE] root belum ada; langkah pertama = git clone {REPO_URL} -> {root} "
            "(butuh koneksi, tidak dijalankan)"
        )
        counters["koneksi"] += 1

    # --- VENV -------------------------------------------------------------
    python = venv_python(root)
    if python.exists():
        info(f"[VENV] SKIP (sudah ada: {python})")
        counters["skip"] += 1
    else:
        info(f"[VENV] AKAN: {sys.executable} -m venv {venv_dir(root)} (LOKAL)")
        counters["lokal"] += 1

    # --- DEPS -------------------------------------------------------------
    req = requirements_file(root)
    deps_state, deps_reason = deps_stamp_state(root)
    if not req.exists():
        info("[DEPS] SKIP (requirements.txt tidak ditemukan)")
        counters["skip"] += 1
    elif not python.exists():
        info(
            f"[DEPS] AKAN: {python} -m pip install --disable-pip-version-check -r {req} "
            "(butuh koneksi; setelah venv dibuat)"
        )
        counters["koneksi"] += 1
    elif deps_state == "skip":
        info(f"[DEPS] SKIP ({deps_reason}; mode simulasi tidak menjalankan probe import)")
        counters["skip"] += 1
    else:
        info(
            f"[DEPS] AKAN: {python} -m pip install --disable-pip-version-check -r {req} "
            f"(butuh koneksi; alasan: {deps_reason})"
        )
        counters["koneksi"] += 1

    # --- ENV --------------------------------------------------------------
    env_file = root / ".env"
    if env_file.exists():
        info("[ENV] SKIP (file .env sudah ada; tidak diubah)")
        counters["skip"] += 1
    else:
        template = next(
            (name for name in ("deployment.template", ".env.example") if (root / name).exists()),
            None,
        )
        if template:
            info(f"[ENV] AKAN: salin {root / template} -> {env_file} (LOKAL)")
            counters["lokal"] += 1
        else:
            info("[ENV] TIDAK DAPAT DILANJUTKAN: template .env tidak ditemukan di root simulasi")

    # --- FRONTEND ---------------------------------------------------------
    dist_index = frontend_dist_index(root)
    node_modules = frontend_dir(root) / "node_modules"
    if skip_frontend:
        info("[FRONTEND] SKIP (--skip-frontend)")
        counters["skip"] += 1
    elif not frontend_dir(root).exists():
        info(f"[FRONTEND] TIDAK DAPAT DILANJUTKAN: folder {frontend_dir(root)} tidak ditemukan")
    elif dist_index.exists() and not rebuild_frontend:
        info(f"[FRONTEND] SKIP (sudah ada: {dist_index})")
        counters["skip"] += 1
    else:
        if node_modules.exists():
            info("[FRONTEND] SKIP (node_modules sudah ada; npm install tidak diperlukan)")
            counters["skip"] += 1
        else:
            info("[FRONTEND] AKAN: npm install (butuh koneksi)")
            counters["koneksi"] += 1
            if not node:
                warn("[FRONTEND] Node.js tidak ditemukan; npm install tidak akan berjalan.")
            elif not npm:
                warn("[FRONTEND] npm tidak ditemukan; npm install tidak akan berjalan.")
        info(
            f"[FRONTEND] AKAN: {node or 'node'} node_modules/vite/bin/vite.js build "
            f"(LOKAL, cwd={frontend_dir(root)})"
        )
        counters["lokal"] += 1
        if not node:
            warn("[FRONTEND] Node.js tidak ditemukan; build frontend tidak akan berjalan.")

    # --- LAUNCH -----------------------------------------------------------
    app_dir = django_app_dir(root)
    if not (app_dir / "manage.py").exists():
        info(f"[LAUNCH] TIDAK DAPAT DILANJUTKAN: manage.py tidak ditemukan di {app_dir}")
    else:
        info(
            f"[LAUNCH] AKAN: {python} manage.py runserver {host}:{effective_port} "
            "(LOKAL, BLOCKING di foreground; dijalankan saat instalasi nyata)"
        )
        counters["lokal"] += 1
        if port is not None:
            info(f"[LAUNCH] port {effective_port} dari argumen --port (override eksplisit)")
        else:
            info(
                f"[LAUNCH] port {effective_port} berasal dari data/settings.json "
                "(fallback otomatis ke port bebas bila sedang dipakai)"
            )
        if port_in_use(host, effective_port):
            warn(
                f"[LAUNCH] port {effective_port} sedang dipakai; saat instalasi nyata "
                "AETHER otomatis pindah ke port bebas berikutnya."
            )
        else:
            info(f"[LAUNCH] port {effective_port} bebas (tidak ada server lain yang memakai).")

    # --- RINGKASAN --------------------------------------------------------
    info(
        f"[SIMULATE] RINGKASAN: {counters['koneksi']} langkah butuh koneksi, "
        f"{counters['lokal']} langkah LOKAL, {counters['skip']} langkah SKIP."
    )
    info("[SIMULATE] Tidak ada perubahan file / unduhan yang dilakukan (dry-run murni).")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AETHER installer + launcher (portable, idempotent).",
    )
    parser.add_argument("--root", default=None, help="Folder root AETHER (default: parent dari scripts/).")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host bind server (default 127.0.0.1).")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "Port server. Bila tidak diberikan, port dibaca dari data/settings.json "
            "(fallback ke port bebas berikutnya bila sedang dipakai; default 8000)."
        ),
    )
    parser.add_argument("--check", action="store_true", help="Hanya verifikasi prasyarat (tanpa mengubah apa pun).")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Dry-run OFFLINE: cetak rencana langkah tanpa unduhan/mutasi apa pun.",
    )
    parser.add_argument("--no-launch", action="store_true", help="Siapkan instalasi saja, jangan jalankan server.")
    parser.add_argument("--skip-frontend", action="store_true", help="Jangan build frontend.")
    parser.add_argument("--rebuild-frontend", action="store_true", help="Paksa build ulang frontend.")
    parser.add_argument("--force-deps", action="store_true", help="Paksa pip install ulang dependency.")
    parser.add_argument("--no-browser", action="store_true", help="Jangan buka browser otomatis.")
    parser.add_argument(
        "--terminate",
        "--stop",
        dest="terminate",
        action="store_true",
        help="Hentikan server AegisCode yang sedang berjalan (Zero-Zombie process tree kill).",
    )
    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    """Normalisasi kapitalisasi flag yang dikirim run.bat.

    Gate simulasi di run.bat memakai pencocokan case-insensitive (findstr /i),
    sehingga user bisa menyetel AETHER_ARGS=--SIMULATE. Flag tersebut
    dinormalisasi ke bentuk kanonik agar argparse tetap menerimanya.
    """
    return ["--simulate" if arg.lower() == "--simulate" else arg for arg in argv]


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(_normalize_argv(raw_argv))
    root = Path(args.root).resolve() if args.root else project_root_default()

    # Opsi terminasi server mandiri (Zero-Zombie)
    if args.terminate:
        target_port = args.port if args.port is not None else port_from_settings(root)
        info(f"Menghentikan server AegisCode pada {args.host}:{target_port}...")
        success = terminate_running_server(args.host, target_port)
        if success:
            info(f"Server pada port {target_port} berhasil dihentikan (Zero-Zombie verified).")
            return 0
        else:
            error(f"Gagal menghentikan server pada port {target_port}.")
            return 1

    # Mode simulasi (dry-run): offline, read-only, tanpa mutasi. Root boleh
    # belum ada karena langkah pertama (git clone) memang belum dijalankan.
    if args.simulate:
        return run_simulation(
            root,
            args.host,
            args.port,
            skip_frontend=args.skip_frontend,
            rebuild_frontend=args.rebuild_frontend,
        )

    info(f"AETHER root: {root}")
    if not looks_like_aether(root):
        error("folder ini tidak terlihat seperti instalasi AETHER (marker tidak ditemukan).")
        return 1

    python_ok = verify_python()
    git_ok = verify_git()

    if args.check:
        node = shutil.which("node")
        info(f"Node.js: {'OK (' + node + ')' if node else 'TIDAK DITEMUKAN (diperlukan untuk build frontend)'}")
        info(f"Venv: {'ADA' if venv_python(root).exists() else 'BELUM ADA (akan dibuat saat setup)'}")
        info(f"Frontend dist: {'ADA' if frontend_dist_index(root).exists() else 'BELUM ADA (akan di-build saat setup)'}")
        return 0 if (python_ok and git_ok) else 1

    if not python_ok or not git_ok:
        return 1

    python = ensure_venv(root)
    if python is None:
        return 1
    if not install_deps(root, python, force=args.force_deps):
        return 1
    ensure_env_file(root)

    if not args.skip_frontend and not ensure_frontend(root, force=args.rebuild_frontend):
        return 1

    if args.no_launch:
        info("Setup selesai (--no-launch). Jalankan run.bat untuk memulai AETHER.")
        return 0

    code = launch(root, python, args.host, args.port, open_browser=not args.no_browser)
    if code != 0:
        error(f"Backend berhenti dengan kode {code}.")
    return code


if __name__ == "__main__":
    sys.exit(main())
