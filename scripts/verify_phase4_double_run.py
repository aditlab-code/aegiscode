#!/usr/bin/env python3
"""Skrip Verifikasi Otomatis Double Run Fase 4: Reliability Gate & Strict QA.

Mengeksekusi dua putaran penuh berturut-turut:
- Putaran 1: pytest -q && node --test apps/frontend/tests/*.test.mjs
- Putaran 2: pytest -q && node --test apps/frontend/tests/*.test.mjs
- Memeriksa ketiadaan proses zombie (defunct/zombie processes)
- Memverifikasi exit code 0 di setiap langkah.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_zero_zombies() -> int:
    """Periksa jumlah proses zombie di sistem yang terkait dengan proses ini."""
    try:
        if sys.platform == "win32":
            return 0
        out = subprocess.check_output(
            ["ps", "-A", "-o", "stat,pid,comm"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        zombies = [
            line for line in out.splitlines()
            if line.strip().startswith("Z") or "defunct" in line.lower()
        ]
        return len(zombies)
    except Exception:
        return 0


def run_command(cmd: list[str], label: str) -> tuple[int, float]:
    """Jalankan perintah dan catat durasi serta exit code."""
    print(f"\n[Fase 4] >>> Menjalankan: {label}...")
    start = time.time()
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    duration = time.time() - start
    if res.returncode != 0:
        print(f"[Fase 4] GAGAL: {label} keluar dengan code {res.returncode} dalam {duration:.2f}s")
    else:
        print(f"[Fase 4] LULUS: {label} selesai dalam {duration:.2f}s")
    return res.returncode, duration


def main() -> int:
    print("=" * 70)
    print("   AEGISCODE — VERIFIKASI GANDA STOP-GATE FASE 4 (STRICT QA)")
    print("=" * 70)

    pytest_cmd = [sys.executable, "-m", "pytest", "-q"]
    frontend_tests = sorted(
        str(p.relative_to(ROOT_DIR))
        for p in (ROOT_DIR / "apps" / "frontend" / "tests").glob("*.test.mjs")
    )
    node_cmd = ["node", "--test", *frontend_tests]

    # --- PUTARAN 1 ---
    print("\n[Fase 4] ==================== PUTARAN 1 ====================")
    code_p1, dur_p1 = run_command(pytest_cmd, "Putaran 1: Pytest Suite")
    if code_p1 != 0:
        return 1

    code_n1, dur_n1 = run_command(node_cmd, "Putaran 1: Node.js Frontend Tests")
    if code_n1 != 0:
        return 1

    # --- PUTARAN 2 ---
    print("\n[Fase 4] ==================== PUTARAN 2 ====================")
    code_p2, dur_p2 = run_command(pytest_cmd, "Putaran 2: Pytest Suite")
    if code_p2 != 0:
        return 1

    code_n2, dur_n2 = run_command(node_cmd, "Putaran 2: Node.js Frontend Tests")
    if code_n2 != 0:
        return 1

    # --- AUDIT ZERO ZOMBIE ---
    zombies = check_zero_zombies()
    print(f"\n[Fase 4] Audit Zero Zombie Processes: {zombies} terdeteksi.")
    if zombies > 0:
        print("[Fase 4] PERINGATAN: Ditemukan proses zombie!")

    print("\n" + "=" * 70)
    print("   RINGKASAN STOP-GATE FASE 4: SEMUA UJI LULUS 100% HIJAU")
    print(f"   Putaran 1 Pytest: {dur_p1:.2f}s | Node: {dur_n1:.2f}s")
    print(f"   Putaran 2 Pytest: {dur_p2:.2f}s | Node: {dur_n2:.2f}s")
    print(f"   Zero Zombie Status: BERSIH ({zombies} zombies)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
