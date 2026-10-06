# Audit AegisCode: Frontend, Integrasi Backend, dan Provider Thinking

Tanggal: 6 Oktober 2026 (Asia/Jakarta). Repository: https://github.com/aditlab-code/aegiscode. Branch: `main`. Snapshot: `8dcf9debba763b25cd56f408a7b6f9962c5091d5`.

> REPO AegisCode Community 


## Kesimpulan

Prioritas tertinggi adalah menjaga edit pengguna, mengisolasi state antarproject dan antartask, lalu menyelaraskan kontrak transport dan provider. Refactor besar sebaiknya mengikuti perbaikan perilaku ini, agar pemindahan kode tidak mempertahankan bug yang sama.

Audit menghasilkan **18 kelompok temuan**: 8 P1 dan 10 P2. Temuan mencakup bug yang direproduksi, cacat kontrak yang dibuktikan dari kode, kandidat kode tidak terpakai, dan risiko maintainability. Tidak semuanya merupakan bug yang sudah diamati di browser. P1 berarti segera diperbaiki karena risiko kehilangan edit, salah workspace/task, atau kontrol akses; P2 berarti perbaikan terencana. Tidak ada P0 yang diklaim.

## Metode dan batas cakupan

- Metadata, snapshot repository, dan daftar GitHub Issues diperiksa melalui koneksi GitHub. Endpoint daftar Issues `state=all` mengembalikan kosong pada saat audit; nomor AEG-xx di dokumen ini adalah ID backlog usulan, bukan issue GitHub yang dibuat.
- Source ditelaah pada root aplikasi Vue, Workbench, editor/model registry, terminal, API client, Django views/services/streaming, autentikasi, konfigurasi LLM, dan adapter provider terkait. Import/reference tracing mencakup frontend.
- Reproduksi terisolasi memakai model registry aktual, fungsi dialog close aktual yang diekstrak dengan dependency mock, normalizer provider aktual, serta Django RequestFactory dengan service mock.
- Tidak dilakukan pengujian browser menyeluruh, OAuth langsung, panggilan berbayar provider, atau pengujian seluruh extension/semantic engine. Tes yang lulus bukan bukti seluruh aplikasi bebas bug.
- Source, lockfile, dan konfigurasi repository tidak diubah; tidak ada commit, PR, atau issue yang dipublikasikan. Dependency sementara dipasang untuk audit.

## Hasil validasi

| Pemeriksaan | Hasil dan interpretasi |
|---|---|
| `npm ci --ignore-scripts --no-audit --no-fund` | Gagal: `Missing: @popperjs/core@2.11.8 from lock file`. Lingkungan Node 24.19.0/npm 11.9.0; perlu ulang pada Node 20 yang disebut README. |
| `npm test` | Gagal: skrip `test` tidak tersedia. |
| `npm install --ignore-scripts --package-lock=false --no-audit --no-fund` | Berhasil untuk memungkinkan audit; ini tidak memperbaiki reproducibility lockfile. |
| `node --test src/*.test.mjs` | **52 lulus, 0 gagal**. Sebagian menguji helper yang sudah tidak dipakai aplikasi. |
| `npm run build` | Berhasil. Chunk utama 621.11 kB dan Monaco 3,334.14 kB sebelum gzip; warning chunk >500 kB. Ukuran adalah baseline, bukan bukti lambat di perangkat pengguna. |
| Backend terpilih | **54 lulus**: provider retry lifecycle, API retry config, execution mode, Google OAuth, terminal consumer, local Git gateway. Django 5.0.14 sesuai rentang pyproject; Python 3.12. |
| Reproduksi model tab | Setelah edit dan `releaseModel('a.js')`, `getModel('a.js')` menghasilkan `null`; membuka lagi menghasilkan isi disk, bukan edit. |
| Reproduksi Save lalu Close | Ketika mock `save()` mengembalikan `false`, fungsi dialog aktual tetap menghapus tab: jumlah tab menjadi 0. |
| Reproduksi normalizer thinking | Respons `content=null`, `reasoning_content` terisi, tanpa tools, `finish_reason=stop` menghasilkan `text=''`, 0 actions, STOP; reasoning masih berada di raw. |
| Reproduksi auth boundary | GET file-content tanpa Authorization mencapai service mock dan mengembalikan HTTP 200. Tidak membaca file pengguna atau menjalankan shell dalam reproduksi. |

