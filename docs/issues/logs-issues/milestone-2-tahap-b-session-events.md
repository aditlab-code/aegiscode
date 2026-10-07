# Milestone 2 (Tahap B) — Konsistensi Sesi, Live Events, dan Validasi Input

Dokumen ini memuat spesifikasi teknis, verifikasi kode, usulan perbaikan, dan kriteria penerimaan untuk seluruh temuan prioritas menengah (**P2**) pada Tahap B.

---

## 1. Ikhtisar Milestone 2

- **Tujuan**: Memastikan keandalan isolasi sesi percakapan, kebersihan koneksi socket terminal, ketahanan streaming event live, pemisahan isolasi cache multi-proyek, ketepatan parser diagnostik sintaks, dan konsistensi kontrak input multimodal antara frontend dan backend.
- **Tingkat Prioritas**: P2 (Stabilitas, Konsistensi State, & Keandalan Alur Kerja).
- **Target Item**: 9 Temuan (AI-04, AI-05, AI-06, BUG-03, BUG-04, BUG-05, BUG-07, BUG-08, BUG-09).

---

## 2. Rincian Isu dan Spesifikasi Teknis

### AI-04 — Inkonsistensi Kontrak Input Multimodal Teks dan Gambar

- **Prioritas**: P2
- **Domain**: Fullstack / Validasi API
- **Berkas Sumber**:
  - [web/frontend/src/components/ConsultantChat.vue#L580-L593](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/ConsultantChat.vue#L580-L593)
  - [web/django_app/api/services.py#L2987-L2989](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/django_app/api/services.py#L2987-L2989)
- **Akar Masalah**:
  Komponen `ConsultantChat.vue` mengizinkan tombol kirim aktif jika pengguna melampirkan gambar walaupun input teks kosong (`if ((!text && !pending.length) || sending.value) return;`). Selain itu, draft teks dan daftar lampiran langsung dikosongkan sebelum request selesai. Di sisi backend, metode `GatewayService.consult` melempar `ValidationError("Field 'message' wajib diisi dan tidak boleh kosong.")` bila parameter teks kosong.
- **Dampak Lapangan**:
  Pengguna yang mengirim pertanyaan hanya berupa gambar mengalami kegagalan request, dan lampiran gambar yang sudah dipilih hilang dari antarmuka tanpa bisa dipulihkan.
- **Usulan Perbaikan**:
  1. Sepakati kontrak apakah input gambar tanpa teks diizinkan dengan menyertakan teks prompt default otomatis (misalnya "Jelaskan gambar ini"), atau cegah pengiriman di frontend jika teks kosong dengan pesan validasi yang jelas.
  2. Pertahankan draft teks dan lampiran sampai proses HTTP dinyatakan berhasil, serta pulihkan tampilan jika terjadi kegagalan request.
- **Acceptance Criteria**:
  - Pengiriman prompt dengan gambar menghasilkan respon yang valid atau memberikan pesan penolakan yang ramah sebelum draft terhapus.
  - Kegagalan pengiriman tidak menghapus berkas lampiran yang telah diunggah.

---

### AI-05 — Definisi Metode Duplikat Menimpa Pemasangan Callback Persistensi

- **Prioritas**: P2
- **Domain**: Backend AI / Consultant Service Persistence
- **Berkas Sumber**:
  - [src/agent_ai/consultant/service.py#L387-L423](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/consultant/service.py#L387-L423)
- **Akar Masalah**:
  Kelas `ConsultantService` memiliki dua deklarasi fungsi `_load_sessions_from_store` berturut-turut pada baris 387 dan baris 407. Python secara otomatis menimpa fungsi pertama dengan fungsi kedua. Pada fungsi kedua, baris `session._on_change = persist_cb` tidak disertakan, sehingga callback persistensi tidak terpasang pada sesi hasil pemulihan (restore).
- **Dampak Lapangan**:
  Sesi yang dipulihkan saat startup aplikasi tidak memiliki mekanisme auto-save write-through saat terjadi perubahan parsial pada sesi tersebut.
- **Usulan Perbaikan**:
  1. Hapus deklarasi duplikat pada baris 407 dan pertahankan deklarasi lengkap yang memasang callback `_on_change`.
  2. Tambahkan aturan linter Python untuk mendeteksi penimpaan nama metode duplikat di kelas.
- **Acceptance Criteria**:
  - Hanya ada satu definisi metode `_load_sessions_from_store`.
  - Sesi yang dipulihkan dari penyimpanan disk memiliki callback persistensi aktif.

---

### AI-06 — Respons Sesi Lama Menimpa Sesi Obrolan Baru

- **Prioritas**: P2
- **Domain**: Frontend Chat / Async Race Guard
- **Berkas Sumber**:
  - [web/frontend/src/components/ConsultantChat.vue#L165-L188](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/ConsultantChat.vue#L165-L188)
- **Akar Masalah**:
  Fungsi `resumeSessionFromId(id)` melakukan pemanggilan asinkron `await getConsultantSession(id, ...)`. Hasil sesi langsung dimasukkan ke `messages.value` tanpa memverifikasi apakah `id` tersebut masih merupakan sesi aktif yang diminta pengguna saat promise terselesaikan.
- **Dampak Lapangan**:
  Jika pengguna berpindah dari sesi A ke sesi B secara cepat, dan permintaan sesi A selesai belakangan dibandingkan sesi B, riwayat obrolan sesi A akan menimpa tampilan sesi B.
- **Usulan Perbaikan**:
  1. Gunakan generation sequence token atau periksa `if (id !== props.activeSessionId) return;` setelah pemanggilan `await getConsultantSession`.
  2. Abaikan respons usang yang tiba di luar urutan aktif.
- **Acceptance Criteria**:
  - Berpindah sesi secara cepat tidak mencampuradukkan riwayat pesan antar-sesi.
  - Tampilan selalu mencerminkan data dari sesi yang sedang aktif dipilih.

---

### BUG-03 — Batas Maksimum Lampiran Terlewati Oleh FileReader Asinkron

- **Prioritas**: P2
- **Domain**: Frontend Input / Task & Chat Composer
- **Berkas Sumber**:
  - [web/frontend/src/components/TaskComposer.vue#L101-L130](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/TaskComposer.vue#L101-L130)
  - [web/frontend/src/components/ConsultantChat.vue#L497-L526](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/ConsultantChat.vue#L497-L526)
- **Akar Masalah**:
  Pengecekan jumlah lampiran `attachments.value.length >= MAX_ATTACHMENTS` dilakukan di dalam loop sebelum `FileReader.readAsDataURL` selesai. Karena proses pembacaan berkas bersifat asinkron, panjang array belum bertambah saat iterasi berikutnya dievaluasi.
- **Dampak Lapangan**:
  Pengguna dapat memilih lebih dari 8 berkas gambar secara bersamaan (batch selection), dan seluruh berkas akan masuk ke daftar lampiran melewati batas yang ditentukan.
- **Usulan Perbaikan**:
  1. Lakukan pemotongan jumlah berkas yang dipilih di awal (`files.slice(0, MAX_ATTACHMENTS - attachments.value.length)`).
  2. Terapkan slot reservasi tertunda agar pembacaan batch tidak melampaui batas kuota.
- **Acceptance Criteria**:
  - Pemilihan batch lebih dari 8 gambar hanya memproses maksimal 8 gambar pertama.
  - Upaya penambahan gambar berikutnya menampilkan pesan peringatan kuota penuh.

---

### BUG-04 — Diagnostik Palsu Pada String Multiline Python dan Template Literal

- **Prioritas**: P2
- **Domain**: Frontend Linter / Syntax Scanner
- **Berkas Sumber**:
  - [web/frontend/src/services/diagnosticService.js#L627-L681](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/services/diagnosticService.js#L627-L681)
- **Akar Masalah**:
  Scanner tanda kurung mendeklarasikan status kutip `let inQuote = null;` di dalam loop per baris, sehingga status kutip ter-reset setiap baris baru. Karakter kurung yang berada di baris kedua pada triple-quoted string Python (`"""`) atau template literal JavaScript (`` ` ``) dianggap sebagai kode aktif dan memicu `SyntaxError: unclosed '('`.
- **Dampak Lapangan**:
  Kode Python atau JavaScript yang sepenuhnya valid ditandai dengan garis merah error sintaks palsu pada Monaco Editor.
- **Usulan Perbaikan**:
  1. Pertahankan status konteks kutip multiline (triple quotes dan template literals) lintas iterasi baris.
  2. Lewati karakter kurung di dalam blok komentar dan string multiline.
- **Acceptance Criteria**:
  - Kode Python dengan string multiline valid tidak menghasilkan SyntaxError palsu.
  - Tanda kurung yang benar-benar tidak tertutup pada kode nyata tetap terdeteksi dengan tepat.

---

### BUG-05 — Callback Penutupan Socket Lama Menghapus Referensi Socket Baru

- **Prioritas**: P2
- **Domain**: Frontend Terminal / WebSocket Lifecycle
- **Berkas Sumber**:
  - [web/frontend/src/components/TerminalView.vue#L108-L132](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/components/TerminalView.vue#L108-L132)
- **Akar Masalah**:
  Variabel `socket` dipakai bersama di tingkat modul/komponen. Pada saat pergantian proyek, socket lama ditutup dan socket baru segera diinisialisasi. Ketika event `onclose` milik socket lama tiba belakangan, handler menjalankan `socket = null;` tanpa memeriksa apakah socket tersebut masih merupakan instance aktif.
- **Dampak Lapangan**:
  Terminal berhenti merespons input dan event resize karena variabel socket aktif terhapus menjadi null.
- **Usulan Perbaikan**:
  1. Simpan referensi socket lokal di dalam closure inisialisasi (`const currentSocket = ...`).
  2. Hanya lakukan pembersihan `socket = null` jika `socket === currentSocket`.
- **Acceptance Criteria**:
  - Pergantian proyek cepat tidak memutus referensi socket terminal proyek baru.
  - Input dan resize terminal tetap berfungsi normal setelah pergantian workspace.

---

### BUG-07 — Cache Miss Proyek Tertentu Mengembalikan Berkas Proyek Aktif Lain

- **Prioritas**: P2
- **Domain**: Frontend Cache / Workspace Isolation
- **Berkas Sumber**:
  - [web/frontend/src/services/fileCacheService.js#L34-L40](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/services/fileCacheService.js#L34-L40)
- **Akar Masalah**:
  Fungsi `getCachedFiles(projectId)` memeriksa keberadaan cache pada `cacheByProject`. Jika kunci proyek tidak ditemukan, fungsi jatuh ke baris fallback `return workspaceFiles.value;` yang memuat berkas milik proyek aktif saat ini.
- **Dampak Lapangan**:
  Komponen yang meminta berkas untuk proyek tertentu yang belum memiliki cache akan menerima daftar berkas dari proyek lain yang sedang aktif, melanggar prinsip isolasi workspace.
- **Usulan Perbaikan**:
  1. Jika `projectId` eksplisit diberikan dan tidak ditemukan di dalam cache, kembalikan array kosong `[]`.
  2. Batasi penggunaan `workspaceFiles.value` hanya ketika `projectId` tidak dispesifikasikan (konteks aktif).
- **Acceptance Criteria**:
  - Pemanggilan `getCachedFiles('NON_EXISTENT')` mengembalikan `[]`.
  - Berkas antar-proyek terisolasi sempurna pada layer cache in-memory.

---

### BUG-08 — Cursor Event Mengabaikan Pembaruan Saat Riwayat Diganti

- **Prioritas**: P2
- **Domain**: Frontend Live Events / SSE Stream Processing
- **Berkas Sumber**:
  - [web/frontend/src/composables/useWorkbenchLiveEvents.js#L59-L69](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/composables/useWorkbenchLiveEvents.js#L59-L69)
- **Akar Masalah**:
  Penjejakan event hanya mengandalkan nilai numerik `lastProcessedEventCount = events.length;`. Jika array riwayat event diganti dengan riwayat tugas baru yang kebetulan memiliki jumlah event sama, `events.slice(lastProcessedEventCount)` mengembalikan array kosong.
- **Dampak Lapangan**:
  Event modifikasi berkas pada tugas baru terlewatkan dan berkas pada editor tidak diperbarui secara otomatis.
- **Usulan Perbaikan**:
  1. Gunakan identitas event yang stabil (misalnya kombinasi `taskId` dan `eventId` atau tracking ID unik).
  2. Reset nomor indeks pemrosesan saat ID tugas atau konteks proyek berubah.
- **Acceptance Criteria**:
  - Pergantian tugas dengan jumlah riwayat event sama tetap memicu pemrosesan seluruh event tugas baru.
  - Pembaruan berkas dari tool `write_file` selalu memicu callback `onFileModified`.

---

### BUG-09 — Deduplikasi Masalah Menyatukan Error Berbeda Karena Pesan Sama

- **Prioritas**: P2
- **Domain**: Frontend Problems Panel / Diagnostic Collector
- **Berkas Sumber**:
  - [web/frontend/src/composables/useWorkbenchLiveEvents.js#L24-L28](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/web/frontend/src/composables/useWorkbenchLiveEvents.js#L24-L28)
- **Akar Masalah**:
  Fungsi `addProblem` menggunakan `seen.has(text)` sebagai kriteria deduplikasi unik tanpa memperhitungkan nama berkas, nomor baris, atau kolom terjadinya error.
- **Dampak Lapangan**:
  Jika terdapat pesan kesalahan yang sama (misalnya "SyntaxError: Unexpected token") di berkas A baris 10 dan berkas B baris 50, hanya kesalahan pertama yang ditampilkan di panel Problems.
- **Usulan Perbaikan**:
  1. Buat kunci komposit unik: `${item.file || ''}:${item.line || 0}:${item.col || 0}:${text}`.
  2. Pertahankan seluruh entri kesalahan yang terjadi pada lokasi yang berbeda.
- **Acceptance Criteria**:
  - Kesalahan dengan pesan identik pada berkas atau baris berbeda tetap tampil sebagai entri terpisah.
  - Event duplikat murni pada lokasi yang persis sama berhasil dideduplikasi.

---

## 3. Gerbang Penyelesaian (Gate B Checklist)

- [x] AI-04: Kontrak pengiriman gambar/teks sinkron antara UI dan endpoint API.
- [x] AI-05: Pemeriksaan AST memastikan tidak ada fungsi duplikat di `service.py`.
- [x] AI-06: Tes out-of-order response obrolan tidak menimpa sesi aktif.
- [x] BUG-03: Penambahan 9 berkas sekaligus hanya menerima tepat 8 berkas.
- [x] BUG-04: String Python multiline dengan tanda kurung lulus validasi tanpa error palsu.
- [x] BUG-05: Simulasi penutupan socket lama tidak mematikan koneksi terminal baru.
- [x] BUG-07: Permintaan cache untuk proyek yang belum dikenal mengembalikan array kosong.
- [x] BUG-08: Penggantian riwayat event dengan panjang sama tetap memproses event baru.
- [x] BUG-09: Dua pesan error identik di lokasi berbeda tampil lengkap pada panel Problems.
