# AegisCode Studio UI Layout & Design System

Dokumen ini mendefinisikan arsitektur antarmuka pengguna (UI), tata letak (*layout*), hierarki visual, dan pedoman sistem desain untuk **AegisCode Studio** (`apps/frontend`).

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

- **Lokasi**: [AppNavbar.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/layout/AppNavbar.vue)
- **Fungsi**: Menampilkan nama proyek aktif, menu navigasi utama (File/Edit/View), indikator proses latar belakang (`.nav-assistant-pill`), dan kontrol akun pengguna.

---

### 1.2. Sidebar Left

Sidebar kiri terdiri dari dua sub-komponen yang bekerja bersama:

#### AppActivityBar
- **Lokasi**: [AppActivityBar.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/layout/AppActivityBar.vue)
- **Fungsi**: Kolom ikon navigasi vertikal di sisi kiri paling luar.
- **Nav keys** (validator): `['explorer', 'git', 'queue', 'settings']`
- **Display label** (computed `navDisplayLabel` di `AppLeftSidebar`):
  - `explorer` → **EXPLORER**
  - `git` → **SOURCE CONTROL**
  - `queue` → **THREADS & HISTORY**
  - `settings` → **SETTINGS**

#### AppLeftSidebar
- **Lokasi**: [AppLeftSidebar.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/layout/AppLeftSidebar.vue)
- **Fungsi**: Host panel sidebar kiri; merender panel aktif berdasarkan prop `activeNav`.
- **Sub-komponen**:
  - **`ExplorerSidebarPanel`** ([ExplorerSidebarPanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/sidebar/ExplorerSidebarPanel.vue))
    - Memuat [FileExplorer.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/explorer/FileExplorer.vue) — pohon berkas proyek aktif, tab, dan navigasi folder.
  - **`GitSidebarPanel`** ([GitSidebarPanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/sidebar/GitSidebarPanel.vue)) — label display: **Source Control**
    - Memuat [GithubBackupPanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/git/GithubBackupPanel.vue) — checkpoint Git dengan tampilan Graph Checkpoint (SVG railway graph).
    - Memuat [ChangesPanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/git/ChangesPanel.vue) — daftar berkas termodifikasi dengan lencana status `M/U/D/A` dan fitur *1-click discard*. Mendukung diff side-by-side via `MonacoDiffEditor`.
  - **`ThreadsHistoryPanel`** ([ThreadsHistoryPanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/sidebar/ThreadsHistoryPanel.vue))
    - Tab **Threads**: sesi aktif dengan operasi CRUD in-situ (rename, hapus, buat baru).
    - Tab **History**: riwayat task selesai dengan rename dan hapus per entri.

---

### 1.3. Editor & Workspace Area

- **Lokasi utama**: [WorkbenchView.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/pages/WorkbenchView.vue)
- **Sub-komponen**:
  - **`CodeEditor.vue`** ([CodeEditor.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/editor/CodeEditor.vue)) — editor Monaco utama dengan multi-tab, dirty indicator, dan AppBreadcrumbs.
  - **`MonacoDiffEditor.vue`** ([MonacoDiffEditor.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/editor/MonacoDiffEditor.vue)) — mode perbandingan *side-by-side* dan *inline diff*; digunakan saat agent mengajukan perubahan berkas (HITL Diff Modal) atau pengguna membuka diff manual dari Source Control.
  - **`AppBottomDrawer.vue`** ([AppBottomDrawer.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/layout/AppBottomDrawer.vue)) — drawer bawah yang dapat diciutkan dan diubah ukurannya:
    - Tab **Terminal**: PTY interaktif via [TerminalView.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/terminal/TerminalView.vue) berbasis `@xterm/xterm` + WebSocket kernel.
    - Tab **Output**: log proses agen.
    - Tab **Problems**: diagnostik editor (LSP errors/warnings).
  - **Splitter**: `AppSplitter.vue` membagi sidebar kiri, area editor, dan drawer kanan secara resizable.

#### HITL Diff Modal
- Saat agen berjalan dalam *supervised mode*, `ApprovalModal.vue` / `DiffModal.vue` menghentikan eksekusi sebelum perubahan ditulis ke disk.
- Menampilkan: ringkasan aksi tool (`write_file`, `delete_file`, `run_destructive_command`) + visual diff.
- Aksi: **Approve** melanjutkan task; **Reject** membatalkan dan memicu *replanning* LLM.

---

### 1.4. Drawer Right — Aegis Assistant

- **Lokasi**: [AppRightDrawer.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/layout/AppRightDrawer.vue)
- **Fungsi**: Panel asisten AI persisten (retensi status `v-show` di DOM).
- **Tab**:
  - **Agent** — [AgentDrawerPanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/drawer/AgentDrawerPanel.vue)
    - Memuat [AgentActivity.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/drawer/AgentActivity.vue) — log aktivitas agen real-time, kontrol task (submit, stop, enqueue).
  - **Ask** — [ConsultantChat.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/drawer/ConsultantChat.vue)
    - Memuat [QueuePanel.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/queue/QueuePanel.vue) — antrian pesan konsultasi multi-turn.
    - Mendukung fitur *1-click "Apply to Editor"* untuk menerapkan saran kode langsung ke Monaco.

