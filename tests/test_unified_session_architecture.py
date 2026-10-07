"""Test Suite untuk Unified Threaded Session Architecture.

Menguji:
1. Unified models & dataclass serialization/deserialization
2. SQLite UnifiedSessionStore CRUD, isolasi per project, auto-title, dan migrasi transparan
3. Gateway API endpoints (/api/sessions/*) via Django test client
4. Backward compatibility facade (/api/tasks & /api/consultant/consult)
5. Penyelarasan ID Sesi, isolasi aliran event (SSE context_type), dan persistensi state harmonis
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Pastikan path source & django app terdaftar
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT / "web" / "django_app") not in sys.path:
    sys.path.insert(0, str(_ROOT / "web" / "django_app"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"

import django
from django.test import Client

django.setup()

from agent_ai.session.unified_models import (
    TurnExecutionData,
    UnifiedSession,
    UnifiedTurn,
    new_session_id,
    new_turn_id,
)
from agent_ai.session.unified_store import UnifiedSessionStore
from api.services import GatewayService, get_service


# ============================================================================ #
# 1. Model & Serialization Tests
# ============================================================================ #

def test_unified_models_serialization():
    """Memastikan konversi model ke dict dan rekonstruksi from_dict akurat."""
    exec_data = TurnExecutionData(
        task_id="task_abc",
        status="completed",
        tool_events=[{"tool": "read_file", "target": "main.py"}],
        changes=[{"file": "main.py", "kind": "modify"}],
        report="Semua perubahan berhasil diterapkan.",
        error=None,
        usage={"prompt_tokens": 120, "completion_tokens": 80},
    )
    exec_dict = exec_data.to_dict()
    assert exec_dict["task_id"] == "task_abc"
    assert exec_dict["status"] == "completed"
    assert len(exec_dict["changes"]) == 1

    reconstructed_exec = TurnExecutionData.from_dict(exec_dict)
    assert reconstructed_exec is not None
    assert reconstructed_exec.task_id == "task_abc"
    assert reconstructed_exec.usage == {"prompt_tokens": 120, "completion_tokens": 80}

    turn = UnifiedTurn(
        turn_id="turn_123",
        role="assistant",
        mode="agent",
        content="Hasil tugas",
        created_at=time.time(),
        images=None,
        execution=reconstructed_exec,
    )
    turn_dict = turn.to_dict()
    assert turn_dict["turn_id"] == "turn_123"
    assert turn_dict["execution"]["task_id"] == "task_abc"

    reconstructed_turn = UnifiedTurn.from_dict(turn_dict)
    assert reconstructed_turn.turn_id == "turn_123"
    assert reconstructed_turn.role == "assistant"
    assert reconstructed_turn.execution is not None
    assert reconstructed_turn.execution.task_id == "task_abc"

    sess = UnifiedSession(
        session_id="sess_xyz",
        project_id="proj_1",
        title="Testing Session",
        created_at=time.time(),
        updated_at=time.time(),
        turns=[turn],
        execution_state="idle",
        active_task_id=None,
    )
    sess_dict = sess.to_dict()
    assert sess_dict["session_id"] == "sess_xyz"
    assert sess_dict["turn_count"] == 1

    reconstructed_sess = UnifiedSession.from_dict(sess_dict)
    assert reconstructed_sess.session_id == "sess_xyz"
    assert len(reconstructed_sess.turns) == 1
    assert reconstructed_sess.turns[0].execution.status == "completed"


# ============================================================================ #
# 2. SQLite Store CRUD, Isolasi & Migrasi
# ============================================================================ #

def test_unified_store_crud_and_isolation():
    """Menguji pembuatan sesi, turn multi-mode, update execution, dan isolasi project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_aegis.db"
        store = UnifiedSessionStore(db_path=db_path, auto_migrate=False)

        # Buat sesi untuk project 1
        s1 = store.create_session(project_id="proj_alpha", title="Sesi Alpha")
        assert s1.session_id.startswith("sess_")
        assert s1.title == "Sesi Alpha"

        # Buat sesi untuk project 2
        s2 = store.create_session(project_id="proj_beta", title="Sesi Beta")
        assert s2.session_id != s1.session_id

        # Isolasi: list_sessions per project
        list_alpha = store.list_sessions(project_id="proj_alpha")
        assert len(list_alpha) == 1
        assert list_alpha[0]["session_id"] == s1.session_id

        list_beta = store.list_sessions(project_id="proj_beta")
        assert len(list_beta) == 1
        assert list_beta[0]["session_id"] == s2.session_id

        # Multi-turn di Sesi Alpha (kombinasi ask dan agent dalam sesi yang sama)
        u1 = UnifiedTurn(turn_id=new_turn_id(), role="user", mode="ask", content="Bagaimana arsitektur ini?")
        store.append_turn(s1.session_id, u1)

        a1 = UnifiedTurn(turn_id=new_turn_id(), role="assistant", mode="ask", content="Ini arsitektur unified session.")
        store.append_turn(s1.session_id, a1)

        u2 = UnifiedTurn(turn_id=new_turn_id(), role="user", mode="agent", content="Tuliskan file README.md")
        store.append_turn(s1.session_id, u2)

        tid = new_turn_id()
        exec_init = TurnExecutionData(task_id="task_99", status="running")
        a2 = UnifiedTurn(turn_id=tid, role="assistant", mode="agent", content="Menjalankan...", execution=exec_init)
        store.append_turn(s1.session_id, a2)
        store.update_session_state(s1.session_id, "running", active_task_id="task_99")

        fetched = store.get_session(s1.session_id)
        assert fetched is not None
        assert fetched.execution_state == "running"
        assert fetched.active_task_id == "task_99"
        assert len(fetched.turns) == 4
        assert fetched.turns[0].mode == "ask"
        assert fetched.turns[2].mode == "agent"

        # Update execution saat task selesai
        exec_done = TurnExecutionData(
            task_id="task_99",
            status="completed",
            changes=[{"file": "README.md", "kind": "create"}],
            report="README berhasil ditulis.",
        )
        store.update_turn_execution(s1.session_id, tid, exec_done)
        store.update_session_state(s1.session_id, "idle", active_task_id=None)

        fetched_after = store.get_session(s1.session_id)
        assert fetched_after.execution_state == "idle"
        assert fetched_after.active_task_id is None
        assert fetched_after.turns[3].execution.status == "completed"
        assert len(fetched_after.turns[3].execution.changes) == 1

        # Rename session
        store.rename_session(s1.session_id, "Sesi Alpha Direname")
        assert store.get_session(s1.session_id).title == "Sesi Alpha Direname"

        # Delete session
        deleted = store.delete_session(s1.session_id)
        assert deleted is True
        assert store.get_session(s1.session_id) is None


