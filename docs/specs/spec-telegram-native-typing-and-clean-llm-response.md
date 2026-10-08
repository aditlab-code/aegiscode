# Spec: Telegram Native Typing Indicator & Pure LLM Response Delivery

## Objective
Menghilangkan seluruh pesan perantara/boilerplate statis hardcode (`'🎯 Instruksi diterima dan diteruskan ke Agen'` dan `'💭 Agen sedang menganalisis instruksi...'`) saat pengguna berinteraksi melalui Telegram. Menggantikannya dengan:
1. Indikator aksi native Telegram `typing` (`sendChatAction`) yang aktif secara asinkron selama LLM sedang berpikir.
2. Pengiriman **satu pesan tunggal** yang langsung berisi jawaban utuh dan asli dari LLM (beserta tombol inline delegasi jika relevan) tanpa bubble pesan ganda.
3. Pada mode Agents (otonom), menyajikan **satu pesan progres tunggal** yang terus diperbarui secara dinamis *in-place* hingga menghasilkan ringkasan riil perubahan repositori IDE.

### User Stories & Acceptance Criteria
1. **Clean Chat Experience**:
   - Pengguna mengirim chat teks di Telegram. Bot TIDAK mengirim pesan terpisah "Instruksi diterima" atau "Agen sedang menganalisis".
   - Bot memicu indikator native Telegram: *"Typing..."* (atau *"sedang mengetik..."* di UI Telegram).
2. **Pure LLM Response Delivery**:
   - Begitu respons dari LLM diterima via `GatewayService.dispatch_remote_turn()`, bot langsung mengirimkan 1 pesan Telegram berisi teks asli respons asisten.
   - Jika giliran percakapan relevan untuk didelegasikan (misal hasil wawancara `interview-me`), tombol `[🚀 Delegasikan ke Agen IDE]` disematkan langsung pada pesan respons asli tersebut.
3. **Single Dynamic Progress Message for Agents Mode**:
   - Pada mode Agents, bot hanya membuat 1 pesan progres awal (misal: `⚡ Mengeksekusi tugas otonom...`) dan mengedit pesan tersebut *in-place* setiap 15 detik dengan info `task_id` riil dan durasi, hingga akhirnya di-finalize dengan hasil laporan diff repositori.
4. **Zero Silent Swallowing & Zero Dead Code**:
   - Seluruh logika pengiriman dan penanganan chat action bebas dari `except Exception: pass`. Galat dicatat ke logger level `ERROR`/`WARNING`.

---

## Tech Stack
- **API**: Telegram Bot API (`sendChatAction`, `sendMessage`, `editMessageText`)
- **Runtime**: Python 3.10+ (`agent_ai.runtime.telegram`)
- **Testing**: `pytest` via `rtk`

---

## Commands
- **Run Targeted Tests**: `rtk pytest tests/test_telegram_companion/test_clean_llm_response.py -v`
- **Run Full Telegram Test Suite**: `rtk pytest tests/test_telegram_companion/ -q`
- **Restart Daemon**: `PYTHONPATH=src:apps/django_app python3 -m agent_ai.runtime.telegram.companion`

---

## Project Structure
```
src/agent_ai/runtime/telegram/
├── bot_client.py   # Menambahkan method send_chat_action(chat_id, action="typing")
├── handler.py      # Menghapus send_message hardcode 'Instruksi diterima'
├── companion.py    # Memperbarui execute_remote_turn_async: typing loop di background + direct response delivery
tests/test_telegram_companion/
└── test_clean_llm_response.py  # Test suite baru khusus validasi native typing dan single clean message delivery
```

---

## Code Style & Architectural Conventions
1. **Native Typing Loop**:
   Typing action di Telegram otomatis kedaluwarsa setelah ~5 detik. Background loop mengirim `send_chat_action(chat_id, "typing")` setiap 4 detik hingga LLM selesai.
   ```python
   def _keep_typing(stop_event):
       while not stop_event.is_set():
           bot_client.send_chat_action(chat_id, "typing")
           stop_event.wait(4.0)
   ```
2. **Direct Delivery on Mode Ask**:
   Pada mode `ask`, tidak membuat pesan placeholder awal; langsung mengirim pesan baru dengan isi respons asli LLM setelah giliran selesai.
3. **In-Place Updates on Mode Agents**:
   Pada mode `agents`, pesan awal `⚡ Memulai task di IDE...` diedit secara berkala hingga laporan akhir selesai.

---

## Testing Strategy
- Unit test terisolasi baru: `tests/test_telegram_companion/test_clean_llm_response.py`.
- Verifikasi:
  1. `bot_client.send_chat_action` memanggil Telegram endpoint `sendChatAction`.
  2. `handler.py` tidak mengirim pesan ganda "Instruksi diterima".
  3. `companion.py` mengirim respons asli LLM langsung sebagai 1 pesan utuh pada mode ask.
  4. Seluruh 75 pengujian lama tetap lulus tanpa regresi.

---

## Boundaries
- **Always do**:
  - Gunakan `rtk` untuk seluruh eksekusi bash / pytest.
  - Sediakan tombol retry jika LLM mengalami kegagalan koneksi.
- **Never do**:
  - Mengirim pesan teks boilerplate hardcode terpisah yang mengotori chat.
  - Memakai silent `try-except pass`.
  - Mengubah skema database SQLite.

---

## Success Criteria
- [ ] 0 pesan teks boilerplate hardcode ("Instruksi diterima", "Agen sedang menganalisis") terkirim saat mode ask.
- [ ] Indikator native Telegram typing aktif selama pemrosesan LLM.
- [ ] Respons asli LLM muncul sebagai 1 pesan bersih.
- [ ] 100% tes unit (75+ tes) lulus via `rtk pytest`.

---

## Open Questions
- Tidak ada (seluruh keputusan desain telah diselesaikan pada sesi interview).
