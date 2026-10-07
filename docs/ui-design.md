# AegisCode Studio UI Layout & Design System

Dokumen ini mendefinisikan arsitektur antarmuka pengguna (UI), tata letak (*layout*), hierarki visual, dan pedoman sistem desain untuk **AegisCode Studio** (`web/frontend`).

---

## 1. Tata Letak Utama (Workbench Layout)

AegisCode Studio menggunakan tata letak multi-panel berbasis grid dan flexbox yang responsif:

```
┌────────────────────────────────────────────────────────────────────────┐
│ AppNavbar: [Logo/Proyek]  [File/Edit/View]     [AI Working Pill] [User]│
├─────────┬───────────────────────────────────┬──────────────────────────┤
│ Activity│ Editor & Workspace Area           │ Assistant Right Drawer   │
│ Bar     │                                   │ (Persistent v-show)      │
│         │ ┌───────────────────────────────┐ │ ┌──────────────────────┐ │
│ [Files] │ │ Multi-Tab Bar (Code & Diffs)  │ │ │ AgentActivity /      │ │
│ [Git]   │ ├───────────────────────────────┤ │ │ ConsultantChat       │ │
│ [Queue] │ │ Monaco Editor /               │ │ │                      │ │
│ [Term]  │ │ MonacoDiffEditor (Side-by-side│ │ │                      │ │
│ [Gear]  │ │ or Inline Diff)               │ │ │                      │ │
│         │ ├───────────────────────────────┤ │ ├──────────────────────┤ │
│         │ │ Bottom Drawer (Terminal PTY)  │ │ │ TaskComposer (Prompt)│ │
│         │ └───────────────────────────────┘ │ └──────────────────────┘ │
├─────────┴───────────────────────────────────┴──────────────────────────┤
│ StatusBar: [Branch: master*] [UTF-8] [Python 3.11]       [Toast Area]  │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.1. Komponen Tata Letak Inti
1. **`AppNavbar.vue`**:
   - Menampilkan status proyek aktif, menu navigasi utama, dan indikator proses latar belakang (`.nav-assistant-pill`).
2. **`ActivityBar.vue`**:
   - Kolom navigasi vertikal di sisi kiri untuk beralih antara Penjelajah Berkas (`FileExplorer`), Perubahan Git (`ChangesPanel`), Antrian Tugas (`QueuePanel`), dan Pengaturan (`SettingsView`).
3. **Area Editor Utama (`CodeEditor.vue` & `MonacoDiffEditor.vue`)**:
   - Mengelola tab berkas aktif, mode tampilan kode penuh, serta komparasi perubahan side-by-side dan inline.
4. **Panel Terminal Bawah (`TerminalView.vue`)**:
   - Terminal interaktif berbasis `@xterm/xterm` dengan jembatan WebSocket PTY kernel non-blocking.
5. **Drawer Asisten Kanan (`AppRightDrawer.vue`)**:
   - Menyimpan `AgentActivity.vue`, `ConsultantChat.vue`, dan `TaskComposer.vue` dengan retensi status `v-show` permanen di DOM.

---

## 2. Sistem Perbandingan Perubahan (Diff Visual Inspection)

### 2.1. Monaco Diff Editor
- **Lokasi**: `web/frontend/src/components/MonacoDiffEditor.vue`
- **Fitur**:
  - Pilihan mode perbandingan: *Side-by-Side* (layar terbelah dua) dan *Inline* (tampilan terpadu satu kolom).
  - Penyorotan perbedaan pada tingkat baris (*line-level diff*) dan karakter (*character-level diff*).
  - Tindakan cepat: Tombol **Revert Change** dan **Accept Patch** per berkas atau baris.
  - Kompatibel dengan tema gelap (*dark mode*) VS Code `vs-dark`.

### 2.2. Changes Panel (Version Control Panel)
- **Lokasi**: `web/frontend/src/components/ChangesPanel.vue`
- **Fitur**:
  - Menampilkan ringkasan jumlah berkas yang dimodifikasi, belum terdeteksi, atau dihapus.
  - Lencana status visual:
    - `M` (Modified - Kuning Amber)
    - `U` (Untracked - Hijau Neon)
    - `D` (Deleted - Merah Koral)
    - `A` (Added - Hijau Zamrud)
  - Fitur *1-click discard* untuk membatalkan perubahan lokal tanpa perlu membuka terminal.

---

## 3. Sistem Modal Persetujuan Interaktif (HITL Diff Modal)

### 3.1. `DiffModal.vue`
- **Tujuan**: Menghentikan eksekusi agen saat berada dalam mode terawasi (*supervised mode*) sebelum perubahan ditulis ke disk.
- **Elemen Tampilan**:
  - Header peringatan aksi berisiko tinggi.
  - Ringkasan aksi tool (`write_file`, `delete_file`, `run_destructive_command`).
  - Panel visual diff dari perubahan berkas yang diajukan.
  - Tombol aksi:
    - **Setujui / Approve** (warna hijau): Menerapkan perubahan dan melanjutkan langkah task.
    - **Tolak / Reject** (warna merah): Membatalkan operasi dan memberikan pesan umpan balik kepada model LLM untuk perencanaan ulang (*replanning*).

---

## 4. Filosofi Desain & Palet Warna (Design Tokens)

AegisCode Studio mengadopsi estetika *Cyberpunk Midnight* berbasis palet resmi [tokyo-night/tokyo-night-vscode-theme](https://github.com/tokyo-night/tokyo-night-vscode-theme) dengan varian Storm untuk mode Dark dan varian Light untuk mode Light:

### 4.1. Tokyo Night Storm (Dark Mode)
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

### 4.2. Tokyo Night Light (Light Mode)
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

### 4.3. Tipografi
- **Antarmuka (Sans)**: `Inter`, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
- **Kode & Terminal (Mono)**: `JetBrains Mono`, `SFMono-Regular`, Consolas, `Liberation Mono`, monospace



---

## 5. Aturan Responsif & Breakpoint Workbench

Ringkasan aturan layout yang telah diimplementasikan (sebelumnya di rencana UI IDE masa depan).

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
- **Pintasan**: `Cmd/Ctrl + P` (buka berkas), `Cmd/Ctrl + K` (perintah agent), `Ctrl + \`` (bottom dock).
- **Kekangan**: tidak ada perubahan pada `web/django_app/` untuk pekerjaan UI murni.
