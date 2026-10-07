
## Rencana pemecahan `src/agent_ai/core/orchestrator.py`

### Kondisi kode yang diperiksa

Nama file aktual adalah `orchestrator.py` (huruf kecil). Pada commit audit, panjangnya **2.831 baris**. Perhitungan baris dan rentang method diperoleh dari AST Python, bukan estimasi ukuran tampilan.

| Kelompok tanggung jawab | Method/rentang saat ini | Masalah pemeliharaan |
|---|---|---|
| Policy dan cancellation | 305–390 | Lifecycle, konfigurasi, dan kontrol eksekusi terhubung ke objek besar yang sama |
| Context, Bible, working state, budget | 395–859 | Perakitan pesan dan lifecycle cache bercampur dengan orkestrasi |
| Retrieval/cache | 865–1085 | Identitas resource, span, dan eviction berada di file loop |
| Completion/evidence/reliability lama | 1174–1640 | Aturan loop lama berdampingan dengan continuous loop yang semantiknya berbeda |
| Logging/provider call/retry | 1648–1985 | Invocation, normalisasi, logging, retry, dan terminal decision bercampur |
| Entry point/loop lama | `run()`, 1990–2274 | Method 285 baris termasuk routing ke continuous loop |
| Continuous loop | `run_continuous_loop()`, 2279–2687 | Method 409 baris mengurus history, compaction, call, event, tool batch, dan finalisasi |
| Hasil tool, vision, coding, learning | 2689–2829 | Adaptasi payload dan post-run work melekat pada loop |

Sumber: [orchestrator.py pada commit audit](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/core/orchestrator.py).

Ukuran besar bukan bukti bug dengan sendirinya. Alasan refactor adalah batas tanggung jawab dan kepemilikan state yang sulit diuji, terutama hubungan provider retry–tool side effect–event lifecycle.

### Struktur tujuan yang diusulkan

Pertahankan `core/orchestrator.py` sebagai facade kompatibilitas. Tambahkan package internal `core/orchestration/`; nama berikut merupakan rencana, belum dibuat.

| Tujuan | Yang dipindah/didelegasikan | Kontrak dan batas |
|---|---|---|
| `orchestrator.py` | Constructor publik, `run`, `run_continuous_loop`, `run_coding_task`, routing, re-export result | Pertahankan import `AgentOrchestrator` dan `OrchestratorResult`; facade tidak memuat parser CLI atau algoritme retry |
| `orchestration/contracts.py` | RunContext, RunState, ProviderAttemptContext, ProviderOutcome, result types | Identitas immutable terpisah dari state mutable per-run; gunakan AgentStatus, CancellationToken, Message dan payload existing |
| `orchestration/context_pipeline.py` | Build/compile messages, budget, Bible lifecycle, environment/working state injection | Gunakan `bible_lifecycle`, `ConversationHistory`, contextbudget dan ProjectBrain existing; keluarkan messages + stats, tanpa memanggil provider/tool |
| `orchestration/retrieval_state.py` | `_retrieval_identity`, span/search key, `_sync_retrieval_cache` | State cache milik satu run; jangan membuat engine retrieval baru atau mengubah scope workspace |
| `orchestration/provider_runner.py` | `_call_provider`, `_generate_with_retry`, retry config, normalisasi dan logging response | Menggunakan provider existing; hasil typed dengan status/attempt; jangan menjadi pemilik status task global |
| `orchestration/event_reporting.py` | Payload provider, commentary, attempt/response log, redaksi dan korelasi | Gunakan sink/sanitizer existing, bukan bus kedua; final usage memiliki satu pemilik; event enum/frontend harus selaras |
| `orchestration/tool_results.py` | `_record_tool_result`, vision message, payload-to-observation, konstruksi payload callback | Delegasikan eksekusi ke ToolExecutor/tool coordinator existing; hasil kembali berdasarkan tool_call_id, bukan urutan selesai |
| `orchestration/continuous_runner.py` | Loop continuous: urutan context → provider → tool batch → history → final | Pemilik RunState untuk continuous; delegasi ke modul di atas; tidak mengeksekusi tool melalui jalur kedua |
| `orchestration/legacy_runner.py` | Loop lama, heuristic completion, evidence/reliability, recovery message | Pertahankan jalur `use_continuous_loop=False`; jangan bocorkan heuristic completion lama ke continuous |

Learning tetap menggunakan ProjectBrain; trigger satu kali pada finalisasi melalui facade/runner yang disepakati. Jangan membuat subsystem learning baru. Bila context_pipeline masih terlalu besar setelah ekstraksi, pecah berdasarkan hasil profiling dependensi, bukan sekadar mengejar batas jumlah baris.

### Aturan state dan dependensi

- Alur dependensi: facade → runner → context/provider/tool/reporting. Modul bawah tidak mengimpor facade atau runner sehingga tidak terbentuk circular import.
- Konfigurasi provider/executor boleh dibagi sebagai dependency; history, round counter, reasoning terakhir, retrieval_seen, dan Bible sent-state harus punya pemilik per-run yang eksplisit. Audit reuse orchestrator sebelum memutuskan migrasi setiap field.
- Provider transport dan parser stream-json tetap di adapter Antigravity; modul generic tidak melakukan branching berdasarkan string nama provider. Gunakan capability untuk membedakan provider yang hanya menghasilkan tool_calls dari CLI yang mengeksekusi tool secara internal.
- Satu cancellation token dipertahankan lintas runtime, provider, dan executor. Perubahan retry sleep menjadi cancel-aware adalah patch perilaku terpisah, bukan disembunyikan dalam ekstraksi file.
- Pisahkan kebijakan safety abort dari semantic completion. Continuous selesai karena respons final tanpa tool_calls; batas keselamatan bukan sukses. Jangan menghapus/mengubah max_steps pada PR pemindahan kode.
- Frontend tetap perlu diperbaiki: memecah Python tidak otomatis menyelesaikan ASYNC-02/03/04/11/12.

