# AGENTS.md — AegisCode & Asgard Multi-Agent Framework (OMA)

## 1. Tujuan
Ekosistem **AegisCode** (Studio & Aegis Agent) dengan orkestrasi **Asgard OMA** untuk Antigravity CLI: Agent Build Hub (6 agen, skills `asgard-*`, hooks RTK), efisiensi token (RTK, Split-Brain < 4.000 token), dan mutu YAGNI (zero-orphan, zero-zombie tree-kill, kompatibilitas `.aegis/` dan `.aether/`).

## 2. Branch Git (detail: `docs/Gitmaster.md`)
- `master`: hub pengembangan; satu-satunya tempat `docs/`, `AGENTS.md`, `Roadmap.md`.
- `main`: edisi komunitas BYOK; dilarang memuat `docs/`, `AGENTS.md`, `Roadmap.md`; hanya `README.md` publik; perubahan lewat issue dan PR; filtrasi via `.gitattributes` (`export-ignore`) dan sparse-checkout.
- `release`: bundle enterprise `.dmg` via Tauri v2; debug dinonaktifkan; kerangka siaga.

## 3. Framework Multi-Agent
Antigravity bertindak sebagai `odin-orchestrator` via PreToolUse Hooks (`.agents/hooks.json`, `~/.gemini/hooks.json`). Alur: Odin (review, tanpa edit) -> Heimdall/Mimir/Forseti (scan, rencana, audit) -> Heimdall/Brokkr (implementasi) -> Thor (stop-gate).

| Agen | Peran | Hak Akses | Tools |
|---|---|---|---|
| `odin-orchestrator` | Orkestrator (1) | review-only | `invoke_subagent`, `send_message`, `manage_subagents`, `ask_question` |
| `heimdall-scout` | Scout AST (2-3) | review-only | `view_file`, `search_web`, `read_url_content`, `codegraph_*` |
| `mimir-architect` | Arsitek (2) | plan-only | `view_file`, `search_web`, `read_url_content`, `define_subagent` |
| `forseti-auditor` | Auditor bash (2) | verification-audit | `view_file`, `run_command`, `read_verification` |
| `brokkr-coder` | Coder (3) | code-editor | `write_to_file`, `replace_file_content`, `view_file`, `run_command` |
| `thor-tester` | QA independen (4) | independent-qa | `run_command`, `view_file` |

Mode (skills): `asgard-orchestrator` (1-2-3-4), `asgard-plan` (2), `asgard-executor` (3-4), `asgard-auditor` (4).

**Zero Self-Grading**: (1) Tahap 4 wajib didelegasikan ke `thor-tester` via `invoke_subagent`; Brokkr dan Odin dilarang mengesahkan kode sendiri. (2) Thor tanpa izin tulis. (3) Jika gagal, Thor menolak stop-gate, mencatat log di `docs/QA/logs/`, dan tidak memperbaiki kode.

## 4. Protokol RTK
Wajib pakai `rtk`: `rtk rg`, `rtk find`, `rtk read`, `rtk git status/diff/log`, `rtk test` atau `node --test`, `rtk json`, `rtk smart`/`rtk err`. Fallback jika `which rtk` gagal: `rg`, `find`, `git`, `node --test`.

## 5. Pengujian & Stop-Gate
- Runner: `node:test`/`node:assert` dan `pytest`, tanpa dependensi tambahan.
- Cakupan wajib: profil `.agents/agents/*/agent.md`, frontmatter `.agents/skills/*/SKILL.md`, validitas `hooks.json` (pemicu `rtk-hook.js`), discovery `.aegis/` dengan fallback `.aether/` (dan `data/aegis.db` / `data/aether.db`), zero-zombie saat sesi ditutup.
- Setiap Stop-Gate penuh atau kegagalan dicatat di `docs/QA/logs/` sesuai `docs/QA/QA_LOGS_RULES.md`.
- Tugas belum selesai sebelum semua uji lulus (exit code 0); assertion dilarang dimatikan.

## 6. Komunikasi & Output
- Internal Inggris; output (respons, komentar, commit, dokumentasi) Bahasa Indonesia baku. Dilarang: Bahasa Jawa, emoji, dan chain-of-thought mentah.
- Operan antar-subagent maks. 250 token, format `[Diagnosis]` `[Keputusan & YAGNI]` `[Kontrak/Diff]` `[Stop-Gate]`; sebutkan dokumen `docs/` rujukan pada `[Kontrak/Diff]` untuk perubahan arsitektur, API, UI, atau pengujian.

## 7. Alur Kerja
Inspeksi simbol dahulu (`rtk rg`/`rtk find`); baca seluruh log saat gagal; jalankan `node --test` atau `npm test` sebelum selesai; laporan ringkas dengan tautan markdown ke berkas yang diubah.

## 8. Rujukan Knowledge Base (JIT, dilarang memuat seluruh `docs/`)
Visi: `docs/PRD.md` | Arsitektur: `docs/architecture.md` | API/JWT/Git/PTY: `docs/api.md` | UI: `docs/ui-design.md` | Standar rekayasa: `docs/ruleset.md` | Git: `docs/Gitmaster.md` | Antigravity: `docs/core-features/antigravity_provider.md` | Workbench: `docs/core-features/workbench_features.md` | CoT/Replanning: `docs/core-features/cot_reasoning_runtime.md` | Roadmap aktif: `Roadmap.md` | QA: `docs/QA/QA_PLAN.md`, `docs/QA/QA_LOGS_RULES.md` | Riwayat: `docs/history/legacy-roadmap.md` | Indeks: `docs/README.md`.

## 9. Standar Front-End (`web/frontend/`)
- **9.1 Dual-Theme**: token latar (`--bg-drawer`, `--bg-sidebar`, `--bg-panel`, `--bg-card`, `--bg-deep`) wajib berpasangan di `src/styles/base/variables.css` (gelap) dan `src/styles/themes/theme-light.css` (`[data-theme="light"]`); dilarang fallback heksadesimal gelap pada `var()`.
- **9.2 Drawer**: tab Agent dan Ask (termasuk `ConsultantChat` embedded) wajib memakai `var(--bg-drawer)` tanpa background independen; sidebar kiri `.app-left-sidebar` memakai `var(--bg-sidebar)`.
- **9.3 Komponen**: gunakan `AppButton.vue` (`primary|ghost|danger|icon`, `sm|md`) dan `AppCard.vue` (`card|panel`); dialog lewat `.unified-popup-*` (tanpa modal overlay level aplikasi); dilarang `<button>` polosan, warna heksadesimal di `.vue`, dan emoji (ikon SVG inline).
