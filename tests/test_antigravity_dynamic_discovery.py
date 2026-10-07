"""Unit tests untuk Dynamic Semantic & AST Code Discovery pada Antigravity Provider."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_ai.config.settings import AntigravityConfig
from agent_ai.providers.base import GenerateOptions
from agent_ai.providers.antigravity import (
    AntigravityProvider,
    _detect_manifest_intel,
    _fallback_dynamic_code_scan,
    _resolve_dynamic_code_context,
    _resolve_semantic_search_candidates,
)


def test_detect_manifest_package_json_missing_test(tmp_path: Path):
    """Pastikan manifest detection memperingatkan ketiadaan test script pada package.json."""
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text(
        json.dumps({
            "name": "presentasi",
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "lint": "next lint"
            }
        }),
        encoding="utf-8",
    )

    intel = _detect_manifest_intel(tmp_path)
    assert len(intel) == 1
    assert "package.json detected" in intel[0]
    assert "NO 'test' script found" in intel[0]
    assert "do NOT run npm test" in intel[0]


def test_detect_manifest_package_json_with_test(tmp_path: Path):
    """Pastikan manifest detection mengonfirmasi bila script test ada."""
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text(
        json.dumps({
            "name": "myapp",
            "scripts": {
                "test": "vitest",
                "build": "vite build"
            }
        }),
        encoding="utf-8",
    )

    intel = _detect_manifest_intel(tmp_path)
    assert len(intel) == 1
    assert "script 'test' is available" in intel[0]


def test_detect_manifest_multiple_languages(tmp_path: Path):
    """Pastikan manifest detection mendeteksi pyproject, cargo, dan go."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='my-py'", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text("[package]\nname='my-rs'", encoding="utf-8")

    intel = _detect_manifest_intel(tmp_path)
    assert any("pyproject.toml detected" in item for item in intel)
    assert any("Cargo.toml detected" in item for item in intel)


def test_fallback_dynamic_code_scan_across_arbitrary_folders(tmp_path: Path):
    """Pastikan dynamic scan mampu mencari ke seluruh folder dinamis (bukan hanya src/)."""
    # Buat berbagai berkas di berbagai folder
    app_dir = tmp_path / "app" / "routes"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text("export default function Page() { return <div>Home</div>; }", encoding="utf-8")

    comp_dir = tmp_path / "components" / "editor"
    comp_dir.mkdir(parents=True)
    (comp_dir / "Toolbar.tsx").write_text("export function Toolbar() { return null; }\nexport type ToolbarState = {};", encoding="utf-8")
    (comp_dir / "SlideCanvas.tsx").write_text("export const SlideCanvas = () => {};", encoding="utf-8")

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "tokens.ts").write_text("export const TOKEN_A = 'abc';", encoding="utf-8")

    # Kueri mencari Toolbar
    results = _fallback_dynamic_code_scan(tmp_path, query="Tolong tambahkan tombol di Toolbar editor", limit=5)
    assert len(results) >= 1
    paths = [r["path"] for r in results]
    assert "components/editor/Toolbar.tsx" in paths
    # Periksa ekstraksi simbol
    toolbar_res = next(r for r in results if r["path"] == "components/editor/Toolbar.tsx")
    assert "Toolbar" in toolbar_res["symbols"]


def test_resolve_dynamic_code_context_mode_limits(tmp_path: Path):
    """Pastikan limit jumlah target berkas mematuhi mode (fast=3, balanced=5, deep=8)."""
    for i in range(10):
        (tmp_path / f"handler_{i}.py").write_text(f"def handler_{i}(): pass\n", encoding="utf-8")

    ctx_fast = _resolve_dynamic_code_context(str(tmp_path), query="handler", mode="fast")
    assert "FAST Mode - Top 3" in ctx_fast
    assert "1. " in ctx_fast
    assert "3. " in ctx_fast
    assert "4. " not in ctx_fast

    ctx_balanced = _resolve_dynamic_code_context(str(tmp_path), query="handler", mode="balanced")
    assert "BALANCED Mode - Top 5" in ctx_balanced
    assert "5. " in ctx_balanced
    assert "6. " not in ctx_balanced

    ctx_deep = _resolve_dynamic_code_context(str(tmp_path), query="handler", mode="deep")
    assert "DEEP Mode - Top 8" in ctx_deep
    assert "8. " in ctx_deep
    assert "9. " not in ctx_deep


