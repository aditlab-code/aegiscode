# Indeks Dokumentasi Pengembang AegisCode

Selamat datang di pusat dokumentasi teknis **AegisCode** (AegisCode Studio & Aegis Agent). Direktori ini mengorganisasi seluruh spesifikasi arsitektur, panduan antarmuka API, tata letak UI, aturan rekayasa, fitur inti, peta jalan masa depan, serta arsip historis.

---

## 1. Dokumen Arsitektur Inti (Root `docs/`)

Dokumen di bawah ini merupakan fondasi spesifikasi teknis repositori:

| Dokumen | Deskripsi |
| :--- | :--- |
| **[docs/PRD.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/PRD.md)** | Product Requirement Document: visi produk, target persona pengguna, pilar arsitektur, dan spesifikasi fungsional sistem. |
| **[docs/architecture.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/architecture.md)** | Ikhtisar arsitektur sistem, Asymmetric Split-Brain Model, pemisahan modul Python `src/agent_ai`, dan siklus hidup eksekusi. |
| **[docs/api.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/api.md)** | Spesifikasi lengkap Django API Gateway: Stateless Signed JWT OAuth, Git Local Facade, Task Runtime, Queue Control, dan Terminal PTY Bridge. |
| **[docs/ui-design.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/ui-design.md)** | Spesifikasi tata letak workbench AegisCode Studio: Monaco Editor, Monaco Diff Editor, Changes Panel, Drawer Persisten, dan Sistem Desain. |
| **[docs/ruleset.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/ruleset.md)** | Standar rekayasa perangkat lunak: prinsip YAGNI, protokol RTK, pengujian dual-stack, zero-zombie process lifecycle, dan aturan branch Git. |
| **[docs/Gitmaster.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/Gitmaster.md)** | Panduan arsitektur Git multi-remote, isolasi kerahasiaan branch privat (master & release), dan alur rilis komunitas (main). |

---

## 2. Fitur Inti (`docs/core-features/`)

Dokumentasi detail mengenai kapabilitas dan modul fungsional yang aktif:

| Dokumen | Deskripsi |
| :--- | :--- |
| **[docs/core-features/antigravity_provider.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/core-features/antigravity_provider.md)** | Panduan integrasi provider Google Antigravity, model frontier reasoning (Gemini, Claude, OSS), dan token bridge CLI `agy`. |
| **[docs/core-features/workbench_features.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/core-features/workbench_features.md)** | Fitur IDE workbench: retensi tampilan latar belakang (`v-show`), indikator AI navbar, completion toast, dan autocomplete sebutan `@file`. |
| **[docs/core-features/cot_reasoning_runtime.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/core-features/cot_reasoning_runtime.md)** | Mekanisme runtime Chain of Thought (CoT), dynamic replanning, dan pemadatan observasi riwayat task. |
| **[docs/core-features/tool_and_provider_extensibility.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/core-features/tool_and_provider_extensibility.md)** | Panduan memperluas tool kustom, konfigurasi server Model Context Protocol (MCP), dan pendaftaran provider baru. |
| **[docs/core-features/omc_agent_framework.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/core-features/omc_agent_framework.md)** | Roster framework 13-agen OMC, topologi star, pipeline 4-role (Lead, Architect, Coder, Tester), dan protokol RTK. |

---

## 3. Sistem Jaminan Kualitas & QA Logs (`docs/QA/`)

Dokumentasi strategi pengujian mutu, penanganan uji rapuh (*flaky*), dan catatan log stop-gate:

| Dokumen | Deskripsi |
| :--- | :--- |
| **[docs/QA/QA_PLAN.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/QA/QA_PLAN.md)** | Rencana strategis arsitektur QA: penanganan uji rapuh (flaky), roadmap pengujian jangka menengah dan panjang, serta alur stop-gate independen. |
| **[docs/QA/QA_LOGS_RULES.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/QA/QA_LOGS_RULES.md)** | Pedoman dan protokol baku pencatatan riwayat eksekusi pengujian (QA Logs) untuk auditibilitas dan pelacakan regresi. |
| **[docs/QA/logs/](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/QA/logs/)** | Direktori penyimpanan berkas log eksekusi uji terstandardisasi (PASS / FAIL) per sesi pengujian. |

---

## 4. Peta Jalan Aktif (`Roadmap.md`)

Roadmap aktif tunggal di root repositori (prioritas, fase 0-5, rincian teknis stabilisasi, orchestrator, HITL dan desktop native, metrik, backlog):

| Dokumen | Deskripsi |
| :--- | :--- |
| **[Roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/Roadmap.md)** | Sumber tunggal roadmap aktif. Fase lama diarsipkan di `docs/history/legacy-roadmap.md`. |

---

## 5. Arsip Historis (`docs/history/`)

Catatan fase yang telah selesai, dokumen migrasi, dan riwayat evolusi basis kode:

| Dokumen | Deskripsi |
| :--- | :--- |
| **[docs/history/legacy-roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/legacy-roadmap.md)** | Satu-satunya arsip fase lama: Phase 0 (Antigravity & OAuth), Phase 1 (UI & Git Monaco Diff), Phase 2.1-2.2 (Local RAG & RRF). |
| **[docs/history/community-fork.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/community-fork.md)** | Catatan strategi pemisahan edisi komunitas sumber terbuka dan edisi komersial/enterprise. |
| **[docs/history/developer_guide_legacy.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/developer_guide_legacy.md)** | Panduan orientasi teknis lawas dan konfigurasi lingkungan awal. |

---

## 6. Rujukan Tingkat Root

- **[AGENTS.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/AGENTS.md)**: Panduan orkestrasi multi-agent, protokol RTK, dan regulasi tri-branch (`master`, `main`, `release`).
- **[README.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/README.md)**: Gambaran umum repositori dan panduan awal pengguna.
- **[Roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/Roadmap.md)**: Ringkasan eksekutif progres fase proyek.
