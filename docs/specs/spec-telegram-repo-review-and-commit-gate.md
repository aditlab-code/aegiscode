# Spec: Telegram `/repo` Git Review, Changed Files Summary, and Bulk Accept/Discard Gate (Aegis IDE Active Project Binding)

## Objective
Menghubungkan perintah `/repo` dan seluruh aksi manajemen Git (Review, Accept, Discard, Init) di bot Telegram secara **mutlak ke Project Aktif di Aegis IDE Workstation** (misal: project pengguna seperti `/Users/aditwicaksono/Documents/presentasi`), dan **menghilangkan seluruh silent fallback** ke direktori source code internal AegisCode platform (`parents[3]`).

Fitur ini mencakup:
1. **Strict Active Project Binding**:
   - Perintah `/repo` dan inspeksi Git selalu terikat pada `active_project["path"]` dari `GatewayService.get_active_project()`.
   - Jika belum ada project yang dibuka/aktif di Aegis IDE, bot tidak menampilkan diff sembarangan, melainkan menyajikan daftar project yang tersimpan di Aegis IDE agar pengguna dapat memilih dan mengaktifkan project langsung dari Telegram (`project:select:<id>`).
2. **Project Switcher (`[🔄 Ganti Project]`)**:
   - Tombol `[🔄 Ganti Project]` selalu tersedia pada tampilan `/repo` sehingga pengguna dapat berpindah antar-project kapan saja dari Telegram.
3. **Penanganan Folder Non-Git (`[⚙️ Inisialisasi Git]`)**:
   - Jika project yang aktif di Aegis IDE belum memiliki repository Git (`.git` belum ada), bot menampilkan notifikasi informatif disertai tombol `[⚙️ Inisialisasi Git]` (`repo:init`) untuk mengeksekusi `git init` pada direktori project tersebut.
4. **Ringkasan Perubahan Berkas**:
   - Menampilkan daftar berkas yang berubah pada project aktif dengan format eksplisit: `<code>{nama_berkas} {jumlah_baris} line {M/A/D}</code>` (`M`: modified, `A`: added/untracked, `D`: deleted).
5. **Bulk Action Buttons**:
   - `[✅ Accept Perubahan]` (`repo:accept`): Melakukan `git add .`, meminta LLM men-generate ringkasan pesan conventional commit, dan membuat `git commit` lokal pada project aktif.
   - `[🗑️ Discard Perubahan]` (`repo:discard`): Menjalankan pembersihan total instan (`git restore .` dan `git clean -fd`) pada project aktif.
   - Repositori bersih: Menampilkan status `Clean (tidak ada perubahan berkas)` tanpa tombol Accept/Discard, namun tetap menyertakan tombol `[🔄 Ganti Project]`.

---

### User Stories & Acceptance Criteria

1. **User Story 1: Meninjau Repo Project Aktif di Aegis IDE**
   - *Sebagai* pengembang yang sedang mengerjakan project di Aegis IDE,
   - *Saya ingin* mengetik `/repo` di Telegram dan melihat status Git dari project yang sedang aktif di IDE,
   - *Sehingga* saya tidak melihat perubahan pada source code internal AegisCode platform (VSCode development).
   - *Kriteria Penerimaan*:
     - Target pemeriksaan Git adalah `active_project["path"]`.
     - Jika ada perubahan, ditampilkan rincian berkas dengan format `<code>{path} {total_lines} line {status_code}</code>`.
     - Tombol inline yang muncul: `[✅ Accept Perubahan]`, `[🗑️ Discard Perubahan]`, dan `[🔄 Ganti Project]`.

2. **User Story 2: Pemilihan Project Saat Belum Ada Project Aktif**
   - *Sebagai* pengguna yang belum membuka project di Aegis IDE,
   - *Saya ingin* mengetik `/repo` dan melihat daftar project yang tersimpan di database IDE,
   - *Sehingga* saya dapat memilih project aktif langsung dari Telegram tanpa membuka laptop.
   - *Kriteria Penerimaan*:
     - Jika `get_active_project()` bernilai `None`, bot menampilkan: `"⚠️ Belum ada project aktif di Aegis IDE. Pilih project untuk ditinjau:"`.
     - Tombol inline menampilkan daftar nama project yang ada di database Aegis IDE (`project:select:<id>`).
     - Mengklik tombol project otomatis menyetel project tersebut sebagai project aktif di `project_store` dan merender ulang tampilan `/repo` untuk project tersebut.

3. **User Story 3: Inisialisasi Git untuk Project Baru**
   - *Sebagai* pengembang dengan project aktif yang belum memiliki Git,
   - *Saya ingin* melihat opsi inisialisasi Git di Telegram,
   - *Sehingga* saya dapat langsung memulai pelacakan versi dari Telegram.
   - *Kriteria Penerimaan*:
     - Jika project aktif bukan git repository (`is_repo == False`), bot menampilkan pesan: `"📁 Project '{name}' belum diinisialisasi sebagai repositori Git."`.
     - Menyediakan tombol inline `[⚙️ Inisialisasi Git]` (`repo:init`) dan `[🔄 Ganti Project]`.
     - Menekan tombol `repo:init` mengeksekusi `git init` pada folder project tersebut dan memperbarui pesan.

