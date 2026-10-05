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

AegisCode Studio mengadopsi estetika *Industrial Dark Engineering*:
- **Background Utama**: `#0f141c` (Deep Slate Navy)
- **Background Surface / Panel**: `#161f2e`
- **Border & Pembatas**: `#24334a`
- **Aksen Primer**: `#3b82f6` (Engineering Blue)
- **Aksen Peringatan / Berjalan**: `#f59e0b` (Amber Pulser)
- **Aksen Sukses / Hijau Git**: `#10b981` (Emerald)
- **Aksen Bahaya / Error**: `#ef4444` (Crimson Red)
- **Tipografi**:
  - Antarmuka: `Inter`, system-ui, sans-serif
  - Kode & Terminal: `Fira Code`, `JetBrains Mono`, Menlo, monospace
