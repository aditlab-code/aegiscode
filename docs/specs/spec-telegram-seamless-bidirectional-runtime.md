# Spec: Telegram Seamless Bidirectional Runtime & Zero-Silent-Failure Architecture

## Objective
Membangun arsitektur runtime Telegram Companion yang benar-benar dua arah (seamless bidirectional) dan transparan tanpa ada *silent error swallowing* (`except Exception: pass`). Sistem ini memastikan setiap instruksi dari pengguna via Telegram dieksekusi secara nyata ke repositori/agen IDE, melaporkan pembaruan status berkala, dan menampilkan galat (error) secara eksplisit jika terjadi kegagalan sistem.

### User Stories & Acceptance Criteria
1. **Zero Silent Swallowing ("ERROR ya ERROR")**:
   - Sebagai pengguna dan pengembang, setiap exception runtime di `companion.py`, `handler.py`, dan `stream_relay.py` harus dicatat di log dengan stacktrace lengkap (`logger.error(..., exc_info=True)`) dan dipaparkan pesan kegagalannya ke antarmuka Telegram.
   - Tidak boleh ada blok `except Exception: pass` yang menyembunyikan kegagalan backend.
2. **Explicit Gateway Initialization Failure**:
   - Jika `_get_gateway_service()` atau bootstrap Django gagal, sistem harus mencatat detail kegagalan secara jelas dan mengabari pengguna bahwa GatewayService offline, bukan mengembalikan `None` dalam keheningan.
3. **True Two-Way Chat Context (`chat_id` Propagation)**:
   - Perintah teks/steering dari `handler.py` harus meneruskan `chat_id` pengguna yang meminta ke `on_steer_command(instruction, chat_id=chat_id)`, memastikan respons dan pembaruan streaming selalu mendarat di ruang obrolan pengirim asli secara dua arah tanpa fallback ID yang membingungkan.
4. **Reliable Autonomous Delegation Bridge**:
   - Alur `handle_agent_delegate` harus selaras dengan pola eksekusi task otonom terbaru: validasi keberadaan `task_id`, pembaruan periodik progres ke Telegram setiap 15 detik, penanganan status timeout/failed secara eksplisit, dan pelaporan output pekerjaan IDE yang komprehensif.
5. **Truthful State Queries (No Deceptive Mock Fallbacks)**:
   - Fungsi getter seperti `get_repo_info`, `get_mode`, `get_providers`, dan `get_skills` tidak boleh menyembunyikan kegagalan gateway di balik data mock palsu secara diam-diam. Galat query harus dicatat dan diinformasikan ke pemanggil.

---

## Tech Stack
- **Runtime**: Python 3.10+
- **Framework**: Django (internal `GatewayService`, `SessionStore`, SQLite `data/aegis.db`)
- **Transport**: Telegram Bot API via long-polling (`agent_ai.runtime.telegram.bot_client.TelegramBotClient`)
- **CLI/Execution**: `rtk` (Rust Token Killer) & `pytest`

---

## Commands
- **Run Targeted Tests**: `rtk pytest tests/test_telegram_companion/test_seamless_bidirectional.py -v`
- **Run Full Telegram Test Suite**: `rtk pytest tests/test_telegram_companion/ -q`
- **Run Companion Daemon**: `PYTHONPATH=src:apps/django_app python3 -m agent_ai.runtime.telegram.companion`

---

## Project Structure
```
src/agent_ai/runtime/telegram/
├── companion.py          # Companion runtime, turn execution, lifecycle monitoring, delegation handler
├── handler.py            # Telegram update & callback router, command dispatcher dengan chat_id propagation
├── stream_relay.py       # Rate-limited progressive streaming sender dengan zero silent error
└── bot_client.py         # HTTP client ke Telegram Bot API
tests/test_telegram_companion/
└── test_seamless_bidirectional.py  # Test suite baru khusus validasi zero-silent-catch dan bidirectional routing
```

---

## Code Style & Architectural Conventions
1. **Explicit Logging & Error Propagation**:
   Setiap blok `try-except` wajib mencatat tipe exception dan pesan deskriptif:
   ```python
   try:
       res = svc.execute(...)
   except Exception as exc:
       logger.error("[TURN] Execution failed for %s: %s", turn_id, exc, exc_info=True)
       relay.error_with_retry(str(exc), retry_callback_data=f"prompt:retry:{cache_id}")
       raise
   ```
2. **Signature Integrity**:
   `on_steer_command` menerima `(instruction: str, chat_id: int) -> None`.

---

## Testing Strategy
- **Framework**: `pytest` (dijalankan via `rtk pytest`).
- **File Baru Non-Redundan**: `tests/test_telegram_companion/test_seamless_bidirectional.py`.
- **Cakupan Tes**:
  1. Validasi `on_steer_command` menerima dan meneruskan `chat_id` dengan benar.
  2. Validasi kegagalan `_get_gateway_service()` memunculkan log error eksplisit (bukan silent `pass`).
  3. Validasi `handle_agent_delegate` menangani kegagalan pembuatan task dan melaporkan status secara akurat.
  4. Validasi getter functions mencatat peringatan/error bila GatewayService gagal merespons.

---

## Boundaries
- **Always do**:
  - Gunakan `rtk` untuk eksekusi perintah terminal.
  - Laporkan error yang terjadi ke pengguna Telegram secara gamblang ("ERROR ya ERROR").
  - Pastikan setiap blok `except` melakukan logging level `ERROR`/`WARNING` dengan `exc_info=True`.
  - Bersihkan dead code dan fungsi mock/stub yang redundant.
  - Pertahankan kelulusan seluruh tes yang ada tanpa regresi.
- **Ask first**:
  - Mengubah skema database SQLite `data/aegis.db`.
  - Mengubah public API endpoint.
- **Never do**:
  - Menulis blok `except Exception: pass` tanpa logging dan notifikasi (Zero Silent Catch).
  - Menyisakan dead code, fungsi yang tidak terpakai, atau placeholder/mock yang menyamarkan kegagalan.
  - Menggunakan kode redundant antar modul.
  - Menggunakan subagen teamwork (`teamwork_preview`).

---

## Success Criteria
- [ ] 0 baris `except Exception: pass` tanpa logging pada modul Telegram runtime.
- [ ] `on_steer_command` meneruskan `chat_id` asli pengguna secara akurat.
- [ ] `handle_agent_delegate` memakai mekanisme validasi task otonom terbaru dengan pelaporan progres aktif.
- [ ] Seluruh unit test (termasuk test baru `test_seamless_bidirectional.py`) lulus 100% via `rtk pytest`.

---

## Open Questions
- Apakah ada batas timeout khusus (misal 5 menit vs 10 menit) untuk task otonom IDE yang memakan waktu lama saat dipantau dari Telegram?
