#!/usr/bin/env bash
# Launcher AETHER untuk macOS / Linux — padanan run.bat (Windows).
# Idempotent: membuat venv, memasang dependency, build frontend, lalu start server.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 scripts/install_aether.py "$@"
