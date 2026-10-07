# Audit bugs dan optimasi AegisCode Community

Tanggal: 6 Oktober 2026 (WIB)  
Repo: [aditlab-code/aegiscode](https://github.com/aditlab-code/aegiscode)  
Branch: main  
Snapshot: [d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc](https://github.com/aditlab-code/aegiscode/commit/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc)

## 1. Ringkasan dan batas audit

Audit mencatat **15 temuan: 14 direproduksi pada fungsi/batas antarfungsi secara terisolasi dan 1 dibuktikan melalui AST/static analysis**. Prioritas: **6 P1 dan 9 P2**. Prioritas utama adalah integritas save, error pemeriksaan sintaks, dan deadlock logis cache file. Ada pula risiko desain serta peluang optimasi provider, lifecycle, dan pengujian.

Laporan ini hanya menilai snapshot **community** di atas. Keterangan pemilik bahwa versi dev sudah stabil diterima sebagai konteks; kode dev tidak tersedia untuk dibandingkan, sehingga temuan ini tidak boleh digeneralisasikan ke versi dev. Sebelum memperbaiki community, cocokkan setiap temuan dengan patch yang mungkin sudah ada di dev.

Metode: pembacaan README dan 36 file sumber/test terpilih; penelusuran panggilan frontend–API dan provider; eksekusi tiga harness JavaScript (Node.js v24.19.0) dan satu harness Python yang mengekstrak fungsi asli dengan dependency browser/Vue/network tiruan. Validator diagnostik diimpor langsung. Tidak ada panggilan model berbayar atau perubahan repository.

**Batas bukti:** ini bukan audit seluruh repo, pentest, atau sertifikasi kesiapan produksi. Build, npm test lengkap, pytest, browser E2E, transport PTY, dan provider live belum dijalankan. Harness membuktikan perilaku fungsi pada input yang dicatat; dampak lintas-komponen yang belum diamati tetap dinyatakan sebagai risiko. Tidak ada benchmark yang membuktikan persentase penghematan token/latensi.

P1 = perlu diprioritaskan sebelum rilis karena risiko kehilangan edit/gangguan alur inti. P2 = perbaikan berikutnya untuk ketepatan, isolasi state, dan keandalan. Tidak ada temuan P0 yang dibuktikan dalam cakupan ini.

## 2. Daftar temuan

| ID | Prioritas | Temuan | Bukti |
|---|---|---|---|
| BUG-01 | P1 | Pemeriksaan sintaks editor melempar ReferenceError | Reproduksi terisolasi |
| BUG-02 | P1 | Save menandai versi yang belum ditulis sebagai sudah tersimpan | Reproduksi terisolasi |
| BUG-03 | P2 | Batas delapan lampiran terlewati oleh FileReader asinkron | Reproduksi terisolasi |
| BUG-04 | P2 | Diagnostik palsu untuk string multiline Python yang valid | Reproduksi terisolasi |
| BUG-05 | P2 | Callback socket terminal lama menghapus referensi socket baru | Reproduksi terisolasi |
| BUG-06 | P1 | Dedup permintaan cache membuat hasil dibuang dan loading macet | Reproduksi terisolasi |
| BUG-07 | P2 | Cache miss proyek tertentu mengembalikan file proyek aktif lain | Reproduksi terisolasi |
| BUG-08 | P2 | Event baru dapat terlewat saat riwayat diganti atau dirotasi | Reproduksi terisolasi |
| BUG-09 | P2 | Problems menyatukan error berbeda hanya karena pesannya sama | Reproduksi terisolasi |

## 3. Detail bugs, perbaikan, dan acceptance criteria

### BUG-01 — Pemeriksaan sintaks editor melempar ReferenceError

- **Prioritas/status:** P1; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/components/CodeEditor.vue#L115-L180](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/CodeEditor.vue#L115-L180).
- **Akar masalah:** `lang` dideklarasikan dengan `const` di blok pembuatan model (baris 135), tetapi dibaca dalam callback timer `runSyntaxCheck` (baris 162) di luar scope itu.
- **Reproduksi:** Buka file, tunggu timer pemeriksaan sintaks 200 ms. Harness menjalankan fungsi `switchToFile` asli dengan model dan timer tiruan, lalu memanggil callback timer.
- **Hasil/dampak:** `ReferenceError: lang is not defined` berhasil direproduksi. Diagnostik tambahan gagal; ini tidak membuktikan seluruh Monaco/editor berhenti.
- **Usulan perbaikan:** Hitung bahasa pada scope fungsi `switchToFile` sebelum percabangan model. Callback perlu menangkap model/path milik load yang sama dan mengabaikan callback usang.
- **Acceptance criteria:** File baru, model yang sudah ada, pindah tab cepat, dan unmount sebelum timer selesai tidak menghasilkan exception; marker melekat pada file yang benar.

### BUG-02 — Save menandai versi yang belum ditulis sebagai sudah tersimpan

- **Prioritas/status:** P1; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/components/CodeEditor.vue#L281-L308](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/CodeEditor.vue#L281-L308).
- **Akar masalah:** Konten diambil sebelum `await writeFileContent`, tetapi version ID diambil setelah request selesai. Selama request berlangsung, model masih dapat berubah. Kode lalu memaksa `dirty=false`.
- **Reproduksi:** Simpan konten A; tahan respons write; ubah model menjadi B; selesaikan request pertama. Harness mengeksekusi fungsi `save()` asli dengan write yang ditunda.
- **Hasil/dampak:** Payload disk tetap A, model B, tetapi version 2 ditandai saved dan dirty=false. Penutupan tab dapat menghilangkan B tanpa peringatan. Pola serupa terdapat pada save tab nonaktif di WorkbenchView sekitar baris 784–798.
- **Usulan perbaikan:** Snapshot `{projectId,path,model,content,version}` sebelum await. Tandai hanya versi snapshot sebagai saved; hitung ulang dirty dari versi model saat ini. Jangan menutup tab yang masih dirty setelah respons. Hindari respons save lama mengubah state tab baru.
- **Acceptance criteria:** Test save lambat + mengetik, save dari dua pane, switch tab/proyek saat save, save gagal, dan close-after-save. Perubahan setelah snapshot tetap dirty dan tidak hilang.

### BUG-03 — Batas delapan lampiran terlewati oleh FileReader asinkron

- **Prioritas/status:** P2; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/components/TaskComposer.vue#L90-L133](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/TaskComposer.vue#L90-L133).
- **Akar masalah:** Pengecekan jumlah memakai `attachments.value.length` sebelum FileReader selesai. Elemen baru baru ditambahkan pada onload. Pola identik ada pada ConsultantChat.vue sekitar baris 497–526.
- **Reproduksi:** Pilih sembilan PNG sekaligus dari keadaan kosong; selesaikan semua callback FileReader sesudah loop pemilihan.
- **Hasil/dampak:** Hasil kedua komponen adalah sembilan lampiran, meskipun batas dinyatakan delapan. Ini kegagalan batas frontend. Backend _normalize_images memang memeriksa maksimum delapan; jalur HTTP penuh belum diuji.
- **Usulan perbaikan:** Reservasi slot pending sebelum membaca, atau batasi daftar terhadap kapasitas tersisa dan pending reads. Gunakan helper bersama, batasi byte per file/total, dan generation token agar callback lama tidak mengisi draft berikutnya.
- **Acceptance criteria:** Pemilihan batch dan pemilihan berturut-turut tidak melampaui delapan; file gagal baca melepaskan slot; submit/reset saat read pending tidak memasukkan lampiran ke pesan berikutnya.

### BUG-04 — Diagnostik palsu untuk string multiline Python yang valid

- **Prioritas/status:** P2; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/services/diagnosticService.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/diagnosticService.js).
- **Akar masalah:** Scanner tanda kurung menyimpan status kutip per baris dan tidak memahami triple-quoted string Python. Tanda kurung yang merupakan isi string dianggap sintaks kode.
- **Reproduksi:** Jalankan `validateCodeSyntax('s = """\n(\n"""', 'python', 'a.py')`.
- **Hasil/dampak:** Validator mengeluarkan `SyntaxError: unclosed '(' opened at line 2` pada Python yang valid. Kontrol JavaScript multiline sederhana dalam harness menghasilkan [] dan tidak dinyatakan gagal.
- **Usulan perbaikan:** Gunakan parser/language service sesuai bahasa. Bila heuristic tetap digunakan, tandai keterbatasannya dan pertahankan lexical state lintas baris, termasuk komentar dan triple quotes.
- **Acceptance criteria:** Triple quotes, komentar, string escape, template literal, serta kode valid multiline tidak menimbulkan false error; bracket yang benar-benar tidak tertutup tetap terdeteksi.

### BUG-05 — Callback socket terminal lama menghapus referensi socket baru

- **Prioritas/status:** P2; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/components/TerminalView.vue#L77-L145](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/TerminalView.vue#L77-L145).
- **Akar masalah:** Socket disimpan dalam variabel bersama. onclose/onerror selalu menulis `socket=null`. Saat proyek berubah, socket lama ditutup lalu socket baru dibuat; event penutupan lama dapat datang belakangan.
- **Reproduksi:** Buat socket A; simulasikan perpindahan proyek dan buat B; kirim onclose milik A setelah B tercipta.
- **Hasil/dampak:** Referensi socket aktif menjadi null meskipun B ada. Input terminal dan resize memakai variabel ini, sehingga dapat berhenti terkirim. Reproduksi memakai transport tiruan, bukan PTY sungguhan.
- **Usulan perbaikan:** Tangkap `const currentSocket` dan ubah state hanya jika `socket===currentSocket`. Abaikan callback dari generation lama. Tambahkan state disconnected dan reconnect eksplisit/terkendali, dengan pencegahan reconnect saat sengaja ditutup.
- **Acceptance criteria:** Switch proyek cepat dan disconnect tak terduga tidak memutus referensi sesi baru; tidak ada input yang terkirim ke proyek lama; reconnect tidak membuat sesi ganda.

### BUG-06 — Dedup permintaan cache membuat hasil dibuang dan loading macet

- **Prioritas/status:** P1; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/services/fileCacheService.js#L80-L138](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/fileCacheService.js#L80-L138).
- **Akar masalah:** `requestSeq` dinaikkan sebelum memeriksa `inflightPromise`. Pemanggil kedua mengembalikan promise pertama tetapi sudah membuat thisSeq milik request pertama kedaluwarsa. Cabang finally juga tidak mereset loading.
- **Reproduksi:** Panggil `fetchWorkspaceFiles()` dua kali sebelum respons listFiles pertama selesai, dengan proyek aktif yang sama dan cache kosong.
- **Hasil/dampak:** Hanya satu request dikirim; kedua pemanggil memperoleh []; `filesLoading` tetap true setelah request selesai. Dibuktikan pada fungsi asli dengan listFiles ditunda.
- **Usulan perbaikan:** Periksa cache/inflight terlebih dahulu; naikkan generation hanya saat memulai request baru atau invalidasi. Gunakan inflight/loading/generation per proyek dan pastikan setiap pemilik request membersihkan state miliknya.
- **Acceptance criteria:** Dua atau lebih pemanggil memperoleh daftar yang sama dari satu request; loading kembali false; force refresh dan switch proyek tidak mengembalikan data lama.

### BUG-07 — Cache miss proyek tertentu mengembalikan file proyek aktif lain

- **Prioritas/status:** P2; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/services/fileCacheService.js#L34-L40](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/fileCacheService.js#L34-L40).
- **Akar masalah:** `getCachedFiles(projectId)` mengembalikan `workspaceFiles.value` ketika cache key tidak ada, bahkan bila projectId eksplisit berbeda dari proyek aktif.
- **Reproduksi:** Isi cache dan daftar aktif proyek B, lalu panggil `getCachedFiles('UNSEEN')`.
- **Hasil/dampak:** Fungsi mengembalikan file B untuk proyek yang belum dicache. Ini pelanggaran kontrak isolasi daftar; belum membuktikan kebocoran file antar-user atau salah tulis backend.
- **Usulan perbaikan:** Untuk projectId eksplisit yang tidak ditemukan, kembalikan []. Batasi fallback hanya konteks aktif yang memang diminta. Audit juga penerusan projectId: fetchWorkspaceFiles saat ini memanggil listFiles('.', true), tanpa identitas target eksplisit.
- **Acceptance criteria:** Cache miss proyek A saat B aktif menghasilkan []; fetch proyek eksplisit tidak mengisi cache A dari respons proyek B; invalidasi satu proyek tidak memengaruhi lainnya.

### BUG-08 — Event baru dapat terlewat saat riwayat diganti atau dirotasi

- **Prioritas/status:** P2; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/composables/useWorkbenchLiveEvents.js#L59-L72](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/composables/useWorkbenchLiveEvents.js#L59-L72).
- **Akar masalah:** Cursor event disimpan hanya sebagai panjang array (`lastProcessedEventCount`). Kode mengasumsikan riwayat selalu append-only, dan reset hanya ketika array kosong.
- **Reproduksi:** Kirim array berisi satu file_modified A; ganti langsung dengan array satu file_modified B tanpa fase array kosong.
- **Hasil/dampak:** Callback perubahan hanya menerima A; B dilewatkan. Ini terbukti pada input tersebut; frekuensi skenario pada UI/SSE nyata masih perlu E2E.
- **Usulan perbaikan:** Gunakan event ID/sequence serta taskId/projectId sebagai cursor. Reset ketika konteks berubah dan tangani truncation/rotation; dedup berdasarkan identitas event.
- **Acceptance criteria:** Pergantian tugas dengan panjang history sama, rotasi buffer, replay reconnect, dan event duplikat tidak menghilangkan perubahan; file refresh tepat satu kali sesuai kontrak.

### BUG-09 — Problems menyatukan error berbeda hanya karena pesannya sama

- **Prioritas/status:** P2; perilaku direproduksi dalam harness terisolasi.
- **Sumber:** [web/frontend/src/composables/useWorkbenchLiveEvents.js#L20-L29](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/composables/useWorkbenchLiveEvents.js#L20-L29).
- **Akar masalah:** Dedup memakai `seen.has(text)` tanpa file, line, column, source, atau code diagnostic.
- **Reproduksi:** Berikan dua problem dengan text='Syntax error', masing-masing pada A.py:1 dan B.py:2.
- **Hasil/dampak:** Daftar effectiveProblems hanya berisi satu entri. Error di lokasi lain tidak terlihat.
- **Usulan perbaikan:** Gunakan kunci gabungan `{projectId,file,line,column,source,code,message}` atau ID diagnostic stabil; bedakan dedup stream event dari dedup tampilan.
- **Acceptance criteria:** Pesan sama pada dua lokasi tetap dua problem, sedangkan event identik untuk lokasi sama tidak berlipat.


## 4. Audit khusus AI Agent dan Ask / Consultant

Ask di UI dipetakan ke Consultant: Quick dan Deep (investigate), berbeda dari Agent Fast/Balanced/Deep. Audit menelusuri ConsultantChat → api.js → GatewayService.consult → ConsultantService → ConsultantBoundProvider → AgentOrchestrator → provider/tool executor. Jalur Agent diperiksa pada runtime, orchestrator, executor, factory, dan retry. Scheduler paralel belum diuji menyeluruh.

### Matriks implementasi dan batasnya

| Area | Implementasi yang ditemukan | Penilaian |
|---|---|---|
| Ask Quick | Map/skill, semantic/hybrid bila tersedia, update Project Bible | Auto-context dan semantic retrieval dapat memasukkan cuplikan source, walaupun direct source tools tidak tersedia. |
| Ask Investigate | Menambah list/read/search dan run_command | Tidak mendaftarkan direct write tools, tetapi interpreter command dapat menulis (AI-02). |
| Ask persistence | Key projectId + sessionId dan store JSON | Isolasi key ada; race UI dan loader ganda tetap ditemukan. |
| Agent | Tool mutasi melalui executor, cancellation token | Cancel pada backoff masih memulai satu request tambahan (AI-03). |
| Continuous loop | Final tanpa tool call menjadi DONE; max_steps memiliki emergency abort | Safety limit ADA. Komentar lama yang mengatakan tidak ada hard stop tidak sesuai kode aktual. DONE belum membuktikan hasil terverifikasi. |
| Provider | Metadata runtime melewati GenerateOptions.extra | Bisa ikut ke body HTTP dan menggagalkan serialisasi (AI-01). |

### AI-01 — P1: callback internal masuk ke JSON request provider

**Status:** direproduksi memakai metode _call_provider dan _build_payload asli yang diekstrak melalui AST; tanpa network/model berbayar.

**Sumber:** src/agent_ai/core/orchestrator.py:1715–1765; src/agent_ai/providers/openai_compatible.py:228–274; src/agent_ai/consultant/guard.py; src/agent_ai/runtime/runtime.py.

Orchestrator memasukkan fungsi event_sink ke GenerateOptions.extra. Provider OpenAI-compatible menggabungkan seluruh opts.extra dengan payload HTTP. Serialisasi menghasilkan **Object of type function is not JSON serializable**. Consultant memasang _sink dan proxy meneruskan options ke provider; Agent runtime juga memasang event sink. execution_policy, mode, dan workspace_root berisiko ikut menjadi parameter HTTP tidak sah atau metadata lokal yang tidak semestinya terkirim bila tidak disaring.

**Dampak:** jalur adapter tersebut dapat gagal sebelum request dikirim. Jangan menggeneralisasikan ke Ollama, Antigravity, atau subclass yang menimpa payload tanpa pemeriksaan tambahan. Retry tidak memperbaiki error serialisasi deterministik.

**Perbaikan:** pisahkan runtime_context dari provider_params dan gunakan allowlist body API per adapter. Jangan sekadar menghapus callback saat serialisasi karena kunci internal lainnya tetap harus dipisahkan.

**Acceptance:** contract test Agent dan Ask melalui adapter sebenarnya dengan mock transport; body JSON valid dan hanya berisi parameter sah; callback telemetry tetap bekerja; workspace_root dan execution_policy tidak masuk HTTP body.

### AI-02 — P1: read-only Ask Investigate tidak ditegakkan terhadap command interpreter

**Status:** guard dan parser asli direproduksi. Argv yang lolos hanya dipakai membuat marker pada direktori temporer yang kemudian dihapus. Full executor/gateway tidak dijalankan. Static tracing menunjukkan run_command diklasifikasikan COMMAND_EXECUTION dan Consultant mengizinkan kelas itu.

**Sumber:** src/agent_ai/consultant/tools.py:155–224; src/agent_ai/consultant/policy.py; src/agent_ai/permission/classifier.py; src/agent_ai/tools/terminal.py.

Guard memblokir command tertentu dan redirect, tetapi meloloskan interpreter Python yang menulis file. shell=False tidak membuat proses Python read-only. Jalur terminal yang diperiksa menjalankan subprocess tanpa sandbox filesystem read-only. Command build/test juga dapat menulis melalui skrip proyek.

**Dampak:** Ask Investigate berpotensi mengubah source meskipun write_file/edit_file tidak didaftarkan. Ini pelanggaran janji read-only, berbeda dari keputusan desain trust ekstensi.

**Perbaikan:** batasi atau hilangkan arbitrary command dari Ask sampai ada isolasi. Sediakan tool diagnostik typed dengan argumen terkontrol; gunakan sandbox/worktree dengan batas write/network untuk eksekusi umum. Bila perlu tindakan mutatif, gunakan transisi eksplisit ke Agent. Menambah blocklist saja tidak cukup.

**Acceptance:** uji gateway/executor sungguhan pada workspace disposable; interpreter, skrip proyek, wrapper, serta build yang mencoba menulis source ditolak atau terisolasi. Diff source tetap kosong setelah Ask; pengecualian Project Bible harus spesifik dan terlihat.

### AI-03 — P1: cancel saat backoff masih memulai provider call berikutnya

**Status:** direproduksi pada _generate_with_retry asli dengan sleep tiruan yang menandai cancel; tanpa penantian/network.

**Sumber:** src/agent_ai/core/orchestrator.py:1864–1935.

Cancel diperiksa ketika exception terjadi, tetapi tidak sebelum setiap attempt atau setelah time.sleep. Pembatalan selama jeda masih diikuti attempt baru; bila berhasil, helper langsung mengembalikan respons. Harness mencatat dua call dan respons success sesudah cancel. Ini tidak membuktikan tool mutatif dieksekusi setelah cancel; outer loop dapat memiliki pemeriksaan tambahan.

**Perbaikan:** cek cancel sebelum setiap call dan setelah wait; gunakan wait yang bisa diinterupsi serta deadline/cancellation transport bila tersedia. Status cancelled tidak boleh berubah menjadi sukses karena respons terlambat.

**Acceptance:** cancel selama backoff membuat jumlah call tetap satu; cancel selama request tidak memulai tool/retry berikutnya; slot antrean dilepas setelah worker aman berhenti.

### AI-04 — P2: frontend Ask menerima gambar saja, backend mewajibkan teks

**Status:** branch validasi GatewayService.consult direproduksi; frontend diperiksa static.

**Sumber:** web/frontend/src/components/ConsultantChat.vue:579–612; web/django_app/api/services.py:2943–3000; src/agent_ai/consultant/service.py.

Frontend mengizinkan teks kosong bila lampiran ada dan menghapus draft sebelum request selesai. Gateway/service menolak message kosong walaupun ada gambar. Reproduksi menghasilkan “Field 'message' wajib diisi dan tidak boleh kosong.”

**Perbaikan:** dukung image-only dengan prompt default yang jelas, atau blok Send dan beri petunjuk wajib teks. Pulihkan draft/lampiran jika submit gagal.

**Acceptance:** kontrak image-only konsisten; kegagalan tidak menghilangkan draft. Backend _normalize_images sudah membatasi delapan gambar dan ukuran byte; BUG-03 adalah kegagalan batas frontend, bukan klaim seluruh backend tanpa batas.

### AI-05 — P2: loader sesi ganda menimpa pemasangan callback persistence

**Status:** AST/static analysis membuktikan dua definisi _load_sessions_from_store pada baris 387 dan 407. Python memilih definisi kedua.

**Sumber:** src/agent_ai/consultant/service.py:387–424.

Definisi pertama memasang _on_change pada sesi restore; definisi kedua tidak. Akibatnya loader pertama menjadi dead code dan write-through callback pada jalur restore tidak terpasang. **Bukan berarti semua pesan hilang:** akhir consult() masih menyimpan eksplisit.

**Perbaikan:** satukan loader; tetapkan satu kontrak persistence. Tambahkan pemeriksaan method duplikat.

**Acceptance:** restart → restore → add/touch → restart mempertahankan data; sesi restore dan sesi baru mempunyai semantik persistence sama; kegagalan tulis terlihat.

### AI-06 — P2: respons sesi lama menimpa sesi baru

**Status:** direproduksi pada resumeSessionFromId asli dengan dua promise tertunda.

**Sumber:** web/frontend/src/components/ConsultantChat.vue:165–188.

Load A lalu B; B selesai dahulu, kemudian A. Tampilan berakhir berisi A karena assignment messages tidak memeriksa generation/session. send() juga tidak memvalidasi identitas konteks saat respons tiba; dampak lintas proyek perlu E2E.

**Perbaikan:** capture projectId, sessionId, requestId; terapkan respons hanya jika konteks masih cocok. Batalkan fetch usang bila sesuai, tetapi abort browser tidak sama dengan membatalkan worker. Simpan hasil terlambat pada sesi asal.

**Acceptance:** respons keluar urutan tidak menimpa sesi baru; switch proyek dan dua tab browser tidak mencampur percakapan.

### Risiko AI tambahan — belum terbukti sebagai bug runtime

| ID | Prioritas audit | Bukti / kekhawatiran | Validasi yang diperlukan |
|---|---|---|---|
| R-AI-01 | P1 | Signature Ask consult tidak meneruskan cancel token; loop sinkron. stop-task berhubungan dengan Agent, belum terbukti membatalkan Ask. | Telusuri request ID Ask sampai worker; cancel pada provider lambat, command, dan retrieval. |
| R-AI-02 | P1 | Lock service melindungi map sesi, bukan seluruh giliran consult; build_task dan add user/assistant di luar lock per giliran. | Dua request sesi sama dengan hasil keluar urutan; gunakan queue/lock per sesi dan turn ID. |
| R-AI-03 | P1 | Parallel agent dan konsistensi write lintas task belum diverifikasi menyeluruh. | Dua task menulis file sama; cancel, checkpoint, rollback, dan SSE; audit lock/version precondition atau worktree per task. |
| R-AI-04 | P2 | Semantic/hybrid didaftarkan langsung; budget guard yang dibaca mencakup atlas/rig/read/search/command/list. | Pastikan budget total meliputi semantic/hybrid serta auto-context; uji query berulang dan zero-result. |
| R-AI-05 | P2 | Store JSON memakai lock per instance, temp path tetap, dan menelan OSError. | Fault injection disk penuh/permission error dan dua instance; status save harus dapat diamati. |
| R-AI-06 | P2 | Final model tanpa tool calls menutup loop sebagai DONE. | Pisahkan completed dan verified; tampilkan bukti checks serta not-run sesuai acceptance task. |

### Trust ekstensi adalah keputusan desain

PermissionPolicy sengaja mengizinkan tool ekstensi enabled sebelum matrix biasa. tests/test_extension_tool_permission.py secara eksplisit mengharapkan auto-ALLOW. Karena itu hal ini dicatat sebagai **risiko kontrak keamanan/desain**, bukan regresi terbukti. Tentukan apakah Enable berarti trust penuh atau capability terbatas, tampilkan konsekuensinya, dan jangan mengubah semantik diam-diam.

## 5. Optimasi yang disarankan

| ID | Area | Bukti / usulan | Ukuran keberhasilan |
|---|---|---|---|
| OPT-01 | Retry provider | Orchestrator mempunyai retry di atas infrastructure retry provider. Pada konfigurasi tiga retry per layer, kondisi tertentu dapat menghasilkan hingga 4×4=16 HTTP attempt per logical call; ini batas kondisional, bukan pengukuran produksi. Buat deadline dan total attempt budget bersama; bedakan error permanen, auth, serialisasi, timeout, rate limit. | Attempt per logical call, p95 latency, 429 rate, cancel latency, biaya/request. Error permanen tidak diulang. |
| OPT-02 | Thinking/reasoning | Factory memasang supports_thinking dan reasoning_budget; perlu contract test apakah tiap adapter menerjemahkan ke parameter wire yang benar. Tidak adanya keyword pada satu file bukan bukti seluruh fitur mati. | Matrix provider/model/capability; request payload tervalidasi, unsupported option terlihat, usage reasoning tercatat bila tersedia. |
| OPT-03 | Retrieval | Pertahankan cache per turn; tambahkan budget gabungan, dedup semantic/hybrid, serta invalidasi berdasarkan revisi file. | Input tokens/task, repeated-read ratio, cache hit, kualitas jawaban pada set tugas tetap. Tidak menetapkan penghematan persentase tanpa baseline. |
| OPT-04 | Event UI | Deep watch history dan reparsing seluruh output di useWorkbenchLiveEvents dapat bertambah mahal; array lokal juga bertambah tanpa batas pada composable yang dibaca. Gunakan cursor ID, buffer terbatas, dan pembaruan incremental. | Render latency, memory setelah task panjang, event lag; tidak menghapus history persisten yang masih diperlukan. |
| OPT-05 | Persistence Ask | Beberapa save per turn dan serialisasi seluruh JSON sesi dapat mahal. Pertimbangkan satu transaksi per turn, antrean write, atau SQLite bila multiworker diperlukan. | Write count/turn, p95 save, integritas setelah crash, tidak hilang silent. |
| OPT-06 | Maintainability | WorkbenchView 2.535 baris dan orchestrator 2.802 baris pada snapshot ini. Besar file adalah sinyal biaya perubahan, bukan bukti spaghetti. Pecah save/lifecycle/protocol/retry berdasarkan invariant. | Perubahan lintas fitur tidak memerlukan edit blok besar; contract tests menjaga perilaku. |
| OPT-07 | Shared attachment pipeline | Pembacaan gambar diduplikasi pada Agent dan Ask. Satukan reservasi slot, MIME/size, cancellation read, dan restore draft. | Satu set regression tests untuk kedua UI; batas konsisten dengan backend. |
| OPT-08 | Kualitas pengujian | editorModelLifecycle.test.mjs menyimulasikan sebagian logika save, tidak menjalankan CodeEditor.save asli. Karena itu async race dapat lolos walau helper test lulus. | Component/integration test memanggil jalur produksi dengan deferred promises; lint no-undef dan duplicate definitions. |

### Dead/orphan code dan fitur parsial

- **Dead code terbukti:** definisi loader pertama tertimpa loader kedua (AI-05).
- **Belum terbukti orphan:** releasePath hanya menghapus bookkeeping, tetapi WorkbenchView memanggil releaseModel pada jalur close. Jangan menyebutnya memory leak hanya dari membaca CodeEditor.
- **Belum terbukti dead feature:** modul MCP atau provider yang ada belum berarti semua jalur UI aktif; butuh tracing registry → API → UI → integration test sebelum dihapus.
- **Dokumentasi tidak konsisten:** README menyebut dukungan langsung Anthropic, sedangkan factory yang diperiksa tidak memuat tipe Anthropic khusus; akses melalui router mungkin tersedia. Verifikasi dan tulis jalur dukungannya.
- **README link rusak:** tautan LICENSE memakai file URI absolut mesin pengembang. Ganti ke LICENSE relatif.
- **Komentar stale:** komentar awal continuous loop menyebut hard stop tidak digunakan; implementasi memiliki emergency max_steps. Sinkronkan dokumentasi dengan perilaku, jangan menghapus guard yang sudah ada.

## 6. Rencana perbaikan dan gate rilis

### Tahap A — integritas dan batas AI (prioritas pertama)

1. AI-01: pisahkan metadata internal dan payload provider; contract test Agent + Ask.
2. AI-02: tegakkan batas read-only Ask atau transisi eksplisit ke Agent.
3. AI-03: cancel sebelum setiap retry dan wait interruptible.
4. BUG-02: save berbasis snapshot versi; jaga dirty dan close semantics.
5. BUG-01 dan BUG-06: perbaiki exception editor serta cache concurrency.

Gate: semua P1 terverifikasi lewat jalur produksi yang relevan; kegagalan provider dan pembatalan tidak menyebabkan write tak terotorisasi atau status sukses palsu.

### Tahap B — konsistensi sesi, event, dan input

1. AI-06, BUG-05, BUG-08: generation guard untuk sesi/socket/events.
2. BUG-07 dan BUG-09: isolasi cache serta identitas diagnostic.
3. AI-04, BUG-03: kontrak gambar dan pemulihan draft.
4. AI-05 dan BUG-04: loader tunggal dan diagnostik yang tidak salah menandai sintaks valid.

Gate: test respons terbalik, koneksi terputus, switch proyek, sesi restore, dan input batas lulus.

### Tahap C — efisiensi dan pengujian beban

1. Ukur baseline per provider: request, token, latency, retries, cancel latency.
2. Satukan retry budget dan kontrak thinking; lanjutkan retrieval dedup/budget.
3. Uji task panjang, output besar, dan dua task paralel yang menyentuh file sama.
4. Perbaiki persistence dan komponen besar hanya dengan contract tests yang menjaga perilaku.

### Matrix minimum pengujian AI

| Skenario | Agent | Ask Quick | Ask Investigate |
|---|---|---|---|
| Payload provider dengan event sink | JSON valid, telemetry lokal | Sama | Sama |
| Upaya tulis source | Sesuai policy/approval | Tidak tersedia | Ditolak/terisolasi termasuk interpreter |
| Provider 401 / invalid JSON | Fail jelas tanpa retry berulang | Sama | Sama |
| Provider 429 / timeout | Retry bounded dan cancellable | Sama | Sama |
| Cancel saat backoff / request | Tidak memulai action berikutnya | Kontrak cancel harus ditentukan dan diuji | Sama |
| Pergantian proyek / sesi | Task tetap pada root asal | Respons tidak menimpa sesi baru | Sama |
| Input gambar saja / >8 gambar | Kontrak UI/API konsisten | Sama | Sama |
| Retrieval berulang | Bounded sesuai mode | Map/semantic bounded | Source/command/semantic bounded |
| Final tanpa verifikasi | completed berbeda dari verified | Klaim jawaban sesuai bukti | Sama |
| Dua request bersamaan | File/task consistency | Giliran sesi konsisten | Sama |

## 7. Hasil verifikasi dan keterbatasan

- Sembilan BUG frontend/service direproduksi pada fungsi asli dengan mocks yang eksplisit.
- AI-01, AI-03, AI-04, AI-06 direproduksi pada fungsi asli atau gabungan metode aslinya.
- AI-02 dibuktikan pada guard/parser dan eksekusi argv temporer; full gateway/executor belum diuji.
- AI-05 dibuktikan melalui AST: method duplikat benar-benar ada.
- Tidak ada klaim seluruh npm test/pytest/build lulus. Tidak ada klaim provider live, app browser, atau versi dev telah diuji.
- Prioritas bersifat rekomendasi audit berdasarkan dampak; belum mengukur frekuensi pada pengguna nyata.
- Belum ada kode repo yang diubah, commit/PR dibuat, atau issue GitHub dipublikasikan. ID BUG/AI/R-AI/OPT dalam dokumen adalah ID laporan lokal.

## 8. Langkah reproduksi ulang

Ambil checkout commit yang sama, lalu tempatkan harness lampiran di root checkout. Harness memotong fungsi asli dan mengganti dependency terbatas; tidak menyalin ulang algoritme bug. Jalankan dengan Node.js dan Python 3. Untuk Python, ubah variabel R dari path audit sementara menjadi root checkout Anda. File JSON output dapat dialihkan ke direktori sementara yang diinginkan.

Harness ini berfungsi sebagai bukti audit, bukan pengganti component/E2E test. Reproduksi AI-02 hanya membuat file marker pada TemporaryDirectory, bukan pada repository. Tidak memerlukan kredensial atau koneksi model.


## Lampiran A — hasil harness

```text
BUG-01: original switchToFile syntax timer throws ReferenceError: lang is not defined
BUG-02: disk payload A; editor B; version 2 marked saved; dirty=false
BUG-03: TaskComposer.vue accepts 9 attachments despite limit 8
BUG-03: ConsultantChat.vue accepts 9 attachments despite limit 8
BUG-04 diagnostic javascript: []
BUG-04 diagnostic python: [{"id":"syntax-unclosed-2-1","text":"SyntaxError: unclosed '(' opened at line 2","type":"syntax","severity":"error","label":"Syntax Error","file":"a.py","line":2,"col":1,"source":"syntax-checker"}]
BUG-05: stale socket onclose clears current replacement socket reference
```

```text
BUG-06: 2 concurrent cache requests => one network call, both results [], filesLoading=true after completion
BUG-07: getCachedFiles(UNSEEN) returns active workspace B files
BUG-08: replacing event array with same-length new history skips file_modified B
BUG-09: two same-message diagnostics in distinct files collapse to one problem
```

```text
AI-01: actual _call_provider + _build_payload => Object of type function is not JSON serializable
AI-02: Consultant guard accepts Python file write; argv execution creates marker in disposable temp directory (full executor not invoked)
AI-05: duplicate _load_sessions_from_store definitions at lines [387, 407]; Python selects latter
AI-03: cancel during backoff still starts second provider call and returns success
AI-04: image-only Ask rejected before image parsing: Field 'message' wajib diisi dan tidak boleh kosong.
```

```text
AI-06: stale session A response overwrites newer session B messages
```

## Lampiran B — kode reproduksi

### repro.mjs

```javascript
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {validateCodeSyntax} from './web/frontend/src/services/diagnosticService.js';
const read=p=>fs.readFileSync('./web/frontend/src/'+p,'utf8');
const between=(s,a,b)=>s.slice(s.indexOf(a),s.indexOf(b,s.indexOf(a)));
const out=[];
const editor=read('components/CodeEditor.vue');
// Execute the original switchToFile function with browser/editor dependencies mocked.
const switchSource=between(editor,'async function switchToFile(', '\nasync function initEditor(');
let callback;
const env={loadSeq:0,loading:{},loadError:{},saveError:{},disposed:false,container:{value:{}},monaco:null,editor:{setModel(){},focus(){}},model:null,savedVersionId:null,currentPath:{},dirty:{},contentSub:null,markerSub:null,syntaxTimer:null,acquiredPaths:new Set(),props:{name:'a.js'},loadMonacoModule:async()=>({getMonaco:()=>({})}),detachModelSubscriptions(){},getEntry:()=>null,readFileContent:async()=>({content:'x'}),languageForFile:()=> 'javascript',getOrCreateModel:()=>({model:{getAlternativeVersionId:()=>1,getValue:()=> 'x',onDidChangeContent:()=>({})},savedVersionId:1}),emit(){},setTimeout(fn,delay){if(delay===200)callback=fn;return 1;},clearTimeout(){},nextTick:async()=>{},layout(){},validateCodeSyntax};
const sw=new Function(...Object.keys(env),switchSource+';return switchToFile;')(...Object.values(env));
await sw('a.js');
assert.throws(()=>callback(), /lang is not defined/);
out.push('BUG-01: original switchToFile syntax timer throws ReferenceError: lang is not defined');
// Real save() with deferred write, edit model before the write resolves.
const saveSource=between(editor,'async function save()', '\nfunction applyContent(');
let resolveWrite, persisted, version=1, value='A', marked;
const dirty={value:true};
const save=new Function('editor','saving','props','model','saveError','dirty','writeFileContent','markSaved','emit','savedVersionId',saveSource+';return save;')({}, {value:false},{path:'a.js'},{getValue:()=>value,getAlternativeVersionId:()=>version},{},dirty,async(p,v)=>{persisted=v;await new Promise(r=>resolveWrite=r);},(p,v)=>marked=v,()=>{},1);
const pending=save();value='B';version=2;resolveWrite();await pending;
assert.equal(persisted,'A');assert.equal(marked,2);assert.equal(dirty.value,false);
out.push('BUG-02: disk payload A; editor B; version 2 marked saved; dirty=false');
// Execute real attachment handler with deferred FileReader callbacks.
for (const file of ['TaskComposer.vue','ConsultantChat.vue']) {
 const source=between(read('components/'+file),'function onFilesPicked(', '\nfunction removeAttachment(');
 const readers=[];const attachments={value:[]};
 class Reader {constructor(){readers.push(this);}readAsDataURL(){this.result='data:image/png;base64,YQ==';}}
 const pick=new Function('attachments','MAX_ATTACHMENTS','ACCEPTED_TYPES','FileReader','attachError','error',source+';return onFilesPicked;')(attachments,8,['image/png'],Reader,{},{ });
 pick({target:{files:Array.from({length:9},(_,i)=>({type:'image/png',name:String(i)}))}});
 readers.forEach(r=>r.onload());assert.equal(attachments.value.length,9);
 out.push('BUG-03: '+file+' accepts 9 attachments despite limit 8');
}
// Actual diagnostic code on valid multi-line JS and Python strings.
for (const [lang,code,path] of [['javascript','const s = `hello\nworld`;\nconst x = 1;','a.js'],['python','s = """\n(\n"""','a.py']]) {
 const errors=validateCodeSyntax(code,lang,path);
 if(lang==='python')assert.ok(errors.length>0);
 out.push('BUG-04 diagnostic '+lang+': '+JSON.stringify(errors));
}
// Old terminal socket onclose races with replacement socket.
const terminal=read('components/TerminalView.vue');
const socketSource=between(terminal,'function initPtySocket()', '\nwatch(');
const sockets=[];class Socket{constructor(){sockets.push(this);}}
const init=new Function('window','localStorage','props',`let isBrowser=true,socket=null,fitAddon=null,term=null;function syncDimensions(){};${socketSource};return {init:initPtySocket,reset:()=>socket=null,get:()=>socket};`)({location:{protocol:'http:',host:'localhost'},WebSocket:Socket},{getItem:()=>''},{projectId:'a'});
init.init();const old=sockets[0];init.reset();init.init();assert.ok(init.get());old.onclose();assert.equal(init.get(),null);
out.push('BUG-05: stale socket onclose clears current replacement socket reference');
fs.writeFileSync('/tmp/aegis-audit/repro-results.json',JSON.stringify(out,null,2));console.log(out.join('\n'));

```

### repro-extra.mjs

```javascript
import fs from 'node:fs';
import assert from 'node:assert/strict';
const read=p=>fs.readFileSync('./web/frontend/src/'+p,'utf8');
const results=[];
const cacheCode=read('services/fileCacheService.js').replace(/^import .*;$/gm,'').replace(/export /g,'');
let resolveList;let calls=0;
const cache=new Function('ref','listFiles',cacheCode+';return {setWorkspaceProject,fetchWorkspaceFiles,getCachedFiles,filesLoading};')(v=>({value:v}),async()=>{calls++;await new Promise(r=>resolveList=r);return {entries:[{path:'src/a.js'}]};});
cache.setWorkspaceProject('A');
const p1=cache.fetchWorkspaceFiles();const p2=cache.fetchWorkspaceFiles();resolveList();
const values=await Promise.all([p1,p2]);
assert.equal(calls,1);assert.deepEqual(values,[[],[]]);assert.equal(cache.filesLoading.value,true);
results.push('BUG-06: 2 concurrent cache requests => one network call, both results [], filesLoading=true after completion');
cache.setWorkspaceProject('B');
const pending=cache.fetchWorkspaceFiles();resolveList();await pending;
assert.deepEqual(cache.getCachedFiles('UNSEEN'),['src/a.js']);
results.push('BUG-07: getCachedFiles(UNSEEN) returns active workspace B files');
// Instantiate actual composable using tiny ref/computed/watch adapters.
const liveCode=read('composables/useWorkbenchLiveEvents.js').replace(/^import .*;$/gm,'').replace(/export /g,'');
const callbacks=[];const props={activityEvents:[],outputLines:[],problems:[]};const modified=[];
const use=new Function('ref','computed','watch','classifyDiagnostic',liveCode+';return useWorkbenchLiveEvents;')(v=>({value:v}),f=>({get value(){return f();}}),(source,fn)=>callbacks.push(fn),()=>({type:'info'}));
const live=use(props,{onFileModified:p=>modified.push(p)});
const evt=p=>({type:'file_modified',payload:{path:p}});
callbacks[0]([evt('A')]);callbacks[0]([evt('B')]);assert.deepEqual(modified,['A']);
results.push('BUG-08: replacing event array with same-length new history skips file_modified B');
props.problems=[{text:'Syntax error',file:'A.py',line:1},{text:'Syntax error',file:'B.py',line:2}];
assert.equal(live.effectiveProblems.value.length,1);
results.push('BUG-09: two same-message diagnostics in distinct files collapse to one problem');
fs.writeFileSync('/tmp/aegis-audit/repro-extra-results.json',JSON.stringify(results,null,2));console.log(results.join('\n'));

```

### repro-ai.py

```python
import ast,json,types,tempfile,subprocess,sys
from pathlib import Path
R=Path('/tmp/aegis-audit')
results=[]
def extract(path,names,cls=None):
    tree=ast.parse((R/path).read_text())
    nodes=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls).body if cls else tree.body
    wanted=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+wanted,type_ignores=[])
    return compile(ast.fix_missing_locations(module),str(path),'exec')
ns={}
exec(extract('src/agent_ai/providers/openai_compatible.py',['_build_payload'],'OpenAICompatibleProvider'),ns)
class Opt:
    def __init__(self,temperature=None,max_tokens=None,model=None,extra=None):
        self.temperature=temperature;self.max_tokens=max_tokens;self.model=model;self.extra=extra or {}
class Provider:
    config=types.SimpleNamespace(model='test');supports_model_discovery=False;send_model_field=True
    _build_messages=lambda *a:[]
    _to_openai_message=lambda self,m:m
    _encode_message_tool_names=lambda self,m:m
    _build_tool_definitions=lambda *a:[]
    def generate(self,**kw):
        payload=ns['_build_payload'](self,None,kw['messages'],kw['options'])
        json.dumps(payload)
    def normalize_response(self,r):return r
scope={'GenerateOptions':Opt}
exec(extract('src/agent_ai/core/orchestrator.py',['_call_provider'],'AgentOrchestrator'),scope)
agent=types.SimpleNamespace(event_sink=lambda *a:None,execution_policy=None,executor=types.SimpleNamespace(workspace_root=None),response_log=None,provider=Provider(),tool_choice=None)
try:
    scope['_call_provider'](agent,messages=[],options=None,tools=None,round_index=1)
    raise AssertionError('expected JSON serialization error')
except TypeError as e:
    assert 'serializable' in str(e);results.append('AI-01: actual _call_provider + _build_payload => '+str(e))
# Actual command parser and Consultant guard. Only create a harmless temporary marker.
ns2={'ToolValidationError':ValueError}
exec(extract('src/agent_ai/tools/terminal.py',['_split_command']),ns2)
tree=ast.parse((R/'src/agent_ai/consultant/tools.py').read_text())
constants=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['_DESTRUCTIVE_GIT_SUBCOMMANDS','_FILE_MUTATING_COMMANDS'] for t in n.targets)]
exec(compile(ast.Module(body=constants,type_ignores=[]),'constants','exec'),ns2)
exec(extract('src/agent_ai/consultant/tools.py',['_has_redirect_outside_quotes','consultant_command_violation']),ns2)
with tempfile.TemporaryDirectory() as d:
    command=f'''{sys.executable} -c "open('audit-marker.txt','w').write('audit')"'''
    assert ns2['consultant_command_violation'](command) is None
    subprocess.run(ns2['_split_command'](command),cwd=d,check=True)
    assert Path(d,'audit-marker.txt').read_text()=='audit'
results.append('AI-02: Consultant guard accepts Python file write; argv execution creates marker in disposable temp directory (full executor not invoked)')
# Inspect duplicate definitions as AST evidence, no import/dependency assumptions.
t=ast.parse((R/'src/agent_ai/consultant/service.py').read_text())
c=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='ConsultantService')
d=[n.lineno for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='_load_sessions_from_store']
assert len(d)==2
results.append('AI-05: duplicate _load_sessions_from_store definitions at lines '+str(d)+'; Python selects latter')
Path('/tmp/aegis-audit/repro-ai-results.json').write_text(json.dumps(results,indent=2));print('\n'.join(results))
# Retry cancellation during backoff: execute original helper with fake sleeping (no real delay).
state={'cancel':False,'calls':0}
def call(**kw):
    state['calls']+=1
    if state['calls']==1:raise RuntimeError('transient')
    return 'reply-after-cancel'
scope2={'emit_event':lambda *a:None,'_redact_credentials':str,'time':types.SimpleNamespace(sleep=lambda s:state.update(cancel=True))}
exec(extract('src/agent_ai/core/orchestrator.py',['_generate_with_retry'],'AgentOrchestrator'),scope2)
a=types.SimpleNamespace(provider=types.SimpleNamespace(name='fake'),_model_name=lambda:'fake',_api_retry_policy=lambda:(1,1),_next_llm_round=lambda:1,_call_provider=call,event_sink=None,_cancel_requested=lambda:state['cancel'],_cancel_reason=lambda:'user')
res=scope2['_generate_with_retry'](a,loop=types.SimpleNamespace(cancel=lambda r:None),messages=[],options=None,tools=None)
assert state['calls']==2 and res=='reply-after-cancel'
results.append('AI-03: cancel during backoff still starts second provider call and returns success')
# Gateway accepts only nonempty text even if images exist.
ns3={'ValidationError':ValueError}
exec(extract('web/django_app/api/services.py',['consult'],'GatewayService'),ns3)
try:
    ns3['consult'](None,'',images=[{'data':'YQ==','mime_type':'image/png'}])
    raise AssertionError('expected message validation error')
except ValueError as e:
    results.append('AI-04: image-only Ask rejected before image parsing: '+str(e))
Path('/tmp/aegis-audit/repro-ai-results.json').write_text(json.dumps(results,indent=2));print('\n'.join(results[-2:]))

```

### repro-ask.mjs

```javascript
import fs from 'node:fs';
import assert from 'node:assert/strict';
const src=fs.readFileSync('./web/frontend/src/components/ConsultantChat.vue','utf8');
const start=src.indexOf('async function resumeSessionFromId(');
const fn=src.slice(start,src.indexOf('\nasync function createNewSession',start));
const messages={value:[]},waiters={};
const resume=new Function('getConsultantSession','props','messages','scrollToBottom',fn+';return resumeSessionFromId;')((id)=>new Promise(r=>waiters[id]=r),{projectId:'P'},messages,()=>{});
const a=resume('A');const b=resume('B');waiters.B({turns:[{role:'user',text:'B'}]});await b;waiters.A({turns:[{role:'user',text:'A'}]});await a;
assert.equal(messages.value[0].text,'A');
const text='AI-06: stale session A response overwrites newer session B messages';
fs.writeFileSync('/tmp/aegis-audit/repro-ask-results.json',JSON.stringify([text]));console.log(text);

```

## Lampiran C — sumber yang diperiksa (permalink snapshot)

- [README.md](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/README.md)
- [src/agent_ai/consultant/guard.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/consultant/guard.py)
- [src/agent_ai/consultant/models.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/consultant/models.py)
- [src/agent_ai/consultant/policy.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/consultant/policy.py)
- [src/agent_ai/consultant/service.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/consultant/service.py)
- [src/agent_ai/consultant/store.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/consultant/store.py)
- [src/agent_ai/consultant/tools.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/consultant/tools.py)
- [src/agent_ai/core/executor.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/core/executor.py)
- [src/agent_ai/core/orchestrator.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/core/orchestrator.py)
- [src/agent_ai/permission/classifier.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/permission/classifier.py)
- [src/agent_ai/permission/policy.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/permission/policy.py)
- [src/agent_ai/providers/antigravity.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/providers/antigravity.py)
- [src/agent_ai/providers/base.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/providers/base.py)
- [src/agent_ai/providers/factory.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/providers/factory.py)
- [src/agent_ai/providers/openai_compatible.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/providers/openai_compatible.py)
- [src/agent_ai/providers/retry.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/providers/retry.py)
- [src/agent_ai/runtime/runtime.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/runtime/runtime.py)
- [src/agent_ai/tools/terminal.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/src/agent_ai/tools/terminal.py)
- [tests/test_extension_tool_permission.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/tests/test_extension_tool_permission.py)
- [web/django_app/api/services.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/django_app/api/services.py)
- [web/django_app/api/views.py](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/django_app/api/views.py)
- [web/frontend/package.json](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/package.json)
- [web/frontend/src/api.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/api.js)
- [web/frontend/src/components/CodeEditor.vue](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/CodeEditor.vue)
- [web/frontend/src/components/ConsultantChat.vue](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/ConsultantChat.vue)
- [web/frontend/src/components/TaskComposer.vue](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/TaskComposer.vue)
- [web/frontend/src/components/TerminalView.vue](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/components/TerminalView.vue)
- [web/frontend/src/composables/useWorkbenchLiveEvents.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/composables/useWorkbenchLiveEvents.js)
- [web/frontend/src/composables/useWorkbenchTabs.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/composables/useWorkbenchTabs.js)
- [web/frontend/src/editorModelLifecycle.test.mjs](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/editorModelLifecycle.test.mjs)
- [web/frontend/src/pages/WorkbenchView.vue](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/pages/WorkbenchView.vue)
- [web/frontend/src/services/diagnosticService.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/diagnosticService.js)
- [web/frontend/src/services/editorTabsService.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/editorTabsService.js)
- [web/frontend/src/services/fileCacheService.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/fileCacheService.js)
- [web/frontend/src/services/monacoModelRegistry.js](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/services/monacoModelRegistry.js)
- [web/frontend/src/workspaceIsolation.test.mjs](https://github.com/aditlab-code/aegiscode/blob/d64cb4fd6140b07fa8eb34ba23fcc9b7ad218cbc/web/frontend/src/workspaceIsolation.test.mjs)
