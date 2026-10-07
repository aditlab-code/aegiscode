#!/usr/bin/env python3
"""Generator Log Kanonik 5 Kondisi Task (Fase 0 - Baseline & Freeze).

Menghasilkan artefak berkas log .aegis/log/<task_id>.log dan memvalidasi
integritas log reader (Aegis TaskLogReader) untuk 5 kondisi terminal/state:
1. completed: sukses penuh
2. failed: fatal error/exception
3. timeout: batas waktu habis (failed dengan alasan timeout)
4. retry: transient error dengan backoff sebelum sukses completed
5. cancelled: dihentikan secara eksplisit oleh pengguna
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_ai.projects.aegis_store import TaskLogReader

FIXTURES_DIR = PROJECT_ROOT / "docs" / "QA" / "fixtures" / "phase0_canonical_logs"


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def generate_logs() -> dict[str, Path]:
    out_files: dict[str, Path] = {}

    # 1. COMPLETED
    task_id_completed = "phase0_canonical_01_completed"
    events_completed = [
        {"event": "task_requested", "timestamp": 1775560000.0, "data": {"prompt": "Implementasi fungsi helper format rupiah"}},
        {"event": "task_started", "timestamp": 1775560001.0, "data": {"task_id": task_id_completed, "model": "gemini-2.5-pro"}},
        {"event": "phase_changed", "timestamp": 1775560002.0, "data": {"phase": "analysis"}},
        {"event": "tool_called", "timestamp": 1775560003.0, "data": {"tool": "read_file", "parameters": {"path": "src/utils.py"}}},
        {"event": "observation_received", "timestamp": 1775560004.0, "data": {"tool": "read_file", "output": "def format_currency(): pass"}},
        {"event": "phase_changed", "timestamp": 1775560005.0, "data": {"phase": "execution"}},
        {"event": "tool_called", "timestamp": 1775560006.0, "data": {"tool": "write_to_file", "parameters": {"path": "src/utils.py"}}},
        {"event": "observation_received", "timestamp": 1775560007.0, "data": {"tool": "write_to_file", "output": "File updated successfully"}},
        {"event": "task_completed", "timestamp": 1775560008.0, "data": {"result": "Fungsi format rupiah selesai diimplementasikan."}},
    ]
    p_completed = FIXTURES_DIR / f"{task_id_completed}.log"
    _write_jsonl(p_completed, events_completed)
    out_files["completed"] = p_completed

    # 2. FAILED
    task_id_failed = "phase0_canonical_02_failed"
    events_failed = [
        {"event": "task_requested", "timestamp": 1775560010.0, "data": {"prompt": "Perbaiki modul database auth"}},
        {"event": "task_started", "timestamp": 1775560011.0, "data": {"task_id": task_id_failed, "model": "gemini-2.5-pro"}},
        {"event": "phase_changed", "timestamp": 1775560012.0, "data": {"phase": "execution"}},
        {"event": "tool_called", "timestamp": 1775560013.0, "data": {"tool": "run_command", "parameters": {"command": "python manage.py migrate"}}},
        {"event": "observation_received", "timestamp": 1775560014.0, "data": {"tool": "run_command", "exit_code": 1, "output": "OperationalError: database locked"}},
        {"event": "task_failed", "timestamp": 1775560015.0, "data": {"error": "OperationalError: database locked, migrasi dihentikan."}},
    ]
    p_failed = FIXTURES_DIR / f"{task_id_failed}.log"
    _write_jsonl(p_failed, events_failed)
    out_files["failed"] = p_failed

    # 3. TIMEOUT (failed with timeout indicator)
    task_id_timeout = "phase0_canonical_03_timeout"
    events_timeout = [
        {"event": "task_requested", "timestamp": 1775560020.0, "data": {"prompt": "Proses parsing log berukuran besar"}},
        {"event": "task_started", "timestamp": 1775560021.0, "data": {"task_id": task_id_timeout, "model": "gemini-2.5-pro"}},
        {"event": "phase_changed", "timestamp": 1775560022.0, "data": {"phase": "execution"}},
        {"event": "warning", "timestamp": 1775560030.0, "data": {"message": "Execution time approaching deadline limit"}},
        {"event": "task_failed", "timestamp": 1775560035.0, "data": {"error": "Task execution timed out after 180 seconds"}},
    ]
    p_timeout = FIXTURES_DIR / f"{task_id_timeout}.log"
    _write_jsonl(p_timeout, events_timeout)
    out_files["timeout"] = p_timeout

    # 4. RETRY (transient error -> warning -> retry_scheduled -> success completed)
    task_id_retry = "phase0_canonical_04_retry"
    events_retry = [
        {"event": "task_requested", "timestamp": 1775560040.0, "data": {"prompt": "Hubungkan dengan upstream API"}},
        {"event": "task_started", "timestamp": 1775560041.0, "data": {"task_id": task_id_retry, "model": "gemini-2.5-pro"}},
        {"event": "warning", "timestamp": 1775560042.0, "data": {"message": "Provider HTTP 429 Too Many Requests, scheduling retry attempt 1/3"}},
        {"event": "provider_retry", "timestamp": 1775560044.0, "data": {"attempt": 1, "backoff_seconds": 2.0}},
        {"event": "phase_changed", "timestamp": 1775560047.0, "data": {"phase": "execution"}},
        {"event": "tool_called", "timestamp": 1775560048.0, "data": {"tool": "web_fetch", "parameters": {"url": "https://api.internal/data"}}},
        {"event": "observation_received", "timestamp": 1775560049.0, "data": {"tool": "web_fetch", "output": "200 OK payload"}},
        {"event": "task_completed", "timestamp": 1775560050.0, "data": {"result": "Upstream API berhasil terhubung setelah retry 1x."}},
    ]
    p_retry = FIXTURES_DIR / f"{task_id_retry}.log"
    _write_jsonl(p_retry, events_retry)
    out_files["retry"] = p_retry

    # 5. CANCELLED
    task_id_cancelled = "phase0_canonical_05_cancelled"
    events_cancelled = [
        {"event": "task_requested", "timestamp": 1775560060.0, "data": {"prompt": "Build ulang container image besar"}},
        {"event": "task_started", "timestamp": 1775560061.0, "data": {"task_id": task_id_cancelled, "model": "gemini-2.5-pro"}},
        {"event": "phase_changed", "timestamp": 1775560062.0, "data": {"phase": "execution"}},
        {"event": "task_cancelled", "timestamp": 1775560065.0, "data": {"reason": "Dibatalkan oleh pengguna via stop_task"}},
    ]
    p_cancelled = FIXTURES_DIR / f"{task_id_cancelled}.log"
    _write_jsonl(p_cancelled, events_cancelled)
    out_files["cancelled"] = p_cancelled

    return out_files


def verify_canonical_logs(out_files: dict[str, Path]) -> None:
    # 1. Verifikasi completed
    reader_c = TaskLogReader(root=PROJECT_ROOT, task_id="phase0_canonical_01_completed")
    reader_c.path = out_files["completed"]
    info_c = reader_c.get_task_info()
    assert info_c is not None, "Log completed tidak terbaca"
    assert info_c["status"] == "completed", f"Status completed salah: {info_c['status']}"
    assert "format rupiah" in info_c["task"]

    # 2. Verifikasi failed
    reader_f = TaskLogReader(root=PROJECT_ROOT, task_id="phase0_canonical_02_failed")
    reader_f.path = out_files["failed"]
    info_f = reader_f.get_task_info()
    assert info_f is not None, "Log failed tidak terbaca"
    assert info_f["status"] == "failed", f"Status failed salah: {info_f['status']}"
    assert "OperationalError" in (info_f["error"] or "")

    # 3. Verifikasi timeout
    reader_t = TaskLogReader(root=PROJECT_ROOT, task_id="phase0_canonical_03_timeout")
    reader_t.path = out_files["timeout"]
    info_t = reader_t.get_task_info()
    assert info_t is not None, "Log timeout tidak terbaca"
    assert info_t["status"] == "failed", f"Status timeout salah: {info_t['status']}"
    assert "timed out" in (info_t["error"] or "")

    # 4. Verifikasi retry
    reader_r = TaskLogReader(root=PROJECT_ROOT, task_id="phase0_canonical_04_retry")
    reader_r.path = out_files["retry"]
    info_r = reader_r.get_task_info()
    assert info_r is not None, "Log retry tidak terbaca"
    assert info_r["status"] == "completed", f"Status retry salah: {info_r['status']}"

    # 5. Verifikasi cancelled
    reader_can = TaskLogReader(root=PROJECT_ROOT, task_id="phase0_canonical_05_cancelled")
    reader_can.path = out_files["cancelled"]
    info_can = reader_can.get_task_info()
    assert info_can is not None, "Log cancelled tidak terbaca"
    assert info_can["status"] == "cancelled", f"Status cancelled salah: {info_can['status']}"
    print(f"[OK] 5 Log Kanonik Task berhasil diverifikasi di: {FIXTURES_DIR}")


def main() -> int:
    print("=== Membangun & Memverifikasi Log Kanonik 5 Kondisi Task ===")
    out_files = generate_logs()
    verify_canonical_logs(out_files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
