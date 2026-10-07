# AGENTS.md — AegisCode & Asgard Multi-Agent Framework (OMA) Operational Guide

## 1. Project Purpose

Repository ini adalah ekosistem pengembangan **AegisCode** (AegisCode Studio & Aegis Agent) dengan kerangka orkestrasi multi-agent **Asgard Multi-Agent Framework (OMA)** untuk Google Antigravity CLI dengan tiga tujuan utama:
- **Agent Build Hub**: Mengelola 6 peran agen Asgard (Odin, Heimdall, Mimir, Forseti, Brokkr, Thor), skills (`asgard-*`), rules, dan PreToolUse hooks berbasis RTK.
- **Efisiensi Token**: Memanfaatkan Rust Token Killer (RTK) dan arsitektur Asymmetric Split-Brain (< 4.000 tokens) untuk meminimalkan beban konteks LLM.
- **Mutu & YAGNI**: Zero-orphan code, tanpa pustaka berlebih, zero-zombie process tree kill, backward-compatibility `.aegis/` dan `.aether/`, serta pengujian berstandar strict stop-gate palu Thor.
---

## 2. Strategi dan Regulasi Branch Git (Khusus Branch 'master')

Repositori ini beroperasi di bawah arsitektur tiga cabang (tri-branch) dengan pemisahan tugas yang tegas:

### 2.1. Branch `master` (Development Hub)
- **Tujuan**: Pusat integrasi dan pengembangan seluruh fitur baru, perbaikan bug, dan dokumentasi arsitektur.
- **Cakupan Dokumen**: Seluruh berkas dokumentasi (`docs/`, `AGENTS.md`, `Roadmap.md`) diperbolehkan dan wajib dikelola di branch ini.
- **Alur Dua Arah**: Bertindak sebagai simpul pusat yang mengalirkan pembaruan ke edisi komunitas (`main`) dan edisi enterprise (`release`).

### 2.2. Branch `main` (Community Publish Edition)
- **Tujuan**: Rilis publik untuk komunitas sumber terbuka dengan filosofi **Bring Your Own Key (BYOK)**.
- **Larangan Ketat**: Dilarang keras memuat folder `docs/`, `AGENTS.md`, maupun `Roadmap.md` di tingkat root.
- **Berkas yang Diizinkan di Root**: Hanya berkas `README.md` versi komunitas (yang memuat panduan setup, konsep BYOK, dan arsitektur publik tanpa dokumen internal perusahaan).
- **Prosedur Kontribusi**: Setiap perubahan dari komunitas wajib melalui proses issue dan Pull Request (PR) dengan review ketat sebelum digabungkan ke remote.
- **Mekanisme Filtrasi**: Sinkronisasi dari `master` ke `main` menggunakan pembatasan `.gitattributes` (`export-ignore`) dan `git sparse-checkout` untuk memastikan berkas dokumentasi internal tidak terbawa.

### 2.3. Branch `release` (Enterprise MVP Bundle)
- **Tujuan**: Jalur rilis enterprise untuk mendistribusikan aplikasi desktop native minimal MVP dalam format `.dmg` (macOS) secara lokal via Tauri v2.
- **Konfigurasi Produksi**: Seluruh modul debug dinonaktifkan (`debug = false`, logger verbose dimatikan).
- **Status Operasional**: Disiapkan sebagai kerangka siaga (standby bundle) untuk pengemasan aplikasi native.

---

## 3. Framework Multi-Agent
 
Antigravity bertindak sebagai **`odin-orchestrator`** (Lead Orchestrator), mengendalikan sub-agents via PreToolUse Hooks (`.agents/hooks.json`, `~/.gemini/hooks.json`).

### Alur Kerja 4 Tahap:
| Step | Agen | Aksi |
|------|------|------|
| 1 | `odin-orchestrator` | Terima input, review murni (tanpa edit kode), tentukan mode operasi |
| 2 | `heimdall-scout`, `mimir-architect`, `forseti-auditor` | AST scan, susun TODO/arsitektur, audit & verifikasi bash |
| 3 | `heimdall-scout`, `brokkr-coder` | Konfirmasi simbol, implementasi kode berdasarkan TODO |
| 4 | `thor-tester` | Stop-gate independen 100% hijau, penegakan 4 aturan QA |

