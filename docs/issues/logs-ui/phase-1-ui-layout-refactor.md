# Phase 1 — Refactor Tata Letak dan Hierarki Komponen UI

## 1. Ikhtisar Phase 1

- **Tujuan**: Memperjelas penamaan dan hierarki komponen UI, merestruktur folder sidebar dan drawer, menyelaraskan label display dengan spesifikasi UX, serta memperbarui dokumentasi `docs/ui-design.md`.
- **Tingkat Prioritas**: P2 (Refactor — Tidak memblokir fitur, wajib sebelum sprint UI berikutnya).
- **Target Item**: 4 Kelompok Perubahan (REFACTOR-UI-01 s/d REFACTOR-UI-04).

---

## 2. Rincian Isu dan Spesifikasi Teknis

### REFACTOR-UI-01 — Restruktur Folder Sidebar dan Drawer
- **Prioritas**: P2
- **Domain**: Frontend Layout / Component Organization
- **Berkas Sumber**:
  - `web/frontend/src/components/ExplorerSidebarPanel.vue` → dipindah ke `sidebar/`
  - `web/frontend/src/components/GitSidebarPanel.vue` → dipindah ke `sidebar/`
  - `web/frontend/src/components/ThreadsHistoryPanel.vue` → dipindah ke `sidebar/`
  - `web/frontend/src/components/AgentDrawerPanel.vue` → dipindah ke `drawer/`
- **Akar Masalah**: Panel sidebar dan drawer tersebar flat di `src/components/` bersama komponen domain lain, menyulitkan orientasi developer baru dan pemeliharaan jangka panjang.
- **Dampak Lapangan**: Tidak ada dampak runtime; dampak pada maintainability dan onboarding.
- **Usulan Perbaikan**:
  1. Buat `src/components/sidebar/` dan pindahkan 3 panel sidebar.
  2. Buat `src/components/drawer/` dan pindahkan `AgentDrawerPanel.vue`.
  3. Update semua import callsite dan path string test.
- **Acceptance Criteria**:
  - `node --test web/frontend/src/*.test.mjs` lulus 0 kegagalan setelah rename.
  - `AppLeftSidebar.vue` mengimpor dari `../sidebar/`.
  - `AppRightDrawer.vue` mengimpor `AgentDrawerPanel` dari `../drawer/`.

---

### REFACTOR-UI-02 — Rename AppFooter → AppStatusBar dan AppBottomDock → AppBottomDrawer
- **Prioritas**: P2
- **Domain**: Frontend Layout / Naming Clarity
- **Berkas Sumber**:
  - `web/frontend/src/components/layout/AppFooter.vue`
  - `web/frontend/src/components/layout/AppBottomDock.vue`
  - `web/frontend/src/App.vue` (callsite AppFooter)
  - `web/frontend/src/pages/WorkbenchView.vue` (callsite AppBottomDock)
- **Akar Masalah**: `AppFooter` tidak mencerminkan fungsi status bar; `AppBottomDock` tidak konsisten dengan terminologi "Bottom Drawer" yang digunakan di spec layout.
- **Dampak Lapangan**: Tidak ada dampak runtime; kebingungan nama saat navigasi codebase.
- **Usulan Perbaikan**:
  1. Rename file dan update semua import/tag.
- **Acceptance Criteria**:
  - File `AppFooter.vue` dan `AppBottomDock.vue` tidak ada di codebase.
  - App masih render normal, statusbar dan bottom drawer berfungsi.

---

### REFACTOR-UI-03 — Update Label Display: "SOURCE CONTROL" dan "Graph Checkpoint"
- **Prioritas**: P2
- **Domain**: Frontend UI / Label Clarity
- **Berkas Sumber**:
  - `web/frontend/src/components/layout/AppLeftSidebar.vue` (computed navDisplayLabel)
  - `web/frontend/src/components/GithubBackupPanel.vue` (referensi label checkpoint graph)
- **Akar Masalah**: Label "GIT" (dari `activeNav.toUpperCase()`) tidak informatif; perlu map eksplisit ke label display yang sesuai spesifikasi UX.
- **Dampak Lapangan**: UX: label tidak sesuai ekspektasi pengguna.
- **Usulan Perbaikan**:
  1. Tambahkan computed map `navDisplayLabel` di `AppLeftSidebar`, ubah template binding.
  2. Label checkpoint graph di `GithubBackupPanel` dikonfirmasi sudah menggunakan variabel `checkpointGraph` tanpa display string "Checkpoint Graph" terpisah — tidak perlu perubahan tambahan.
- **Acceptance Criteria**:
  - Sidebar header menampilkan "SOURCE CONTROL" saat nav aktif adalah `git`.
  - `navDisplayLabel` computed tersedia untuk semua nav key (`explorer`, `git`, `queue`, `settings`).

---

### REFACTOR-UI-04 — Rewrite `docs/ui-design.md`
- **Prioritas**: P2
- **Domain**: Documentation
- **Berkas Sumber**:
  - `docs/ui-design.md`
- **Akar Masalah**: Dokumen lama tidak mencerminkan hierarki 5 komponen utama yang ditetapkan, menyebut nama komponen lama (`AppFooter`, `AppBottomDock`, `ActivityBar`), dan tidak mendokumentasikan subfolder `sidebar/` dan `drawer/`.
- **Dampak Lapangan**: Developer mengacu dokumen yang tidak sinkron dengan struktur aktual.
- **Acceptance Criteria**:
  - Section 1 memuat diagram ASCII dan deskripsi per komponen sesuai hierarki 5 area utama.
  - Nama komponen terkini: `AppStatusBar`, `AppBottomDrawer`, `AppActivityBar`.
  - Subfolder baru (`sidebar/`, `drawer/`) tercantum pada deskripsi sub-komponen.
  - Design tokens (Section 2) dan breakpoint (Section 3) tetap lengkap.

---

## 3. Gerbang Penyelesaian (Gate UI-1 Checklist)

- [x] REFACTOR-UI-01: `node --test web/frontend/src/*.test.mjs` exit code 0 (119 pass, 0 fail), semua import path baru valid.
- [x] REFACTOR-UI-02: `grep -r "AppFooter\|AppBottomDock" web/frontend/src/` mengembalikan 0 hasil pada file Vue/JS aktif.
- [x] REFACTOR-UI-03: Sidebar menampilkan "SOURCE CONTROL" untuk nav `git` via computed `navDisplayLabel`.
- [x] REFACTOR-UI-04: `docs/ui-design.md` Section 1 memuat hierarki 5 komponen utama dengan sub-komponen, lokasi file, dan nama terkini.