def test_unified_store_auto_migration_from_json():
    """Menguji migrasi transparan berkas JSON legacy ke SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_aegis.db"
        json_path = Path(tmpdir) / "consultant_sessions.json"

        legacy_data = {
            "sessions": [
                {
                    "session_id": "legacy_001",
                    "project_id": "proj_legacy",
                    "title": "Percakapan Lama",
                    "created_at": 1690000000.0,
                    "updated_at": 1690000050.0,
                    "turns": [
                        {"role": "user", "text": "Pertanyaan lama"},
                        {"role": "consultant", "text": "Jawaban lama"},
                    ],
                }
            ]
        }
        json_path.write_text(json.dumps(legacy_data), encoding="utf-8")

        store = UnifiedSessionStore(db_path=db_path, auto_migrate=True, legacy_json_path=json_path)
        sess = store.get_session("legacy_001")
        assert sess is not None
        assert sess.title == "Percakapan Lama"
        assert len(sess.turns) == 2
        assert sess.turns[0].content == "Pertanyaan lama"
        assert sess.turns[0].role == "user"
        assert sess.turns[1].content == "Jawaban lama"
        assert sess.turns[1].role == "consultant"
        assert sess.turns[1].mode == "ask"


# ============================================================================ #
# 3. Gateway REST API Endpoints (/api/sessions/*)
# ============================================================================ #

def test_api_sessions_lifecycle():
    """Menguji endpoint REST /api/sessions: create, list, get, rename, delete."""
    client = Client()

    # 1. Create session
    create_resp = client.post(
        "/api/sessions",
        data=json.dumps({"title": "Thread Eksperimen", "project_id": "proj_test"}),
        content_type="application/json",
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    sid = created_data["session_id"]
    assert sid.startswith("sess_")
    assert created_data["title"] == "Thread Eksperimen"

    # 2. List sessions
    list_resp = client.get("/api/sessions?project_id=proj_test")
    assert list_resp.status_code == 200
    sessions = list_resp.json()["sessions"]
    assert any(s["session_id"] == sid for s in sessions)

    # 3. Get session detail
    detail_resp = client.get(f"/api/sessions/{sid}?project_id=proj_test")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["session_id"] == sid
    assert detail_resp.json()["title"] == "Thread Eksperimen"

    # 4. Rename session (PATCH)
    patch_resp = client.patch(
        f"/api/sessions/{sid}?project_id=proj_test",
        data=json.dumps({"title": "Thread Direname"}),
        content_type="application/json",
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Thread Direname"

    # 5. Cancel session run (POST /cancel saat idle mengembalikan cancelled: True)
    cancel_resp = client.post(f"/api/sessions/{sid}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled"] is True

    # 6. Delete session (DELETE)
    del_resp = client.delete(f"/api/sessions/{sid}?project_id=proj_test")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # 7. Pastikan sudah terhapus
    not_found_resp = client.get(f"/api/sessions/{sid}?project_id=proj_test")
    assert not_found_resp.status_code == 404


def test_api_sessions_turns_multi_mode():
    """Menguji pengiriman turn mode ask dan mode agent ke sesi yang sama."""
    client = Client()

    # Buat sesi
    c_resp = client.post(
        "/api/sessions",
        data=json.dumps({"title": "Multi-mode Thread"}),
        content_type="application/json",
    )
    assert c_resp.status_code == 201
    sid = c_resp.json()["session_id"]

    # Kirim turn mode "ask"
    ask_resp = client.post(
        f"/api/sessions/{sid}/turns",
        data=json.dumps({"content": "Halo, bisakah jelaskan proyek ini?", "mode": "ask"}),
        content_type="application/json",
    )
    assert ask_resp.status_code == 201
    ask_data = ask_resp.json()
    assert ask_data["session_id"] == sid
    assert ask_data["user_turn"]["content"] == "Halo, bisakah jelaskan proyek ini?"
    assert ask_data["user_turn"]["mode"] == "ask"
    assert "assistant_turn" in ask_data

    # Ambil sesi untuk verifikasi turn tersimpan
    sess_resp = client.get(f"/api/sessions/{sid}")
    assert sess_resp.status_code == 200
    turns = sess_resp.json()["turns"]
    assert len(turns) >= 2


# ============================================================================ #
# 4. Backward Compatibility Facade & Penyelarasan ID Sesi
# ============================================================================ #

def test_legacy_tasks_facade_and_session_alignment():
    """Memastikan POST /api/tasks mengaitkan task ke unified session secara harmonis."""
    client = Client()

    # Buat unified session terlebih dahulu
    sess_resp = client.post(
        "/api/sessions",
        data=json.dumps({"title": "Session dari Facade"}),
        content_type="application/json",
    )
    sid = sess_resp.json()["session_id"]

    # Kirim task via endpoint lama /api/tasks dengan menyertakan session_id di metadata
    task_resp = client.post(
        "/api/tasks",
        data=json.dumps({
            "task": "Buat file verifikasi facade",
            "metadata": {"session_id": sid},
        }),
        content_type="application/json",
    )
    assert task_resp.status_code == 201
    tdata = task_resp.json()
    task_id = tdata["task_id"]

    # Verifikasi bahwa session_id yang dipakai runtime selaras
    assert tdata["session_id"] == sid

    # Periksa unified session: turn harus otomatis tersinkronisasi
    detail = client.get(f"/api/sessions/{sid}").json()
    matching_turns = [
        t for t in detail["turns"]
        if t.get("execution") and t["execution"].get("task_id") == task_id
    ]
    assert len(matching_turns) == 1
    assert matching_turns[0]["mode"] == "agent"


def test_sse_event_context_type_isolation():
    """Memastikan emit_event selalu menyertakan context_type dan mode untuk isolasi tab."""
    service = get_service()
    sid = new_session_id()

    # Event tanpa task_id (konsultasi)
    evt_consult = service.emit_event(sid, "provider_response", payload={"step": 1})
    assert evt_consult["payload"]["context_type"] == "consultation"
    assert evt_consult["payload"]["mode"] == "ask"

    # Event dengan task_id (agent task)
    evt_agent = service.emit_event(sid, "tool_called", task_id="task_xyz", payload={"tool": "edit"})
    assert evt_agent["payload"]["context_type"] == "agent"
    assert evt_agent["payload"]["mode"] == "agent"


def test_task_creation_without_session_id_does_not_create_ghost_session():
    """Memastikan pembuatan task queue mandiri tanpa session_id tidak mencemari database dengan sesi hantu."""
    client = Client()
    service = get_service()

    sessions_before = service.unified_session_store.list_sessions()
    count_before = len(sessions_before)

    resp = client.post(
        "/api/tasks",
        data=json.dumps({"task": "Task antrian mandiri tanpa session"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    tdata = resp.json()
    assert tdata["task_id"]

    sessions_after = service.unified_session_store.list_sessions()
    assert len(sessions_after) == count_before


def test_send_turn_message_agent_mode_creates_exactly_one_pair_of_turns():
    """Memastikan eksekusi turn mode agent hanya menghasilkan tepat 1 user turn dan 1 assistant turn (tidak duplikat)."""
    client = Client()

    sess_resp = client.post(
        "/api/sessions",
        data=json.dumps({"title": "Sesi Tes Giliran Tunggal"}),
        content_type="application/json",
    )
    assert sess_resp.status_code == 201
    sid = sess_resp.json()["session_id"]

    turn_resp = client.post(
        f"/api/sessions/{sid}/turns",
        data=json.dumps({
            "content": "Jalankan refactor modular",
            "mode": "agent",
        }),
        content_type="application/json",
    )
    assert turn_resp.status_code == 201
    res_data = turn_resp.json()
    assert "user_turn" in res_data
    assert "assistant_turn" in res_data

    detail_resp = client.get(f"/api/sessions/{sid}")
    assert detail_resp.status_code == 200
    turns = detail_resp.json()["turns"]

    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[0]["mode"] == "agent"
    assert turns[1]["role"] == "assistant"
    assert turns[1]["mode"] == "agent"

