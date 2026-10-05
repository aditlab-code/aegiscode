@echo off
REM ===========================================================================
REM  AegisCode - Self-bootstrapping Launcher
REM ===========================================================================
REM  Cukup double-click file ini untuk menjalankan AegisCode. Launcher akan:
REM    1) Menyiapkan folder AegisCode (git clone bila belum ada).
REM    2) Menyiapkan environment (venv + dependency + frontend production build).
REM    3) Menjalankan AegisCode (Django Gateway + frontend production build).
REM
REM  Mode: PRODUCTION BUILD. Hanya SATU proses dan SATU URL, memakai port dari
REM        konfigurasi `data/settings.json` (key `port`); fallback otomatis ke
REM        port bebas berikutnya bila port tersebut sedang dipakai.
REM        Override manual: set AEGIS_PORT=8478 && run.bat
REM
REM  Logika instalasi/verifikasi yang berat berada di skrip Python portable:
REM        scripts\install_aegis.py
REM  Batch ini hanya: deteksi folder AegisCode -> git clone bila perlu -> panggil
REM  installer -> teruskan exit code. Aman dijalankan berulang (idempotent).
REM
REM  Anda bisa override folder instalasi lewat environment variable:
REM        set AEGIS_INSTALL_DIR=D:\apps\aegiscode
REM  Anda juga bisa meneruskan argumen tambahan ke installer:
REM        set AEGIS_ARGS=--check         (verifikasi prasyarat saja)
REM        set AEGIS_ARGS=--rebuild-frontend
REM
REM  MODE SIMULASI (dry-run, offline) — untuk menguji alur instalasi TANPA
REM  mengunduh/mengubah apa pun. Git clone dilewati dan installer dicetak
REM  sebagai rencana langkah saja:
REM        set AEGIS_SIMULATE=1           && run.bat
REM        set AEGIS_ARGS=--simulate      && run.bat
REM  Set AEGIS_NONINTERACTIVE=1 untuk mencegah 'pause' (konteks otomatis/CI).
REM ===========================================================================

setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
REM %~dp0 selalu berakhir dengan "\". Buang trailing backslash agar path aman
REM dipakai sebagai argumen berkutip ("<path>\"" akan merusak parsing quote).
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "REPO_URL=https://github.com/aditlab-code/aegiscode.git"
set "HOST=127.0.0.1"
REM Port dasar dibaca dari konfigurasi `data/settings.json` (key `port`) oleh
REM installer (scripts/install_aegis.py). JANGAN hardcode 8000 di sini: bila
REM AEGIS_PORT / AETHER_PORT diset, nilai itu dipakai sebagai override eksplisit.
set "PORT_ARG="
if defined AEGIS_PORT (
    set "PORT_ARG=--port %AEGIS_PORT%"
) else if defined AETHER_PORT (
    set "PORT_ARG=--port %AETHER_PORT%"
)

REM Folder default hasil clone bila AegisCode belum ada di samping run.bat.
set "INSTALL_DIR=%SCRIPT_DIR%\aegiscode"
if defined AEGIS_INSTALL_DIR (
    set "INSTALL_DIR=%AEGIS_INSTALL_DIR%"
) else if defined AETHER_INSTALL_DIR (
    set "INSTALL_DIR=%AETHER_INSTALL_DIR%"
)
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo [AegisCode] Launcher...

REM --- 0) Deteksi mode simulasi (dry-run) ------------------------------------
REM Aktif bila AEGIS_SIMULATE / AETHER_SIMULATE diset ATAU argumen memuat "--simulate".
set "SIMULATE="
if defined AEGIS_SIMULATE set "SIMULATE=1"
if defined AETHER_SIMULATE set "SIMULATE=1"
if defined AEGIS_ARGS (
    echo(%AEGIS_ARGS%| findstr /i /c:"--simulate" >nul 2>&1 && set "SIMULATE=1"
)
if defined AETHER_ARGS (
    echo(%AETHER_ARGS%| findstr /i /c:"--simulate" >nul 2>&1 && set "SIMULATE=1"
)
if defined SIMULATE echo [AegisCode] [SIMULATE] Dry-run aktif: unduhan/mutasi dilewati.

REM --- 1) Deteksi folder AegisCode (marker khas) -----------------------------
call :detect_aegis "%SCRIPT_DIR%"
if defined AEGIS_DIR goto :aegis_found

call :detect_aegis "%INSTALL_DIR%"
if defined AEGIS_DIR goto :aegis_found

REM --- 2a) Folder AegisCode belum ada + mode simulasi -> jangan git clone ----
if defined SIMULATE goto :simulate_no_root

REM --- 2) Folder AegisCode belum ada -> git clone ----------------------------
echo [AegisCode] Folder AegisCode belum ditemukan. Menyiapkan di:
echo          %INSTALL_DIR%

