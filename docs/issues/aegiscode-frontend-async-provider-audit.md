# Audit bug frontend async, agent, dan provider — Aegiscode

Tanggal: 7 Oktober 2026 (WIB)\
Repository: [aditlab-code/aegiscode](https://github.com/aditlab-code/aegiscode)\
Branch: `main`\
Commit diperiksa: [`2ce8887901ce05672bd0d6e59ef3673215ab4767`](https://github.com/aditlab-code/aegiscode/commit/2ce8887901ce05672bd0d6e59ef3673215ab4767) — HEAD dikonfirmasi kembali saat audit ini.

## Ringkasan

Ditemukan **12 temuan**: **5 P1** dan **7 P2**. Sepuluh merupakan pendalaman baru pada alur agent/provider; dua mengonfirmasi kembali masalah History dan buffer event dari audit sebelumnya.

Masalah utamanya adalah identitas task/session dan urutan respons async tidak dipertahankan konsisten. Antigravity menambah masalah kontrak event: delta reasoning dan peringatan tidak memiliki jalur render yang utuh, dan usage berpotensi dihitung dua kali.

P1 berarti berisiko menjalankan kontrol pada task yang salah, mencampur workspace/sesi, atau membuat status eksekusi salah secara material. P2 berarti fungsi, observabilitas, atau performa terganggu dan perlu diperbaiki setelah P1. Tidak ada klaim P0.

| ID       | Prioritas | Temuan                                                               | Validasi                                                    |
| -------- | --------- | -------------------------------------------------------------------- | ----------------------------------------------------------- |
| ASYNC-01 | P2        | Reasoning/warning Antigravity kehilangan tipe event dan tidak tampil | Kontrak backend + listener + renderer diperiksa             |
| ASYNC-02 | P1        | Stop dari Queue mengabaikan ID task pilihan                          | Fungsi asli direproduksi                                    |
| ASYNC-03 | P1        | Respons Cancel terlambat menimpa task baru; hasil backend diabaikan  | Dua skenario fungsi asli direproduksi                       |
| ASYNC-04 | P1        | Task selesai sebelum respons create diterima ditampilkan running     | Fungsi asli direproduksi; urutan dispatch backend diperiksa |
| ASYNC-05 | P2        | Perpindahan otomatis Queue membawa state task lama                   | Fungsi asli direproduksi                                    |
| ASYNC-06 | P1        | Respons submit workspace lama diadopsi workspace baru                | Fungsi asli direproduksi                                    |
| ASYNC-07 | P1        | Respons Ask sesi lama mencemari sesi yang baru dipilih               | Fungsi asli direproduksi; navigasi sesi diperiksa           |
| ASYNC-08 | P2        | Usage Antigravity dapat dihitung ganda                               | Jalur dua emisi + parser usage diverifikasi                 |
| ASYNC-09 | P2        | Composer agent aktif menolak enqueue saat agent running              | Fungsi asli direproduksi                                    |
| ASYNC-10 | P2        | Detail kegagalan provider tidak ditampilkan di timeline              | Penelusuran statis dispatcher UI                            |
| ASYNC-11 | P2        | Respons History datang terbalik dan menukar isi task                 | Reproduksi ulang temuan sebelumnya                          |
| ASYNC-12 | P2        | Buffer penuh memproses ulang ratusan event lama                      | Reproduksi ulang temuan sebelumnya                          |

## Metode dan batas validasi

- Memeriksa frontend Vue: `App.vue`, `api.js`, `WorkbenchView.vue`, `AppRightDrawer.vue`, `AgentActivity.vue`, `ConsultantChat.vue`, `QueuePanel.vue`, service/reducer terkait.
- Menelusuri kontrak backend yang diperlukan: gateway `services.py`, `views.py`, SSE `streaming.py`, runtime, enum event, orchestrator, parser usage, dan provider `antigravity.py`.
- Harness Node mengambil fungsi asli dari source Vue dan menjalankannya dengan ref serta API/response terkontrol. Harness tidak mengganti logika fungsi yang diuji. Ini reproduksi level fungsi, bukan E2E Vue/Monaco/browser.
- Sembilan skenario async dijalankan; dua skenario lama yang relevan diuji kembali. Enum event dan normalisasi usage diperiksa dengan potongan Python asli.
- Empat file tes existing dijalankan: `taskStateReducer.test.mjs`, `taskView.test.mjs`, `sseGapAndTelemetry.test.mjs`, `tokenFormat.test.mjs`. Hasil Node: **11 tests passed, 0 failed**. Dua file memakai pemeriksaan top-level, sehingga angka runner bukan jumlah seluruh assertion.
- Tidak menjalankan CLI Antigravity, OAuth, request model berbayar, atau aplikasi browser penuh. Tidak mengubah kode repository, membuat commit, maupun menerbitkan GitHub Issue.
- Tidak menyimpulkan bahwa provider tertentu “kurang cerdas”, root brain salah, atau model tertentu penyebab loop. Temuan di bawah dibatasi bukti kode yang diperiksa.

## ASYNC-01 — Reasoning dan warning Antigravity hilang di kontrak event

**P2 · Khusus jalur event Antigravity yang diperiksa.**

Provider mengirim `agent_reasoning_delta` dengan payload `delta`, serta `warning` untuk redundansi tool/read. Kedua nama tidak ada dalam `EventType`. Runtime menangkap `ValueError` lalu mengganti tipe menjadi `PHASE_CHANGED`.

Akibatnya pada jalur runtime saat ini, event tetap dapat sampai ke frontend sebagai `phase_changed`, tetapi payload tidak memiliki `phase`. `App.vue` tidak memperoleh fase yang valid, sementara dispatcher `AgentActivity.vue` tidak merender event itu sebagai reasoning. Dispatcher hanya mengenali `agent_commentary` dengan `text` untuk baris reasoning. Jika backend kelak mempertahankan nama asli, frontend juga belum mendaftarkan listener kedua nama tersebut.

**Pemicu:** Antigravity streaming mengirim thought delta atau warning redundansi saat task berjalan.

**Aktual:** pengguna tidak melihat delta/warning tersebut pada timeline; indikator “Agent reasoning” tetap bisa tampil karena berasal dari status running. Ini bukan bukti provider tidak menghasilkan reasoning.

**Bukti:** [emisi provider, 939–1046](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/providers/antigravity.py#L939-L1046), [fallback runtime, 1096–1113](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/runtime/runtime.py#L1096-L1113), [enum event](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/session/events.py#L18-L62), [listener SSE](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/api.js#L628-L700), [dispatcher UI](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/AgentActivity.vue#L410-L523).

**Perbaikan:** definisikan kontrak event end-to-end; pertahankan tipe warning dan rangkum progres provider dalam payload UI yang disengaja. Hindari fallback semua event tak dikenal menjadi perubahan fase. Tambahkan contract test dari event provider sampai output renderer.

## ASYNC-02 — Stop Queue membatalkan task yang salah

**P1 · Semua provider; berbahaya saat parallel atau melihat History.**

`QueuePanel` mengirim `stop-task` dengan `t.task_id`. Sidebar dan Workbench meneruskannya, tetapi `App.vue` menghubungkan event ke `requestStop()` yang tidak menerima parameter. Target dihitung ulang dari `runningTaskId || task.id`.

**Reproduksi:** task A sedang dipantau; task B juga running. Pilih Stop pada B. Dalam harness, `requestStop('B')` memanggil `cancelTask('A')`.

**Dampak:** task A berhenti tanpa dimaksudkan, sementara B yang ingin dihentikan terus berjalan. Jika sedang melihat task historis dan running ID kosong, target juga bisa menjadi task historis.

**Bukti:** [QueuePanel:252](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/QueuePanel.vue#L252), [wiring App:705](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L705), [requestStop:370–392](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L370-L392).

**Perbaikan:** buat handler Queue yang menerima ID eksplisit; handler Stop task aktif memanggil fungsi tersebut dengan ID aktif. Jangan mengandalkan argumen default yang dapat menerima DOM event tombol. Simpan status pembatalan per task.

## ASYNC-03 — Respons Cancel merusak status task lain

**P1 · Semua provider.**

`requestStop()` mengubah state global setelah `await cancelTask(...)` tanpa memastikan task yang dipantau masih target yang sama. Respons API juga dibuang dan status selalu diset `cancelled`.

**Dua reproduksi:**

1. Cancel A masih menunggu; pengguna berpindah ke B yang running. Respons A tiba: B ditandai cancelled dan `runningTaskId` B dikosongkan.
2. Backend mengembalikan `{status:'completed'}` karena A selesai lebih dahulu. UI tetap menulis cancelled. Backend memang mempertahankan terminal status pada kondisi ini.

**Dampak:** status, tombol kontrol, dan indikator reasoning tidak sesuai proses sebenarnya. Jalur catch dapat pula memulihkan status lama ke task yang berbeda.

**Bukti:** [App:370–392](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L370-L392), [kontrak cancel backend:2883–2959](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/django_app/api/services.py#L2883-L2959).

**Perbaikan:** capture task ID + generation saat request dimulai, terapkan hasil ke state task tersebut, gunakan status respons, dan bedakan cancel-requested dari eksekusi yang benar-benar terminal.

## ASYNC-04 — Respons create dapat menghidupkan kembali task yang selesai

**P1 · Semua provider; mudah dipicu task cepat gagal atau cepat selesai.**

Backend memulai thread/scheduler sebelum `create_task()` mengembalikan record. Karena itu event terminal atau record terminal dapat mendahului pemrosesan respons HTTP frontend.

Frontend hanya membedakan `queue_state === 'pending'` dan cabang lainnya. Cabang lain menetapkan running, tanpa memeriksa `res.status`. Event awal sebelum ID diketahui juga tidak cocok dengan task yang dipantau.

**Reproduksi:** `createTask()` mengembalikan `{task_id:'T', queue_state:'done', status:'completed'}`. UI berakhir dengan `task.status === 'running'`. Skenario failed/cancelled memiliki masalah pemetaan serupa.

**Dampak:** spinner/timer berjalan meskipun backend sudah selesai; event terminal yang telah lewat tidak harus datang lagi. Antigravity yang langsung gagal karena CLI/konfigurasi dapat terlihat masih berpikir.

**Bukti:** [dispatch sebelum return:1772–1806](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/django_app/api/services.py#L1772-L1806), [adopsi frontend:295–362](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L295-L362).

**Perbaikan:** hormati status terminal respons; setelah mendapat task ID, rekonsiliasi snapshot dan event berdasarkan sequence. Jangan menurunkan terminal kembali ke running karena respons lebih lama.

## ASYNC-05 — Queue A ke B membawa prompt, event, token, dan timer A

**P2 · Semua provider.**

Saat `task_started` mengadopsi B dari `deferredTaskIds`, handler hanya mengganti beberapa field. Prompt, event, changes, token, telemetry, `taskEndedAt`, serta milestone A tidak direset. `taskStartedAt` hanya diisi jika sebelumnya kosong.

Selain itu, `isForMonitored` dihitung sebelum `task.id` berubah; event start B sendiri tidak dimasukkan ke activity B pada handoff tersebut.

**Reproduksi:** A completed, B deferred, lalu kirim start B. Hasil: ID B dengan prompt A, token A=77, event A, end-time A=200; event start B tidak tercatat di buffer UI.

**Dampak:** panel B terlihat memiliki riwayat/durasi/tokens task lain. Ini dapat menyerupai kegagalan fetch Queue/History walaupun event backend masuk.

**Bukti:** [App:148–192](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L148-L192), [append event:257–270](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L257-L270).

**Perbaikan:** gunakan satu fungsi aktivasi task yang menginisialisasi seluruh view dari state per-task; hitung ulang relevansi setelah adopsi dan masukkan start event tepat satu kali.

## ASYNC-06 — Request project lama menimpa project baru

**P1 · Semua provider.**

`submitTask()` mengirim project aktif saat request dimulai, tetapi tidak menyimpan generation/project untuk memvalidasi respons. `handleOpenProject()` mereset task state, tetapi reset tidak membatalkan kelanjutan promise submit lama.

**Reproduksi:** submit T di P1, tahan respons HTTP, buka P2, lalu selesaikan respons P1. UI P2 mengadopsi T-P1 sebagai task running.

**Dampak:** pengguna melihat task provider milik workspace lain dan dapat mengirim kontrol dengan konteks yang keliru. Reproduksi ini membuktikan kontaminasi UI, bukan bahwa backend memindahkan eksekusi ke P2.

**Bukti:** [submit App:295–362](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L295-L362), [switch/reset App:437–512](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L437-L512).

**Perbaikan:** capture project ID + workspace generation. Respons tetap boleh memperbarui cache task P1, tetapi tidak boleh mengubah view P2. Pembatalan fetch tidak otomatis berarti pembatalan task yang sudah dibuat di backend.

## ASYNC-07 — Jawaban Ask A masuk ke chat B

**P1 · Semua provider, makin mudah terlihat pada respons lambat.**

`switchSession()` tidak memblokir perpindahan ketika `sending`; item session tetap dapat diklik. `send()` setelah await selalu menulis `sessionId` dari respons dan menambahkan jawaban ke `messages` yang saat itu aktif, tanpa memeriksa request/session asal.

**Reproduksi:** kirim pertanyaan di A, pilih B sebelum jawaban datang, lalu selesaikan consult A. Pesan B mendapat Answer A dan `sessionId` kembali menjadi A.

**Dampak:** konteks percakapan tercampur. Bug ini dibuktikan pada state tampilan; tidak menyatakan backend menyimpan jawaban ke sesi B.

**Bukti:** [switchSession:132–164](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/ConsultantChat.vue#L132-L164), [send:553–622](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/ConsultantChat.vue#L553-L622), [klik sesi:1300–1304](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/ConsultantChat.vue#L1300-L1304).

**Perbaikan:** pisahkan messages/request state per session, sertakan project/session/request ID, dan terapkan jawaban ke sesi asal. Jika mempertahankan state tunggal, cegah perpindahan sampai request selesai dengan perilaku yang jelas.

## ASYNC-08 — Token Antigravity dapat dihitung dua kali

**P2 · Kondisional pada result CLI yang menyertakan `usage.total_tokens`.**

Provider Antigravity mengemit `provider_response` berisi usage ketika menerima result CLI. Hasil yang sama disimpan sebagai `raw_data` dan dikembalikan. Orchestrator kemudian mengemit `provider_response` lagi menggunakan `_provider_response_payload(response)`, yang mengekstrak usage dari raw tersebut. Frontend menjumlahkan seluruh provider_response tanpa identitas request untuk deduplikasi.

**Pemeriksaan kontrak:** raw `{usage:{input_tokens:60, output_tokens:40, total_tokens:100}}` menghasilkan usage orchestrator `{total:100}`. Event langsung provider membawa total_tokens=100. Kedua payload dikenali `usageTokens()`, sehingga jika keduanya diterima pada task yang dipantau, UI menjumlahkan 200 untuk penggunaan 100.

**Dampak:** telemetry token tidak akurat. Ini bukan bukti tagihan provider digandakan. Tidak berlaku sebagai klaim universal untuk semua format usage/transport.

**Bukti:** [Antigravity:1068–1077](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/providers/antigravity.py#L1068-L1077), [raw result:1112–1122](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/providers/antigravity.py#L1112-L1122), [orchestrator payload:1102–1121](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/core/orchestrator.py#L1102-L1121), [emisi setelah call:2076–2080](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/core/orchestrator.py#L2076-L2080), [akumulasi frontend:159–163](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L159-L163).

**Perbaikan:** tetapkan satu pemilik emisi final usage. Pisahkan progress dari final response; gunakan request ID + attempt dan semantik delta/cumulative eksplisit.

## ASYNC-09 — Composer agent utama tidak bisa enqueue saat running

**P2 · Semua provider.**

`AppRightDrawer.handleSubmit()` langsung return jika `props.isRunning`. Tombol Send juga disabled oleh isRunning. Ini berbeda dari kemampuan backend scheduler dan kontrak `TaskComposer.vue` yang membedakan enqueue dari slot eksekusi.

**Reproduksi:** isRunning=true dan prompt kedua valid; handleSubmit tidak mengemit submit-task. Yang diperiksa adalah composer yang benar-benar dirender oleh Workbench saat ini.

**Dampak:** pengguna tidak dapat mengantrekan prompt berikutnya lewat composer agent utama ketika Antigravity atau provider lain sedang berjalan. Dukungan queue pada backend tidak dapat diakses dari jalur ini.

**Bukti:** [AppRightDrawer:274–281](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/layout/AppRightDrawer.vue#L274-L281), [Send disabled:608](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/layout/AppRightDrawer.vue#L608), [kontrak composer lain:158–179](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/TaskComposer.vue#L158-L179).

**Perbaikan:** bedakan isSubmitting dari isRunning. Cegah submit ganda selama POST berjalan, tetapi izinkan enqueue berikutnya. Pertahankan draft sampai ada acknowledgement sukses atau pulihkan saat gagal.

## ASYNC-10 — Detail error provider hilang di timeline

**P2 · Semua provider. Validasi statis.**

Orchestrator mengirim `provider_response` dengan field `error` saat provider gagal. Listener SSE sudah menerima tipe ini, tetapi `EVENT_DESCRIBERS` tidak memiliki handler provider_response. Handler task_failed hanya menghasilkan judul “Task failed”, tanpa detail error.

**Pemicu:** kegagalan CLI, timeout, atau error provider yang menghasilkan event error tersebut.

**Dampak:** timeline utama tidak memperlihatkan alasan provider gagal, walaupun payload tersedia. Output/Problems atau log terpisah mungkin memuat sebagian detail; temuan ini tidak menyatakan error hilang dari seluruh sistem.

**Bukti:** [error provider:2059–2069](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/src/agent_ai/core/orchestrator.py#L2059-L2069), [dispatcher:410–523](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/components/AgentActivity.vue#L410-L523).

**Perbaikan:** tampilkan error provider terstruktur dengan provider/model, kategori, attempt, dan status recovery; gunakan pesan yang sudah disanitasi. Jangan mengganti error spesifik dengan label running/reasoning generik.

## ASYNC-11 — History tidak memiliki penjagaan respons terbaru

**P2 · Temuan sebelumnya, direproduksi kembali.**

Klik A lalu B, buat respons B tiba lebih dahulu. `handleViewTask()` menetapkan task.id saat request dimulai, tetapi respons A yang terlambat tetap mengganti activityEvents dan telemetry. Hasil reproduksi: ID B, events A.

Pada provider yang menghasilkan history panjang atau jaringan lambat, kemungkinan urutan respons terbalik semakin nyata.

**Bukti:** [App:514–560](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L514-L560).

**Perbaikan:** request generation + project/task ID guard untuk success maupun catch; merge snapshot history dengan event live berdasarkan sequence agar respons snapshot lama tidak menghapus event yang baru masuk.

## ASYNC-12 — Rolling buffer mengulang efek event lama

**P2 · Temuan sebelumnya, direproduksi kembali.**

App membatasi activityEvents menjadi 500 dengan shift. Watcher `useWorkbenchLiveEvents` menganggap perubahan event pertama sebagai reset dan mulai lagi dari indeks 0. Setelah buffer penuh, satu event baru dapat memproses ulang 499 event lama.

**Reproduksi:** 500 file_modified diproses, lalu geser satu dan tambahkan satu. Callback file-modified total menjadi 1.000, seharusnya 501.

**Dampak:** request reload, pemeriksaan konflik, dan output dapat berulang pada task agent panjang. Ini pengulangan pekerjaan frontend; bukan bukti CLI mengulangi tool call yang sama.

**Bukti:** [watcher:67–86](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/composables/useWorkbenchLiveEvents.js#L67-L86), [rolling buffer App:257–260](https://github.com/aditlab-code/aegiscode/blob/2ce8887901ce05672bd0d6e59ef3673215ab4767/web/frontend/src/App.vue#L257-L260).

**Perbaikan:** deduplikasi efek berdasarkan event ID/sequence, bukan panjang/elemen pertama array. Pisahkan konsumsi event dari daftar yang dipangkas untuk tampilan. History replay tidak boleh menjalankan ulang efek live file-write.

## Mengapa tes existing tetap lulus?

`App.vue` hanya mengimpor `isEventForMonitoredTask` dari taskStateReducer; logika submit, cancel, dan terminal lain tetap ditulis langsung di App. Karena itu tes reducer dapat lulus tanpa memverifikasi perilaku handler yang sebenarnya dipanggil UI.

Tes SSE menguji daftar event yang ditulis eksplisit dalam tes; daftar tersebut tidak mencakup reasoning/warning Antigravity. Tes telemetry memeriksa counter pada buffer panjang, bukan side effect watcher file-modified atau dua emisi usage untuk satu respons.

Perlu menguji sambungan antarkomponen dan respons tak berurutan, bukan hanya fungsi helper secara terpisah.

## Rencana perbaikan dan acceptance test

| Urutan | Pekerjaan                                       | Acceptance test minimum                                                                                                 |
| ------ | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 1      | Identitas target Stop dan cancellation per task | Stop B ketika A dipantau harus memanggil cancel B; respons A tidak mengubah B; completed tetap completed                |
| 2      | Rekonsiliasi create/SSE dan state per task      | Terminal sebelum HTTP tetap terminal; A ke B tidak membawa prompt/event/token/timer A                                   |
| 3      | Isolation project/session/request               | Respons P1 tidak mengubah view P2; jawaban chat A tidak masuk B; respons History lama diabaikan                         |
| 4      | Kontrak event Antigravity                       | Reasoning/progress dan warning punya jalur render teruji; error provider tampil; satu usage final dihitung sekali       |
| 5      | Queue UI dan event buffer                       | Prompt kedua bisa enqueue saat running; event ke-501 tidak mengulang callback event 2–500                               |
| 6      | Integrasi Vue + simulasi jaringan               | Mount root dan child nyata; tunda/acak HTTP, kirim SSE sebelum/sesudah HTTP, pindah sesi/project, uji dua task parallel |

Desain state yang disarankan: simpan task menurut `(projectId, taskId)`, pisahkan `viewedTaskId` dari kumpulan task running, dan pakai generation untuk request yang mengubah view. Transisi task terminal tidak boleh dibalik oleh respons snapshot lebih lama. Untuk Ask, simpan message/request state per session.

## Batas kesimpulan Antigravity

Bukti paling kuat yang khusus terkait Antigravity adalah hilangnya semantik event reasoning/warning serta dua jalur emisi usage. Bug Stop, Queue, History, dan race session bersifat provider-agnostic; Antigravity yang berjalan lama membuatnya lebih mudah terlihat.

Laporan ini belum membuktikan penyebab loop pencarian konteks di sisi model, kesalahan kredensial pada mesin pengguna, kompatibilitas versi CLI tertentu, atau kualitas keputusan model. Untuk itu dibutuhkan log runtime tersanitasi dan pengujian CLI terpisah. Perbaikan frontend di atas tetap diperlukan agar observasi perilaku provider dapat dipercaya.
