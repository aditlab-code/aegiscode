# AegisCode Studio UI Layout & Design System

Dokumen ini mendefinisikan arsitektur antarmuka pengguna (UI), tata letak (*layout*), hierarki visual, dan pedoman sistem desain untuk **AegisCode Studio** (`web/frontend`).

---

## 1. Hierarki Komponen Utama (Workbench Layout)

AegisCode Studio menggunakan tata letak multi-panel berbasis grid dan flexbox yang responsif dengan **5 area utama**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. AppNavbar                                                                │
│    [Logo/Proyek]  [File/Edit/View]              [AI Working Pill]  [User]   │
├──────────────────────────────────────────────────────────┬──────────────────┤
│ 2. Sidebar Left                                          │ 4. Drawer Right  │
│  AppActivityBar    AppLeftSidebar                        │  AppRightDrawer  │
│  [Explorer]   ├── ExplorerSidebarPanel                   │  ┌─ Tab: Agent   │
│  [Source Ctrl]│    └── FileExplorer                      │  │  AgentDrawer  │
│  [Threads ]   ├── GitSidebarPanel  (Source Control)      │  │  Panel        │
│  [Settings]   │    ├── GithubBackupPanel                 │  │  └─ AgentAct  │
│               │    │    └── Graph Checkpoint             │  │     ivity     │
│               │    └── ChangesPanel                      │  └─ Tab: Ask    │
│               └── ThreadsHistoryPanel                    │     Consultant  │
│                    └── Tabs: Threads / History           │     Chat        │
│                                                          │      └─ Queue   │
│                                                          │         Panel   │
├──────────────────────────────────────────────────────────┴──────────────────┤
│ 3. Editor & Workspace Area                                                  │
│    Multi-tab bar (split window) │ CodeEditor / MonacoDiffEditor             │
│    AppBottomDrawer: Terminal · Output · Problems                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. StatusBar  (AppStatusBar)                                                │
│    [Branch: master*]  [UTF-8]  [Model aktif]              [Toast Area]      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 1.1. AppNavbar

- **Lokasi**: `web/frontend/src/components/layout/AppNavbar.vue`
- **Fungsi**: Menampilkan nama proyek aktif, menu navigasi utama (File/Edit/View), indikator proses latar belakang (`.nav-assistant-pill`), dan kontrol akun pengguna.

---

### 1.2. Sidebar Left

Sidebar kiri terdiri dari dua sub-komponen yang bekerja bersama:

#### AppActivityBar
- **Lokasi**: `web/frontend/src/components/layout/AppActivityBar.vue`
- **Fungsi**: Kolom ikon navigasi vertikal di sisi kiri paling luar.
- **Nav keys** (validator): `['explorer', 'git', 'queue', 'settings']`
- **Display label** (computed `navDisplayLabel` di `AppLeftSidebar`):
  - `explorer` → **EXPLORER**
  - `git` → **SOURCE CONTROL**
  - `queue` → **THREADS & HISTORY**
  - `settings` → **SETTINGS**

#### AppLeftSidebar
- **Lokasi**: `web/frontend/src/components/layout/AppLeftSidebar.vue`
- **Fungsi**: Host panel sidebar kiri; merender panel aktif berdasarkan prop `activeNav`.
- **Sub-komponen**:
  - **`ExplorerSidebarPanel`** (`src/components/sidebar/ExplorerSidebarPanel.vue`)
    - Memuat `FileExplorer.vue` (`src/components/explorer/FileExplorer.vue`) — pohon berkas proyek aktif, tab, dan navigasi folder.
  - **`GitSidebarPanel`** (`src/components/sidebar/GitSidebarPanel.vue`) — label display: **Source Control**
    - Memuat `GithubBackupPanel.vue` (`src/components/git/GithubBackupPanel.vue`) — checkpoint Git dengan tampilan Graph Checkpoint (SVG railway graph).
    - Memuat `ChangesPanel.vue` (`src/components/git/ChangesPanel.vue`) — daftar berkas termodifikasi dengan lencana status `M/U/D/A` dan fitur *1-click discard*. Mendukung diff side-by-side via `MonacoDiffEditor`.
  - **`ThreadsHistoryPanel`** (`src/components/sidebar/ThreadsHistoryPanel.vue`)
    - Tab **Threads**: sesi aktif dengan operasi CRUD in-situ (rename, hapus, buat baru).
    - Tab **History**: riwayat task selesai dengan rename dan hapus per entri.

