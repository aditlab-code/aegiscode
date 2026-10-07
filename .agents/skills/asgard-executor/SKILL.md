---
name: asgard-executor
description: "Aturan workflow Asgard Executor Mode (EXECUTION: 3-4). Eksekusi penulisan kode penempaan presisi Brokkr dan pengujian palu Thor."
---

# Asgard Executor Mode — Aturan Workflow (EXECUTION: 3-4)

## 1. Definisi & Ruang Lingkup
Skill ini mengatur aturan alur kerja **Asgard Executor Mode**, yang berfokus langsung pada penempaan teknis kode dan pengujian mutu (**Step 3 dan Step 4**).

## 2. Alur Eksekusi Antar-Agen (Flow)
`heimdall-scout` ──▶ `brokkr-coder` ──▶ `thor-tester`

## 3. Disiplin & Tanggung Jawab Agen (Step 3 & 4)
1. **`heimdall-scout` (Code Scout)**:
   - Memandu `brokkr-coder` menemukan simbol, kelas, atau baris yang akan diedit via *Precision Slice Protocol*.
2. **`brokkr-coder` (Lead Artisan Coder - Step 3)**:
   - Hak Akses: `code-editor`.
   - Menempa kode minimal yang bekerja dan bersih berdasarkan checklist TODO Mimir. Wajib melakukan verifikasi cepat sebelum menyerahkan berkas.
3. **`thor-tester` (Independent QA Verifier - Step 4)**:
   - Hak Akses: `independent-qa` (hanya `run_command` dan `view_file`, tanpa izin menulis kode).
   - Wajib bertindak sebagai sub-agent independen (*zero self-grading*). Brokkr dilarang keras mengesahkan atau memverifikasi kodenya sendiri untuk gerbang rilis.
   - Mengayunkan palu Mjolnir untuk memastikan hasil kode lolos pengujian 100% hijau dan mematuhi standar bebas cacat mutu. Jika gagal, Thor menolak stop-gate dan mengembalikan temuan ke Brokkr.

## 4. Protokol Delegasi Sub-Agents Sejati (invoke_subagent)
- **Step 3 (Penulisan Kode)**: Panggil `invoke_subagent` dengan `TypeName: "self"`, `Role: "brokkr-coder"`.
- **Step 4 (Pengujian Mutu Independen)**: Panggil `invoke_subagent` dengan `TypeName: "self"`, `Role: "thor-tester"`.
Brokkr dilarang melewati langkah ini atau menandatangani kelulusan QA tanpa pendelegasian ke sub-agent independen Thor.
