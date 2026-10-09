# Catatan Rilis Fitur AegisCode Studio (Release Notes)

Dokumen ini mencatat riwayat rilis, changelog, dan catatan fitur untuk **AegisCode Studio**.

Konvensi penomoran versi mengikuti prinsip [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

---

## 🚀 Versi Aktif: v0.2.05

*Tanggal Rilis: Oktober 2026*  
*Tag Repositori: `v0.2.05`*

Rilis **v0.2.05** menetapkan fondasi stabil (*stable baseline*) bagi AegisCode Studio dengan integrasi penuh antara antarmuka pengembang lokal, kedaulatan data, pendamping jarak jauh via Telegram, dan koordinasi agen Olympus.

### 🌟 Sorotan Fitur Utama (Highlights)

1. **Sovereign Local Authentication (Login Pengembang Lokal)**
   - Dialog inisialisasi kata sandi awal pada first-run tanpa ketergantungan layanan cloud luar.
   - Algoritma hashing PBKDF2-HMAC-SHA256 (100.000 iterasi) dengan penyimpanan lokal terenkripsi di `.aegis/auth.json`.
   - Penerbitan sesi JWT stateless dan opsi konfigurasi otomatis melalui variabel lingkungan `AEGIS_PASSWORD`.

2. **Telegram Remote Companion (Pengawasan Jarak Jauh)**
   - Arsitektur zero-trust outbound long-polling: tidak membutuhkan port publik atau reverse proxy.
   - Pemasangan instan (*instant pairing*) menggunakan pemindaian QR code di IDE atau deep link sekali klik.
   - Gerbang persetujuan Human-in-the-Loop (HITL): ponsel menerima notifikasi unified diff beserta tombol interaktif `[Approve]` dan `[Reject]`.
   - Remote steering: balas pesan bot dari ponsel untuk memberikan instruksi langsung ke agen.

3. **Workbench IDE & Monaco Visual Editor**
   - Integrasi Monaco Code Editor berkecepatan tinggi dengan syntax highlighting dan minimap.
   - Manajemen multi-tab cerdas dengan pelacakan perubahan (*dirty flag*), konfirmasi penutupan, dan breadcrumbs.
   - Layout responsif modular dengan splitter drag-and-drop yang mulus antara Explorer, Editor, dan Assistant Drawer.

4. **Olympus Multi-Agent Framework**
   - Struktur persona spesialis terkoordinasi: Zeus (Orchestrator), Athena (Planner), Hermes (Scout), Hephaestus (Coder), Heracles (Tester), Themis (Reviewer).
   - Mode kerja fleksibel: *Ask Mode* untuk konsultasi arsitektur dan *Agents Mode* untuk eksekusi tugas otonom.
   - Tinjauan diff visual sebelum agent menuliskan kode ke disk.

5. **Unified Theming Engine (10 Preset)**
   - 10 tema dual-mode elegan (6 tema gelap dan 4 tema terang) berbasis CSS token murni.
   - Sinkronisasi instan tanpa reload halaman pada UI, Monaco Editor, dan terminal xterm.js.

6. **Smart Web Terminal & Background Tasks**
   - Terminal xterm.js terintegrasi langsung dengan shell sistem lokal.
   - Pemantauan kesehatan server dan pelacakan proses latar belakang secara real-time.

---

## 📦 Riwayat Versi Terdahulu (Early Baseline)

### v0.2.0 - v0.2.04
- Implementasi awal arsitektur modular orchestrator dan runtime.
- Pengenalan kontrak event SSE kanonik dan pelacakan telemetri tugas monotonic.
- Integrasi CodeGraph AST dasar untuk eksplorasi simbol repositori.
- Penataan fondasi komponen presentasional Vue 3 dan Tailwind token styling.

---

## 🔮 Rencana Rilis Berikutnya

- **v0.3.0**: Standardisasi adapter provider BYOK (Gemini, Claude, OpenAI, Ollama) dan Community Tool Registry.
- **v0.4.0**: Sandbox eksekusi perintah terminal dan Triple-Gate QA testing harness.
- **v1.0.0**: Bundling aplikasi desktop native lintas platform via Tauri v2.