where git >nul 2>&1
if errorlevel 1 (
    echo [AegisCode] ERROR: git tidak ditemukan di PATH.
    echo [AegisCode] Instal Git for Windows ^(https://git-scm.com/download/win^) lalu jalankan ulang run.bat.
    goto :fail
)

if exist "%INSTALL_DIR%" (
    echo [AegisCode] ERROR: folder "%INSTALL_DIR%" sudah ada tetapi bukan instalasi AegisCode.
    echo [AegisCode] Hapus/pindahkan folder tersebut lalu jalankan ulang, atau set AEGIS_INSTALL_DIR.
    goto :fail
)

echo [AegisCode] Mengambil AegisCode dari %REPO_URL% ...
git clone "%REPO_URL%" "%INSTALL_DIR%"
if errorlevel 1 (
    echo [AegisCode] ERROR: git clone gagal. Periksa koneksi internet/akses repo.
    goto :fail
)

call :detect_aegis "%INSTALL_DIR%"
if not defined AEGIS_DIR (
    echo [AegisCode] ERROR: hasil clone tidak dikenali sebagai instalasi AegisCode.
    goto :fail
)

:aegis_found
echo [AegisCode] Folder AegisCode: %AEGIS_DIR%

REM --- 3) Validasi Python (untuk bootstrap installer) ------------------------
call :detect_python
if not defined SYS_PY (
    echo [AegisCode] ERROR: Python tidak ditemukan di PATH.
    echo [AegisCode] Instal Python 3.10+ ^(https://www.python.org/downloads/windows/^).
    echo [AegisCode] Saat instalasi, centang "Add python.exe to PATH", lalu jalankan ulang run.bat.
    goto :fail
)

set "INSTALLER=%AEGIS_DIR%\scripts\install_aegis.py"
if not exist "%INSTALLER%" set "INSTALLER=%AEGIS_DIR%\scripts\install_aether.py"
if not exist "%INSTALLER%" (
    echo [AegisCode] ERROR: installer tidak ditemukan di "%INSTALLER%".
    goto :fail
)

REM --- 4) Jalankan installer Python (setup + launch) -------------------------
REM Argumen tambahan opsional dari user (mis. --check, --rebuild-frontend).
set "EXTRA_ARGS="
if defined AEGIS_ARGS (
    set "EXTRA_ARGS=%AEGIS_ARGS%"
) else if defined AETHER_ARGS (
    set "EXTRA_ARGS=%AETHER_ARGS%"
)

REM Mode simulasi: installer dipanggil sebagai dry-run (tanpa unduhan/mutasi).
set "SIM_ARGS="
if defined SIMULATE set "SIM_ARGS=--simulate"

pushd "%AEGIS_DIR%"
%SYS_PY% "%INSTALLER%" --root "%AEGIS_DIR%" --host %HOST% %PORT_ARG% %SIM_ARGS% %EXTRA_ARGS%
set "EXITCODE=%ERRORLEVEL%"
popd

if not "%EXITCODE%"=="0" goto :fail
goto :end

REM --- Subroutine: deteksi interpreter Python untuk bootstrap ----------------
:detect_python
set "SYS_PY="
where python >nul 2>&1 && set "SYS_PY=python"
if not defined SYS_PY (
    where py >nul 2>&1 && set "SYS_PY=py -3"
)
exit /b 0

REM --- Subroutine: mode simulasi saat folder AegisCode belum ada -------------
REM git clone DILEWATI (dry-run offline); installer dijalankan dengan
REM --simulate --root "%INSTALL_DIR%" bila skrip installer tersedia.
:simulate_no_root
echo [AegisCode] [SIMULATE] clone dilewati: %REPO_URL% -^> %INSTALL_DIR%
set "INSTALLER=%SCRIPT_DIR%\scripts\install_aegis.py"
if not exist "%INSTALLER%" set "INSTALLER=%SCRIPT_DIR%\scripts\install_aether.py"
if not exist "%INSTALLER%" (
    echo [AegisCode] [SIMULATE] installer belum tersedia ^(folder AegisCode belum ada^); tidak ada aksi.
    goto :end
)
call :detect_python
if not defined SYS_PY (
    echo [AegisCode] [SIMULATE] Python tidak ditemukan; simulasi dilewati.
    goto :end
)
%SYS_PY% "%INSTALLER%" --simulate --root "%INSTALL_DIR%"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" goto :fail
goto :end

REM --- Subroutine: deteksi marker AegisCode pada sebuah folder ---------------
REM Normalisasi path (buang trailing backslash) agar aman dipakai sebagai
REM argumen berkutip. %%~fI TIDAK membuang trailing backslash, jadi di-strip manual.
:detect_aegis
set "AEGIS_DIR="
set "CANDIDATE="
if exist "%~1\pyproject.toml" if exist "%~1\web\django_app\manage.py" set "CANDIDATE=%~1"
if exist "%~1\web\django_app\manage.py" if exist "%~1\scripts\install_aegis.py" set "CANDIDATE=%~1"
if exist "%~1\web\django_app\manage.py" if exist "%~1\scripts\install_aether.py" set "CANDIDATE=%~1"
if not defined CANDIDATE exit /b 0
set "AEGIS_DIR=%CANDIDATE%"
if "%AEGIS_DIR:~-1%"=="\" set "AEGIS_DIR=%AEGIS_DIR:~0,-1%"
exit /b 0

:fail
echo.
echo [AegisCode] Gagal menjalankan AegisCode. Lihat pesan di atas untuk penyebabnya.
echo.
REM Mode simulasi / non-interaktif tidak boleh menggantung di 'pause'.
if defined SIMULATE goto :end
if defined AEGIS_NONINTERACTIVE goto :end
if defined AETHER_NONINTERACTIVE goto :end
echo [AegisCode] Jendela ini TIDAK ditutup otomatis agar Anda dapat membaca error.
echo.
pause
goto :end

:end
endlocal
