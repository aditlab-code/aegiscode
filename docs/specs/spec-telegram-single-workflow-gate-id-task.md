# Spec: Telegram Single-Workflow Pipeline, Strict `id_task` Gate, and Zero-Callback Elimination

## 1. Objective
Mengimplementasikan **1 Alur Workflow Linier (Single-Workflow Pipeline)** pada Telegram Remote Companion AegisCode, dengan **eliminasi total terhadap inline button `callback_query`** dan **peniadaan mekanisme diam (*zero-silent mechanism*)**. Seluruh interaksi inbound diatur secara mutlak oleh **`TelegramContextGate` berbasis `id_task` (`task_id`)** untuk menjamin tidak ada eksekusi tugas yang tumpang tindih (*overlapping*), tidak ada balasan duplikat (*zero duplicate responses*), dan setiap galat dikomunikasikan secara eksplisit kepada pengguna.

---

## 2. Latar Belakang & Masalah
1. **Bifurkasi Alur via Callback Query**: 
   Sebelumnya, interaksi terbelah menjadi dua jalur: pesan teks (`message`) dan penekanan tombol inline (`callback_query`). Hal ini memicu race condition, penanganan parsial, dan inkonsistensi status pada koneksi polling Telegram.
2. **Silent Mechanism & Fallback Diam-diam**: 
   Jika task ID tidak ditemukan atau proses gagal, sistem sebelumnya rentan mengabaikan error atau jatuh ke silent fallback tanpa memberikan umpan balik nyata ke pengguna di Telegram.
3. **Ketiadaan Gate Check pada Pesan Masuk**:
   `TelegramUpdateHandler` sebelumnya langsung meneruskan instruksi teks tanpa memeriksa apakah workstation IDE sedang sibuk mengeksekusi tugas lain, sehingga tugas baru dapat menabrak tugas yang sedang berjalan.

---

## 3. User Stories & Acceptance Criteria

### User Story 1: Pintu Gerbang Tunggal Berbasis `id_task`
*Sebagai* pengguna yang mengirimkan instruksi ke bot Telegram,  
*Saya ingin* instruksi saya divalidasi oleh `TelegramContextGate` sebelum dieksekusi,  
*Sehingga* jika ada tugas (`id_task`) yang sedang berjalan, saya langsung diberi tahu dan tidak terjadi eksekusi ganda yang membingungkan.
* **Kriteria Penerimaan**:
  1. Setiap pesan masuk dievaluasi oleh `gate.gate_inbound_turn(chat_id, text)`.
  2. Jika ada `id_task` aktif pada `chat_id` tersebut, bot membalas secara eksplisit:  
     `⏳ Agen sedang menjalankan task [id_task] di IDE. Harap tunggu hingga selesai atau batalkan di workstation.`
  3. Jika `chat_id` idle, instruksi dialokasikan `id_task` baru, dicatat ke Gate via `gate.register_task(chat_id, task_id)`, dan dilepaskan pada blok `finally: gate.complete_task(chat_id, task_id)`.

### User Story 2: Eliminasi Total Callback Query (100% Text-Driven Workflow)
*Sebagai* pengguna yang berinteraksi via obrolan Telegram,  
*Saya ingin* semua kontrol dilakukan melalui perintah teks langsung tanpa tombol inline callback,  
*Sehingga* alur pesan linier, riwayat obrolan bersih, dan tidak ada race condition tombol.
* **Kriteria Penerimaan**:
  1. Seluruh router `_callback_router` dan penangan `callback_query` dihilangkan.
  2. Persetujuan HITL dilakukan via teks: `/allow <request_id>` dan `/deny <request_id>`.
  3. Penggantian mode dilakukan via teks: `/mode ask` atau `/mode agents` (alias: `/aegis_mode`).
  4. Pengelolaan repo dilakukan via teks: `/repo` (inspeksi), `/repo accept` (commit), `/repo discard` (bersihkan), dan `/repo init`.
  5. Pesan konfirmasi atau bantuan dikirimkan sebagai pesan teks biasa (`sendMessage`), bukan inline keyboard.

### User Story 3: Peniadaan Mekanisme Diam (Zero-Silent Policy)
*Sebagai* pengguna di Telegram,  
*Saya ingin* menerima pesan kesalahan yang jelas dan transparan jika terjadi kegagalan jaringan, LLM, atau backend,  
*Sehingga* saya selalu mengetahui status workstation tanpa ada pesan yang hilang secara diam-diam.
* **Kriteria Penerimaan**:
  1. Jika backend mengembalikan kegagalan/timeout, bot wajib mengirimkan pesan galat eksplisit berisi ringkasan error dan kode trace.
  2. Tidak ada penelanan error secara diam-diam (*no silent exception swallowing*).
  3. Log diagnostik selalu mencatat `[GATE-FAIL]`, `[DISPATCH-FAIL]`, atau `[TASK-TIMEOUT]`.

