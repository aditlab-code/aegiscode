# Milestone 1 (Tahap A) — Integritas Inti dan Batas Aman AI

Dokumen ini memuat spesifikasi teknis, verifikasi kode, usulan perbaikan, dan kriteria penerimaan untuk seluruh temuan berprioritas tinggi (**P1**) pada Tahap A.

---

## 1. Ikhtisar Milestone 1

- **Tujuan**: Menjamin integritas data saat operasi simpan editor, mencegah kegagalan serialisasi pada pemanggilan model AI, membatasi eksekusi mutatif pada mode read-only Ask, serta memperbaiki konkurensi cache berkas.
- **Tingkat Prioritas**: P1 (Kritis — Wajib selesai sebelum rilis berikutnya).
- **Target Item**: 6 Temuan (AI-01, AI-02, AI-03, BUG-01, BUG-02, BUG-06).

---

## 2. Rincian Isu dan Spesifikasi Teknis

### AI-01 — Metadata Internal Masuk ke JSON Request Provider

- **Prioritas**: P1
- **Domain**: Backend AI / Provider Adapter
- **Berkas Sumber**:
  - [src/agent_ai/core/orchestrator.py#L1735-L1753](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/core/orchestrator.py#L1735-L1753)
  - [src/agent_ai/providers/openai_compatible.py#L273](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/providers/openai_compatible.py#L273)
- **Akar Masalah**:
  Metode `AgentOrchestrator._call_provider` menambahkan fungsi callback `self.event_sink`, `self.execution_policy`, dan `workspace_root` ke dalam objek `GenerateOptions.extra`. Pada adapter `OpenAICompatibleProvider._build_payload`, kode mengeksekusi `payload.update(opts.extra or {})`. Saat payload tersebut diserialisasi ke JSON untuk HTTP request (`json.dumps(payload)`), Python melempar `TypeError: Object of type function is not JSON serializable` karena objek fungsi tidak dapat diserialisasi ke format JSON standar.
- **Dampak Lapangan**:
  Setiap pemanggilan model yang menggunakan adapter OpenAI-compatible dengan event sink aktif akan langsung gagal secara deterministik sebelum request dikirimkan ke jaringan.
- **Usulan Perbaikan**:
  1. Pisahkan `runtime_context` dari parameter provider murni pada `GenerateOptions`.
  2. Terapkan mekanisme allowlist atau pemfilteran eksplisit pada adapter sebelum memperbarui payload HTTP; jangan izinkan kunci non-wire seperti `event_sink`, `execution_policy`, `mode`, atau `workspace_root` masuk ke body permintaan HTTP.
- **Acceptance Criteria**:
  - Pemanggilan model melalui adapter OpenAI-compatible berhasil menserialisasi payload JSON tanpa error.
  - Callback event telemetry lokal tetap berjalan normal di tingkat runtime.
  - Body JSON yang dikirimkan ke endpoint provider hanya memuat parameter API yang sah.

---

### AI-02 — Batas Read-Only Ask Investigate Tidak Ditegakkan Terhadap Command Interpreter

- **Prioritas**: P1
- **Domain**: Backend AI / Consultant Security Guard
- **Berkas Sumber**:
  - [src/agent_ai/consultant/tools.py#L156-L187](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/consultant/tools.py#L156-L187)
  - [src/agent_ai/tools/terminal.py](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/tools/terminal.py)
- **Akar Masalah**:
  Fungsi `consultant_command_violation` hanya memverifikasi nama program biner pertama dari daftar statis `_FILE_MUTATING_COMMANDS` (`rm`, `mv`, `del`, dsb.) dan operator redirect `>`. Namun, pemanggilan interpreter skrip seperti `python -c "open('file.txt', 'w').write(...)"` atau `node -e "..."` dieksekusi secara native melalui `RunCommandTool.execute()` tanpa isolasi berkas atau sandbox OS read-only.
- **Dampak Lapangan**:
  Mode Ask Investigate yang diklaim sebagai mode read-only dapat memodifikasi atau merusak berkas kode proyek melalui eksekusi perintah interpreter, melanggar kontrak keamanan read-only.
- **Usulan Perbaikan**:
  1. Batasi eksekusi command pada mode Ask hanya pada perintah diagnostik yang telah divalidasi (misalnya `git status`, `git diff`, `pytest`, `npm test`) dengan argumen terkontrol.
  2. Tolak evaluasi ekspresi inline arbitrer (`-c`, `-e`, skrip kustom) yang tidak memiliki jaminan read-only, atau sediakan transisi eksplisit ke mode Agent jika modifikasi berkas diperlukan.
- **Acceptance Criteria**:
  - Perintah inline interpreter yang mencoba membuat atau menulis berkas pada direktori kerja ditolak sebelum eksekusi.
  - Perintah diagnostik sah tetap dapat dieksekusi dan mengembalikan output teks.
  - Perubahan berkas (git diff) pada direktori kerja proyek tetap kosong setelah giliran Ask selesai.

---

### AI-03 — Pembatalan Saat Jeda Backoff Tetap Menjalankan Provider Call Berikutnya

- **Prioritas**: P1
- **Domain**: Backend AI / Orchestrator Retry Lifecycle
- **Berkas Sumber**:
  - [src/agent_ai/core/orchestrator.py#L1872-L1919](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/core/orchestrator.py#L1872-L1919)
- **Akar Masalah**:
  Pada metode `AgentOrchestrator._generate_with_retry`, status pembatalan `self._cancel_requested()` hanya diperiksa di dalam blok `except Exception`. Setelah jeda `time.sleep(failed_sleep)` selesai, loop berlanjut ke attempt berikutnya tanpa memeriksa kembali apakah pembatalan telah diajukan selama jeda tersebut, atau sebelum memanggil `self._call_provider`. Jika pemanggilan berikutnya berhasil, fungsi mengembalikan respons sukses.
- **Dampak Lapangan**:
  Tugas yang telah dibatalkan oleh pengguna saat terjadi error transien tetap menjalankan pemanggilan provider tambahan, memboroskan kuota token dan berpotensi mengubah state sistem setelah pembatalan.
- **Usulan Perbaikan**:
  1. Tambahkan pemeriksaan `if self._cancel_requested(): return None` tepat sebelum pemanggilan `self._call_provider` pada setiap iterasi attempt.
  2. Gunakan mekanisme jeda yang dapat diinterupsi atau periksa flag pembatalan segera setelah `time.sleep`.
  3. Pastikan status cancelled tidak dapat berubah menjadi status success karena respons yang terlambat tiba.
- **Acceptance Criteria**:
  - Pembatalan selama jeda retry langsung menghentikan proses tanpa pemanggilan provider berikutnya.
  - Jumlah pemanggilan provider tercatat tepat 1 jika pembatalan terjadi pada jeda pertama.

---

### BUG-01 — Pemeriksaan Sintaks Editor Melempar ReferenceError

- **Prioritas**: P1
- **Domain**: Frontend Editor / Monaco Lifecycle
- **Berkas Sumber**:
  - [web/frontend/src/components/CodeEditor.vue#L135-L163](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/CodeEditor.vue#L135-L163)
- **Akar Masalah**:
  Pada fungsi `switchToFile`, variabel `lang` dideklarasikan menggunakan `const` di dalam blok `if (!entry)`. Namun, pada fungsi timer `runSyntaxCheck`, pemanggilan `validateCodeSyntax(textVal, lang, targetPath)` mencoba membaca variabel `lang` tersebut. Jika model Monaco sudah ada di cache (`entry` tidak null) atau saat timer dijalankan, scope variabel tidak dapat dijangkau dan memicu `ReferenceError: lang is not defined`.
- **Dampak Lapangan**:
  Pemeriksaan sintaks editor gagal secara senyap atau melempar unhandled exception di konsol browser, menghentikan penandaan diagnostik pada editor.
- **Usulan Perbaikan**:
  1. Hitung variabel `lang` di tingkat scope utama fungsi `switchToFile` sebelum percabangan model.
  2. Pastikan timer `syntaxTimer` dibersihkan jika tab berganti atau komponen di-unmount.
- **Acceptance Criteria**:
  - Membuka berkas baru maupun berkas yang sudah dimuat sebelumnya tidak melempar ReferenceError.
  - Marker sintaks Monaco melekat pada model dan berkas yang sesuai.

---

### BUG-02 — Save Menandai Versi yang Belum Ditulis Sebagai Tersimpan

- **Prioritas**: P1
- **Domain**: Frontend Editor / Data Persistence
- **Berkas Sumber**:
  - [web/frontend/src/components/CodeEditor.vue#L281-L298](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/CodeEditor.vue#L281-L298)
- **Akar Masalah**:
  Pada fungsi `save()`, konten teks diambil sebelum operasi asinkron `await writeFileContent(targetPath, value)`. Namun, pengambilan ID versi tersimpan (`targetModel.getAlternativeVersionId()`) dan penetapan `dirty.value = false` baru dilakukan setelah penulisan disk selesai. Jika pengguna mengetik teks baru saat permintaan HTTP simpan sedang berjalan lambat, versi baru tersebut dianggap sudah tersimpan dan indikator dirty direset ke `false`.
- **Dampak Lapangan**:
  Perubahan kode terbaru yang diketik pengguna selama proses simpan tidak tertulis ke disk, dan penutupan tab tidak memunculkan konfirmasi simpan, mengakibatkan kehilangan data kode.
- **Usulan Perbaikan**:
  1. Ambil snapshot versi ID bersamaan dengan pengambilan konten sebelum `await writeFileContent`.
  2. Tandai hanya versi ID snapshot yang telah tersimpan.
  3. Setelah simpan selesai, evaluasi ulang status `dirty.value` berdasarkan perbandingan versi model saat ini dengan versi snapshot yang baru saja disimpan.
- **Acceptance Criteria**:
  - Mengetik saat proses simpan lambat tetap mempertahankan status `dirty: true` setelah respons simpan kembali.
  - Berkas tidak kehilangan perubahan terbaru saat tab ditutup setelah operasi simpan parsial.

---

### BUG-06 — Dedup Permintaan Cache Membuat Hasil Dibuang dan Loading Macet

- **Prioritas**: P1
- **Domain**: Frontend Cache / State Concurrency
- **Berkas Sumber**:
  - [web/frontend/src/services/fileCacheService.js#L91-L132](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/services/fileCacheService.js#L91-L132)
- **Akar Masalah**:
  Pada fungsi `fetchWorkspaceFiles`, variabel `requestSeq` dinaikkan (`++requestSeq`) sebelum memeriksa apakah `inflightPromise` sudah ada. Pemanggilan kedua akan menaikkan `requestSeq` lagi, membuat `thisSeq` milik pemanggilan pertama tidak lagi sama dengan `requestSeq`. Akibatnya, pemanggilan pertama menganggap dirinya kedaluwarsa dan mengembalikan array kosong `[]`, serta blok `finally` melewatkan pengaturan `filesLoading.value = false`.
- **Dampak Lapangan**:
  Pemanggilan ganda daftar berkas secara simultan (misalnya saat aplikasi pertama kali dimuat) menyebabkan pohon berkas gagal tampil dan indikator loading berputar tanpa henti.
- **Usulan Perbaikan**:
  1. Periksa `inflightPromise` sebelum menaikkan nomor urut `requestSeq`.
  2. Pastikan generation counter hanya bertambah saat memulai request jaringan baru atau saat invalidasi eksplisit.
  3. Pastikan `filesLoading` selalu direset ke `false` setelah promise selesai.
- **Acceptance Criteria**:
  - Dua pemanggilan bersamaan ke `fetchWorkspaceFiles` mengembalikan daftar berkas yang identik dari satu request jaringan.
  - Nilai `filesLoading.value` kembali ke `false` setelah proses pemuatan berkas selesai.

---

## 3. Gerbang Penyelesaian (Gate A Checklist)

- [ ] AI-01: Contract test adapter OpenAI-compatible dengan mock callback lulus tanpa serialisasi error.
- [ ] AI-02: Tes eksekusi command pada mode Ask menolak script interpretasi mutatif.
- [ ] AI-03: Tes pembatalan saat jeda retry memastikan hanya 1 pemanggilan provider yang dieksekusi.
- [ ] BUG-01: Tes unit Monaco switchToFile bebas dari ReferenceError.
- [ ] BUG-02: Tes async save lambat membuktikan teks ketikan baru tetap mempertahankan status dirty.
- [ ] BUG-06: Tes konkuren `fetchWorkspaceFiles` mengembalikan hasil utuh dan mereset status loading.
