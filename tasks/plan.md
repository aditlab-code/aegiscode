# Implementation Plan: Telegram Remote Skill Delegation Bridge to IDE Agents

## Context & Objectives
- **Masalah Saat Ini**:
  1. Interaksi di Telegram saat ini hanya berfungsi sebagai percakapan chat/Q&A biasa dan belum memiliki mekanisme pendelegasian langsung ke agen-agen di IDE.
  2. Ketika sesi wawancara `interview-me` selesai dan kebutuhan disepakati di Telegram, pengguna harus membuka IDE secara manual untuk membuat task implementasi.
  3. Dibutuhkan tombol aksi remote `[🚀 Delegasikan ke Agen IDE]` di Telegram yang secara otomatis memicu pembuatan dan eksekusi `Task` di backend IDE (mode `agents`), lalu memantau progres dan melaporkan diff/ringkasan berkas kembali ke Telegram.
  4. Seluruh pengujian harus dibuat di berkas tes baru yang terisolasi (`test_delegation_bridge.py`) tanpa redundansi dengan tes lama.

---

## Architecture & Dependency Graph

```
Telegram Companion (interview-me Q&A)
    │
    ├── 1. Finalize with Delegation Button (src/agent_ai/runtime/telegram/stream_relay.py)
    │       │ - Menambahkan method `finalize_with_delegation(final_text, session_id)`
    │       │ - Menyertakan inline button `[🚀 Delegasikan ke Agen IDE]` (callback: `agent:delegate:<session_id>`)
    │       ▼
    ├── 2. Delegation Callback Router (src/agent_ai/runtime/telegram/handler.py)
    │       │ - Menangkap callback `agent:delegate:<session_id>`
    │       │ - Mengarahkan ke listener `on_agent_delegate(session_id, chat_id)`
    │       ▼
    ├── 3. Delegation Service Handler (apps/django_app/api/services.py)
    │       │ - Method `delegate_session_to_agent_task(session_id, project_id)`
    │       │ - Mengonversi percakapan sesi menjadi `create_task()` mode `agents`
    │       │ - Menetapkan subagen yang relevan di IDE
    │       ▼
    ├── 4. Async Delegation Worker & Monitor (src/agent_ai/runtime/telegram/companion.py)
    │       │ - Eksekusi delegasi di background daemon thread
    │       │ - Relay streaming: `⚡ Mendelegasikan ke Agen IDE...` -> `⚡ Menjalankan task <task_id>...`
    │       │ - Polling task sampai selesai dan mengirimkan diff/summary ke Telegram
    │       ▼
    └── 5. Dedicated Verification Suite (tests/test_telegram_companion/test_delegation_bridge.py)
            │ - Unit tests tombol delegasi di stream relay
            │ - Unit tests callback router handler
            │ - Unit tests delegasi pembuatan task di backend
            │ - Zero redundancy dengan berkas tes lama
```

---

## Detailed Task Breakdown
- **Task 1: Delegation Button in `TelegramStreamRelay`** (`src/agent_ai/runtime/telegram/stream_relay.py`)
  - Tambahkan `finalize_with_delegation(text, session_id)` yang merender tombol `[🚀 Delegasikan ke Agen IDE]` dengan callback `agent:delegate:<session_id>`.
- **Task 2: Delegation Callback Router in `TelegramUpdateHandler`** (`src/agent_ai/runtime/telegram/handler.py`)
  - Tambahkan `on_agent_delegate` callback parameter dan route callback data `agent:delegate:<session_id>`.
- **Task 3: Backend Delegation Service in `GatewayService`** (`apps/django_app/api/services.py`)
  - Implementasikan `delegate_session_to_agent_task(session_id)` yang mengekstrak intisari sesi dan memanggil `create_task()` dengan mode `agents`.
- **Task 4: Async Delegation Execution & Observability in `TelegramCompanion`** (`src/agent_ai/runtime/telegram/companion.py`)
  - Implementasikan `handle_agent_delegate()` yang memanggil service delegasi di thread terpisah, memantau task hingga selesai, dan melaporkan laporan ke Telegram.
- **Task 5: Dedicated Test Suite** (`tests/test_telegram_companion/test_delegation_bridge.py`)
  - Buat berkas tes baru yang menguji seluruh alur delegasi secara terisolasi tanpa redundansi.
- **Task 6: Daemon Restart & Live Verification**
  - Restart daemon companion dan pastikan bot siap menerima interaksi delegasi.
