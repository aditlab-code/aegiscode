# Indeks Milestone Pelacakan Isu AegisCode

Dokumen ini adalah hub navigasi dan pelacakan implementasi perbaikan bugs, mitigasi risiko keamanan, serta optimasi arsitektur AegisCode Community berdasarkan hasil audit independen 6 Oktober 2026.

---

## 1. Tata Kelola Branch dan Regulasi Rilis

Seluruh perbaikan dikerjakan di branch pengembangan utama (`master`) dengan pemisahan tugas yang tegas:
- **Branch `master`**: Integrasi perbaikan kode, penulisan tes regresi, dan pemeliharaan dokumen arsitektur/isu di `docs/`.
- **Branch `main`**: Rilis publik edisi komunitas tanpa memuat dokumen internal `docs/`, `AGENTS.md`, atau `Roadmap.md` di root (sinkronisasi menggunakan filtrasi `.gitattributes` dan `export-ignore`).
- **Branch `release`**: Standby bundle desktop native via Tauri v2 (mode rilis non-debug).

---

## 2. Dashboard Status Milestone

| Milestone | Tahap | Fokus Utama | Target Prioritas | Jumlah Item | Status | Dokumen Rujukan |
|---|---|---|---|---|---|---|
| **Milestone 1** | Tahap A | Integritas Penyimpanan & Batas Aman AI | P1 | 6 Isu | Selesai (Terverifikasi 100%) | [milestone-1-tahap-a-core-integrity.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/issues/milestone-1-tahap-a-core-integrity.md) |
| **Milestone 2** | Tahap B | Konsistensi Sesi, Live Events, & Validasi Input | P2 | 9 Isu | Selesai (Terverifikasi 100%) | [milestone-2-tahap-b-session-events.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/issues/milestone-2-tahap-b-session-events.md) |
| **Milestone 3** | Tahap C | Efisiensi Token, Thinking Adapter, & Pengujian Beban | OPT & Riset | 8 Optimasi + 6 Risiko | Selesai (Terverifikasi 100%) | [milestone-3-tahap-c-optimization-scale.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/issues/milestone-3-tahap-c-optimization-scale.md) |

---

## 3. Matriks Temuan Audit dan Verifikasi Lapangan

Berikut adalah ringkasan seluruh temuan yang telah diverifikasi langsung pada basis kode branch `master`:

| ID | Prioritas | Domain | Ringkasan Masalah | Berkas Sumber Terkait |
|---|---|---|---|---|
| **AI-01** | P1 | Backend AI | Metadata internal `event_sink` masuk ke JSON payload HTTP provider | `src/agent_ai/core/orchestrator.py`, `src/agent_ai/providers/openai_compatible.py` |
| **AI-02** | P1 | Backend AI | Perintah interpreter kode meloloskan penulisan berkas pada mode Ask Investigate | `src/agent_ai/consultant/tools.py`, `src/agent_ai/tools/terminal.py` |
| **AI-03** | P1 | Backend AI | Pembatalan saat jeda backoff retry tetap menjalankan pemanggilan provider berikutnya | `src/agent_ai/core/orchestrator.py` |
| **BUG-01** | P1 | Frontend Editor | Syntax checker melempar ReferenceError karena deklarasi `lang` salah scope | `web/frontend/src/components/CodeEditor.vue` |
| **BUG-02** | P1 | Frontend Editor | Operasi simpan lambat menimpa ketikan baru dan mereset status dirty prematur | `web/frontend/src/components/CodeEditor.vue` |
| **BUG-06** | P1 | Frontend Cache | Peningkatan `requestSeq` membatalkan dedup inflight dan membekukan loading berkas | `web/frontend/src/services/fileCacheService.js` |
| **AI-04** | P2 | Fullstack | Frontend mengizinkan prompt gambar tanpa teks, sedangkan backend menolaknya | `web/frontend/src/components/ConsultantChat.vue`, `web/django_app/api/services.py` |
| **AI-05** | P2 | Backend AI | Definisi metode duplikat `_load_sessions_from_store` menimpa callback persistensi | `src/agent_ai/consultant/service.py` |
| **AI-06** | P2 | Frontend Chat | Respons sesi lambat yang keluar urutan menimpa sesi obrolan aktif baru | `web/frontend/src/components/ConsultantChat.vue` |
| **BUG-03** | P2 | Frontend Input | Batas 8 lampiran terlewati akibat evaluasi array sebelum pembacaan asinkron selesai | `web/frontend/src/components/TaskComposer.vue`, `web/frontend/src/components/ConsultantChat.vue` |
| **BUG-04** | P2 | Frontend Linter | Scanner kurung mengeluarkan SyntaxError palsu pada triple quotes multiline | `web/frontend/src/services/diagnosticService.js` |
| **BUG-05** | P2 | Frontend Terminal | Callback penutupan socket proyek lama menghapus instance socket proyek baru | `web/frontend/src/components/TerminalView.vue` |
| **BUG-07** | P2 | Frontend Cache | Cache miss proyek tertentu mengembalikan berkas proyek aktif lain | `web/frontend/src/services/fileCacheService.js` |
| **BUG-08** | P2 | Frontend Events | Penggantian riwayat event dengan panjang sama melewatkan event modifikasi berkas | `web/frontend/src/composables/useWorkbenchLiveEvents.js` |
| **BUG-09** | P2 | Frontend Problems | Deduplikasi masalah hanya berdasarkan teks menyatukan error dari berkas berbeda | `web/frontend/src/composables/useWorkbenchLiveEvents.js` |

---

## 4. Gerbang Rilis (Release Gate Protocol)

Penyelesaian setiap milestone wajib memenuhi kriteria gerbang berikut:
1. **Stop-Gate P1 (Milestone 1)**: Tidak ada pengecualian yang belum ditangani; data disk selalu mencerminkan state editor; provider payload bersih dari objek internal Python; eksekusi interpreter diisolasi.
2. **Stop-Gate P2 (Milestone 2)**: Perpindahan proyek cepat tidak menyebabkan kebocoran state atau tabrakan socket; batas lampiran ditegakkan konsisten di frontend dan backend.
3. **Stop-Gate Efisiensi (Milestone 3)**: Alokasi memori stream stabil; retry budget terikat batas maksimum yang jelas; pengujian regresi mencakup skenario deferred promise.
4. **Verifikasi Lingkungan**: Seluruh pengujian otomatis (`node --test` / `npm test` dan `pytest`) wajib berakhir dengan kode keluar 0 tanpa menonaktifkan assertion.

---

## 5. Berkas Referensi Asli

Dokumen audit lengkap tanpa modifikasi tersimpan pada [aegiscode-community-audit-bugs-optimasi-1.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/issues/aegiscode-community-audit-bugs-optimasi-1.md).
