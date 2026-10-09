# Implementation Plan: Aegis IDE Active Project Binding for `/repo`

## Context & Objectives
Menghubungkan perintah `/repo` dan seluruh kontrol Git di bot Telegram secara mutlak ke **Project Aktif di Aegis IDE Workstation** (`active_project["path"]`) sesuai spesifikasi [`docs/specs/spec-telegram-repo-review-and-commit-gate.md`](../docs/specs/spec-telegram-repo-review-and-commit-gate.md).
Mencegah seluruh *silent fallback* ke root direktori AegisCode platform (`parents[3]`).
Menyediakan alur:
1. Pemilihan project jika belum ada project aktif (`project:select:<id>`).
2. Inisialisasi Git jika project aktif belum menjadi repo Git (`repo:init`).
3. Tampilan perubahan berkas `<code>{path} {lines} line {status}</code>` pada project aktif.
4. Bulk Accept (`repo:accept`), Bulk Discard (`repo:discard`), dan Ganti Project (`repo:switch_project`).

---

## Dependency Graph & Architecture

```
User triggers /repo
    │
    ├── 1. Service Strict Binding (apps/django_app/api/services.py)
    │       │ - `get_active_repository_info`: hapus fallback `parents[3]`
    │       │ - Jika `get_active_project()` None, return `has_active_project: False`
    │       ▼
    ├── 2. Git Facade Methods (src/agent_ai/git/repository.py)
    │       │ - Pastikan `get_changed_files_summary()` terpasang di `GitRepositoryFacade`
    │       │ - Gunakan `init()` untuk penanganan folder non-Git
    │       ▼
    ├── 3. Telegram Views & UI State (src/agent_ai/runtime/telegram/views.py)
    │       │ - `render_project_selector_view(projects)`: tombol `project:select:<id>`
    │       │ - `render_repo_view(info, changed_files)`:
    │       │     * non-git view: tombol `[⚙️ Inisialisasi Git]` & `[🔄 Ganti Project]`
    │       │     * clean/dirty view: diff summary + Accept/Discard + tombol `[🔄 Ganti Project]`
    │       ▼
    ├── 4. Companion Bridge (src/agent_ai/runtime/telegram/companion.py)
    │       │ - `list_projects()`, `set_active_project(id)`
    │       │ - `init_repo()`, `get_changed_files()`, `accept_repo_changes()`, `discard_repo_changes()`
    │       │ - Bekerja strictly pada path project aktif pengguna
    │       ▼
    ├── 5. Handler Commands & Callbacks (src/agent_ai/runtime/telegram/handler.py)
    │       │ - Routing `/repo` berdasarkan status `has_active_project` dan `is_repo`
    │       │ - Callback routing: `repo:accept`, `repo:discard`, `repo:init`, `repo:switch_project`, `project:select:`
    │       ▼
    └── 6. Test Suite & Verification (tests/test_telegram_companion/test_repo_review.py)
            │ - Unit & integration tests untuk seluruh cabang skenario
            │ - Verifikasi zero-regression pada seluruh test suite eksisting
```

---

## Detailed Task Breakdown

### Task 1: Strict Active Project in `apps/django_app/api/services.py`
- Perbarui `get_active_repository_info()`:
  - Hapus kode fallback `parents[3]`.
  - Jika `active` bernilai None / tidak memiliki path, kembalikan `{"has_active_project": False, "is_repo": False, ...}`.
  - Jika ada project aktif, targetkan `GitRepositoryFacade(root=Path(active["path"]))` dan sertakan `"has_active_project": True`.

### Task 2: Ensure `get_changed_files_summary()` in `src/agent_ai/git/repository.py`
- Pastikan `GitRepositoryFacade.get_changed_files_summary()` tersedia dan menangani kasus bila bukan repository Git secara anggun (kembalikan `[]`).

### Task 3: Views for Project Selection & Non-Git in `src/agent_ai/runtime/telegram/views.py`
- Tambahkan `render_project_selector_view(projects)` dengan tombol inline `project:select:<id>`.
- Perbarui `render_repo_view(info, changed_files)`:
  - Jika `not info.get("has_active_project")`, arahkan ke pesan belum ada project aktif.
  - Jika `not info.get("is_repo")`, tampilkan pesan non-git dengan tombol `[⚙️ Inisialisasi Git]` dan `[🔄 Ganti Project]`.
  - Jika repo aktif, sertakan tombol `[🔄 Ganti Project]` di bawah tombol Accept/Discard (atau di bawah status clean).

### Task 4: Companion Logic in `src/agent_ai/runtime/telegram/companion.py`
- Tambahkan method `list_projects()`, `set_active_project(project_id)`, dan `init_repo()`.
- Pastikan `get_changed_files()`, `accept_repo_changes()`, dan `discard_repo_changes()` strictly mengambil path dari active project, dan menolak beroperasi jika tidak ada active project.

### Task 5: Handler Callbacks in `src/agent_ai/runtime/telegram/handler.py`
- Tambahkan penanganan:
  - `/repo`: jika `has_active_project` False, tampilkan project selector view.
  - `repo:init`: eksekusi `init_repo()`, edit pesan dengan konfirmasi inisialisasi Git berhasil.
  - `repo:switch_project`: tampilkan project selector view.
  - `project:select:<id>`: set active project, lalu panggil ulang `_handle_repo` untuk merender status repo project yang baru diaktifkan.

### Task 6: Comprehensive Test Suite & Verification in `tests/test_telegram_companion/test_repo_review.py`
- Tulis pengujian untuk:
  - `get_active_repository_info` tanpa project aktif (no fallback leak).
  - `/repo` tanpa project aktif -> project selector menu.
  - Callback `project:select:` -> project aktif berubah & repo status ter-render.
  - Project non-git -> tombol `[⚙️ Inisialisasi Git]`.
  - Callback `repo:init` -> inisialisasi git sukses.
  - Project aktif dengan perubahan -> format `<file> <lines> line <M/A/D>`, Accept, Discard, dan `[🔄 Ganti Project]`.
  - Jalankan `./venv/bin/pytest tests/test_telegram_companion/ -v`.
