# Milestone 3 (Tahap C) — Efisiensi Token, Thinking Adapter, dan Skalabilitas

Dokumen ini memuat spesifikasi teknis, rencana optimasi performa (**OPT-01 s/d OPT-08**), serta strategi mitigasi risiko arsitektur (**R-AI-01 s/d R-AI-06**).

---

## 1. Ikhtisar Milestone 3

- **Tujuan**: Mengurangi konsumsi token berlebih, membatasi latensi retry loop, mengintegrasikan parameter thinking/reasoning model secara tepat, mencegah lonjakan penggunaan memori browser pada task panjang, serta meningkatkan modularitas kode monolitik.
- **Tingkat Prioritas**: P3 / Arsitektural & Performa.
- **Target Item**: 8 Inisiatif Optimasi (OPT-01 – OPT-08) dan 6 Mitigasi Risiko Desain (R-AI-01 – R-AI-06).

---

## 2. Rincian Inisiatif Optimasi (OPT)

### OPT-01 — Konsolidasi Batas Retry Provider dan Pemilahan Error
- **Masalah**: Retry berlapis pada tingkat orchestrator dan adapter dapat memicu hingga 16 kali percobaan HTTP untuk satu pemanggilan logis pada kondisi kegagalan tertentu.
- **Solusi**:
  1. Tetapkan total attempt budget terpadu (maksimal 3–4 percobaan secara keseluruhan).
  2. Bedakan penanganan error permanen (auth 401/403, error serialisasi, invalid schema) yang harus langsung gagal tanpa retry, dari error transien (rate limit 429, timeout jaringan) yang memerlukan backoff eksponensial.
- **Ukuran Keberhasilan**: Penurunan latensi p95 pada saat terjadi kegagalan jaringan dan eliminasi pemanggilan berulang untuk error deterministik.

### OPT-02 — Standarisasi Parameter Wire Model Thinking / Reasoning
- **Masalah**: Konfigurasi `supports_thinking` dan `reasoning_budget` belum memiliki validasi pemetaan format wire JSON yang seragam antar-adapter provider.
- **Solusi**:
  1. Buat pemetaan eksplisit parameter thinking per-adapter (misalnya parameter vendor untuk Anthropic, OpenAI, atau Ollama).
  2. Tambahkan contract test untuk memastikan parameter reasoning diteruskan tanpa merusak serialisasi HTTP.
- **Ukuran Keberhasilan**: Metadata reasoning diterima dan tercatat di telemetry tanpa memicu error API.

### OPT-03 — Deduplikasi dan Budgeting Retrieval Konteks
- **Masalah**: Query retrieval berulang pada giliran percakapan yang panjang dapat menyumbang konsumsi token prompt yang tidak efisien.
- **Solusi**:
  1. Terapkan cache in-memory untuk pembacaan berkas pada satu giliran (turn-level read cache).
  2. Batasi total kuota token yang dapat dialokasikan untuk hasil retrieval semantik dan hybrid.
- **Ukuran Keberhasilan**: Rasio pembacaan ulang berkas berkurang dan jumlah token input per task lebih terkontrol.

### OPT-04 — Pengendalian Memori Buffer Event UI
- **Masalah**: Array event live pada `useWorkbenchLiveEvents.js` bertambah tanpa batas selama task berdurasi panjang, membebani memori dan proses rendering Vue.
- **Solusi**:
  1. Terapkan circular buffer (misalnya maksimal 500 event aktif di antarmuka tampilan).
  2. Gunakan cursor ID stabil untuk pembaruan tambahan (incremental update) tanpa mengevaluasi ulang seluruh riwayat.
- **Ukuran Keberhasilan**: Pemakaian memori browser tetap stabil setelah ribuan iterasi event.

### OPT-05 — Optimasi Persistensi Sesi Consultant
- **Masalah**: Serialisasi seluruh objek JSON sesi pada setiap perubahan kecil dapat membebani I/O disk saat percakapan menjadi panjang.
- **Solusi**:
  1. Gunakan mekanisme penulisan transaksional per giliran (single write per turn).
  2. Siapkan migrasi ke SQLite untuk penyimpanan sesi jika diperlukan konkurensi multi-worker.
- **Ukuran Keberhasilan**: Frekuensi operasi penulisan disk berkurang drastis tanpa risiko korupsi data.

