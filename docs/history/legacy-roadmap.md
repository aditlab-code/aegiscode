# Arsip Peta Jalan & Riwayat Fitur Legacy (Completed Milestones)

Dokumen ini merupakan satu-satunya berkas arsip resmi yang memuat catatan historis, arsitektur, dan dokumentasi teknis dari seluruh fase serta modul awal yang telah berhasil diselesaikan dan lolos verifikasi pada basis kode **AegisCode** (AegisCode Studio & Aegis Agent).

---

## 1. Ringkasan Fase yang Telah Diselesaikan

| Fase Legacy | Nama Modul | Cakupan Utama | Status Verifikasi |
| :--- | :--- | :--- | :---: |
| **Phase 0** | Integrasi Provider Google Antigravity & Stateless OAuth | Provider native `agy` CLI bridge, keluarga model frontier Gemini/Claude/GPT-OSS, stateless signed JWT OAuth anti-CSRF, dan discovery database `.aegis/` / `.aether/`. | Lulus (Exit Code 0) |
| **Phase 1** | Interaksi UI & Fondasi Version Control (Git Facade) | Penyelesaian sebutan file `@file` batas aman 64KB, slash commands, API REST Git facade, status badge Monaco Diff Editor dua arah/satu arah, dan retensi komponen DOM latar belakang. | Lulus (Exit Code 0) |
| **Phase 2.1** | Mesin Semantik Lokal & Basis Data Vektor On-Device | Integrasi `fastembed` (`BAAI/bge-small-en-v1.5`), `sqlite-vec` embedded di `.aegis/vectors.db`, chunking AST Python/JS/TS, sidik jari SHA-256 untuk indexing inkremental, dan read-only semantic tool. | Lulus (Exit Code 0) |
| **Phase 2.2** | Asymmetric Split-Brain Engine & Reciprocal Rank Fusion (RRF) | Penggabungan pencarian leksikal `atlas.json` dengan kemiripan `sqlite-vec` via algoritma RRF (`hybrid_search`), serta kurasi paket konteks cloud reasoning di bawah batas 4.000 token. | Lulus (Exit Code 0) |

---

## 2. Rincian Teknis Implementasi Per Fase

### 2.1. Phase 0: Google Antigravity Provider & Stateless OAuth

*Status*: Selesai dan terverifikasi penuh pada test suite.

