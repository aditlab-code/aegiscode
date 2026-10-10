# Implementation Plan: Git Source Control Commit & Staging Lifecycle Refinement

## Context & Objectives
Memperbaiki bug siklus commit Git pada `apps/frontend`:
- Saat berkas di-stage dan di-commit, berkas sempat kembali muncul di list "Changes" (unstaged) karena fallback `ChangesPanel.vue` ke memory task changes (`props.changes`) saat status Git bersih (`localGitChanges` kosong).
- Pengguna sebelumnya terpaksa me-refresh peramban secara manual untuk melihat status repositori yang bersih.
- Menetapkan `localGitChanges` sebagai **Single Source of Truth** ketika `isRepository: true`.
- Menyambungkan event pipeline `checkpoint-created` ke `App.vue` untuk membersihkan task memory changes dan menyinkronkan badge counter di Top Navbar serta Activity Bar secara reaktif.

---

## Dependency Graph & Architecture

```
useTaskLifecycle.js (clearTaskChanges helper)
      ▲
      │
      ├── App.vue (handleCheckpointCreated, synchronize badge & explorerRefresh)
      │     ▲
      │     │
      │     └── WorkbenchView.vue (forward @checkpoint-created)
      │           ▲
      │           │
      │           ├── useWorkbenchEditorFacade.js (handleCheckpointCreated, close diff tabs)
      │           │
      │           └── GitSidebarPanel.vue (forward @checkpoint-created, loadGitChanges)
      │                 ▲
      │                 │
      │                 ├── GithubBackupPanel.vue (emit checkpoint-created on commit)
      │                 │
      │                 └── ChangesPanel.vue (Single Source of Truth in activeFiles)
```

---

## Detailed Task Breakdown

### Task 1: Expose `clearTaskChanges` in `useTaskLifecycle.js`
- Sediakan fungsi pembantu `clearTaskChanges()` pada composable `useTaskLifecycle.js`.
- Ekspor `clearTaskChanges` agar dapat dikonsumsi oleh `App.vue`.
- Files: `apps/frontend/src/composables/useTaskLifecycle.js`

### Task 2: Strict Single Source of Truth in `ChangesPanel.vue`
- Perbarui computed property `activeFiles` di `ChangesPanel.vue`:
  - Jika `isRepository.value === true`, gunakan secara eksklusif `localGitChanges.value`. Jangan pernah fallback ke `props.changes` saat status Git bersih.
  - Jika `isRepository.value === false`, pertahankan fallback ke `props.changes` untuk kompatibilitas workspace non-git.
- Pastikan method `loadGitChanges` diekspos dengan benar dan memperbarui `localGitChanges` secara deterministik.
- Files: `apps/frontend/src/components/git/ChangesPanel.vue`

### Task 3: Event Pipeline & Badge Synchronization in `App.vue` & Layout
- Tangani event `@checkpoint-created` pada `<WorkbenchView>` di `App.vue`:
  - Panggil `clearTaskChanges()` untuk membersihkan list in-memory task changes.
  - Inkrementasikan `explorerRefresh.value++` agar tree explorer dan panel git status tersinkronisasi otomatis.
- Pastikan badge `changes-count` pada `AppNavbar` dan `AppActivityBar` langsung mencerminkan kondisi bersih (0 atau sisa uncommitted changes).
- Files:
  - `apps/frontend/src/App.vue`
  - `apps/frontend/src/components/sidebar/GitSidebarPanel.vue`
  - `apps/frontend/src/composables/workbench/useWorkbenchEditorFacade.js`

### Task 4: Unit Testing & Verification Gates
- Buat test suite baru `apps/frontend/tests/gitCommitLifecycle.test.mjs` untuk menguji:
  1. Logika evaluasi `activeFiles` ketika `isRepository: true` (clean git status tidak fallback ke stale changes).
  2. Logika evaluasi `activeFiles` ketika `isRepository: false` (fallback aman ke `props.changes`).
  3. Pembersihan state `changes` dan propagasi event commit.
- Jalankan 6 mandatory frontend verification gates:
  1. Theme check (0 data-theme in Vue `<style>`).
  2. Inline color check (0 `:style=".*color"`).
  3. HEX token check (0 hardcoded hex in CSS outside presets).
  4. Vue HEX token check (0 hardcoded hex in `.vue`).
  5. Build check (`rtk npm --prefix apps/frontend run build` lolos).
  6. Unit test check (`rtk node --test apps/frontend/tests/*.test.mjs` 100% pass).
- Files: `apps/frontend/tests/gitCommitLifecycle.test.mjs`
