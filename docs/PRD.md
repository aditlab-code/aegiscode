# Product Requirement Document (PRD): AegisCode

## 1. Executive Summary & Vision

* **Nama Produk**: AegisCode (AegisCode Studio & Aegis Agent)
* **Visi**: Menyediakan *Autonomous AI Coding Workbench* yang mengutamakan privasi (*local-first*), deterministik, hemat token, dan aman digunakan pada basis kode produksi melalui perlindungan *guardrails* ketat.


* **Posisi Pasar**: Alternatif mandiri untuk developer dan tim *engineering* yang membutuhkan agen AI berkemampuan tinggi tanpa ketergantungan langganan bulanan (*pay-once/perpetual license*) serta bebas dari risiko kebocoran data repositori.

---

## 2. Target Pengguna & Persona

* **Solo Developer / Indie Hacker**: Membutuhkan asisten coding otonom yang bisa menjalankan eksekusi *task* panjang tanpa menghabiskan kuota token API.


* **Lead Engineer / Tech Lead**: Memerlukan jaminan bahwa perubahan kode oleh AI dapat ditinjau via visual diff sebelum menyentuh *filesystem* (*zero code destruction*).
* **Enterprise / Security-Conscious Teams**: Membutuhkan lingkungan kerja *on-premise/air-gapped* dengan audit kepatuhan dan isolasi memori repositori.

---

## 3. Pilar Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────┐
│              AegisCode Studio (Vue 3 SPA)                   │
│   [Monaco Multi-Tab] [Diff Viewer] [ANSI PTY Terminal]      │
└──────────────────────────────┬──────────────────────────────┘
                               │ WebSocket / SSE / REST
┌──────────────────────────────▼──────────────────────────────┐
│           Django API Gateway (web/django_app)               │
│   [Stateless Auth] [Git Facade] [PTY Bridge Consumer]       │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│             Aegis Agent Engine (src/agent_ai)               │
│  ┌────────────────────────┐    ┌─────────────────────────┐  │
│  │ Local Worker (Eyes)    │    │ Cloud Orchestrator      │  │
│  │ fastembed + sqlite-vec │    │ High-level Reasoning    │  │
│  │ AST Chunking / RRF     │    │ Unified Diff Generation │  │
│  └───────────┬────────────┘    └────────────▲────────────┘  │
│              └───────────────┬──────────────┘               │
│                   Budgeted Context (< 4k)                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Guardrail Runtime: FileWriteLock & HITL Policy        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

