# Tasks: Telegram Remote Skill Delegation Bridge to IDE Agents

- [x] Task 1: Delegation Button in `TelegramStreamRelay` (`src/agent_ai/runtime/telegram/stream_relay.py`)
  - Acceptance: `finalize_with_delegation(text, session_id)` mengirim pesan final dengan inline button `[🚀 Delegasikan ke Agen IDE]` ber-callback `agent:delegate:<session_id>`.
  - Verify: Test memverifikasi `edit_message_text` dipanggil dengan `reply_markup` tombol delegasi.
  - Files: `src/agent_ai/runtime/telegram/stream_relay.py`

- [x] Task 2: Delegation Callback Router in `TelegramUpdateHandler` (`src/agent_ai/runtime/telegram/handler.py`)
  - Acceptance: Handler mendeteksi callback `agent:delegate:<session_id>`, memanggil `on_agent_delegate()`, dan mengonfirmasi callback query dengan notifikasi pop-up.
  - Verify: Test memverifikasi `on_agent_delegate` dipanggil dengan `session_id` dan `chat_id`.
  - Files: `src/agent_ai/runtime/telegram/handler.py`

- [x] Task 3: Backend Delegation Service in `GatewayService` (`apps/django_app/api/services.py`)
  - Acceptance: `delegate_session_to_agent_task(session_id)` mengambil intisari pesan giliran dari sesi aktif dan membuat `Task` resmi dengan mode `agents` di IDE.
  - Verify: Test memverifikasi pemanggilan `create_task()` mengembalikan `task_id` yang valid.
  - Files: `apps/django_app/api/services.py`

- [x] Task 4: Async Delegation Execution & Observability in `TelegramCompanion` (`src/agent_ai/runtime/telegram/companion.py`)
  - Acceptance: `handle_agent_delegate()` menjalankan delegasi di background daemon thread, mengupdate status streaming relay, memantau task hingga selesai, dan merelay diff/laporan akhir.
  - Verify: Test memverifikasi worker delegasi memanggil service dan menyelesaikan stream relay.
  - Files: `src/agent_ai/runtime/telegram/companion.py`

- [x] Task 5: Dedicated Test Suite (`tests/test_telegram_companion/test_delegation_bridge.py`)
  - Acceptance: Berkas test baru berisi pengujian komprehensif untuk seluruh alur delegasi (relay button, handler routing, service delegation, async worker) tanpa redundansi dengan tes lama.
  - Verify: `rtk pytest tests/test_telegram_companion/test_delegation_bridge.py` lulus 100%.
  - Files: `tests/test_telegram_companion/test_delegation_bridge.py`

- [x] Task 6: Daemon Restart & Live Verification
  - Acceptance: Daemon berjalan stabil di background; siap menerima wawancara dan mendelegasikan tugas ke agen IDE.
  - Verify: Bot aktif dan merespons interaksi.
  - Files: Runtime daemon
