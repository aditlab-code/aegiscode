# Roadmap MVP AegisCode: The Production-Ready Engine

Dokumen ini memuat peta jalan eksekusi resmi berbasis dependensi untuk pengembangan **AegisCode** (AegisCode Studio & Aegis Agent). Seluruh detail pencapaian fitur yang telah diselesaikan (Phase 0 dan Phase 1) kini telah diarsipkan secara permanen di [docs/history/completed-features.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/completed-features.md), sedangkan rincian teknis mendalam untuk fase mendatang dapat ditinjau pada [docs/future-roadmap/future_roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/future-roadmap/future_roadmap.md).

---

## 1. Status Milestone Terkini

| Fase | Nama Modul | Status | Lokasi Dokumentasi |
| :--- | :--- | :---: | :--- |
| **Phase 0** | Integrasi Provider Google Antigravity & Stateless OAuth | Selesai | [docs/history/completed-features.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/completed-features.md#1-phase-0-google-antigravity-provider--stateless-oauth) |
| **Phase 1** | Fondasi Interaksi UI & Git Facade Monaco Diff | Selesai | [docs/history/completed-features.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/completed-features.md#2-phase-1-interaksi-ui--fondasi-version-control) |
| **Phase 2** | Mesin Semantik & Hybrid Split-Brain Engine | Direncanakan | [docs/future-roadmap/future_roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/future-roadmap/future_roadmap.md#2-matriks-rincian-tugas--verifikasi-masa-depan) |
| **Phase 3** | Keamanan & Human-in-the-Loop Guardrails | Direncanakan | [docs/future-roadmap/future_roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/future-roadmap/future_roadmap.md#2-matriks-rincian-tugas--verifikasi-masa-depan) |
| **Phase 4** | Rilis Desktop Native (Tauri v2 macOS Bundle) | Direncanakan | [docs/future-roadmap/future_roadmap.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/future-roadmap/future_roadmap.md#2-matriks-rincian-tugas--verifikasi-masa-depan) |

---

## 2. Grafik Dependensi Arsitektur

```mermaid
graph TD
    subgraph Selesai ["Fase yang Telah Selesai & Terverifikasi"]
        F0["Phase 0: Provider Google Antigravity<br/>(Native agy CLI Bridge + Stateless OAuth)"]
        F1["Phase 1: Interaksi UI & Git Local<br/>(Mention @file + Monaco Diff)"]
    end

    subgraph Berjalan ["Fase Masa Depan (Future Roadmap)"]
        F2_1["2.1 Local Embeddings & Vector DB<br/>(fastembed + sqlite-vec di perangkat)"]
        F2_2["2.2 Asymmetric Split-Brain Engine<br/>(Retrieval Lokal + Cloud Reasoning < 4k)"]
        F3_1["3.1 Persetujuan Diff Interaktif HITL<br/>(Supervised Gating + DiffModal.vue)"]
        F3_2["3.2 Checkpoint Snapshot Otomatis<br/>(Rollback 1-Klik Tanpa Risiko)"]
        F4_1["4.1 Pengemasan Desktop Native<br/>(Tauri v2 + Pengawas Sidecar Rust)"]
        F4_2["4.2 Siklus Hidup Proses & Tree-Kill<br/>(SIGTERM Tree-Kill + Zero Zombie)"]
        F4_3["4.3 Installer Standalone Lintas Platform<br/>(.dmg macOS lokal, .exe Windows, .AppImage)"]
    end

    F0 --> F1
    F1 --> F2_1
    F2_1 --> F2_2
    F1 & F2_2 --> F3_1
    F3_1 --> F3_2
    F0 & F1 & F2_2 & F3_2 --> F4_1
    F4_1 --> F4_2
    F4_2 --> F4_3
```

---

## 3. Rencana Eksekusi Sprint Mendatang

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ SPRINT 2: The Semantic Engine (Phase 2)                                         │
│ • Integrasikan fastembed + sqlite-vec on-device di .aegis/vectors.db            │
│ • Terapkan chunking berbasis AST dan filtering sidik jari SHA-256               │
│ • Luncurkan Asymmetric Split-Brain (Retrieval lokal RRF + Reasoning Cloud < 4k) │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ SPRINT 3: The Trust & Guardrails (Phase 3)                                      │
│ • Integrasikan SupervisedModePolicy dengan komponen interaktif DiffModal.vue    │
│ • Terapkan pembuatan checkpoint otomatis pra-tugas dan 1-Click Rollback         │
│ • Pastikan tidak ada penulisan filesystem yang tidak disetujui pengguna         │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ SPRINT 4: The Packaging & Release (Phase 4)                                     │
│ • Bungkus aplikasi dalam kerangka Tauri v2 Rust dengan sidecar Python manager   │
│ • Terapkan terminasi tree-kill proses native OS dan dialog native               │
│ • Bangun biner mandiri (.dmg untuk macOS secara lokal pada branch release)       │
└─────────────────────────────────────────────────────────────────────────────────┘
```