```

1. **Hybrid Asymmetric Split-Brain**: Pembacaan, pengindeksan vektor, dan penelusuran AST dijalankan secara lokal di mesin pengguna (*Local Worker*). LLM Cloud (*Cloud Orchestrator*) hanya menerima potongan kode relevan yang telah diringkas (< 4.000 token) untuk penyusunan *patch diff*.
2. **Deterministic Guardrails & HITL**: Operasi penulisan berkas dan perintah terminal berisiko tinggi wajib melalui verifikasi kunci berkas (*FileWriteLock*) dan persetujuan pengguna (*Human-in-the-Loop Diff Modal*).
3. **Interactive Pseudo-Terminal (PTY)**: Sesi shell interaktif penuh berbasis PTY kernel non-blocking untuk terminal IDE yang responsif terhadap `Ctrl+C` dan pembersihan *zombie process*.

---

## 4. Spesifikasi Fungsional (Functional Requirements)

### 4.1. Core Agent Runtime & Planning

* **Autonomous Task Loop**: Runtime menjalankan siklus *native tool calling* berkelanjutan yang mengeksekusi rencana tanpa *timeout* prematur.
* **Deterministic Planner & Replanner**: Memecah instruksi pengguna menjadi tahapan modular serta menyesuaikan langkah jika terjadi kegagalan eksekusi secara otomatis.
* **Task Resumer**: Menyimpan *state snapshot* berbasis hash SHA-256 berkas agar *task* yang terhenti dapat dilanjutkan secara idempoten.
* **File Write Safety**: Setiap modifikasi berkas dikawal oleh `FileWriteLock` untuk mencegah tabrakan *race condition* saat agen bekerja paralel.

### 4.2. Semantic Intelligence & Retrieval (Split-Brain)

* **On-Device Vector Database**: Menggunakan ekstensi `sqlite-vec` yang tersimpan di direktori kerja (`.aegis/vectors.db`).
* **Local Embedding Engine**: Ekstraksi embedding otomatis menggunakan `fastembed` tanpa koneksi internet.
* **Hybrid Search (RRF)**: Menggabungkan hasil pencarian leksikal simbol (`atlas.json`) dan kemiripan vektor kosinus menggunakan algoritma *Reciprocal Rank Fusion*.
* **Backward-Compatible State Discovery**: Mendeteksi konfigurasi dan basis data dari folder `.aegis/` dan `data/aegis.db`, dengan *fallback* otomatis ke `.aether/` dan `data/aether.db`.

### 4.3. Version Control & Human-in-the-Loop (HITL)

* **Git Local Facade**: Integrasi langsung dengan repositori Git lokal untuk mendeteksi status file (`M`, `U`, `D`) secara *real-time*.
* **Monaco Diff Viewer**: Menampilkan visualisasi perubahan baris kode (tambah/hapus) secara berdampingan sebelum perubahan diterapkan ke berkas.
* **Supervised Mode**: Penahanan eksekusi otomatis pada aksi destruktif hingga pengguna menekan tombol *Approve* atau *Reject*.
* **Snapshot Rollback**: Fasilitas pemulihan instan (*1-click revert*) untuk membatalkan seluruh perubahan yang dibuat agen dalam satu sesi tugas.

### 4.4. Workbench & Developer Experience

* **Layout 3-Kolom IDE**: Activity Bar, Collapsible Sidebar (File Explorer & Git Changes), Center Monaco Editor Canvas, dan Right AI Drawer.
* **ANSI Interactive PTY Terminal**: Terminal terintegrasi di Bottom Dock menggunakan `@xterm/xterm` yang terhubung via WebSocket ke backend PTY master/slave.
* **Stateless Google OAuth**: Mekanisme autentikasi menggunakan *Signed Cryptographic JWT State* untuk mencegah *session drop* dan *CORS cookie rejection*.

---

## 5. Matriks Distribusi Fitur (Community vs. Pro)

| Fitur | Community Edition (Open-Core) | Pro / Commercial Edition |
| --- | --- | --- |
| **Model Distribusi** | Git Repo / Web Runner (`run.bat` / CLI) | Single-binary Desktop Installer (Tauri v2) |
| **Model Lisensi** | Bebas (MIT License) | Pay-Once Lifetime License (1 Year Free Updates) |
| **Model AI & Providers** | BYOK (OpenCode, OpenAI, DeepSeek, Ollama) | BYOK + Managed Enterprise Endpoints & Gateways |
| **Hybrid Split-Brain** | Manual configuration / Local Only | Automated Context Compaction (< 4k tokens) |
| **HITL Guardrails** | Standard Diff Review & Approve Modal | Advanced Snapshot History & Selective Chunk Revert |
| **Project Memory** | Single Workspace Memory (`.aegis/`) | Centralized Knowledge & Multi-Repo Team Sync |

---

## 6. Persyaratan Non-Fungsional (Non-Functional Requirements)

* **Keamanan & Kedaulatan Data**: Tidak ada kode sumber mentah yang dikirimkan ke server pihak ketiga tanpa pemangkasan konteks dan persetujuan pengguna. Kunci API tersimpan di berkas lokal dan wajib dimaskir pada antarmuka pengguna.
* **Performa Runtime**:
* Latensi inisiasi embedding lokal < 200 ms per fungsi berkas.
* Respons kueri pencarian semantik lokal < 50 ms pada repositori dengan < 10.000 *chunks*.
* PTY Terminal *round-trip latency* < 15 ms untuk input pengetikan.


* **Manajemen Sumber Daya (Zero-Zombie)**:
* Penghentian aplikasi via `Ctrl+C` atau penutupan antarmuka wajib mengirimkan sinyal `SIGTERM/SIGKILL` ke seluruh sub-proses (PTY slave, Django worker, dan runner lokal) guna mencegah penahanan port.


* **Kompatibilitas Sistem**: Berjalan stabil di lingkungan Linux (Debian/Ubuntu/Arch), macOS (Apple Silicon & Intel), dan Windows via sub-sistem terminal yang disesuaikan.

---

## 7. Metrik Keberhasilan (Success Metrics)

1. **Zero Data Loss**: 0 insiden penimpaan kode yang tidak diinginkan karena perlindungan `FileWriteLock` dan modal persetujuan.
2. **Token Efficiency**: Penghematan konsumsi token LLM Cloud sebesar 60%–80% dibandingkan pengiriman berkas mentah utuh melalui mekanisme *Asymmetric Split-Brain*.
3. **Execution Reliability**: Tingkat keberhasilan eksekusi *task resume* mencapai > 95% tanpa pengulangan komputasi dari awal.
4. **Clean Exit**: Tingkat proses orphan/zombie adalah 0% pada penutupan sesi terminal atau penghentian server.