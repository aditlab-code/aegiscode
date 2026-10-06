"""Pengujian regresi untuk Milestone 2 (Tahap B) — Konsistensi Sesi, Live Events, dan Validasi Input.

Mencakup pengujian otomatis untuk:
- AI-04: Kontrak input multimodal teks dan gambar di GatewayService.consult.
- AI-05: Pemasangan callback persistensi _load_sessions_from_store dan eliminasi metode duplikat di ConsultantService.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_ai.consultant.service import ConsultantService


def test_ai05_consultant_service_has_single_load_sessions_method_and_persists_callback():
    """Memverifikasi bahwa ConsultantService hanya memiliki 1 definisi _load_sessions_from_store."""
    service_file = Path("src/agent_ai/consultant/service.py")
    tree = ast.parse(service_file.read_text(encoding="utf-8"))

    cls_node = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ConsultantService"
    )

    load_methods = [
        node for node in cls_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load_sessions_from_store"
    ]

    assert len(load_methods) == 1, (
        f"Diharapkan tepat 1 metode _load_sessions_from_store, ditemukan {len(load_methods)}"
    )

    # Verifikasi bahwa callback persist_cb dipasang di dalam metode tersebut
    method_source = ast.unparse(load_methods[0])
    assert "session._on_change = persist_cb" in method_source or "_on_change" in method_source


def test_ai04_gateway_consult_accepts_image_only_with_default_prompt():
    """Memverifikasi GatewayService.consult mengisi prompt default bila teks kosong tetapi gambar dilampirkan."""
    from web.django_app.api.services import GatewayService

    gateway = GatewayService.__new__(GatewayService)
    gateway._normalize_images = lambda imgs: imgs or []
    gateway.project_store = MagicMock()
    gateway.project_store.get_active_project_id = MagicMock(return_value="test-proj")
    gateway._resolve_workspace_root = MagicMock(return_value="/tmp/test-workspace")

    mock_result = MagicMock()
    mock_result.to_dict = MagicMock(return_value={
        "session_id": "sess-1",
        "reply": "Gambar berhasil dianalisis.",
        "status": "success",
        "error": None,
        "iterations": 1,
        "tool_events": [],
        "task_proposal": None,
    })
    mock_consultant_service = MagicMock()
    mock_consultant_service.consult = MagicMock(return_value=mock_result)
    gateway._get_consultant_service = MagicMock(return_value=mock_consultant_service)
    gateway._consultant_service = mock_consultant_service

    images = [{"data": "base64data", "mime_type": "image/png", "filename": "test.png"}]

    # Panggil dengan message kosong string "" tetapi membawa gambar dan provider override
    mock_provider = MagicMock()
    res = gateway.consult(
        message="",
        images=images,
        session_id="sess-1",
        project_id="test-proj",
        mode="quick",
        provider=mock_provider,
    )

    assert res["status"] == "success"
    # Pastikan panggilan ke ConsultantService menerima prompt default
    called_prompt = mock_consultant_service.consult.call_args[0][0]
    assert "Tolong analisis gambar yang dilampirkan." in called_prompt


def test_ai04_gateway_consult_rejects_empty_message_when_no_images():
    """Memverifikasi GatewayService.consult tetap menolak pesan kosong jika TIDAK ada gambar."""
    from web.django_app.api.services import GatewayService, ValidationError

    gateway = GatewayService.__new__(GatewayService)
    gateway._normalize_images = lambda imgs: imgs or []

    with pytest.raises(ValidationError, match="Field 'message' wajib diisi dan tidak boleh kosong."):
        gateway.consult(
            message="   ",
            images=None,
        )