---

### 1.3. Editor & Workspace Area

- **Lokasi utama**: `web/frontend/src/pages/WorkbenchView.vue`
- **Sub-komponen**:
  - **`CodeEditor.vue`** (`src/components/editor/CodeEditor.vue`) — editor Monaco utama dengan multi-tab, dirty indicator, dan AppBreadcrumbs.
  - **`MonacoDiffEditor.vue`** (`src/components/editor/MonacoDiffEditor.vue`) — mode perbandingan *side-by-side* dan *inline diff*; digunakan saat agent mengajukan perubahan berkas (HITL Diff Modal) atau pengguna membuka diff manual dari Source Control.
  - **`AppBottomDrawer.vue`** (`src/components/layout/AppBottomDrawer.vue`) — drawer bawah yang dapat diciutkan dan diubah ukurannya:
    - Tab **Terminal**: PTY interaktif via `TerminalView.vue` (`src/components/terminal/TerminalView.vue`) berbasis `@xterm/xterm` + WebSocket kernel.
    - Tab **Output**: log proses agen.
    - Tab **Problems**: diagnostik editor (LSP errors/warnings).
  - **Splitter**: `AppSplitter.vue` membagi sidebar kiri, area editor, dan drawer kanan secara resizable.

#### HITL Diff Modal
- Saat agen berjalan dalam *supervised mode*, `DiffModal.vue` menghentikan eksekusi sebelum perubahan ditulis ke disk.
- Menampilkan: ringkasan aksi tool (`write_file`, `delete_file`, `run_destructive_command`) + visual diff.
- Aksi: **Approve** (hijau) melanjutkan task; **Reject** (merah) membatalkan dan memicu *replanning* LLM.

---

### 1.4. Drawer Right — Aegis Assistant

- **Lokasi**: `web/frontend/src/components/layout/AppRightDrawer.vue`
- **Fungsi**: Panel asisten AI persisten (retensi status `v-show` di DOM).
- **Tab**:
  - **Agent** — `AgentDrawerPanel.vue` (`src/components/drawer/AgentDrawerPanel.vue`)
    - Memuat `AgentActivity.vue` (`src/components/drawer/AgentActivity.vue`) — log aktivitas agen real-time, kontrol task (submit, stop, enqueue).
  - **Ask** — `ConsultantChat.vue` (`src/components/drawer/ConsultantChat.vue`)
    - Memuat `QueuePanel.vue` (`src/components/queue/QueuePanel.vue`) — antrian pesan konsultasi multi-turn.
    - Mendukung fitur *1-click "Apply to Editor"* untuk menerapkan saran kode langsung ke Monaco.

---

### 1.5. StatusBar

- **Lokasi**: `web/frontend/src/components/layout/AppStatusBar.vue`
- **Fungsi**: Bar status bawah yang menampilkan: branch Git aktif, encoding berkas, model AI aktif, status koneksi gateway, dan versi Aegis.
- **Props kunci**: `cursor`, `language`, `modelLabel`, `providerLabel`, `taskStatus`, `connected`, `gitBranchInfo`, `bottomDockOpen`.
- **Events**: `@toggle-dock` (buka/tutup `AppBottomDrawer`), `@open-git` (aktifkan nav Source Control).

---

## 2. Design Tokens & Palet Warna

