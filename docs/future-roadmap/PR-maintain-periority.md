# Strategi Komprehensif AegisCode

## 1. Ringkasan Eksekutif

`aditlab-code/aegiscode` memiliki ide produk yang kuat, tetapi belum perlu diposisikan sebagai pengganti langsung VS Code atau Cursor. Posisi yang lebih defensible adalah:

> **Local-first autonomous coding workbench untuk repository produksi yang membutuhkan kontrol, privasi, auditability, dan provider AI yang fleksibel.**

Strategi ini memprioritaskan reliabilitas alur agent terlebih dahulu, kemudian kualitas developer experience, lalu diferensiasi platform. Prinsip utamanya:

1. Satu alur eksekusi yang dapat dipercaya.
2. Satu sumber kebenaran untuk task, queue, history, dan reasoning events.
3. Provider-agnostic boundary yang konsisten.
4. Orchestrator kecil dengan tanggung jawab terpisah.
5. Produk dipasarkan berdasarkan kontrol dan privasi, bukan jumlah fitur.

---

## 2. Bukti Kondisi Saat Ini

### 2.1 Bukti skala dan cakupan

Snapshot repository `main` yang dianalisis menunjukkan:

| Indikator | Bukti |
|---|---|
| Ukuran source tree | Sekitar 722 file tracked |
| Frontend | `web/frontend`, Vue 3, Vite, Monaco Editor, xterm |
| Gateway | `web/django_app`, Django, Channels, Daphne |
| Agent core | `src/agent_ai` dengan runtime, provider, tools, context, projects, tasks |
| Provider | `src/agent_ai/providers/antigravity.py`, `ollama.py`, `openai_compatible.py`, `openrouter.py`, `custom.py` |
| Queue dan task | `QueuePanel.vue`, `useTaskLifecycle.js`, `taskStateReducer.js`, task lifecycle dan scheduler |
| Project intelligence | `projects/project_map.py`, `project_map_query.py`, `intelligence.py`, `retrieval.py` |
| Test coverage | Test provider, agent, queue, lifecycle, frontend, SSE, workspace, dan integration scripts |

Bukti langsung:

