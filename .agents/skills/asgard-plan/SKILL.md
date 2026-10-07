---
name: asgard-plan
description: "Aturan workflow Asgard Plan Mode (REVIEW: only 2). Menjalankan riset fakta kode oleh Heimdall, perancangan arsitektur defensif oleh Mimir, checklist TODO, serta audit keadilan oleh Forseti tanpa modifikasi kode."
---

# Asgard Plan Mode — Aturan Workflow (REVIEW: only 2)

## 1. Definisi & Ruang Lingkup
Skill ini mengatur aturan alur kerja **Asgard Plan Mode**, yang beroperasi murni pada **Step 2** untuk penelaahan mendalam, perancangan arsitektur defensif, dan audit kepatuhan tanpa menulis kode implementasi.

## 2. Alur Eksekusi Antar-Agen (Flow)
`heimdall-scout` ──▶ `mimir-architect` ──▶ `forseti-auditor`

## 3. Disiplin & Tanggung Jawab Agen (Step 2)
1. **`heimdall-scout` (Fast AST Scout)**:
   - Hak Akses: `review-only`.
   - Mengamati struktur kode melalui teropong Bifrost, memetakan fungsi, modul, dan simbol yang sudah ada di codebase via CodeGraph AST.
2. **`mimir-architect` (Chief Architect & Planner)**:
   - Hak Akses: `plan-only`.
   - Mengambil intisari dari sumur kebijaksanaan, mendiagnosis akar masalah, menegakkan filter YAGNI, merancang arsitektur modular defensif, dan menyusun checklist TODO. Dilarang keras menulis kode.
3. **`forseti-auditor` (Hakim Glitnir & Bash Verifier)**:
   - Hak Akses: `verification-audit`.
   - Menelaah kepatuhan rencana arsitektur terhadap etika sistem, memeriksa potensi efek samping, dan mengeksekusi uji verifikasi bash terhadap asumsi path dan direktori lingkungan.

## 4. Protokol Delegasi Sub-Agents Sejati (invoke_subagent)
- **Step 2 (Riset AST & Audit)**: Panggil `invoke_subagent` dengan `TypeName: "research"`, `Role: "heimdall-scout"`.