def test_resolve_semantic_search_candidates_mocked(tmp_path: Path):
    """Pastikan kandidat semantik diekstrak dengan baik ketika service aktif."""
    mock_service_inst = MagicMock()
    mock_service_inst.__enter__.return_value = mock_service_inst
    mock_service_inst.search.return_value = [
        {"path": "src/app/page.tsx", "symbol": "Page", "kind": "function", "start_line": 1, "end_line": 20},
        {"path": "src/components/Toolbar.tsx", "symbol": "Toolbar", "kind": "class", "start_line": 10, "end_line": 50},
    ]

    with patch("agent_ai.repointel.semantic.availability.is_available", return_value=(True, "")):
        with patch("agent_ai.repointel.semantic.paths.resolve_vectors_db") as mock_res_db:
            fake_db = tmp_path / "vectors.db"
            fake_db.touch()
            mock_res_db.return_value = fake_db
            with patch("agent_ai.repointel.semantic.service.SemanticIndexService", return_value=mock_service_inst):
                candidates = _resolve_semantic_search_candidates(tmp_path, query="toolbar page", limit=3)

    assert len(candidates) == 2
    assert candidates[0]["path"] == "src/app/page.tsx"
    assert candidates[0]["symbol"] == "Page"
    assert candidates[1]["path"] == "src/components/Toolbar.tsx"
    assert candidates[1]["symbol"] == "Toolbar"


def test_antigravity_generate_injects_workspace_intel(tmp_path: Path):
    """Pastikan AntigravityProvider.generate() menyuntikkan intel ke dalam input_text CLI."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "scripts": {"build": "vite build"}}),
        encoding="utf-8"
    )
    (tmp_path / "main.py").write_text("def run_app(): pass\n", encoding="utf-8")

    cfg = AntigravityConfig(cli_path="/mock/agy")
    prov = AntigravityProvider(config=cfg)

    captured_cmd = []

    def fake_subprocess_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        mock_res = MagicMock()
        mock_res.return_value = 0
        mock_res.returncode = 0
        mock_res.stdout = json.dumps({"response": "Done implementasi."})
        mock_res.stderr = ""
        return mock_res

    options = GenerateOptions(
        model="gemini-3.8-flash-medium",
        extra={
            "workspace_root": str(tmp_path),
            "mode": "fast",
        }
    )

    with patch("os.path.exists", return_value=True):
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            prov.generate(
                prompt="Tolong ubah run_app di main.py",
                options=options,
            )

    assert len(captured_cmd) > 0
    prompt_idx = captured_cmd.index("-p")
    injected_prompt = captured_cmd[prompt_idx + 1]

    # Verifikasi Workspace Intel ada dalam prompt CLI
    assert "WORKSPACE INTEL (DYNAMIC CODE DISCOVERY - PRE-COMPUTED)" in injected_prompt
    assert "package.json detected" in injected_prompt
    assert "NO 'test' script found" in injected_prompt
    assert "main.py" in injected_prompt
    assert "--dangerously-skip-permissions" in captured_cmd


def test_antigravity_stream_json_result_event_breaks_cleanly(tmp_path: Path):
    """Pastikan stream-json langsung memproses event 'result' dan tidak menggantung."""
    cfg = AntigravityConfig(cli_path="/mock/agy")
    prov = AntigravityProvider(config=cfg)

    # Simulasi stream NDJSON nyata dari Antigravity CLI
    stream_lines = [
        json.dumps({"event": "step_update", "step_update": {"step_type": "tool", "state": "DONE", "tool_name": "replace_file_content", "tool_info": {"parameters": {"path": "useDeck.ts"}}}}),
        json.dumps({"event": "step_update", "step_update": {"step_type": "thought", "thought_delta": "Perubahan slide berhasil diterapkan."}}),
        json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": "Selesai menyunting berkas presentasi.", "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160}}}),
    ]

    captured_events = []
    def fake_event_sink(evt_name, payload):
        captured_events.append((evt_name, payload))

    options = GenerateOptions(
        extra={
            "event_sink": fake_event_sink,
            "workspace_root": str(tmp_path),
        }
    )

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "\n".join(stream_lines)
    mock_res.stderr = ""

    with patch("os.path.exists", return_value=True):
        with patch("subprocess.run", return_value=mock_res):
            res = prov.generate(prompt="edit useDeck", options=options)

    assert res.text == "Selesai menyunting berkas presentasi."
    assert "Perubahan slide berhasil diterapkan." in (res.reasoning or "")
    # Sesuai kontrak ASYNC-08: AntigravityProvider tidak memancarkan provider_response manual
    # ke event_sink (pencegahan duplikasi token di UI). Data usage disimpan di res.raw
    # dan dipancarkan oleh Orchestrator secara terpusat.
    usage_events = [p for name, p in captured_events if name == "provider_response"]
    assert len(usage_events) == 0
    assert res.raw.get("usage", {}).get("total_tokens") == 160