Perintah backend terpilih: `python -m pytest -q tests/test_provider_retry_lifecycle.py tests/test_api_retry_config.py tests/test_agent_execution_mode.py tests/test_google_oauth.py tests/test_terminal_consumer.py tests/test_git_local_gateway.py`.

## Backlog ringkas

| ID | Prioritas | Temuan | Kategori | Bukti |
|---|---|---|---|---|
| AEG-01 | P1 | Edit tab hilang saat berpindah file | Bug frontend | Reproduksi registry + jalur editor |
| AEG-02 | P1 | Save gagal tetap menutup tab; target save bisa salah | Bug frontend | Reproduksi fungsi dialog |
| AEG-03 | P1 | Pergantian project mempertahankan tab/model lama | Integrasi frontend/backend | Kontrak source |
| AEG-04 | P1 | Event semua task masuk ke state task tunggal | Inconsistency/concurrency | Kontrak source |
| AEG-05 | P1 | Task pending langsung ditampilkan running | Dead fix/orphan helper | Kontrak source + helper tidak terpakai |
| AEG-06 | P1 | Load/save/apply editor tidak mengunci identitas operasi async | Race frontend | Analisis source; perlu E2E |
| AEG-07 | P1 | Terminal tetap terhubung ke project lama | Integrasi terminal | Lifecycle source |
| AEG-08 | P1* | Identitas OAuth tidak menjaga API/PTY sensitif | Auth inconsistency | RequestFactory + source |
| AEG-09 | P2 | Kontrak event backend lebih luas dari listener frontend | Inconsistency | Perbandingan enum/listener |
| AEG-10 | P2 | Reconnect tidak memulihkan event yang terlewat | Integrasi SSE | Kontrak source |
| AEG-11 | P2 | Stop gagal tetap membuat UI idle | Bug state | Source |
| AEG-12 | P2 | Cache file global dapat membawa respons project lama | Race/cache | Source |
| AEG-13 | P2 | Git Clone merupakan placeholder aktif | Dead feature | Handler hanya timer |
| AEG-14 | P2 | Helper/widget tertinggal; tes hijau tidak menjamin wiring | Orphan code | Reference tracing |
| AEG-15 | P2 | Jalur instalasi, tes, dan dependency tidak konsisten | Reproducibility | Perintah aktual + manifest |
| AEG-16 | P2 | Thinking/capability model belum menjadi kontrak terstruktur | Provider optimization | Reproduksi normalizer + config |
| AEG-17 | P2 | Coordinator besar menggabungkan domain dan state | Maintainability/spaghetti risk | Struktur dan bug lintas state |
| AEG-18 | P2 | Telemetri, status koneksi, dan bundle perlu ditata | Performance/observability | Reducer + build |

\* AEG-08 mendesak apabila layanan diakses melalui jaringan atau login dianggap sebagai pembatas akses. Untuk mode lokal satu pengguna, desain trusted-local harus eksplisit; jangan mengasumsikan OAuth sekarang melindungi filesystem/terminal.

## Detail temuan dan acceptance criteria

### AEG-01 — Model dimiliki view editor, bukan tab