---

### 1.5. StatusBar

- **Lokasi**: [AppStatusBar.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/layout/AppStatusBar.vue)
- **Fungsi**: Bar status bawah yang menampilkan: branch Git aktif, encoding berkas, model AI aktif, status koneksi gateway, dan versi Aegis.
- **Props kunci**: `cursor`, `language`, `modelLabel`, `providerLabel`, `taskStatus`, `connected`, `gitBranchInfo`, `bottomDockOpen`.
- **Events**: `@toggle-dock` (buka/tutup `AppBottomDrawer`), `@open-git` (aktifkan nav Source Control).

---

## 2. Design Tokens & Palet Warna (Unified Presets Architecture)

AegisCode Studio menerapkan sistem desain berbasis **CSS Custom Properties** terpadu dengan arsitektur **Single Source of Truth** di [theme-presets.css](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/styles/themes/theme-presets.css).

### 2.1. Prinsip & Aturan Desain Token
1. **Single Source of Truth (Pure HEX)**:
   - Seluruh kode warna didefinisikan secara eksklusif di [theme-presets.css](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/styles/themes/theme-presets.css) menggunakan format 6-digit `#RRGGBB` atau 8-digit `#RRGGBBAA`.
   - Dilarang keras menggunakan fungsi CSS bertingkat (`rgba()`, `color-mix()`, `hsl()`) di dalam katalog preset.
2. **Zero Hardcoded HEX di Luar Presets**:
   - Seluruh stylesheet di `apps/frontend/src/styles/` di luar `theme-presets.css` bersih 100% dari nilai hex hardcoded.
   - Seluruh komponen Vue (`apps/frontend/src/components/`) bersih 100% dari nilai hex hardcoded.
3. **Zero Token Overrides di Komponen Vue**:
   - Blok `<style>` komponen Vue dilarang memuat selektor `[data-theme="light"]` atau override warna token.
   - Seluruh variasi mode terang didelegasikan ke stylesheet reusable [theme-light.css](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/styles/themes/theme-light.css).
4. **Pewarnaan Semantik Berbasis Data Attribute**:
   - Komponen pohon berkas ([FileExplorer.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/explorer/FileExplorer.vue) dan [ExplorerTreeNode.vue](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/components/explorer/ExplorerTreeNode.vue)) tidak menggunakan inline `:style="{ color: ... }"`.
   - Pewarnaan tipe berkas didelegasikan ke atribut `:data-file-type` yang diatur di [explorer.css](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/apps/frontend/src/styles/components/explorer.css).

---

### 2.2. Taksonomi Token Semantik

Setiap tema dalam katalog menyediakan token standar berikut:

| Kategori Token | Nama Token CSS | Fungsi & Penempatan |
| :--- | :--- | :--- |
| **Surfaces** | `--bg` | Kanvas utama workbench & background root editor |
| | `--bg-surface`, `--bg-panel` | Permukaan sidebar, drawer, dan panel sekunder |
| | `--bg-header`, `--bg-secondary`| Top navbar, header panel, dan bilah judul |
| | `--bg-elev`, `--bg-card` | Kartu elevasi, modal dialog, popover |
| | `--bg-deep` | Input form, container embedded, code fallback block |
| | `--bg-hover` | Efek sorot hover pada baris, item list, dan tombol |
| | `--bg-sidebar`, `--bg-drawer` | Alias struktural khusus wadah navigasi & asisten |
| **Borders** | `--border` | Garis batas komponen utama, panel, dan dialog |
| | `--border-soft` | Garis pembatas internal antarkolom atau list |
| | `--border-subtle`, `--line`, `--edge` | Garis batas minimalis, pemisah tab, dan outline kartu |
| **Typography** | `--text` | Teks utama, judul, dan isi konten berkepekatan tinggi |
| | `--text-dim` | Label sekunder, sub-judul, dan deskripsi |
| | `--text-faint` | Metadata redup, timestamp, dan placeholder |
| | `--text-invert` | Kontras inversi untuk status atau lencana khusus |
| **Accents** | `--accent` | Warna aksen primer, tombol aksi utama, tab aktif |
| | `--accent-2` | Aksen sekunder (magenta/violet), highlight fitur |
| | `--accent-soft` | Latar belakang transparan aksen untuk seleksi aktif |
| **Status** | `--ok` | Status sukses, berkas ditambahkan (A), indikator stabil |
| | `--warn` | Peringatan, berkas termodifikasi (M), peringatan agent |
| | `--err` | Status galat/bahaya, berkas dihapus (D), kegagalan build |
| **Traffic Lights** | `--traffic-close`, `--traffic-min`, `--traffic-max` | Kontrol jendela ala macOS (`#ff6058`, `#febc2e`, `#29c840`) |
| **Syntax** | `--syntax-keyword`, `--syntax-string`, `--syntax-fn`, dll. | Palet pewarnaan sintaksis editor & badge bahasa |

---

### 2.3. Katalog 10 Presets Terkurasi