### Roster 6 Agen & Hak Akses:
| Agen | Peran (Step) | Hak Akses | Tools Diizinkan |
|------|-------------|-----------|-----------------|
| `odin-orchestrator` | Lead Orchestrator (1) | `review-only` | `invoke_subagent`, `send_message`, `manage_subagents`, `ask_question` |
| `heimdall-scout` | Fast AST Scout (2 & 3) | `review-only` | `view_file`, `search_web`, `read_url_content`, `codegraph_query`, `codegraph_find_references` |
| `mimir-architect` | Chief Architect & Planner (2) | `plan-only` | `view_file`, `search_web`, `read_url_content`, `define_subagent` |
| `forseti-auditor` | Hakim Etika & Verifikator Bash (2) | `verification-audit` | `view_file`, `run_command`, `read_verification` |
| `brokkr-coder` | Lead Artisan Coder (3) | `code-editor` | `write_to_file`, `replace_file_content`, `view_file`, `run_command` |
| `thor-tester` | Independent QA (4) | `independent-qa` | `run_command`, `view_file` |

### 4 Mode Operasi (Skills / Paket Asgard):
| Mode | Skill ID | Alur |
|------|----------|------|
| Orkestrator (1-2-3-4) | `asgard-orchestrator` | Odin → Heimdall → Mimir → Forseti → Heimdall → Brokkr → Thor → Odin |
| Plan (2) | `asgard-plan` | Heimdall → Mimir → Forseti |
| Eksekutor (3-4) | `asgard-executor` | Heimdall → Brokkr → Thor |
| Independent (4) | `asgard-auditor` | Thor |

### Matriks RACI:
| Fungsi | odin | forseti | mimir | heimdall | brokkr | thor |
|--------|------|---------|-------|----------|--------|------|
| Dekomposisi Kebutuhan (Step 1) | **A** | C | C | I | I | I |
| Audit Independen & Etika (Step 2) | C | **R** | I | I | I | C |
| Desain & Arsitektur (Step 2) | **A** | C | **R** | C | C | I |
| AST Scan & Pindai Simbol (Step 2-3) | I | I | C | **R** | C | I |
| Implementasi Kode (Step 3) | **A** | I | C | I | **R** | C |
| Gerbang Pengujian (Step 4) | **A** | C | I | I | C | **R** |

### Aturan Mutlak Independensi QA (Zero Self-Grading):
1. **Wajib Agen Terpisah**: Tahap 4 (QA & Stop-Gate) WAJIB didelegasikan ke sub-agent independen `thor-tester` via `invoke_subagent`. Agen pengembang (`brokkr-coder`) dan orchestrator (`odin-orchestrator`) dilarang keras mengesahkan kodenya sendiri tanpa verifikasi independen Thor.
2. **Isolasi Izin**: `thor-tester` dibatasi murni pada hak akses `independent-qa` (`run_command`, `view_file`) tanpa izin modifikasi berkas (`write_to_file`, `replace_file_content`).
3. **Larangan Self-Repair**: Jika pengujian gagal, `thor-tester` menolak stop-gate, mencatat log di `docs/QA/logs/`, dan mengembalikan laporan cacat; dilarang memperbaiki kode sendiri.

---

## 4. Protokol RTK (Rust Token Killer)

Agen **WAJIB** menggunakan `rtk` untuk semua operasi CLI:

| Operasi | Perintah RTK |
|---------|-------------|
| Pencarian / Grep | `rtk rg <pola>` |
| Pencarian Berkas | `rtk find <jalur> <bendera>` |
| Pembacaan Berkas | `rtk read <jalur>` |
| Git | `rtk git status/diff/log` |
| Pengujian | `rtk test` atau `node --test` |
| Inspeksi JSON | `rtk json` / `rtk json --keys-only` |
| Ringkasan / Error | `rtk smart` / `rtk err <perintah>` |

> **Fallback**: Jika `rtk` tidak tersedia (`which rtk` gagal), gunakan native command (`rg`, `find`, `git`, `node --test`).

---

## 5. Protokol Pengujian & Backward-Compatibility