[CodeEditor.vue:105](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/components/CodeEditor.vue#L105) melepas model lama sebelum membaca file berikutnya. [Registry:96](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/services/monacoModelRegistry.js#L96) membuang model saat refCount nol; tab yang masih terbuka tidak memegang referensi. Dalam satu pane, A → B → A dapat menghilangkan edit A dan undo history.

Perbaikan: tab/session editor memiliki model; perpindahan view hanya detach/attach. Dispose saat tab terakhir ditutup melalui guard yang benar. Acceptance: edit A, pindah ke B dan kembali, isi serta undo A tetap utuh; shared model antar-pane tetap satu; menutup referensi terakhir membersihkan model.

### AEG-02 — Dialog Save lalu Close mengabaikan hasil save

[WorkbenchView.vue:1116](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/pages/WorkbenchView.vue#L1116) memanggil editor aktif lalu selalu `closeTab(..., {force:true})`. [CodeEditor.vue:262](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/components/CodeEditor.vue#L262) mengembalikan `false` pada kegagalan, sehingga catch parent tidak melindungi tab. Menutup dirty tab yang bukan tab aktif juga dapat menyimpan file aktif yang berbeda.

Perbaikan: save berdasarkan model/path target; tutup hanya jika save sukses untuk target yang sama. Acceptance: 403/500/offline membuat tab tetap terbuka dan dirty; menutup A saat B aktif menyimpan A saja; close split menangani seluruh dirty tab dengan keputusan eksplisit.

### AEG-03 — Workspace dan identitas model tidak terisolasi

[WorkbenchView.vue:1362](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/pages/WorkbenchView.vue#L1362) membersihkan pane1 saja; watcher hanya membersihkan ketika project menjadi kosong, bukan A → B. [App.vue:234](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/App.vue#L234) mengganti active project tanpa guard edit. Registry berkunci relative path. [GatewayService:1240](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/django_app/api/services.py#L1240) membaca/menulis relatif terhadap active project global.

Akibat yang diturunkan dari kontrak: isi A dapat tetap tampil setelah B aktif; save path yang sama dapat menulis ke B. Perbaikan: workspace ID dalam model/tab/URI dan setiap request file; guard project transition; reset atau restore kedua pane perproject. Acceptance: A dan B dengan `src/main.js` berbeda tidak berbagi model, isi, dirty flags, cache, atau tujuan write.

### AEG-04 — Kontaminasi event antartask

[App.vue:103–160](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/App.vue#L103) membuka stream tanpa filter, menerima semua event, dan langsung mengubah satu `task.status`, activity, changes, serta timer. Event task B selesai dapat membuat tampilan task A completed; event project lain juga bisa memicu refresh file yang salah.

Perbaikan: reducer/store berkunci task ID dan project ID; pisahkan viewed task, running tasks, history, dan queue. Acceptance: dua task paralel dengan event berselang-seling tidak saling mengubah status, changes, report, atau timer; melihat history tidak mengambil alih kontrol Stop task lain.

### AEG-05 — Fix task queue terputus dari aplikasi

[App.vue:171](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/App.vue#L171) menetapkan setiap task baru sebagai running dan menghapus activity task yang sebelumnya dilihat, tanpa memakai `queue_state` backend. [taskView.js](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/taskView.js) justru mendokumentasikan dan mengatasi kasus A running/B pending, tetapi tidak diimpor aplikasi. Tes helper tersebut lulus.

Perbaikan: sambungkan kebijakan adopsi task ke reducer aplikasi dan gunakan respons backend. Acceptance: submit B saat A running mempertahankan activity A; B pending di queue; mengikuti B hanya setelah benar-benar started dan sesuai pilihan user.

### AEG-06 — Async editor tidak memiliki generation/target guard

`switchToFile` memeriksa `disposed` sebelum `await readFileContent`, tetapi tidak setelahnya; tidak ada request sequence/abort. Respons A yang terlambat dapat mengganti B. `save()` menangkap isi awal tetapi membaca `props.path`/`model` lagi setelah await. [Apply to Editor:1413](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/pages/WorkbenchView.vue#L1413) menangkap editorRef sebelum membuka target dan hanya menunggu `nextTick`, bukan loading model selesai.

Perbaikan: capture workspace/path/model/version per operasi; token generation/AbortController; apply berdasarkan model target setelah readiness. Acceptance: respons A/B terbalik, unmount saat load, pindah tab saat save, dan apply ke file belum aktif tetap menyentuh target yang benar. Ini analisis race source, belum reproduksi browser.

### AEG-07 — Socket PTY tidak mengikuti perubahan project

[TerminalView.vue:82](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/components/TerminalView.vue#L82) membaca project ID saat membuat socket dari mount, tanpa watcher project. [AppBottomDock.vue:331](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/components/layout/AppBottomDock.vue#L331) tidak memberi key project. Ketika komponen tetap mounted pada A → B, shell A dapat tetap menjadi tujuan input sementara UI menampilkan B.

Perbaikan: lifecycle PTY per workspace; close/detach sesuai kebijakan, reconnect untuk B, label session/cwd. Acceptance: A → B mengirim input hanya ke B; invalid project di backend ditolak, bukan fallback diam-diam ke process cwd seperti jalur connect saat ini.

### AEG-08 — Auth tidak menjadi boundary operasi sensitif

[api/auth.py:require_auth](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/django_app/api/auth.py#L138) ada tetapi tidak dipakai views operasional. ASGI menghubungkan [URLRouter langsung](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/django_app/config/asgi.py); consumer menerima koneksi sebelum membuat shell tanpa validasi identitas atau origin. LoginOverlay tidak diimpor App. MIDDLEWARE tidak mencantumkan SecurityMiddleware/CSRF middleware walaupun terdapat setting keamanan production.

Perbaikan: tetapkan mode trusted-local vs authenticated secara eksplisit. Untuk mode authenticated, lindungi HTTP, SSE, WS, filesystem, terminal, dan terminate; validasi origin WS; gunakan transport auth yang kompatibel. `request()` menambahkan bearer, sedangkan EventSource, terminal streaming, dan serverService tidak mengikuti pola itu: memasang decorator saja akan memutus sebagian frontend. Acceptance: koneksi anonymous ditolak di mode authenticated; origin tidak diizinkan ditolak sebelum PTY dibuat; pengguna sah memakai semua transport. Uji middleware benar-benar menerapkan kebijakan production.

### AEG-09 — Event bernama tertentu tidak pernah diterima live

[EventType](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/src/agent_ai/session/events.py#L18) memuat `tool_result`, `agent_observation`, `policy_applied`, `policy_escalated`, `verification_strategy_applied`. Daftar KNOWN_EVENTS di [api.js:603](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/api.js#L603) tidak memuatnya. `onmessage` bukan fallback bagi custom named SSE event.

Perbaikan: kontrak event terversi/generate listener dari skema bersama. Acceptance: semua event operasional yang diharapkan UI diterima tepat sekali, termasuk escalation dan verification; event baru tidak hilang tanpa terdeteksi tes kontrak.

### AEG-10 — Tidak ada recovery gap event

[views.events:1189](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/django_app/api/views.py#L1189) berlangganan event baru tanpa membaca Last-Event-ID/replay. Queue subscriber [streaming.py](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/django_app/api/streaming.py#L105) membuang event saat penuh. Frontend onOpen hanya menandai connected.

Perbaikan: bounded replay/cursor dengan dedup event_id; snapshot resync saat reconnect atau gap terdeteksi. Acceptance: putus ketika task completed lalu sambung kembali menghasilkan status/report benar; overflow terdeteksi dan dipulihkan. Tidak wajib menambah broker baru.

### AEG-11 — UI idle walaupun cancellation gagal

[App.vue:200](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/App.vue#L200) memakai finally untuk menetapkan idle dan mengosongkan running ID, termasuk setelah error HTTP/network. Backend mungkin tetap running.

Perbaikan: gunakan cancelling/failed-cancel state; pertahankan running ID ketika request gagal; reconcile respons atau event terminal. Acceptance: mock cancel 500 tidak menyembunyikan task aktif; cancel sukses konsisten dengan queue dan event.

### AEG-12 — Cache tidak memiliki workspace identity

[fileCacheService.js:40](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/services/fileCacheService.js#L40) memakai satu cache dan inflightPromise global. `force=true` tetap mengembalikan request inflight lama; invalidate tidak mencegah respons lama menulis kembali cache. handleOpenProject tidak membatalkan request A sebelum meminta B.

Perbaikan: cache per workspace dan request generation; invalidasi saat perubahan filesystem relevan. Acceptance: request A lambat, lalu buka B, autocomplete/quick-open hanya menampilkan B, termasuk project kosong.

### AEG-13 — Git Clone menjanjikan alur yang belum ada

[WorkbenchView.vue:1387](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/src/pages/WorkbenchView.vue#L1387) hanya timer satu detik dan pesan pipeline initialized. Tidak ada pemanggilan clone backend di handler.

Perbaikan: nonaktifkan/tandai Coming Soon sampai tersedia, atau implementasikan endpoint clone dengan destination, validation, progress, cancellation, dan error. Acceptance: tombol aktif benar-benar membuat checkout dan membuka project; invalid URL/target tidak mengklaim sukses.

### AEG-14 — Orphan helper dan UI

Tidak ditemukan referensi import aplikasi ke `taskView.js`, `activityCopy.js`, `tokenFormat.js`, `LoginOverlay.vue`, `AppThinkingBlock.vue`, `AppDrawer.vue`, dan `AppToggle.vue`. Tiga helper pertama masih memiliki tes. Ini kandidat unreachable dari entrypoint sekarang; tracing statis tidak membuktikan seluruh penggunaan eksternal tidak ada. `gitGraphLayout.js` **bukan orphan**: dipakai melalui import tanpa ekstensi oleh GithubBackupPanel.

Perbaikan: AEG-05 dihubungkan kembali; putuskan restore vs remove untuk token/activity/auth UI; hapus widget hanya setelah reference/runtime audit. Acceptance: fungsi yang dites juga masuk jalur produksi yang relevan; orphan inventory mencatat alasan preserve/remove; jangan menghapus berdasar nama atau umur file.

### AEG-15 — Install/test contract bertentangan

[package.json](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/web/frontend/package.json) tidak menyediakan `test`; README memintanya. Lockfile gagal clean install pada lingkungan audit. `requirements.txt` memuat PyJWT/google-auth tetapi tidak channels/daphne; pyproject memuat channels/daphne tetapi tidak PyJWT/google-auth. Django INSTALLED_APPS membutuhkan keduanya; manifest tidak setara dengan komentar single source.

Perbaikan: satu definisi dependency yang diturunkan ke jalur install lain; regenerate lock dengan runtime yang disepakati; skrip test dan CI clean install. Acceptance: fresh environment dapat menjalankan README sampai gateway/build/tests tanpa dependency manual; uji Node 20 dan runtime CI yang dipilih. Jangan memperluas dukungan Node 24 hanya karena audit dilakukan di sana.

### AEG-16 — Thinking provider belum memiliki kontrak terpadu

[OpenAI normalizer:461](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/src/agent_ai/providers/openai_compatible.py#L461) membaca content dan tool_calls, tidak memisahkan reasoning metadata. Ollama memiliki fallback thinking ke teks jika content/tools kosong; perilaku antarpovider berbeda. `GenerateOptions` memiliki extra generik, tetapi [ModelConfig](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/src/agent_ai/llm_config/models.py#L95) tidak memuat kemampuan thinking/token/window. [resolve_runtime_config:537](https://github.com/aditlab-code/aegiscode/blob/8dcf9debba763b25cd56f408a7b6f9962c5091d5/src/agent_ai/llm_config/service.py#L537) tidak mengirim timeout/context_window walaupun factory mendukungnya.

Ini tidak membuktikan semua model reasoning gagal. Reproduksi menunjukkan respons reasoning-only tidak mendapat klasifikasi khusus, dan pemilihan model tersimpan tidak cukup untuk menyatakan kemampuan model.

Perbaikan: capability permodel, mapping opsi peradapter, separate final answer/action/reasoning metadata, serta explicit empty-final handling. Jangan menampilkan raw reasoning sebagai jawaban atau men-stream chain-of-thought; source event memang mendefinisikan metadata operasional tanpa CoT. Acceptance: fixture text-only, tool+reasoning, reasoning-only, content kosong, truncated tools, usage, dan parameter unsupported menghasilkan perilaku jelas; parameter kemampuan diteruskan dari UI ke runtime secara teruji.

### AEG-17 — Boundary tanggung jawab menyulitkan perawatan

Workbench 2,905 baris, Gateway services 3,419 baris, views 1,505 baris, ConsultantChat 1,312 baris. Ukuran sendiri bukan bukti spaghetti. Risiko nyata terlihat karena Workbench sekaligus mengatur dua pane, model, save/close, konflik agent, Git, navigation, settings, terminal, dan apply; App menyatukan selected/viewed/running task. Error mapping `_handle` memakai substring pesan exception, termasuk `unknown` yang tertangkap sebagai 400 sebelum cabang 404.

Perbaikan: ekstrak composable/service berdasarkan domain setelah tes perilaku; facade gateway untuk projects/files/tasks/providers/extensions; typed error mapping. Acceptance: satu pemilik state per domain, event/action API eksplisit, error code stabil, dan perubahan save tidak memerlukan perubahan task/terminal. Hindari rewrite serentak.

### AEG-18 — Observability dan bundle belum mendukung evaluasi optimalisasi

App membatasi activity 500 event lalu menghitung ulang telemetry dari jendela itu setiap event: rounds/tool calls dapat turun ketika event awal terbuang. `tokenFormat.js` tidak dipakai, sementara backend sudah menyediakan usage. Health monitor menulis `connected=true` walaupun SSE belum pulih. Build Monaco 3.33 MB minified membutuhkan pengukuran loading pada target device.

Perbaikan: telemetry total incremental dedup atau authoritative snapshot; pisahkan HTTP/SSE/PTY connectivity; hubungkan usage yang tersedia; ukur bundle lalu kurangi language contributions/lazy-load jika dibutuhkan. Acceptance: >500 event tidak menurunkan total; retry tidak double count; gateway online/SSE offline tampil akurat; tetapkan budget bundle dan ukur sebelum/sesudah.

## Rencana perbaikan bertahap

Estimasi berikut adalah effort engineer-days, bukan tanggal janji. Asumsi satu developer memahami Vue/Django, ditambah review dan buffer integrasi 20–30%. Sesuaikan setelah reproduksi E2E.

| Tahap / PR | Scope | Dependensi | Estimasi | Syarat selesai |
|---|---|---|---|---|
| PR-01 Baseline reproducible | AEG-15; scripts test, manifests, lockfile, CI | Tidak ada | 1–2 hari | Clean install/build/tests pada runtime resmi |
| PR-02 Editor ownership & save | AEG-01,02,06; model lifecycle, target identity, async guards | PR-01 | 3–5 hari | Semua skenario kehilangan edit/async lulus |
| PR-03 Workspace transition | AEG-03,07,12; kedua pane, project-aware API/cache/PTY | PR-02 | 3–4 hari | Project A/B tidak berbagi state atau tujuan write |
| PR-04 Task state & queue | AEG-04,05,11; task reducer, adoption, cancel reconciliation | PR-01 | 2–4 hari | Queue/history/parallel/Stop konsisten |
| PR-05 Event recovery | AEG-09,10 dan connectivity AEG-18 | PR-04 | 2–3 hari | Event contract, reconnect/gap/dedup lulus |
| PR-06 Access boundary | AEG-08; mode lokal/authenticated, HTTP/SSE/WS, origin/middleware | Keputusan mode + PR-05 | 2–4 hari | Semua transport sah berfungsi, anonymous ditolak sesuai mode |
| PR-07 Provider capabilities | AEG-16; schema/config/UI/adapters/fixtures/metrics | PR-01; koordinasi event PR-05 | 3–5 hari | Model capability tersimpan dan diteruskan tanpa fallback ambigu |
| PR-08 Product cleanup & refactor | AEG-13,14,17 dan bundle/usage AEG-18 | Perilaku domain stabil | 3–5 hari | Placeholder jujur, wiring diuji, domain dipisah, baseline terukur |

Total awal sekitar **19–32 engineer-days**, belum buffer. Jika aplikasi saat ini dipakai melalui jaringan, PR-06 diprioritaskan segera bersama perbaikan P1; jangan menunggu seluruh refactor.

## Matriks tes regresi yang diperlukan

| Area | Skenario wajib | Lapisan |
|---|---|---|
| Editor | Dirty A → B → A; close inactive dirty tab; save 500; split shared model; unmount saat load; load responses terbalik | Integration komponen + E2E |
| Workspace | A/B punya path sama; switch dengan dirty tabs; close kedua pane; request A terlambat; save saat switch | Frontend/backend integration |
| Tasks | A running/B pending; 2 parallel; history saat event live; failed cancel; task selesai sebelum create response diproses | Reducer + gateway + E2E |
| SSE | Seluruh enum event; Last-Event-ID/resync; duplicate/gap; queue overflow; health online tetapi stream offline | Transport contract |
| Terminal/auth | Ganti workspace; invalid project; origin ditolak; auth permode HTTP/SSE/WS; cleanup PTY | Gateway/consumer + E2E |
| Provider | Final/text/tools/reasoning-only; truncated args; actual usage; opsi unsupported; timeout/context config propagation | Fixture adapter + config integration |
| Install/maintainability | Fresh install dua jalur; npm ci; npm test; build; typed error mapping; production helper wiring | CI |

## Strategi optimalisasi provider thinking

1. **Capability sebagai data.** Simpan declared/verified capability: API mode, tool support, vision, reasoning option mapping, context window, output budget, dan timeout. Jangan menyimpulkan dukungan hanya dari nama model.
2. **Budget terpisah.** Bedakan prompt, tool schema, output, dan reasoning budget jika provider melaporkannya. Reserve tetap 4,096 pada adapter sekarang perlu dievaluasi terhadap output limit dan tool schema aktual. Tampilkan unknown ketika usage tidak tersedia.
3. **Output ternormalisasi.** Final text/action harus eksplisit. Reasoning-only bukan otomatis final answer; gunakan error/recovery yang bounded dan sesuai finish reason. Pertahankan tools/argument lengkap; jangan memperbaiki JSON terpotong dengan tebakan.
4. **Cancellation dan retry terukur.** Pertahankan retry infrastruktur yang sudah diuji; ukur latency dan cancellation saat request/backoff. Jangan menambah retry buta yang menaikkan biaya. Propagasikan deadline/cancel sesuai kemampuan adapter.
5. **Mode agent berbeda dari reasoning effort.** fast/balanced/deep adalah strategi agent/verifikasi dalam source saat ini; jangan mengklaim mode tersebut otomatis mengubah thinking provider. Buat mapping eksplisit bila diinginkan, dengan batas biaya.
6. **Evaluasi sebelum optimasi.** Benchmark fixture yang sama: success rate task, latency median/p95, time-to-first-operational-update, prompt/completion usage, reasoning usage bila tersedia, retry, truncation, dan biaya bila tarif dikonfigurasi. Bandingkan kualitas hasil, bukan hanya jumlah token.

## Urutan tindakan pertama

Mulai dari reproducible test entrypoint dan tes editor yang menangkap AEG-01/02, kemudian perbaiki project isolation dan task reducer. Jangan menghapus helper `taskView.js` sebagai cleanup sebelum perilaku queue digantikan dan diuji di jalur aplikasi. Jangan mengaktifkan auth decorator secara massal sebelum transport SSE/WS memiliki kontrak autentikasi yang kompatibel.

Laporan ini adalah hasil audit snapshot yang disebutkan. Setiap issue yang ditindaklanjuti sebaiknya mencantumkan ID, file sumber, trigger, expected/actual behavior, acceptance criteria, dan test regresi dari bagian terkait.