#### Rincian Arsitektur:
- **Provider Core**: Mengimplementasikan `AntigravityProvider` pada `src/agent_ai/providers/antigravity.py` dengan jembatan CLI native (`agy`) serta pemanggilan langsung ke endpoint frontier reasoning.
- **Stateless Google OAuth**: Mengimplementasikan otentikasi Google berbasis stateless signed JWT dengan validasi token anti-CSRF pada `web/django_app/api/auth.py`.
- **Sistem Pembacaan Kredensial Otomatis**: Membaca kredensial OAuth lokal pengguna secara otomatis dari `~/.gemini/oauth_creds.json`.
- **Registri Model Frontier**: Mendukung model penalaran:
  - Gemini: `gemini-3.8-flash-high`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-low`, `gemini-3.7-flash-high`, `gemini-3.1-pro-high`, `gemini-3.1-pro-low`.
  - Thinking Models: `claude-sonnet-4-6`, `claude-opus-4-6-thinking`.
  - Open Weights: `gpt-oss-120b-medium`.
- **Integrasi Database Ganda**: Pendaftaran otomatis Google Antigravity pada `LLMConfigService` dengan discovery database `.aegis/` (`data/aegis.db`) dan fallback otomatis ke `.aether/` (`data/aether.db`).

#### Berkas Terkait:
- `src/agent_ai/providers/antigravity.py`
- `src/agent_ai/config/settings.py`
- `src/agent_ai/providers/factory.py`
- `src/agent_ai/llm_config/provider_service.py`
- `web/django_app/api/auth.py`

#### Bukti Pengujian:
- `tests/test_antigravity_provider.py`
- `tests/test_oauth_state.py`

---

### 2.2. Phase 1: Interaksi UI & Fondasi Version Control

*Status*: Selesai dan terverifikasi penuh pada test suite.

#### Rincian Arsitektur:
- **Pencarian Sebutan Cepat (@file)**: Implementasi resolver sebutan file berbasis fuzzy search pada `src/agent_ai/contextbuilder/mention.py` dengan batas atas aman 64KB per pembacaan file.
- **Template Perintah Cepat (Slash Commands)**: Penyediaan template perintah terstandarisasi (`/fix`, `/test`, `/audit`, `/refactor`) pada prompt input.
- **Git Local Repository Facade**: Menghubungkan abstraksi `GitRepositoryFacade` (`src/agent_ai/git/repository.py`) ke API Gateway REST:
  - `/api/git/status`: Mendeteksi perubahan file secara real-time.
  - `/api/git/diff`: Menghasilkan representasi unified diff baris dan karakter.
  - `/api/git/commits`: Menampilkan riwayat commit repositori lokal.
  - `/api/git/branches`: Menampilkan daftar branch lokal dan remote.
  - `/api/git/discard`: Membatalkan perubahan lokal file yang belum di-commit.
- **Indikator Status Berkas Real-Time**: Lencana status berkas (`M` Modified, `U` Untracked, `D` Deleted, `A` Added) pada `web/frontend/src/components/FileExplorer.vue`.
- **Monaco Diff Editor Terintegrasi**: Visualisasi perbandingan berkas dua arah (*side-by-side*) dan satu arah (*inline*) di dalam AegisCode Studio via `web/frontend/src/components/MonacoDiffEditor.vue` dan `ChangesPanel.vue`.
- **Retensi Komponen DOM Latar Belakang (`v-show`)**: Kolom AI Assistant pada `web/frontend/src/pages/WorkbenchView.vue` dipertahankan menggunakan `v-show="assistantVisible"`, menjaga proses eksekusi task, posisi scroll, riwayat obrolan, dan panggilan tool tetap aktif saat drawer ditutup.
- **Indikator Navbar & Notifikasi**: Komponen `AppNavbar.vue` menampilkan pil status denyut saat AI aktif di latar belakang, dilengkapi komponen `.wb-bg-toast` untuk pratinjau hasil task yang telah rampung.

#### Berkas Terkait:
- `src/agent_ai/contextbuilder/mention.py`
- `src/agent_ai/git/repository.py`
- `web/django_app/api/views.py`
- `web/frontend/src/components/ChangesPanel.vue`
- `web/frontend/src/components/MonacoDiffEditor.vue`
- `web/frontend/src/components/FileExplorer.vue`
- `web/frontend/src/components/CommandPalette.vue`
- `web/frontend/src/pages/WorkbenchView.vue`
- `web/frontend/src/components/AppNavbar.vue`

#### Bukti Pengujian:
- `tests/test_mention_resolver.py`
- `tests/test_git_facade.py`
- `web/frontend/tests/MonacoDiffEditor.test.ts`

---

### 2.3. Phase 2.1: Local Embeddings & Basis Data Vektor On-Device

*Status*: Selesai dan terverifikasi penuh pada test suite.

#### Rincian Arsitektur:
- **FastEmbed In-Memory & On-Device**: Pustaka `fastembed` diintegrasikan menggunakan model `BAAI/bge-small-en-v1.5` (384 dimensi, ~67MB bobot lokal) dengan opsi penimpaan lingkungan via variabel `AEGIS_EMBED_MODEL`.
- **Penyimpanan Vektor SQLite-Vec**: Pemanfaatan ekstensi embedded `sqlite-vec` pada `.aegis/vectors.db` dengan fallback otomatis ke `.aether/vectors.db`, didukung fallback ganda `BruteForceVectorStore` via `sqlean.py` jika ekstensi biner tidak tersedia.
- **AST Semantic Chunking**: Pemisahan berkas kode sumber berdasarkan batasan sintaksis logis (fungsi dan kelas) untuk Python (`ast.parse`), JS/TS (`_match_braces`), serta fallback LangChain text splitter dengan batas ~450 token (~1.800 karakter).
- **Idempotensi Sidik Jari SHA-256**: Skema cache sidik jari berkas (`file_fingerprints`) memastikan pengindeksan inkremental hanya memproses berkas yang mengalami modifikasi konten aktual.
- **Peralatan Semantic AI**: Integrasi tool `semantic_search` (tersedia bagi Agen dan Konsultan) serta `refresh_semantic_index`.

#### Berkas Terkait:
- `src/agent_ai/repointel/semantic/chunker.py`
- `src/agent_ai/repointel/semantic/indexer.py`
- `src/agent_ai/repointel/semantic/vector_store.py`
- `src/agent_ai/tools/semantic.py`
- `src/agent_ai/codeindex/parsers/python.py`
- `src/agent_ai/runtime/telemetry/hardware.py`

#### Bukti Pengujian:
- `tests/test_fastembed_indexer.py`
- `tests/test_sqlite_vec_store.py`
- `tests/test_semantic_chunker.py`
- `tests/test_semantic_tools.py`
- `tests/test_hardware_profile.py`

---

### 2.4. Phase 2.2: Asymmetric Split-Brain Engine & Reciprocal Rank Fusion (RRF)

*Status*: Selesai dan terverifikasi penuh pada test suite.

#### Rincian Arsitektur:
- **Pemisahan Peran Asimetris (Split-Brain)**:
  - *Local Worker (The Eyes & Indexer)*: Menjalankan parsing AST, pemeliharaan indeks vektor lokal, dan kompresi konteks di mesin pengembang tanpa konsumsi latensi jaringan.
  - *Cloud Orchestrator (The Brain & Hands)*: Menerima paket konteks bersih yang telah dipadatkan secara ketat (< 4.000 token) untuk proses penalaran tingkat tinggi dan pembentukan kode diff.
- **Hybrid Retrieval Reciprocal Rank Fusion (RRF)**: Implementasi algoritma pemeringkatan RRF pada `src/agent_ai/repointel/semantic/rrf.py` dan `hybrid.py` yang menggabungkan hasil pencarian leksikal `atlas.json` dengan kemiripan vektor semantik `sqlite-vec`.
- **Proteksi Penulisan Berkas**: Integrasi penguncian penulisan berkas (`FileWriteLock`) untuk menjamin keselamatan saat menerapkan patch diff dari cloud ke disk fisik.

#### Berkas Terkait:
- `src/agent_ai/repointel/semantic/rrf.py`
- `src/agent_ai/repointel/semantic/hybrid.py`
- `src/agent_ai/contextbudget/budget.py`
- `src/agent_ai/tools/project_map.py`

#### Bukti Pengujian:
- `tests/test_rrf_ranker.py`
- `tests/test_split_brain_budget.py`

---

### 2.5. Arsip Dokumen Local Hybrid RAG (`rag_local_future.md`, dinyatakan selesai)

Dokumen perencanaan RAG lokal dinyatakan selesai dan diarsipkan di sini; berkasnya dihapus dari `Roadmap.md`.

- **Rancangan inti**: Local Worker (indeks, pencarian vektor, traversal AST di perangkat) dan Cloud Orchestrator (menerima paket konteks kurang dari 4.000 token). Mode eksekusi: Full Cloud, Full Local (air-gapped), dan Hybrid Asymmetric.
- **Tahap selesai**: infrastruktur vektor dan embeddings lokal, AST chunking dan ingestion SHA-256, orkestrasi hybrid retrieval (RRF) dengan registrasi tool di `ToolRegistry`.
- **Strategi verifikasi**: pengujian retrieval dipisahkan dari generasi LLM, memakai repositori tiruan `tests/fixtures/mock_repo/` dan metrik Recall@K/MRR; modifikasi pada `src/agent_ai/contextbudget/` atau `src/agent_ai/repointel/` wajib menjaga 100% test lulus.
- **Butir yang tidak dikerjakan dan dilepas dari roadmap aktif demi fokus stabilitas** (YAGNI): adapter runner lokal Ollama/llama.cpp dengan auto-detection, integrasi retrieval ke compaction dan dedup terhadap tab editor terbuka (`contextbudget/dedup.py`), serta telemetri hardware dan panel transparansi RAG di UI. Butir ini hanya dapat dibuka kembali lewat keputusan baru setelah Fase 4 lulus.

---

## 3. Catatan Transisi Menuju Arsitektur Stabil

Dengan rampungnya Phase 0 hingga Phase 2.2, seluruh pengembangan selanjutnya dialihkan secara ketat menuju program stabilisasi dan pengerasan mutu arsitektur (Fase 1 hingga Fase 4 pada [Roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/Roadmap.md) dan [Roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/Roadmap.md)). Seluruh kebutuhan historis yang berkaitan dengan fitur dasar di atas dinyatakan tuntas dan tidak boleh dimodifikasi tanpa proses audit regresi.