AegisCode Studio mengadopsi estetika *Cyberpunk Midnight* berbasis palet resmi [tokyo-night/tokyo-night-vscode-theme](https://github.com/tokyo-night/tokyo-night-vscode-theme) dengan varian Storm untuk mode Dark dan varian Light untuk mode Light:

### 2.1. Tokyo Night Storm (Dark Mode)
- **Background Utama (`--bg`)**: `#24283b` (Storm background)
- **Surface / Panel (`--bg-panel`, `--bg-surface`, `--bg-card`)**: `#1f2335` (Sidebar & drawers)
- **Header & Navbar (`--bg-header`, `--bg-secondary`)**: `#1a1b26` (Classic dark top navbar)
- **Elevated Surfaces (`--bg-elev`)**: `#292e42` (Elevated cards & dialogs)
- **Hover State (`--bg-hover`)**: `#2f354f` (Hover highlight)
- **Deep Containers & Inputs (`--bg-deep`)**: `#16161e` (Form inputs & embedded widgets)
- **Border & Pembatas (`--border`)**: `#292e42`
- **Inner Dividers (`--border-soft`)**: `#1f2335`
- **Subtle Boundaries (`--border-subtle`)**: `#16161e`
- **Tipografi Utama (`--text`)**: `#c0caf5` (Crisp light blue-white)
- **Tipografi Sekunder (`--text-dim`)**: `#9aa5ce` (Slate secondary labels)
- **Tipografi Redup / Inaktif (`--text-faint`)**: `#565f89` (Muted comments/timestamps)
- **Aksen Primer (`--accent`)**: `#7aa2f7` (Tokyo Night Electric Blue)
- **Aksen Sekunder (`--accent-2`)**: `#bb9af7` (Neon Magenta / Violet)
- **Status Sukses (`--ok`)**: `#9ece6a` (Tokyo Night Green)
- **Status Peringatan (`--warn`)**: `#e0af68` (Tokyo Night Amber/Yellow)
- **Status Bahaya / Error (`--err`)**: `#f7768e` (Tokyo Night Red/Pink)

### 2.2. Tokyo Night Light (Light Mode)
- **Background Utama (`--bg`)**: `#e6e7ed` (Light canvas)
- **Surface / Panel (`--bg-panel`, `--bg-surface`, `--bg-card`)**: `#d6d8df` (Light slate panels)
- **Header & Navbar (`--bg-header`, `--bg-secondary`)**: `#cdced1` (Header boundaries)
- **Elevated Surfaces (`--bg-elev`)**: `#f5f6f9` (Elevated cards)
- **Hover & Inputs (`--bg-hover`, `--bg-deep`)**: `#d0d2db`
- **Border & Pembatas (`--border`)**: `#c1c2c7` (Cool silver outline)
- **Inner Dividers (`--border-soft`)**: `#d0d2db`
- **Tipografi Utama (`--text`)**: `#343b59` (Deep slate typography)
- **Tipografi Sekunder (`--text-dim`)**: `#565a6e`
- **Tipografi Redup / Inaktif (`--text-faint`)**: `#707280`
- **Aksen Primer (`--accent`)**: `#2959aa` (Deep Electric Blue)
- **Aksen Sekunder (`--accent-2`)**: `#7c3aed` (Violet / Magenta)
- **Status Sukses (`--ok`)**: `#485e30` (Forest Green)
- **Status Peringatan (`--warn`)**: `#8f5e15` (Amber Brown)
- **Status Bahaya / Error (`--err`)**: `#8c4351` (Crimson Rose)

### 2.3. Tipografi
- **Antarmuka (Sans)**: `Inter`, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
- **Kode & Terminal (Mono)**: `JetBrains Mono`, `SFMono-Regular`, Consolas, `Liberation Mono`, monospace

---

## 3. Aturan Responsif & Breakpoint Workbench

Ringkasan aturan layout yang telah diimplementasikan.

| Tier | Lebar | Perilaku |
| :--- | :--- | :--- |
| Desktop | > 1280px | Tiga kolom penuh (sidebar kiri, editor, drawer kanan) dengan splitter yang dapat diseret |
| Compact | 900px - 1280px | Editor meluas; drawer kanan menjadi drawer mengambang |
| Mobile | < 900px | Sidebar dan drawer menjadi overlay slide-out; editor 100% lebar |

- **Backdrop overlay**: saat sidebar atau drawer terbuka sebagai overlay, tampilkan `.overlay-backdrop` semi-transparan; klik backdrop atau tombol `Escape` menutup overlay.
- **Pemangkasan berprioritas (header)**: > 1280px path penuh dan semua chip; 900-1280px path dipangkas ke basename; < 900px chip sekunder disembunyikan.
- **Pemangkasan berprioritas (statusbar)**: 900-1280px sembunyikan encoding dan indentasi; < 900px hanya `Ln/Col`, model aktif, dan indikator sinkronisasi.
- **Ukuran desktop**: splitter 4px dan tinggi tab 28px dipertahankan tanpa inflasi padding mobile.
- **Splitter**: sidebar kiri 200-450px, drawer kanan 320-650px, bottom dock 150-400px; klik ganda untuk reset.
- **Pintasan**: `Cmd/Ctrl + P` (buka berkas), `Cmd/Ctrl + K` (perintah agent), `` Ctrl + ` `` (bottom dock).
- **Kekangan**: tidak ada perubahan pada `web/django_app/` untuk pekerjaan UI murni.