### OPT-06 — Modularisasi Berkas Monolitik
- **Masalah**: Berkas `WorkbenchView.vue` (lebih dari 2.500 baris) dan `orchestrator.py` (lebih dari 2.800 baris) menggabungkan terlalu banyak tanggung jawab domain.
- **Solusi**:
  1. Ekstrak logika save/lifecycle editor, manajemen tab, dan git facade ke dalam composable independen.
  2. Pisahkan retry handler, lifecycle loop, dan telemetry dispatcher pada orchestrator ke modul-modul terpisah.
- **Ukuran Keberhasilan**: Pengurangan kompleksitas siklomatik dan kemudahan penulisan unit test terisolasi.

### OPT-07 — Pipeline Terpadu Pengolahan Lampiran (Shared Composable)
- **Masalah**: Logika pembacaan `FileReader`, validasi MIME, dan pembatasan ukuran berkas diduplikasi antara `TaskComposer.vue` dan `ConsultantChat.vue`.
- **Solusi**:
  1. Buat composable bersama `useAttachmentPipeline.js` yang menangani seleksi berkas, validasi kuota, konversi Base64, dan pemulihan draft saat error.
- **Ukuran Keberhasilan**: Satu sumber kebenaran untuk penanganan lampiran gambar di seluruh aplikasi.

### OPT-08 — Peningkatan Cakupan Pengujian Terintegrasi
- **Masalah**: Sebagian besar unit test lama menggunakan simulasi terisolasi dan belum menguji jalur produksi penuh komponen dengan deferred promises.
- **Solusi**:
  1. Tulis integration tests yang menjalankan fungsi produksi asli dengan mock network/timer terkontrol.
  2. Tambahkan linting untuk mencegah deklarasi variabel tak terdefinisi dan definisi metode ganda.
- **Ukuran Keberhasilan**: Pendeteksian dini terhadap masalah konkurensi sebelum mencapai tahap review.

---

## 3. Mitigasi Risiko Arsitektur (R-AI)

| ID | Risiko Teridentifikasi | Langkah Mitigasi |
|---|---|---|
| **R-AI-01** | Permintaan pembatalan Ask tidak menghentikan proses worker | Teruskan token pembatalan dari gateway hingga ke tingkat eksekutor tool dan panggilan LLM. |
| **R-AI-02** | Race condition pada pemanggilan simultan sesi yang sama | Terapkan antrean giliran (turn queue) atau lock berbasis sesi per ID obrolan. |
| **R-AI-03** | Inkonsistensi penulisan berkas pada eksekusi task paralel | Terapkan precondition versi berkas atau isolasi worktree terpisah untuk setiap task aktif. |
| **R-AI-04** | Alokasi token retrieval semantik melebihi batas model | Gabungkan penghitungan budget semantik ke dalam guard batas token prompt. |
| **R-AI-05** | Penanganan silent fail pada penulisan file store sesi | Tangkap `OSError` secara eksplisit dan tampilkan status kegagalan penyimpanan ke log/UI. |
| **R-AI-06** | Task ditandai DONE tanpa bukti verifikasi otomatis | Pisahkan status `completed` dari status `verified`, serta sertakan ringkasan hasil test acceptance. |

---

## 4. Gerbang Penyelesaian (Gate C Checklist)

- [x] Beban memori browser stabil di bawah beban 1.000+ streaming events (dibatasi circular buffer 500 baris di `useWorkbenchLiveEvents.js`).
- [x] Retry budget terpadu membatasi maksimum attempt pada 3–4 kali percobaan serta memutus retry loop seketika pada error permanen/non-retryable di `orchestrator.py`.
- [x] Pipeline lampiran gambar disatukan dalam satu composable bersama (`useAttachmentPipeline.js`) yang digunakan di `TaskComposer.vue` dan `ConsultantChat.vue`.
- [x] Observabilitas persistensi sesi `ConsultantSessionStore` dengan pelacakan `last_save_error` pada `OSError`.
- [x] Parameter thinking terverifikasi dengan fixture adapter resmi dan seluruh rangkaian pengujian lulus 100%.

### Ringkasan Verifikasi Otomatis Gate C:
- **Python Test Suite**: `tests/test_milestone3_optimization_scale.py` (Lulus 3/3, 100%).
- **Frontend Test Suite**: `web/frontend/src/milestone3OptimizationScale.test.mjs` (Lulus 3/3, 100%).
- **Regresi Keseluruhan**: 82/82 frontend unit tests lulus, 24/24 backend pytest milestone lulus (exit code 0).
