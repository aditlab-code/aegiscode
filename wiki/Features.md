# Katalog Fitur AegisCode Studio v0.2.05

Dokumen ini memuat katalog fitur lengkap yang tersedia di **AegisCode Studio v0.2.05**.

---

## 1. Workbench IDE & Visual Editor

- **Monaco Code Editor Berkecepatan Tinggi**: Integrasi penuh dengan engine Monaco (engine yang mentenagai VS Code), mendukung penyorotan sintaksis (*syntax highlighting*), autocompletion, dan pencarian cepat.
- **Sistem Tab & Breadcrumb Reaktif**: Pengelolaan banyak tab berkas secara bersamaan dengan pelacakan perubahan (*dirty flag*), konfirmasi penutupan berkas belum tersimpan, dan navigasi breadcrumb direktori.
- **File Explorer Terpadu**: Navigasi struktur proyek dengan pohon berkas interaktif dan ikon tipe berkas semantik.
- **Layout Responsif & Splitter Fleksibel**: Panel kiri (Explorer, Search, Threads), area editor tengah, dan panel kanan (Assistant Drawer) dapat disesuaikan ukurannya secara halus (*smooth resizing*).

---

## 2. Tim Otonom Olympus Framework

- **Arsitektur Multi-Agent Spesialis**: Memecah tugas rekayasa perangkat lunak ke dalam persona terkoordinasi:
  - **Zeus**: Master orchestrator yang mengawal 6 fase siklus pengembangan.
  - **Athena**: Perencana strategis dan pengurai kebutuhan.
  - **Hermes**: Penjelajah kode cepat berbasis struktur CodeGraph AST.
  - **Hephaestus**: Penulis kode bedah dalam irisan tipis terverifikasi.
  - **Heracles**: Penegak pengujian TDD dengan prinsip *Prove-It*.
  - **Themis**: Penilai kualitas multi-axis (Correctness, Readability, Architecture, Security, Performance).
- **Mode Fleksibel (Ask vs Agents)**:
  - *Mode Ask*: Konsultasi cepat dan tanya-jawab arsitektur tanpa mengubah kode di disk.
  - *Mode Agents*: Pendelegasian eksekusi tugas otonom lengkap dengan verifikasi kode.

---

## 3. Human-in-the-Loop (HITL) & Visual Diff Review

- **Tinjauan Diff Sebelum Tulis**: Setiap modifikasi kode yang diajukan oleh agent ditampilkan dalam penampil diff visual (*unified diff viewer*) sebelum disimpan ke disk.
- **Kontrol Persetujuan Mutlak**: Pengembang memegang kendali penuh untuk menekan tombol **Approve** atau **Reject** terhadap setiap usulan perubahan.

---

## 4. Telegram Remote Companion (Mobile Steering)

- **Zero-Trust Outbound Architecture**: Tidak membutuhkan port publik, IP statis, atau reverse proxy (ngrok). Komputer lokal terhubung langsung ke Telegram API via *outbound long-polling*.
- **Pairing Instan via QR Code**: Menghubungkan akun Telegram dalam hitungan detik melalui pemindaian QR code di IDE atau deep link sekali klik.
- **Notifikasi & Interaksi Ponsel**: Menerima peringatan saat agent membutuhkan persetujuan, melihat cuplikan perubahan kode, menekan tombol `[Approve]`/`[Reject]`, serta membalas pesan untuk mengarahkan agent dari jarak jauh.

---

## 5. Smart Terminal Terintegrasi

- **xterm.js Terminal Console**: Terminal interaktif berbasis web yang terintegrasi langsung dengan shell lokal mesin Anda (zsh/bash/PowerShell).
- **Pemantauan Proses & Background Tasks**: Manajemen tugas latar belakang, pengecekan status server backend, dan isolasi proses eksekusi.

---

## 6. Unified Theming Engine (10 Presets)

- **Sistem Token CSS Dual-Mode**: Arsitektur token warna murni tanpa hardcoded hex di dalam komponen, memastikan sinkronisasi sempurna antara UI, editor Monaco, dan terminal xterm.
- **10 Pilihan Preset Menawan**:
  - *6 Tema Gelap*: Aegis Dark, Midnight Obsidian, Cyberpunk Neon, Tokyo Twilight, Monokai Pro, Deep Space.
  - *4 Tema Terang*: Clean Porcelain, Warm Paper, Solar Light, Arctic Frost.
- **Peralihan Instan**: Ganti tema kapan saja tanpa memuat ulang (*reload*) halaman.

---

## 7. Kedaulatan Data & Filosofi BYOK

- **Sovereign Local Authentication**: Kredensial lokal terlindungi dengan PBKDF2-HMAC-SHA256 (100.000 iterasi) dan token sesi JWT.
- **Bring Your Own Key (BYOK)**: Fleksibilitas memilih provider model AI (Google Gemini, OpenAI, Claude/Anthropic, atau engine lokal) secara mandiri.