### Tahapan implementasi dan gate setiap PR

| Tahap | Perubahan | Bukti wajib sebelum lanjut |
|---|---|---|
| PR-0: baseline | Inventaris pemanggil dan import publik/private, fixture provider normal/error/retry/cancel, event trace dan urutan side effect | Jejak perilaku baseline terdokumentasi; tests yang ada dijalankan; tidak ada request model berbayar untuk characterization |
| PR-1: kontrak + reporting | Perkenalkan data per-run dan ekstrak helper payload/redaksi/logging dengan facade tetap kompatibel | Import lama tetap berjalan; urutan event dan satuan usage tidak berubah; fixture secret tetap tersanitasi |
| PR-2: context + retrieval | Pindahkan context pipeline/cache state; delegasikan ke modul existing | Snapshot messages, budget, cache invalidation setelah mutasi, working state dan batas workspace sama dengan baseline |
| PR-3: provider runner | Ekstrak invocation/normalisasi/retry tanpa mengubah kebijakan | Attempt count, retryable/permanent error, cancel sebelum/sesudah call, partial response logging, provider_error sama dengan baseline |
| PR-4: tool result + continuous | Pisahkan adapter hasil dan continuous runner | Parallel tools selesai tak berurutan tetapi history tetap tepat per ID; cancel tidak memulai tool baru; final/truncation/safety abort tetap benar |
| PR-5: legacy + facade | Pindahkan completion/evidence loop lama, tipiskan facade, rapikan import | Continuous dan legacy lulus terpisah; public constructor/method/result tetap kompatibel; learning tidak ganda |
| PR-6: bugfix integrasi | Perbaiki event Antigravity, ownership usage, race UI dan replay yang sudah dibuktikan | Regression ASYNC serta USR-01 lulus; trace yang berbeda dari baseline dijelaskan sebagai perbaikan yang disengaja |

Bug P1 tidak perlu menunggu semua tahap refactor: perbaikan Stop/identity dan race yang sudah terbukti dapat dibuat sebagai PR kecil lebih dahulu. Setiap ekstraksi harus bisa direvert sendiri; jangan menggabungkan perubahan strategi agent, retry policy, prompt, dan perpindahan modul dalam satu diff besar.

### Matriks pengujian utama

1. **Kompatibilitas:** import facade/result, constructor keyword, `run`, `run_continuous_loop`, `run_coding_task`, jalur legacy eksplisit.
2. **Context:** pesan identik sebelum/sesudah ekstraksi; Bible tidak dikirim berulang tanpa perubahan; cache invalidated setelah write; task kedua tidak mewarisi state task pertama.
3. **Provider:** sukses attempt 1; retry lalu sukses; permanent error; attempts exhausted; cancellation di batas call; log partial response tersanitasi.
4. **Antigravity CLI:** fixture stream-json dengan tool internal, warning, delta, result usage dan error setelah side effect. Tentukan apakah retry aman/resumable sebelum mengubah kebijakan; jangan menjalankan ulang command mutatif hanya untuk validasi refactor.
5. **Tool batch:** sukses/gagal campuran, completion tak berurutan, tool_call_id tetap cocok, cancel menahan tool berikutnya, result/observation tidak ganda.
6. **Lifecycle:** satu terminal result per run; terminal tidak menjadi running akibat respons terlambat; safety abort tetap failed; learning maksimal satu kali sesuai kontrak caller.
7. **UI integrasi:** Stop task B saat A dipantau, respons create terminal, switch project/sesi saat request pending, SSE replay/reconnect dan >500 event, satu usage final per request.

Mulai dari suite existing yang relevan (`check_orchestrator`, `check_continuous_loop`, `check_provider_retry`, cancellation/parallel-tools, provider-contract, Antigravity activity/guardrails) setelah memastikan nama dan entrypoint pada checkout implementasi. Jangan mengklaim gate backend lulus berdasarkan 11 tes frontend dari audit sebelumnya.

### Definition of done dan rollback

Refactor selesai bila facade kompatibel; dependensi satu arah; state task terisolasi; trace baseline tetap sama kecuali bugfix yang disetujui dalam scope; tidak ada duplikasi eksekusi, usage, atau finalisasi; dan skenario USR-01 memiliki hasil diagnosis yang dapat diulang. Target facade sekitar 200–350 baris merupakan pedoman, bukan acceptance criterion utama.

Rollback dilakukan per PR ekstraksi melalui facade yang tetap memiliki API sama. Tidak ada migrasi data wajib pada rencana ini; bila implementasi memerlukan perubahan schema event/log, sediakan kompatibilitas pembaca sebelum memindahkan penulis. Hentikan tahap berikutnya jika event order, cancellation, atau hasil tool berubah tanpa penjelasan.

**Status pekerjaan dokumen ini:** laporan pengguna dan rencana sudah ditambahkan. Refactor kode, patch bug, pengujian CLI langsung, dan publikasi ke repository belum dilakukan.
