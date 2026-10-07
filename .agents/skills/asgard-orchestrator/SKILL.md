---
name: asgard-orchestrator
description: "Aturan workflow Asgard Orchestrator Mode (REVIEW: 1-2-3-4). Koordinasi dewan paripurna Asgard 4-tahap end-to-end dari telaah awal Odin hingga pengujian palu Mjolnir Thor."
---

# Asgard Orchestrator Mode — Aturan Workflow (REVIEW: 1-2-3-4)

## 1. Definisi & Ruang Lingkup
Skill ini mengatur aturan alur kerja **Asgard Orchestrator Mode**, yaitu siklus sidang dewan Asgard 4-tahap lengkap dari awal penerimaan amanat oleh Allfather Odin hingga verifikasi mutu independen stop-gate dengan palu Mjolnir Thor.

## 2. Alur Eksekusi Antar-Agen (Flow)
`odin-orchestrator` ──▶ `heimdall-scout` ──▶ `mimir-architect` ──▶ `forseti-auditor` ──▶ `heimdall-scout` ──▶ `brokkr-coder` ──▶ `thor-tester` ──▶ `odin-orchestrator`

## 3. Rincian 4 Tahap Alur Kerja Dewan Asgard
1. **Step 1: Terima Input & Review (Odin-Orchestrator)**:
   - Hak Akses: `review-only`.
   - Mengamati seluruh ranah dari singgasana Hlidskjalf, menelaah kebutuhan pengguna, mendekomposisi tugas, dan mengarahkan sidang dewan. Dilarang keras menulis kode langsung.
2. **Step 2: Riset, Plan & Audit (Heimdall, Mimir, Forseti)**:
   - Heimdall (`review-only`): Pengawas gerbang Bifrost, memindai simbol dan relasi kode via CodeGraph AST.
   - Mimir (`plan-only`): Sumber hikmat, menganalisis arsitektur defensif, menyaring kebutuhan lewat filter minimalis (YAGNI), dan menyusun checklist TODO. Dilarang menulis kode implementasi.
   - Forseti (`verification-audit`): Hakim Glitnir, mengaudit etika arsitektur dan mengeksekusi verifikasi bash terhadap lingkungan sistem.
3. **Step 3: Riset & Penempaan Kode (Heimdall, Brokkr)**:
   - Heimdall (`review-only`): Menemukan irisan baris kode target secara presisi (Precision Slice).
   - Brokkr (`code-editor`): Penempa kode artisan, menulis implementasi modular berdasarkan checklist TODO Mimir dan menjalankan verifikasi cepat.
4. **Step 4: Verifikasi Independen Palu Mjolnir (Thor-Tester)**:
   - Hak Akses: `independent-qa` (murni `run_command` dan `view_file`, tanpa izin edit kode).
   - Wajib dieksekusi oleh sub-agent independen terisolasi (*zero self-grading*). Mengayunkan palu Mjolnir untuk menguji keandalan test suite native 100% hijau tanpa toleransi, serta menegakkan 4 aturan QA: `no-orphan-code`, `no-spaghetti-code`, `no-empty-catch-without-fallback`, dan `no-dummy-pass`. Jika pengujian gagal, Thor menolak stop-gate dan melarang perbaikan kode sendiri.

## 4. Protokol Delegasi Sub-Agents Sejati (invoke_subagent)
Untuk mematuhi prinsip isolasi tugas, integritas audit independen, dan pencegahan pembengkakan konteks LLM, `odin-orchestrator` WAJIB mendelegasikan eksekusi tahapan dewan melalui `invoke_subagent` (atau `define_subagent`):
- **Step 2 (Riset AST & Audit)**: Panggil `invoke_subagent` dengan `TypeName: "research"`, `Role: "heimdall-scout"`.
- **Step 3 (Implementasi Kode)**: Panggil `invoke_subagent` dengan `TypeName: "self"`, `Role: "brokkr-coder"`.
- **Step 4 (Verifikasi Palu Mjolnir Independen)**: Panggil `invoke_subagent` dengan `TypeName: "self"`, `Role: "thor-tester"`.
Orchestrator dan Coder dilarang keras mengesahkan pengujian atau menjalankan verifikasi stop-gate akhir secara mandiri tanpa pemanggilan subagent QA independen.

## 5. Protokol Eksekusi RTK & Strict Stop-Gate
- Seluruh inspeksi berkas dan eksekusi terminal WAJIB memanfaatkan utilitas RTK (`rtk rg`, `rtk find`, `rtk read`, `rtk git`, `rtk test`).
- Tugas belum selesai sebelum seluruh pengujian lulus dengan kode keluar 0 (exit code 0).
