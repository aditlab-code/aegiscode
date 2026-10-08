"""Verifikasi folder .aegis TIDAK muncul di File Explorer AegisCode.

Masalah: File Explorer (apps/frontend/src/components/FileExplorer.vue) merender
daftar file/folder dari endpoint GET /api/files, yang di backend memakai
ListFilesTool AegisCode (src/agent_ai/tools/filesystem.py). Folder internal
AegisCode `.aegis` ikut terdaftar sehingga tampil di UI.

Perbaikan (HANYA menyembunyikan dari tampilan, TIDAK menghapus/mengubah
filesystem):
    1. Backend: `.aegis` ditambahkan ke `_IGNORED_DIRS` pada
       ListFilesTool/SearchCodeTool -> entri `.aegis` tidak dikembalikan API.
    2. Frontend: FileExplorer.vue memfilter nama `.aegis` (HIDDEN_NAMES)
       sebagai pengaman di UI.

Verifier ini:
    - Membuat fixture nyata (folder `.aegis` + folder biasa) di
      dummy_test/explorer_fixture.
    - Menjalankan ListFilesTool terhadap fixture dan memastikan:
        * `.aegis` TIDAK ada di daftar entri (hidden),
        * folder/file biasa (src, docs, README.md) TETAP muncul.
    - Memastikan search_code tidak menelusuri isi `.aegis`.
    - Memastikan filesystem TIDAK berubah (folder `.aegis` masih ada di disk).
    - Cek statis sumber frontend memuat filter `.aegis`.
    Fixture dibersihkan setelah test.

Jalankan:
    python scripts/check_explorer_hidden_aegis.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_ai.tools.filesystem import ListFilesTool, SearchCodeTool  # noqa: E402

DUMMY_ROOT = PROJECT_ROOT / "dummy_test"
FIXTURE = DUMMY_ROOT / "explorer_fixture"
FRONTEND_SRC = PROJECT_ROOT / "apps" / "frontend" / "src" / "components" / "FileExplorer.vue"


def setup_fixture() -> None:
    """Buat fixture project dummy: punya folder `.aegis` + folder biasa."""
    shutil.rmtree(FIXTURE, ignore_errors=True)
    (FIXTURE / ".aegis" / "brain").mkdir(parents=True, exist_ok=True)
    (FIXTURE / "src").mkdir(parents=True, exist_ok=True)
    (FIXTURE / "docs").mkdir(parents=True, exist_ok=True)

    (FIXTURE / "README.md").write_text("# dummy fixture\n", encoding="utf-8")
    (FIXTURE / ".aegis" / "project.json").write_text(
        '{ "note": "internal aegis - harus hidden" }\n', encoding="utf-8"
    )
    (FIXTURE / ".aegis" / "brain" / "facts.md").write_text(
        "- dummy fact aegis\n", encoding="utf-8"
    )
    (FIXTURE / "src" / "main.py").write_text('print("hi")\n', encoding="utf-8")
    (FIXTURE / "docs" / "guide.md").write_text("# guide\n", encoding="utf-8")


def teardown_fixture() -> None:
    shutil.rmtree(FIXTURE, ignore_errors=True)


def _run() -> int:
    assert FIXTURE.is_dir(), f"fixture tidak ada: {FIXTURE}"
    aegis_dir = FIXTURE / ".aegis"
    assert aegis_dir.is_dir(), "fixture harus punya folder .aegis di disk"

    # 1) ListFilesTool root = fixture -> `.aegis` HARUS hidden, lain tampil.
    tool = ListFilesTool(root=FIXTURE)
    listing = tool.execute(path=".")
    names = {e["name"] for e in listing["entries"]}

    assert ".aegis" not in names, f".aegis masih muncul di list_files: {names}"
    for expected in ("README.md", "src", "docs"):
        assert expected in names, f"entri normal '{expected}' hilang dari listing: {names}"
    print(f"[1] list_files('.') menyembunyikan .aegis, entri normal tampil: OK -> {sorted(names)}")

    # 2) ListFilesTool di dalam folder biasa tetap normal.
    sub = tool.execute(path="src")
    sub_names = {e["name"] for e in sub["entries"]}
    assert "main.py" in sub_names, f"isi src/ harus tampil: {sub_names}"
    print(f"[2] list_files('src') tetap normal: OK -> {sorted(sub_names)}")

    # 3) search_code TIDAK menelusuri isi `.aegis`.
    search = SearchCodeTool(root=FIXTURE)
    result = search.execute(query="dummy fact", path=".")
    hit_files = {m["file"].replace("\\", "/") for m in result["matches"]}
    assert not any(".aegis" in f for f in hit_files), (
        f"search_code menembus metadata: {hit_files}"
    )
    print("[3] search_code tidak menelusuri .aegis: OK")

    # 4) Filesystem TIDAK berubah: folder `.aegis` masih ada di disk.
    assert aegis_dir.is_dir(), "folder metadata di disk TIDAK boleh hilang"
    assert (aegis_dir / "project.json").exists()
    print("[4] folder .aegis tetap ada di disk (tidak dihapus): OK")

    # 5) Cek statis: sumber frontend memuat filter `.aegis`.
    src_text = FRONTEND_SRC.read_text(encoding="utf-8")
    assert ".aegis" in src_text, "FileExplorer.vue tidak memuat filter .aegis"
    assert "HIDDEN_NAMES" in src_text and "visibleEntries" in src_text, (
        "FileExplorer.vue tidak menerapkan filter HIDDEN_NAMES/visibleEntries"
    )
    print("[5] FileExplorer.vue memuat filter .aegis (HIDDEN_NAMES/visibleEntries): OK")

    print()
    print("[OK] Folder .aegis tersembunyi dari File Explorer; filesystem tak berubah.")
    return 0


def main() -> int:
    print("=== Verifikasi File Explorer: folder .aegis disembunyikan ===")
    setup_fixture()
    try:
        return _run()
    finally:
        teardown_fixture()


if __name__ == "__main__":
    raise SystemExit(main())