### User Story 4: Idempotensi & Proteksi Duplikasi Lintas-Restart
*Sebagai* sistem runtime,  
*Saya ingin* setiap pesan diproses tepat satu kali (*exactly-once processing*),  
*Sehingga* tidak pernah ada respons ganda akibat reconnect Telegram API atau restart Django.
* **Kriteria Penerimaan**:
  1. `TelegramBotClient` menyaring duplikasi `update_id` via LRU cache dan menyimpan offset terakhir secara persisten di `.aegis/run/telegram_offset.json`.
  2. Hanya 1 instansi poller yang dapat aktif di OS pada satu waktu berkat `TelegramPollerLock` (`fcntl` mutual exclusion).
  3. Poller loop memeriksa generasi (`_polling_generation`), menjamin thread lama mati seketika saat dihentikan.

---

## 4. Spesifikasi Arsitektur & State Machine `id_task`

### Alur Eksekusi Linier (Single Pipeline)
```
[User Telegram Text]
        │
        ▼
[TelegramBotClient: Deduplikasi update_id & Offset Check]
        │
        ▼
[TelegramContextGate: Evaluasi Otorisasi & id_task Aktif]
   ├── [Ada id_task Aktif] ──► Kirim Pesan Sibuk: "⏳ Task [id_task] sedang berjalan"
   └── [Idle & Sah]
           │
           ▼
[Workflow Dispatcher]
   ├── [Command: /status, /repo, /mode, /allow, /deny, /agents, /help] ──► Eksekusi Cepat & Balas Teks
   └── [Instruction / Steering Turn]
           │
           ▼
      [gate.register_task(chat_id, task_id)]
           │
           ▼
      [Eksekusi Turn: Ask Mode / Agents Mode]
           │
           ▼
      [Kirim Hasil / Stream Relay ke Telegram]
           │
           ▼
      [finally: gate.complete_task(chat_id, task_id)]
```

---

## 5. Matriks Perintah Teks Resmi (Pengganti Seluruh Callback)

| Perintah Teks | Argumen | Fungsi | Contoh Penggunaan |
| :--- | :--- | :--- | :--- |
| `/repo` | *opsional:* `accept`, `discard`, `init` | Periksa status repo atau jalankan mutasi git | `/repo`, `/repo accept`, `/repo discard` |
| `/mode` | `ask` \| `agents` | Ubah mode operasional workstation | `/mode ask`, `/mode agents` |
| `/allow` | `<request_id>` | Setujui permintaan tindakan kritis HITL | `/allow req-9872` |
| `/deny` | `<request_id>` | Tolak permintaan tindakan kritis HITL | `/deny req-9872` |
| `/status` | *tidak ada* | Periksa status runtime, branch, dan gateway | `/status` |
| `/agents` | *tidak ada* | Lihat daftar armada Olympus Fleet | `/agents` |
| `/help` | *tidak ada* | Tampilkan panduan resmi perintah Aegis | `/help` |
| `<teks bebas>` | instruksi coding | Menjalankan turn percakapan/eksekusi agen | `Tolong buat unit test untuk auth module` |

---

## 6. Rencana Tugas Implementasi (Task Breakdown)

### Tahap 1: Pembersihan Callback di `handler.py` dan `views.py`
- [ ] Hapus `_handle_callback_query` dan seluruh `_callback_router` di [`handler.py`](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/runtime/telegram/handler.py).
- [ ] Ubah `views.py` agar tidak merender `InlineKeyboardMarkup` pada pesan Telegram, ganti dengan petunjuk format teks perintah.
- [ ] Tambahkan command handler `/allow` dan `/deny` pada `TelegramUpdateHandler`.
- [ ] Tambahkan dukungan sub-perintah pada `/repo` (`accept`, `discard`, `init`).

### Tahap 2: Penegakan Strict `id_task` Gate pada Inbound Pipeline
- [ ] Integrasikan `self.gate.gate_inbound_turn(chat_id, text, username)` sebagai pintu masuk utama di [`TelegramUpdateHandler._handle_message`](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/runtime/telegram/handler.py#L124).
- [ ] Tautkan siklus `register_task` dan `complete_task` secara konsisten di `execute_remote_turn_async` baik untuk Ask Mode maupun Agents Mode.
- [ ] Pastikan penolakan task sibuk mengembalikan teks yang menyebutkan `id_task` aktif.

### Tahap 3: Eliminasi Silent Mechanism & Penyelarasan Stream Relay
- [ ] Pastikan seluruh blok `try-except` di [`turn_executors.py`](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/runtime/telegram/turn_executors.py) dan [`companion.py`](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/runtime/telegram/companion.py) mengirimkan pesan error eksplisit ke chat jika terjadi kegagalan.
- [ ] Bersihkan dependensi inline button dari [`stream_relay.py`](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/src/agent_ai/runtime/telegram/stream_relay.py) (`finalize_with_delegation`).

### Tahap 4: Verifikasi & Test Suite 100% Green
- [ ] Perbarui dan tambahkan pengujian unit di `tests/test_telegram_companion/` untuk menguji:
  - Penolakan pesan saat ada `id_task` aktif.
  - Perintah teks `/allow` dan `/deny`.
  - Penanganan `/repo accept`, `/repo discard`, `/repo init`.
  - Tidak adanya pemrosesan callback query.
- [ ] Jalankan seluruh test suite (`pytest tests/test_telegram_companion` dan `npm test`).
