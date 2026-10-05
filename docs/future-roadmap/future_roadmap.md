# AegisCode Future Execution Roadmap

Dokumen ini mendefinisikan peta jalan pelaksanaan berorientasi dependensi teknis untuk pengembangan lanjutan **AegisCode** (AegisCode Studio & Aegis Agent). Seluruh fase dan fitur yang telah selesai diimplementasikan (Phase 0 dan Phase 1) telah diarsipkan pada [docs/history/completed-features.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/history/completed-features.md).

---

## 1. Diagram Alur Ketergantungan Fase Mendatang

```mermaid
graph TD
    subgraph Selesai ["Fase Sebelumnya (Selesai & Diarsipkan)"]
        F0["Phase 0: Provider Antigravity & Stateless OAuth"]
        F1["Phase 1: Interaksi UI & Git Facade Monaco Diff"]
    end

    subgraph F2 ["Phase 2: Mesin Semantik & Hybrid Split-Brain"]
        F2_1["2.1 Local Embeddings & Vector DB<br/>(fastembed + sqlite-vec di perangkat lokal)"]
        F2_2["2.2 Asymmetric Split-Brain Engine<br/>(Retrieval Lokal + Cloud Reasoning/Editing < 4k)"]
    end

    subgraph F3 ["Phase 3: Keamanan & Human-in-the-Loop Guardrails"]
        F3_1["3.1 Persetujuan Diff Interaktif (HITL)<br/>(Supervised Gating + DiffModal.vue)"]
        F3_2["3.2 Checkpoint Snapshot & 1-Click Rollback<br/>(Zero-Risk Revert filesystem)"]
    end

    subgraph F4 ["Phase 4: Rilis & Distribusi Desktop Native"]
        F4_1["4.1 Pengemasan Desktop Native<br/>(Tauri v2 + Pengawas Sidecar Rust)"]
        F4_2["4.2 Siklus Hidup Proses & Tree-Kill<br/>(SIGTERM Tree-Kill + Zero Zombie Processes)"]
        F4_3["4.3 Installer Standalone Lintas Platform<br/>(.dmg macOS lokal, .exe Windows, .AppImage Linux)"]
    end

    F1 --> F2_1
    F2_1 --> F2_2
    F1 & F2_2 --> F3_1
    F3_1 --> F3_2
    F2_2 & F3_2 --> F4_1
    F4_1 --> F4_2
    F4_2 --> F4_3
```

---

## 2. Matriks Rincian Tugas & Verifikasi Masa Depan