- **Runner**: Node.js Native (`node:test`, `node:assert`) dan Python (`pytest`) — tanpa dependensi pihak ketiga yang tidak perlu.
- **Cakupan wajib**:
  1. Integritas profil entitas di `.agents/agents/*/agent.md` (metadata tools dan role valid).
  2. Integritas alur kerja di `.agents/skills/*/SKILL.md` (frontmatter YAML valid).
  3. Validitas `hooks.json` (JSON valid + pemicu `rtk-hook.js` ada jika digunakan).
  4. Dukungan state discovery dua arah: `.aegis/` (primer) dengan fallback transparan ke `.aether/`, serta `data/aegis.db` (primer) dengan fallback ke `data/aether.db`.
  5. Kebersihan proses sistem: zero-zombie process lifecycle pada penutupan sesi.
  6. Pencatatan QA Logs: Setiap verifikasi Stop-Gate penuh atau kegagalan uji wajib dicatat pada `docs/QA/logs/` mengikuti standar [docs/QA/QA_LOGS_RULES.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/QA/QA_LOGS_RULES.md).
- **Strict Stop-Gate**: Tugas TIDAK boleh dinyatakan selesai sebelum semua pengujian lulus (exit code 0). Assertion dilarang dimatikan.
---

## 6. Aturan Komunikasi & Output

| Aturan | Ketentuan |
|--------|-----------|
| **Bahasa internal** | Inggris (reasoning, pencarian kode, logika) |
| **Bahasa output** | Bahasa Indonesia baku — wajib untuk semua respons, komentar, commit, dokumentasi |
| **Bahasa Jawa** | DILARANG KERAS dalam output apa pun |
| **Emoji/Emotikon** | DILARANG dalam respons, komentar kode, commit, maupun dokumentasi |
| **Kuota operan antar-subagent** | Maks. 250 token/operan, format 4-kotak: `[Diagnosis]` `[Keputusan & YAGNI]` `[Kontrak/Diff]` `[Stop-Gate]` — wajib menyebutkan dokumen rujukan `docs/` spesifik pada kotak `[Kontrak/Diff]` saat menyangkut perubahan arsitektur, API, UI, atau kriteria pengujian |
| **Chain-of-thought mentah** | DILARANG dicetak ke output; wajib dipadatkan |

---

## 7. Alur Kerja Verifikasi & Eksekusi

1. **Inspeksi dulu**: Verifikasi simbol via `rtk rg` / `rtk find` sebelum menyunting.
2. **Jangan sembunyikan galat**: Selalu baca seluruh log build/test saat gagal.
3. **Wajib test sebelum selesai**: Jalankan `node --test` atau `npm test`.
4. **Laporan ringkas**: Sertakan tautan markdown ke file yang dimodifikasi; tanpa emoji.

---

## 8. Panduan Rujukan Knowledge Base (`docs/`)

Untuk menjaga kepatuhan batas kuota konteks LLM (< 4.000 token), pembacaan dokumentasi internal pada folder `docs/` diatur dengan prinsip **Just-in-Time (JIT) dan Terarah**:
- **Larangan Pemuatan Massal**: Dilarang keras membaca seluruh direktori `docs/` sekaligus ke dalam konteks. Agen hanya diizinkan membaca berkas spesifik yang relevan langsung dengan modul yang sedang dianalisis atau dikerjakan.
- **Rujukan Operan Wajib**: Saat mengoper tugas antar-agen, `mimir-architect` atau agen pengirim wajib mencantumkan berkas kontrak `docs/` yang menjadi acuan teknis pada kotak `[Kontrak/Diff]`.

### Matriks Pemetaan Topik Tugas & Tanggung Jawab Konsultasi:

| Topik / Domain Tugas | Berkas Rujukan Wajib di `docs/` | Agen Utama yang Berkonsultasi |
| :--- | :--- | :--- |
| **Visi Produk & Batasan Ruang Lingkup** | `docs/PRD.md` | `odin-orchestrator`, `mimir-architect` |
| **Arsitektur Sistem & Sub-sistem Python** | `docs/architecture.md` | `mimir-architect`, `brokkr-coder` |
| **Kontrak API, Auth JWT, Git Facade, PTY** | `docs/api.md` | `mimir-architect`, `brokkr-coder` |
| **Tata Letak UI, Monaco Diff, Komponen Vue** | `docs/ui-design.md` | `brokkr-coder` |
| **Standar Rekayasa, YAGNI, RTK, Tree-Kill** | `docs/ruleset.md` | `forseti-auditor`, `thor-tester`, `brokkr-coder` |
| **Regulasi Git Multi-Remote & Alur Branch** | `docs/Gitmaster.md` | `odin-orchestrator`, `forseti-auditor` |
| **Provider AI (Google Antigravity & LLM)** | `docs/core-features/antigravity_provider.md` | `mimir-architect`, `brokkr-coder` |
| **Fitur IDE Workbench & Eksekusi Background** | `docs/core-features/workbench_features.md` | `mimir-architect`, `brokkr-coder` |
| **Runtime Penalaran (CoT) & Replanning** | `docs/core-features/cot_reasoning_runtime.md` | `odin-orchestrator`, `mimir-architect` |
| **Peta Jalan Masa Depan & RAG Semantik** | `docs/future-roadmap/future_roadmap.md` | `odin-orchestrator`, `mimir-architect` |
| **Arsitektur & Aturan Pencatatan Log QA** | `docs/QA/QA_PLAN.md` & `docs/QA/QA_LOGS_RULES.md` | `thor-tester`, `odin-orchestrator` |
| **Riwayat Implementasi Selesai** | `docs/history/completed-features.md` | `heimdall-scout`, `forseti-auditor` |
| **Indeks Navigasi Lengkap Dokumentasi** | `docs/README.md` | Seluruh Agen |

---

## 9. Pedoman Standarisasi & Modifikasi Front-End (UI/UX)

Setiap agen yang melakukan perubahan pada front-end AegisCode Studio (`web/frontend/`) **WAJIB** mematuhi pedoman baku berikut:

### 9.1. Simetri Desain Dual-Theme (Dark & Light Mode)
- **Definisi Token Ganda**: Setiap penambahan atau modifikasi token warna kontainer/latar belakang (misalnya `--bg-drawer`, `--bg-sidebar`, `--bg-panel`, `--bg-card`, `--bg-deep`) **wajib** didefinisikan secara berpasangan dan simetris di kedua berkas tema:
  - `web/frontend/src/styles/base/variables.css` (tema gelap dasar: Tokyo Night Storm).
  - `web/frontend/src/styles/themes/theme-light.css` (tema terang `[data-theme="light"]`: Tokyo Night Light).
- **Larangan Fallback Statis Kontras Gelap**: Dilarang keras mengandalkan nilai fallback heksadesimal gelap (seperti `#13141f` atau `#101018`) pada deklarasi `var()` tanpa memastikan token tersebut terdefinisi secara adaptif di `[data-theme="light"]`.

### 9.2. Harmonisasi Background Drawer Right (Tab 'Agent' & Tab 'Ask')
- **Satu Kesatuan Latar Belakang**: Tab 'Agent' (`.rd-activity-view`, `.rd-scroll-area`) dan Tab 'Ask' (`.rd-consultant-view`, `.consultant-wrapper.consultant-embedded`, `.consultant-content-pane.consultant-embedded-pane`, `.consultant-messages`) **wajib** memiliki latar belakang yang sama persis menggunakan token `var(--bg-drawer)` pada mode gelap maupun terang.
- **Embedded Isolation**: Komponen obrolan tertanam (`ConsultantChat` dalam mode `embedded: true`) dilarang memiliki background independen yang membuat kontras visual terpisah dari drawer.
- **Left Sidebar**: Panel kiri (`.app-left-sidebar`) wajib konsisten menggunakan token `var(--bg-sidebar)` pada kedua mode.

### 9.3. Komponen Terpadu (Unified Components) & YAGNI
- **Tombol**: Gunakan `AppButton.vue` (`variant="primary" | "ghost" | "danger" | "icon"`, `size="sm" | "md"`). Dilarang menyisipkan tag `<button class="btn-aether">` atau tag `<button>` polosan baru.
- **Panel & Kartu**: Gunakan `AppCard.vue` (`variant="card"` atau `variant="panel"`).
- **Dialog & Popover**: Gunakan sistem kelas in-situ `.unified-popup-*` (`.unified-popup-backdrop`, `.unified-popup-card`, `.unified-popup-head`, `.unified-popup-body`, `.unified-popup-close-btn`). Dilarang memunculkan mekanisme modal overlay penuh di tingkat aplikasi untuk dialog lokal.
- **Bebas Warna Hardcoded**: Dilarang menuliskan kode warna heksadesimal mentah di berkas `.vue`. Selalu gunakan variabel CSS dari `variables.css`.
- **Zero Emoji**: Seluruh ikon wajib berbasis SVG inline terstandarisasi. Emotikon atau emoji unicode dilarang keras di seluruh antarmuka pengguna.