- [Repository root](https://github.com/aditlab-code/aegiscode)
- [Agent core](https://github.com/aditlab-code/aegiscode/tree/main/src/agent_ai)
- [Provider layer](https://github.com/aditlab-code/aegiscode/tree/main/src/agent_ai/providers)
- [Frontend](https://github.com/aditlab-code/aegiscode/tree/main/web/frontend)
- [Django gateway](https://github.com/aditlab-code/aegiscode/tree/main/web/django_app)

### 2.2 Bukti kekuatan arsitektur

Repository sudah memiliki fondasi untuk produk yang serius:

- provider abstraction melalui `providers/base.py`;
- provider-safe tool name encoding untuk mengatasi perbedaan kontrak API;
- project intelligence dan context builder;
- permission policy dan approval coordinator;
- task lifecycle, cancellation, session store, dan SSE;
- frontend IDE dengan editor, terminal, explorer, consultant, dan queue.

Ini menunjukkan bahwa AegisCode bukan sekadar wrapper API model. Ia sudah mencoba membangun execution platform.

### 2.3 Bukti risiko utama

Risiko paling penting bukan kekurangan fitur, tetapi koordinasi antar-layer:

1. `src/agent_ai/providers/antigravity.py` berukuran besar dan memuat banyak tanggung jawab provider, streaming, tool call, normalisasi, retry, serta integrasi perilaku agent.
2. `src/agent_ai/runtime/runtime.py` berukuran sangat besar dan menjadi pusat eksekusi banyak concern.
3. `web/django_app/api/services.py` juga sangat besar karena menjadi facade untuk task, provider, session, queue, consultant, policy, dan project state.
4. Frontend memiliki banyak state service yang harus tetap sinkron dengan backend: `QueuePanel.vue`, `useTaskLifecycle.js`, `useWorkbenchLiveEvents.js`, `taskStateReducer.js`, dan service task.
5. Repository sendiri telah menyediakan test/check khusus untuk queue, provider retry, agent loop, reasoning status, conversation history, dan async provider contract. Ini adalah sinyal bahwa area tersebut merupakan boundary paling kritis.

Bukti file dan test:

- [Antigravity provider](https://github.com/aditlab-code/aegiscode/blob/main/src/agent_ai/providers/antigravity.py)
- [Runtime](https://github.com/aditlab-code/aegiscode/blob/main/src/agent_ai/runtime/runtime.py)
- [Gateway services](https://github.com/aditlab-code/aegiscode/blob/main/web/django_app/api/services.py)
- [Queue panel](https://github.com/aditlab-code/aegiscode/blob/main/web/frontend/src/components/QueuePanel.vue)
- [Async provider tests](https://github.com/aditlab-code/aegiscode/blob/main/tests/test_async_provider_contract.py)
- [Antigravity tests](https://github.com/aditlab-code/aegiscode/blob/main/tests/test_antigravity_provider.py)
- [Queue checks](https://github.com/aditlab-code/aegiscode/tree/main/scripts)

---

## 3. Positioning Produk

### 3.1 Posisi yang disarankan

Jangan menjual AegisCode sebagai “VS Code yang lebih baik” atau “Cursor versi open source”. Gunakan positioning berikut:

> AegisCode adalah workbench coding agent yang memberi developer kontrol penuh atas model, workspace, permission, context, dan perubahan kode.

### 3.2 Target pengguna awal

Prioritas target:

1. Developer yang ingin menggunakan model lokal atau BYOK.
2. Tim yang tidak dapat mengirim seluruh source code ke platform cloud.
3. Tim engineering yang membutuhkan approval dan audit trail sebelum perubahan diterapkan.
4. Pengguna yang ingin menggabungkan beberapa provider dalam satu workflow.
5. Maintainer repository besar yang membutuhkan project map dan context terstruktur.

### 3.3 Bukan target utama pada fase awal

- pengguna yang hanya mencari autocomplete tercepat;
- pengguna yang menilai produk berdasarkan jumlah extension;
- pengguna yang menginginkan onboarding tanpa konfigurasi;
- perusahaan yang memerlukan enterprise support sebelum reliabilitas dasar stabil.

---

## 4. Prioritas Strategis

### P0 — Stabilitas alur agent dan state

**Tujuan:** satu task dapat berjalan dari prompt sampai hasil akhir tanpa loop, state hilang, atau history tidak sinkron.

Alur kanonik:

```text
Prompt
  -> Task preparation
  -> Context selection
  -> Agent iteration
  -> Provider request
  -> Tool call / tool result
  -> Permission / approval
  -> File change or answer
  -> Session event
  -> Queue/history/UI projection
  -> Terminal result
```

Kriteria selesai:

- setiap event mempunyai `task_id`, `session_id`, `sequence`, dan timestamp;
- event dapat diproses ulang tanpa menggandakan state;
- task tidak dapat masuk dua kali ke scheduler;
- cancellation menghentikan loop pada safe boundary;
- history dan queue mengambil state dari model kanonik yang sama;
- provider timeout, retry, malformed response, dan tool error menghasilkan status terminal yang jelas;
- satu task memiliki satu lifecycle yang dapat diverifikasi dari log sampai UI.

### P1 — Pecah Orchestrator dan runtime menjadi komponen kecil

**Tujuan:** mengurangi coupling dan membuat bug async dapat dilokalisasi.

Struktur target:

```text
agent/
  coordinator.py       # koordinasi state tingkat tinggi
  iteration_loop.py    # satu loop agent
  decision_policy.py   # keputusan lanjut/berhenti/replan
  tool_dispatcher.py   # dispatch tool dan normalisasi hasil
  completion.py        # deteksi terminal state
  cancellation.py      # safe boundary dan cooperative stop

providers/
  contract.py          # kontrak request/response kanonik
  adapters/            # adapter per provider
  streaming.py         # normalisasi event stream
  retry.py             # retry/backoff/circuit behavior
  errors.py            # error taxonomy
```

Aturan desain:

- provider tidak boleh mengatur lifecycle task;
- UI tidak boleh menebak status dari teks event;
- orchestrator tidak boleh membuat format JSON provider-specific;
- scheduler tidak boleh menyimpan state task kedua di luar state store kanonik;
- setiap loop harus mempunyai batas iterasi, batas waktu, dan kondisi terminal eksplisit.

### P2 — Satukan kontrak data queue, history, reasoning, dan SSE

**Tujuan:** menyelesaikan masalah queue sidebar tidak ter-fetch saat agent running dan history tidak ter-fetch saat reasoning.

Model event minimum:

```json
{
  "event_id": "evt-...",
  "task_id": "task-...",
  "session_id": "session-...",
  "sequence": 42,
  "type": "reasoning|tool_call|tool_result|status|error|completed",
  "status": "queued|running|waiting|completed|failed|cancelled",
  "payload": {},
  "created_at": "..."
}
```

Frontend harus membangun projection berikut dari event yang sama:

- Queue view: task yang belum terminal.
- Activity view: urutan event live.
- History view: task/session terminal.
- Reasoning view: event reasoning yang terhubung ke `task_id` dan `session_id`.

Tidak boleh ada parsing terpisah dari format JSON provider untuk masing-masing view.

### P3 — Stabilkan provider boundary

**Tujuan:** semua provider terlihat konsisten bagi agent core.

Kontrak internal yang disarankan:

```text
ProviderRequest
  model
  messages
  tools
  generation_options
  runtime_context

ProviderEvent
  kind: text | reasoning | tool_call | usage | error | done
  provider
  provider_event_id
  payload
  finish_reason

ProviderError
  category
  retryable
  provider
  raw_reference
```

Antigravity, Ollama, OpenAI-compatible, dan provider lain boleh memiliki format wire berbeda, tetapi harus menghasilkan `ProviderEvent` yang sama.

### P4 — Quality gate, observability, dan regression harness

**Tujuan:** setiap perubahan runtime dapat dibuktikan aman sebelum masuk branch utama.

Minimum gate:

- lint Python dan JavaScript;
- unit test provider contract;
- test malformed response;
- test timeout dan retry;
- test cancellation;
- test queue submit saat task berjalan;
- test history setelah reasoning;
- test SSE reconnect dan gap sequence;
- test workspace isolation;
- test end-to-end satu task read-only dan satu task write-with-approval.

### P5 — Product polish dan diferensiasi

Kerjakan setelah P0–P4 stabil:

- onboarding provider yang sederhana;
- preset “local”, “BYOK”, dan “safe production”;
- task timeline yang dapat diaudit;
- diff review yang jelas;
- project map yang mudah dipahami;
- dokumentasi deployment dan security boundary;
- benchmark melawan workflow manual, bukan hanya benchmark model.

---

## 5. Roadmap Pelaksanaan

### Fase 0 — Baseline dan freeze arsitektur

Output:

- diagram lifecycle task;
- daftar state resmi;
- daftar event resmi;
- daftar owner setiap state;
- reproducer untuk setiap bug queue/history/loop;
- baseline test dan latency.

Checklist:

- [ ] Tetapkan branch atau tag baseline.
- [ ] Catat commit yang menjadi baseline.
- [ ] Jalankan seluruh test provider dan queue yang tersedia.
- [ ] Simpan log satu task sukses, gagal, timeout, retry, dan cancel.
- [ ] Tandai state yang hanya ada di frontend atau hanya ada di backend.
- [ ] Hentikan sementara penambahan fitur baru pada P0 boundary.

### Fase 1 — Perbaikan lifecycle dan event contract

Output:

- `TaskState` resmi;
- `ProviderEvent` resmi;
- sequence-aware event store;
- idempotent reducer;
- queue/history/reasoning projection yang sama.

Checklist:

- [ ] Tambahkan `event_id`, `task_id`, `session_id`, dan `sequence`.
- [ ] Buat reducer backend yang idempotent.
- [ ] Buat reducer frontend yang idempotent.
- [ ] Validasi sequence gap dan duplicate event.
- [ ] Pastikan history dibuat dari terminal task/session state.
- [ ] Pastikan queue tidak bergantung pada polling yang tidak konsisten.
- [ ] Tambahkan test refresh UI ketika agent masih running.
- [ ] Tambahkan test reconnect SSE.

### Fase 2 — Refactor orchestrator/runtime

Output:

- coordinator tipis;
- iteration loop terisolasi;
- tool dispatcher terisolasi;
- completion detector terisolasi;
- cancellation boundary terisolasi.

Checklist:

- [ ] Inventaris semua method dan state pada orchestrator/runtime.
- [ ] Kelompokkan berdasarkan concern.
- [ ] Tulis characterization test sebelum memindahkan kode.
- [ ] Pindahkan satu concern per commit kecil.
- [ ] Pertahankan adapter kompatibilitas sementara.
- [ ] Hapus state duplikat setelah semua caller berpindah.
- [ ] Ukur jumlah dependensi masuk/keluar sebelum dan sesudah refactor.
- [ ] Pastikan tidak ada import cycle.

### Fase 3 — Provider normalization

Checklist:

- [ ] Definisikan schema request kanonik.
- [ ] Definisikan schema event kanonik.
- [ ] Definisikan taxonomy error.
- [ ] Uji tool-call name encoding/decoding.
- [ ] Uji streaming text dan reasoning.
- [ ] Uji response kosong dan malformed.
- [ ] Uji retry hanya untuk error yang retryable.
- [ ] Uji timeout tidak meninggalkan task `running`.
- [ ] Uji provider fallback tidak menggandakan tool call.
- [ ] Catat capability provider secara eksplisit.

### Fase 4 — Reliability gate dan release candidate

Checklist:

- [ ] Semua P0 tests lulus dua kali berturut-turut.
- [ ] Tidak ada task stuck pada `running` setelah test suite selesai.
- [ ] Tidak ada duplicate terminal event.
- [ ] Queue/history/reasoning konsisten setelah reload.
- [ ] Cancellation selesai dalam batas waktu yang ditetapkan.
- [ ] Provider failure menghasilkan error yang dapat dipahami user.
- [ ] Tidak ada credential dalam log atau event payload.
- [ ] Workspace di luar project tidak berubah tanpa approval.
- [ ] Dokumentasi instalasi berhasil diikuti dari mesin bersih.

### Fase 5 — Productization

Checklist:

- [ ] Satu landing page menjelaskan positioning secara spesifik.
- [ ] Quick start selesai kurang dari 15 menit untuk target user.
- [ ] Tersedia demo workflow end-to-end.
- [ ] Tersedia dokumentasi privacy dan permission model.
- [ ] Tersedia provider compatibility matrix.
- [ ] Tersedia changelog dan migration notes.
- [ ] Tersedia issue template untuk bug async/provider.
- [ ] Tersedia benchmark workflow yang dapat diulang.

---

## 6. Definition of Done

### Task execution

- [ ] Task queued dapat dijalankan tepat satu kali.
- [ ] Task running memiliki heartbeat atau event progress.
- [ ] Task completed/failed/cancelled selalu terminal.
- [ ] Task timeout tidak meninggalkan resource aktif.
- [ ] Task dapat dibatalkan tanpa merusak task lain.

### Queue dan history

- [ ] Queue menampilkan task saat status berubah ke `running`.
- [ ] History menampilkan session setelah task terminal.
- [ ] Reasoning event muncul tanpa menunggu task selesai.
- [ ] Refresh browser tidak menghilangkan state.
- [ ] Duplicate SSE tidak menggandakan item UI.

### Provider

- [ ] Provider wire JSON tidak bocor ke UI.
- [ ] Tool call memiliki format kanonik.
- [ ] Tool result dapat dipasangkan ke tool call yang benar.
- [ ] Error provider memiliki kategori dan retry policy.
- [ ] Provider berbeda menghasilkan lifecycle event yang sama.

### Security dan workspace

- [ ] Permission policy dievaluasi sebelum tool berisiko.
- [ ] Approval user tercatat sebagai event.
- [ ] Path workspace tervalidasi.
- [ ] Secret tidak masuk log, history, atau reasoning payload.
- [ ] Perubahan kode selalu dapat ditampilkan sebagai diff.

---

## 7. Metrik Keberhasilan

| Area | Metrik awal | Target release candidate |
|---|---:|---:|
| Task completion | baseline dicatat pada Fase 0 | >= 95% untuk smoke workflow |
| Stuck task | baseline dicatat pada Fase 0 | 0 pada regression suite |
| Duplicate events | baseline dicatat pada Fase 0 | 0 pada idempotency tests |
| Queue/history mismatch | baseline dicatat pada Fase 0 | 0 pada refresh/reconnect tests |
| Provider malformed response | belum stabil | semua kasus memiliki terminal error |
| Cancellation | baseline dicatat pada Fase 0 | berhenti pada safe boundary |
| Test reproducibility | baseline dicatat pada Fase 0 | 2 run berturut-turut lulus |
| Onboarding | baseline dicatat pada Fase 5 | <= 15 menit untuk target provider |

Angka target dapat disesuaikan setelah baseline nyata tersedia. Jangan mengklaim reliabilitas berdasarkan jumlah test saja; ukur juga task yang benar-benar selesai dan state yang konsisten.

---

## 8. Urutan Kerja yang Disarankan

```text
Baseline
  -> Reproduce bugs
  -> Freeze state/event contract
  -> Fix queue/history/reasoning projection
  -> Isolate async loop
  -> Split orchestrator/runtime
  -> Normalize providers
  -> Add reliability gates
  -> Improve UX
  -> Publish focused positioning
```

Jangan memulai dari visual redesign, provider baru, atau fitur agent tambahan sebelum P0 dan P1 selesai. Fitur baru akan memperbesar permukaan bug jika lifecycle dan event contract belum stabil.

---

## 9. Keputusan Strategis

### Keputusan yang direkomendasikan

- Pertahankan Vue + Django/Channels selama masih memenuhi kebutuhan; jangan migrasi framework hanya untuk mengejar kematangan VS Code.
- Pertahankan provider abstraction, tetapi perketat kontrak internalnya.
- Jadikan Antigravity satu provider reference untuk pengujian, bukan satu-satunya sumber logika agent.
- Pisahkan “agent decision” dari “provider response parsing”.
- Jadikan local-first, approval, audit trail, dan BYOK sebagai pembeda utama.
- Ukur kualitas AegisCode berdasarkan keandalan perubahan kode, bukan banyaknya fitur.

### Keputusan yang perlu dihindari

- Menambah provider sebelum provider contract stabil.
- Membuat state queue baru di frontend tanpa event backend yang kanonik.
- Menyimpan reasoning sebagai teks bebas yang tidak memiliki sequence.
- Menangani error provider langsung di banyak layer.
- Membesarkan orchestrator untuk setiap fitur baru.
- Mengklaim kompatibilitas penuh dengan Cursor atau VS Code terlalu dini.

---

## 10. Checklist Ringkas Eksekusi

### Minggu pertama

- [ ] Freeze baseline.
- [ ] Reproduksi loop Antigravity.
- [ ] Reproduksi queue saat agent running.
- [ ] Reproduksi history saat reasoning.
- [ ] Petakan state backend/frontend.
- [ ] Tetapkan event schema.

### Minggu kedua

- [ ] Implementasikan sequence-aware events.
- [ ] Satukan reducer queue/history/reasoning.
- [ ] Tambahkan duplicate dan gap detection.
- [ ] Tambahkan test refresh dan SSE reconnect.
- [ ] Perbaiki stuck-running cleanup.

### Minggu ketiga dan keempat

- [ ] Pecah iteration loop.
- [ ] Pisahkan tool dispatcher.
- [ ] Pisahkan completion detector.
- [ ] Pisahkan provider adapter dari agent policy.
- [ ] Jalankan characterization tests setiap tahap.

### Setelah reliability stabil

- [ ] Sederhanakan onboarding.
- [ ] Perkuat diff review.
- [ ] Dokumentasikan provider matrix.
- [ ] Publikasikan demo.
- [ ] Komunikasikan AegisCode sebagai controlled autonomous coding workbench.

---

## 11. Kesimpulan

AegisCode memiliki ide yang layak dan diferensiasi yang nyata. Kesenjangan terhadap VS Code dan Cursor terutama berada pada kematangan eksekusi, bukan pada tidak adanya arah produk.

Strategi yang paling masuk akal adalah mempersempit fokus sementara: **buat satu autonomous coding workflow yang sangat dapat dipercaya, dapat diaudit, dan dapat dikontrol**. Setelah alur tersebut stabil, fitur yang sudah ada—provider fleksibel, project intelligence, permission policy, queue, consultant, dan IDE frontend—dapat menjadi keunggulan platform yang sulit ditiru hanya dengan menambahkan chatbot ke editor.

Dokumen ini harus ditinjau ulang setelah baseline test dan reproducer P0 tersedia, karena target numerik dan urutan refactor sebaiknya dikalibrasi berdasarkan data runtime aktual.