| Fase / Modul | Tugas Implementasi | Berkas & Komponen Terdampak | Kriteria Keberterimaan | Rencana Pengujian (*Unit & Integration*) | Status |
|---|---|---|---|---|:---:|
| **Phase 2.1: Local Embeddings & Vector DB** | • Integrasi `fastembed` lokal (`bge-small-en-v1.5` atau `all-MiniLM-L6-v2`).<br><br>• Konfigurasi basis data vektor embedded `sqlite-vec` pada `.aegis/vectors.db` (dengan fallback otomatis `.aether/vectors.db`).<br><br>• Implementasi chunking berbasis AST untuk fungsi dan kelas Python/JS/TS.<br><br>• Penambahan cache sidik jari SHA-256 untuk melewati file yang tidak berubah saat re-indexing. | `src/agent_ai/repointel/semantic/`<br><br>`src/agent_ai/repointel/indexer.py`<br><br>`src/agent_ai/tools/semantic.py`<br><br>`src/agent_ai/runtime/telemetry/hardware.py` | • Vektor tersimpan lokal di `.aegis/vectors.db` tanpa latensi panggilan API eksternal.<br><br>• Ekstraksi AST mempertahankan signature fungsi, docstrings, dan scope kelas secara utuh.<br><br>• Berkas yang tidak dimodifikasi dilewati secara otomatis. | `tests/test_fastembed_indexer.py`<br><br>`tests/test_sqlite_vec_store.py` | Direncanakan |
| **Phase 2.2: Asymmetric Split-Brain Engine** | • Konfigurasi Local Worker untuk kueri AST, kesamaan vektor, dan pemadatan token.<br><br>• Konfigurasi Cloud Orchestrator untuk menerima paket konteks terkurasi (< 4.000 token) untuk pembuatan diff.<br><br>• Implementasi Reciprocal Rank Fusion (RRF) menggabungkan pencarian leksikal `atlas.json` dengan kemiripan `sqlite-vec`.<br><br>• Penerapan patch diff Cloud ke disk lokal dengan proteksi `FileWriteLock`. | `src/agent_ai/routing/`<br><br>`src/agent_ai/contextbuilder/`<br><br>`src/agent_ai/contextbudget/budget.py`<br><br>`src/agent_ai/tools/project_map.py` | • Paket konteks yang dikirim ke LLM Cloud tidak pernah melebihi batas kuota (< 4.000 token).<br><br>• Seluruh kode mentah repositori tidak pernah dikirim sembarangan melalui jaringan.<br><br>• Akurasi RRF mengungguli pencarian leksikal murni. | `tests/test_split_brain_budget.py`<br><br>`tests/test_rrf_ranker.py` | Direncanakan |
| **Phase 3: Keamanan & Guardrails HITL** | • Integrasi `SupervisedModePolicy` ke dalam permission gateway runtime.<br><br>• Render modal persetujuan interaktif `DiffModal.vue` saat agen mengajukan perintah `write_file`, `delete_file`, atau eksekusi perintah destruktif.<br><br>• Implementasi checkpoint Git otomatis pra-tugas untuk rollback 1-klik. | `src/agent_ai/permission/`<br><br>`src/agent_ai/runtime/policy.py`<br><br>`src/agent_ai/git/checkpoint.py`<br><br>`web/frontend/src/components/DiffModal.vue`<br><br>`web/frontend/src/components/SourceControlDrawer.vue` | • Eksekusi agen berhenti otomatis sebelum pemanggilan tool yang mengubah sistem berkas pada mode terawasi.<br><br>• Pengguna dapat menekan Setuju atau Tolak.<br><br>• Rollback checkpoint mengembalikan kondisi ruang kerja secara bersih. | `tests/test_supervised_policy.py`<br><br>`tests/test_checkpoint_rollback.py`<br><br>`web/frontend/tests/DiffModal.test.ts` | Direncanakan |
| **Phase 4: Aplikasi Desktop Native (Tauri v2)** | • Pembuatan shell aplikasi Tauri v2 (`src-tauri/`) dengan backend Rust.<br><br>• Implementasi pengawas proses latar belakang Python (mengelola daemon Django/Aegis Agent).<br><br>• Penegakan tree-kill proses native OS (`SIGTERM` / `taskkill /T /F`) saat jendela aplikasi ditutup.<br><br>• Integrasi dialog sistem operasi (`tauri-plugin-dialog`) dan notifikasi sistem (`tauri-plugin-notification`).<br><br>• Pemaketan berkas installer standalone (`.dmg` macOS pada branch `release`, `.exe` Windows, `.AppImage` Linux). | `src-tauri/src/main.rs`<br><br>`src-tauri/src/sidecar.rs`<br><br>`src-tauri/Cargo.toml`<br><br>`src-tauri/tauri.conf.json`<br><br>`.github/workflows/release.yml` | • Instalasi desktop sekali klik tanpa memerlukan pengaturan terminal Python atau Node manual.<br><br>• Terminasi total proses anak saat aplikasi ditutup (zero zombies). | `tests/test_sidecar_lifecycle.rs`<br><br>`.github/workflows/verify_packaging.yml` | Direncanakan |

---

## 3. Backlog Pasca-MVP (Fitur Ditangguhkan)

Untuk menjaga momentum rilis terarah dan mencegah over-engineering yang melanggar prinsip YAGNI, inisiatif berikut ditempatkan pada backlog lanjutan:

1. **Autonomous Fine-Tuning LoRA**: Pelatihan model lokal pada commit history repositori tertentu.
2. **Multi-Agent Swarm Orchestration**: Koordinasi paralel antar sub-agent di mesin terdistribusi di luar framework OMJ lokal.
3. **Penyimpanan Vektor Terdistribusi**: Pilihan konektor cloud vector database pihak ketiga (Pinecone, Qdrant Cloud).