AegisCode Studio menyediakan 10 preset bawaan yang dapat dipilih melalui Settings:

#### 6 Dark Mode Presets:
1. **Default Dark (`default-dark`)**: Palet Midnight Obsidian dengan kontras tajam untuk sesi coding intensif (`--bg: #111217`, `--accent: #4f8ff7`).
2. **Tokyo Night Storm (`tokyo-night`)**: Palet Cyberpunk Storm bernuansa biru keunguan mendalam (`--bg: #24283b`, `--accent: #7aa2f7`, `--accent-2: #bb9af7`).
3. **Nordic Frost (`nordic-frost`)**: Palet Arctic Sub-zero bernuansa biru es dan aurora (`--bg: #2e3440`, `--accent: #88c0d0`, `--ok: #a3be8c`).
4. **Dracula Neo (`dracula-neo`)**: Palet Gothic Neon ungu gelap dengan aksen merah muda dan hijau cerah (`--bg: #282a36`, `--accent: #bd93f9`, `--accent-2: #ff79c6`).
5. **Gruvbox Dark (`gruvbox-dark`)**: Palet Retro Groove bernuansa cokelat hangat dan oranye tanah (`--bg: #282828`, `--accent: #fe8019`, `--ok: #b8bb26`).
6. **Catppuccin Mocha (`catppuccin-mocha`)**: Palet Soothing Pastel dengan nada lavender dan mawar tenang (`--bg: #1e1e2e`, `--accent: #cba6f7`, `--accent-2: #f5c2e7`).

#### 4 Light Mode Presets:
1. **Default Light (`default-light`)**: Palet Alabaster Paper bersih dengan keterbacaan tinggi (`--bg: #f8fafc`, `--accent: #2563eb`, `--text: #0f172a`).
2. **Orbit Light (`orbit-light`)**: Palet Electric High-Contrast bertenaga biru elektrik dan garis batas tegas (`--bg: #f5f7fb`, `--accent: #0284c7`, `--border: #cbd5e1`).
3. **Nordic Light (`nordic-light`)**: Palet Salju Arktik dengan kontras dingin dan tipografi abu-abu pekat (`--bg: #eceff4`, `--accent: #5e81ac`, `--text: #2e3440`).
4. **Gruvbox Light (`gruvbox-light`)**: Palet Perkamen Hangat terinspirasi kertas cetak retro klasik (`--bg: #fbf1c7`, `--accent: #af3a03`, `--text: #3c3836`).

---

### 2.4. Tipografi

- **Antarmuka Pengguna (UI Sans)**: `Inter`, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
- **Editor & Terminal (Code Mono)**: `JetBrains Mono`, `SFMono-Regular`, Consolas, `Liberation Mono`, monospace.

---

## 3. Aturan Responsif & Breakpoint Workbench

| Tier | Lebar Layar | Perilaku Layout |
| :--- | :--- | :--- |
| **Desktop** | > 1280px | Tiga kolom penuh (sidebar kiri, editor, drawer kanan) dengan splitter yang dapat diseret bebas. |
| **Compact** | 900px - 1280px | Editor meluas; drawer kanan beralih menjadi drawer mengambang (*floating drawer*). |
| **Mobile** | < 900px | Sidebar kiri dan drawer kanan menjadi overlay *slide-out*; editor menempati 100% lebar layar. |

### Detail Perilaku Responsif:
- **Backdrop Overlay**: Saat sidebar atau drawer terbuka sebagai overlay (mobile/compact), latar belakang `.overlay-backdrop` semi-transparan ditampilkan; menekan tombol `Escape` atau mengeklik backdrop langsung menutup overlay.
- **Pemangkasan Header Berprioritas**:
  - Pada tier Desktop (> 1280px), path proyek ditampilkan penuh beserta seluruh chip status.
  - Pada tier Compact (900-1280px), path proyek dipangkas menjadi *basename*.
  - Pada tier Mobile (< 900px), chip sekunder disembunyikan.
- **Pemangkasan StatusBar Berprioritas**:
  - Tier Compact menyembunyikan encoding dan indikator indentasi.
  - Tier Mobile hanya menampilkan indikator baris/kolom (`Ln/Col`), model AI aktif, dan ikon sinkronisasi.
- **Batas Ukuran Splitter**:
  - Sidebar kiri: minimum 200px, maksimum 450px.
  - Drawer kanan: minimum 320px, maksimum 650px.
  - Bottom dock: minimum 150px, maksimum 400px.
  - Klik ganda pada splitter mengembalikan ukuran ke nilai baku (*default*).
- **Pintasan Keyboard Global**:
  - `Cmd/Ctrl + P`: Buka pencarian berkas cepat (*Quick Open*).
  - `Cmd/Ctrl + K`: Buka Command Palette & AI Agent Command.
  - `` Ctrl + ` ``: Alihkan keterlihatan Bottom Dock (Terminal/Output/Problems).
- **Kekangan Implementasi**: Seluruh logika styling dan presentasi UI murni berada di `apps/frontend/` tanpa ketergantungan pada modifikasi rute internal `apps/django_app/`.