4. **User Story 4: Ganti Project Kapan Saja**
   - *Sebagai* pengembang yang mengelola beberapa project,
   - *Saya ingin* menekan tombol `[🔄 Ganti Project]`,
   - *Sehingga* saya dapat beralih ke project lain dan meninjau status Git-nya.
   - *Kriteria Penerimaan*:
     - Menekan `repo:switch_project` menampilkan daftar project yang tersimpan di Aegis IDE.
     - Memilih salah satu project mengubah active project dan memperbarui tampilan `/repo`.

5. **User Story 5: Bulk Accept & Discard pada Project Aktif**
   - *Sebagai* pengguna,
   - *Saya ingin* menekan `[✅ Accept Perubahan]` atau `[🗑️ Discard Perubahan]`,
   - *Sehingga* perubahan pada project aktif di-commit dengan pesan LLM atau dibersihkan seketika.
   - *Kriteria Penerimaan*:
     - Mutasi Git hanya berjalan pada direktori project aktif.
     - Accept menghasilkan commit lokal dengan pesan dari LLM.
     - Discard membersihkan file tracked dan untracked pada project aktif.

---

## Tech Stack
- **Runtime**: Python 3.10+
- **Telegram Framework**: `agent_ai.runtime.telegram` (`TelegramBotClient`, `TelegramUpdateHandler`, `TelegramCompanion`)
- **Git Engine**: `agent_ai.git.repository.GitRepositoryFacade`
- **Aegis Project Engine**: `apps.django_app.api.services.GatewayService`, `ProjectStore`
- **Testing**: `pytest` via `./venv/bin/pytest`

---

## Commands
- **Targeted Test Suite**:
  ```bash
  ./venv/bin/pytest tests/test_telegram_companion/test_repo_review.py -v
  ```
- **Full Telegram Companion Test Suite**:
  ```bash
  ./venv/bin/pytest tests/test_telegram_companion/ -v
  ```
- **Companion Daemon Runner**:
  ```bash
  PYTHONPATH=src:apps/django_app python3 -m agent_ai.runtime.telegram.companion
  ```

---

## Project Structure

```
src/agent_ai/git/
└── repository.py                                # GitRepositoryFacade: get_changed_files_summary(), init(), commit(), discard()

src/agent_ai/runtime/telegram/
├── views.py                                     # render_repo_view(), render_project_selector_view(), render_non_git_repo_view()
├── companion.py                                 # Bridge ke GatewayService.get_active_project(), list_projects(), set_active_project()
└── handler.py                                   # Routing callback repo:accept, repo:discard, repo:init, repo:switch_project, project:select:*

apps/django_app/api/
└── services.py                                  # Perbarui get_active_repository_info(): hilangkan silent fallback ke parents[3]

tests/test_telegram_companion/
└── test_repo_review.py                          # Test suite pengujian seluruh skenario di atas
```

---

## Code Style & Architectural Conventions

1. **Strict Active Project Boundary**:
   Di `services.py` dan `companion.py`, jika `get_active_project()` mengembalikan `None`:
   ```python
   active = self.get_active_project()
   if not active or not active.get("path"):
       return {
           "has_active_project": False,
           "name": "-",
           "root": "-",
           "branch": "-",
           "last_commit": "-",
           "uncommitted_changes": 0,
           "is_dirty": False,
           "is_repo": False,
       }
   ```
   DILARANG KERAS fallback ke `parents[3]`.

2. **Router Callback Baru**:
   - `repo:accept` -> Commit semua perubahan di project aktif.
   - `repo:discard` -> Discard semua perubahan di project aktif.
   - `repo:init` -> Jalankan `git init` di project aktif.
   - `repo:switch_project` -> Buka menu pemilihan project.
   - `project:select:<project_id>` -> Aktifkan project ID tersebut dan tampilkan status repo barunya.

---

## Boundaries
- **Always do**:
  - Gunakan `active_project["path"]` dari Aegis IDE.
  - Periksa otorisasi Zero-Trust pada setiap callback query.
  - Segera panggil `answer_callback_query` agar antarmuka Telegram responsif.
- **Never do**:
  - Mengeksekusi mutasi Git atau membaca diff dari root codebase AegisCode (`parents[3]`) secara diam-diam.
  - Menyembunyikan exception dengan silent `pass`.

---

## Success Criteria
- [ ] `/repo` mendeteksi project aktif Aegis IDE secara akurat (contoh: `/Users/aditwicaksono/Documents/presentasi`).
- [ ] Tidak ada berkas platform AegisCode yang bocor ke `/repo`.
- [ ] Jika tidak ada project aktif, bot menampilkan daftar project tersimpan dengan tombol `project:select:<id>`.
- [ ] Jika project aktif bukan git repository, tombol `[⚙️ Inisialisasi Git]` tersedia dan berfungsi.
- [ ] Tombol `[🔄 Ganti Project]` selalu ada untuk beralih project secara dinamis dari Telegram.
- [ ] 100% test suite unit & integrasi lulus uji via `./venv/bin/pytest`.

---

## Open Questions
- *Tidak ada* (seluruh keputusan cabang desain telah diselesaikan pada sesi `/grill-me`).
