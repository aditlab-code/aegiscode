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

AegisCode Studio mengadopsi estetika *Solid Matte Retro* berbasis palet resmi [morhetz/gruvbox](https://github.com/morhetz/gruvbox) varian Medium untuk mode Dark dan Light:

### 4.1. Gruvbox Dark (Medium)
- **Background Utama (`--bg`)**: `#282828` (dark0)
- **Surface / Panel (`--bg-panel`, `--bg-surface`, `--bg-card`)**: `#32302f` (dark0_soft)
- **Header & Container Tertanam (`--bg-header`, `--bg-deep`, `--bg-secondary`)**: `#1d2021` (dark0_hard)
- **Elevated Surfaces (`--bg-elev`)**: `#3c3836` (dark1)
- **Hover State (`--bg-hover`)**: `#504945` (dark2)
- **Border & Pembatas (`--border`)**: `#504945` (dark2)
- **Inner Dividers (`--border-soft`)**: `#3c3836` (dark1)
- **Tipografi Utama (`--text`)**: `#ebdbb2` (light1)
- **Tipografi Sekunder (`--text-dim`)**: `#d5c4a1` (light2)
- **Aksen Primer (`--accent`)**: `#8ec07c` (Bright Aqua) / `#b8bb26` (Bright Green)
- **Aksen Sekunder (`--accent-2`)**: `#fe8019` (Bright Orange)
- **Status Sukses (`--ok`)**: `#b8bb26` (Bright Green)
- **Status Peringatan (`--warn`)**: `#fabd2f` (Bright Yellow)
- **Status Bahaya / Error (`--err`)**: `#fb4934` (Bright Red)

### 4.2. Gruvbox Light (Medium)
- **Background Utama (`--bg`)**: `#fbf1c7` (light0)
- **Surface / Panel (`--bg-panel`, `--bg-surface`, `--bg-card`)**: `#f2e5bc` (light0_soft)
- **Header & Navbar (`--bg-header`, `--bg-secondary`)**: `#f9f5d7` (light0_hard)
- **Elevated Surfaces (`--bg-elev`)**: `#fbf1c7` (light0)
- **Hover & Inputs (`--bg-hover`, `--bg-deep`)**: `#ebdbb2` (light1)
- **Border & Pembatas (`--border`)**: `#d5c4a1` (light2)
- **Inner Dividers (`--border-soft`)**: `#ebdbb2` (light1)
- **Tipografi Utama (`--text`)**: `#282828` (dark0)
- **Tipografi Sekunder (`--text-dim`)**: `#504945` (dark2)
- **Aksen Primer (`--accent`)**: `#427b58` (Faded Aqua) / `#689d6a` (Neutral Aqua)
- **Aksen Sekunder (`--accent-2`)**: `#af3a03` (Faded Orange) / `#d65d0e` (Neutral Orange)
- **Status Sukses (`--ok`)**: `#79740e` (Faded Green)
- **Status Peringatan (`--warn`)**: `#b57614` (Faded Yellow)
- **Status Bahaya / Error (`--err`)**: `#9d0006` (Faded Red)

### 4.3. Tipografi
- **Antarmuka (Sans)**: `Inter`, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
- **Kode & Terminal (Mono)**: `JetBrains Mono`, `SFMono-Regular`, Consolas, `Liberation Mono`, monospace

