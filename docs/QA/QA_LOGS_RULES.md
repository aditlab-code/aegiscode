# Pedoman & Aturan Baku Pencatatan Log QA (QA Logs Protocol)

Dokumen ini menetapkan aturan standar pencatatan riwayat pengujian (*QA Logging Rules*) untuk seluruh pengembang dan sub-agent otonom (khususnya `werkudara-tester` dan `semar-orchestrator`) di repositori **AegisCode**.

---

## 1. Tujuan & Filosofi QA Logs

Pencatatan log pengujian bertujuan untuk:
1. **Auditibilitas dan Transparansi**: Menyediakan bukti rekam jejak eksekusi Stop-Gate (exit code 0 atau defect) yang dapat diverifikasi secara independen.
2. **Pelacakan Regresi & Flakiness**: Mengidentifikasi pengujian yang gagal secara berulang atau bersifat fluktuatif (*flaky*) antar-commit.
3. **Efisiensi Token**: Menstandarisasi ringkasan eksekusi agar padat informasi tanpa menyalin seluruh keluaran terminal mentah ke dalam konteks agen (< 250 token untuk operan).
4. **Kepatuhan Regulasi**: Menegakkan kepatuhan terhadap standar rekayasa di [docs/ruleset.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/ruleset.md) dan [AGENTS.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/AGENTS.md).

---

## 2. Struktur Direktori & Konvensi Penamaan Berkas

Seluruh rekam jejak pengujian disimpan pada direktori:
```
docs/QA/logs/
```

### Konvensi Penamaan Berkas:
```
YYYY-MM-DD_<lingkup>_<status>.md
```
- **`YYYY-MM-DD`**: Tanggal eksekusi uji (misal: `2026-10-07`).
- **`<lingkup>`**: Cakupan pengujian: `backend`, `frontend`, `contract`, `e2e`, atau `full-suite`.
- **`<status>`**: Hasil pengujian: `PASS` (semua lolos) atau `FAIL` (terdapat kegagalan).
- *Contoh*: `docs/QA/logs/2026-10-07_backend_FAIL.md`, `docs/QA/logs/2026-10-07_frontend_PASS.md`.

---

## 3. Format Baku Laporan Log QA

Setiap berkas log QA **wajib** mengikuti struktur format di bawah ini:

```markdown
# QA Test Run Log: [Lingkup Pengujian]

- **Waktu Eksekusi**: YYYY-MM-DD HH:mm:ss (Zona Waktu)
- **Eksekutor**: [werkudara-tester | semar-orchestrator | Developer]
- **Branch / Commit**: master @ [commit-hash-pendek]
- **Runner**: [pytest | node:test | vitest | playwright]
- **Status Akhir**: [PASS (Exit Code 0) | FAIL (Exit Code 1)]

---

## 1. Ringkasan Eksekusi
- **Total Pengujian**: [Jumlah]
- **Lulus (Passed)**: [Jumlah]
- **Gagal (Failed)**: [Jumlah]
- **Dilewati (Skipped)**: [Jumlah]
- **Durasi Eksekusi**: [Durasi dalam detik / ms]

---

## 2. Rincian Kegagalan (Hanya jika Status FAIL)
Jika ada pengujian yang gagal, cantumkan tabel kegagalan secara spesifik:

| ID / Nama Pengujian | Berkas & Baris | Jenis Galat | Ringkasan Penyebab |
| :--- | :--- | :--- | :--- |
| `test_fungsi_x` | `tests/test_x.py:42` | `AssertionError` | Nilai actual != expected |

### Cuplikan Stack Trace Kritis:
\`\`\`
[Sertakan hanya 5-10 baris paling relevan dari trace kegagalan, dilarang menyalin seluruh log ratusan baris]
\`\`\`

---

## 3. Analisis Akar Masalah & Tindakan Remediasi
- **Diagnosis**: [Analisis penyebab kerusakan logika, timing, atau ketidaksesuaian skema]
- **Tindakan yang Diambil**: [Langkah perbaikan kode atau isolasi pengujian]
- **Verifikasi Ulang**: [Hasil pengujian ulang setelah perbaikan dilakukan]
```

---

## 4. Aturan Penegakan untuk Sub-Agent (Kepatuhan AGENTS.md)

1. **Kewajiban Werkudara (Step 4)**:
   - Sebelum tugas diserahkan kembali kepada `semar-orchestrator`, `werkudara-tester` wajib membuat atau memperbarui berkas log QA di `docs/QA/logs/` jika terjadi kegagalan atau jika menjalankan verifikasi stop-gate penuh.
   - Ringkasan format 4-kotak pada kotak `[Stop-Gate]` **wajib** mencantumkan tautan ke berkas log yang bersangkutan.
2. **Larangan Emoji & Bahasa Daerah**:
   - Seluruh teks log wajib menggunakan Bahasa Indonesia baku, tanpa emoji, dan tanpa kosakata bahasa Jawa.
3. **Penyaringan Log Mentah (Lean Logging)**:
   - Dilarang menyimpan log mentah verbose (> 500 baris) di `docs/QA/logs/`. Gunakan perintah peringkas seperti `rtk smart` atau saring trace hanya pada blok kegagalan inti.
