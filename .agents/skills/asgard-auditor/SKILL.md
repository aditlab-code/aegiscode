---
name: asgard-auditor
description: "Aturan workflow Asgard Auditor Mode (QA INDEPENDEN: 4). Penegakan gerbang-henti mutu ketat (strict stop-gate) palu Mjolnir Thor 100% hijau dan jaminan anti-orphan."
---

# Asgard Auditor Mode — Aturan Workflow (QA INDEPENDEN: 4)

## 1. Definisi & Ruang Lingkup
Skill ini mengatur aturan alur kerja **Asgard Auditor Mode**, yang beroperasi mandiri pada **Step 4** untuk audit mutu, test runner execution, dan penegakan strict stop-gate.

## 2. Alur Eksekusi Agen (Flow)
`thor-tester`

## 3. Disiplin & 4 Aturan Evaluasi Independen (QA Rules)
`thor-tester` memegang hak akses `independent-qa` dan WAJIB menolak kode bila ditemukan:
1. **`no-orphan-code`**: Kode, fungsi, atau variabel yatim yang tidak terhubung ke alur sistem.
2. **`no-spaghetti-code`**: Struktur kode kusut dan mutasi global liar.
3. **`no-empty-catch-without-fallback`**: Blok try-catch yang menelan galat diam-diam tanpa fallback aman.
4. **`no-dummy-pass`**: Deklarasi dummy `pass` atau no-op placeholder functions.

## 4. Mekanisme QA Independen Agents (Zero Self-Grading)
Untuk menjamin integritas mutu tanpa bias, proses QA WAJIB dijalankan oleh agen independen dengan mekanisme berikut:
1. **Isolasi Peran & Konteks Bersih**:
   - Agen penguji (`thor-tester`) wajib berjalan sebagai sub-agent mandiri via `invoke_subagent`, terpisah dari sesi penulisan kode (`brokkr-coder`) maupun kepemimpinan orchestrator (`odin-orchestrator`).
   - Penulis kode dilarang keras mengesahkan atau menguji kodenya sendiri (*zero self-grading*).
2. **Pembatasan Hak Akses Ketat (`independent-qa`)**:
   - Alat yang diizinkan murni alat inspeksi dan eksekusi uji: `run_command` dan `view_file`.
   - Dilarang keras memegang alat pengubah berkas (`write_to_file`, `replace_file_content`).
3. **Larangan Memperbaiki Kode Sendiri**:
   - Jika ditemukan kegagalan uji atau cacat kode, `thor-tester` dilarang mereparasi atau menyunting kode secara langsung.
   - `thor-tester` wajib menolak stop-gate, mencatat rincian kegagalan pada `docs/QA/logs/`, dan mengembalikan laporan cacat (*defect report*) kepada `odin-orchestrator` untuk diperbaiki oleh `brokkr-coder`.
4. **Hak Veto Mutlak Palu Mjolnir**:
   - Keputusan lulus atau tolak murni ditentukan oleh eksekusi test runner (exit code 0).
   - Tidak ada peran lain (termasuk orchestrator) yang dapat membatalkan veto palu Thor jika pengujian masih merah atau terdapat pelanggaran 4 aturan QA.

## 5. Protokol Delegasi Sub-Agents Sejati (invoke_subagent)
- **Step 4 (Verifikasi Palu Mjolnir Independen)**:
  Panggil `invoke_subagent` dengan spesifikasi:
  - `TypeName`: `"self"` atau agen verifikasi independen
  - `Role`: `"thor-tester"`
  - `Prompt`: Berikan instruksi verifikasi bersih, perintah test runner target, dan daftar periksa 4 aturan QA.
Orchestrator dan Coder dilarang menjalankan pengujian akhir sendiri tanpa mendelegasikan ke sub-agent independen.
