# Implementation Plan: IDE Real-Time Synchronization for Remote Task Delegation

## Context & Objectives
Membangun sinkronisasi seketika antara pendelegasian tugas dari Telegram (`[🚀 Delegasikan ke Agen IDE]`) dengan antarmuka IDE workstation. Task yang didelegasikan otomatis mengikat project aktif, memperbarui daftar threads, membuka right drawer jika tertutup, dan mengalihkan tab ke 'Agents' dengan status live-update. Mengikuti spesifikasi [`docs/specs/spec-ide-delegation-synchronization.md`](../docs/specs/spec-ide-delegation-synchronization.md).

---

## Dependency Graph & Architecture

```
Telegram Delegation Button Click
    │
    ├── 1. Active Project Auto-Binding (apps/django_app/api/services.py)
    │       │ - `delegate_session_to_agent_task`: jika `sess.project_id` kosong,
    │       │   otomatis tautkan ke `project_store.get_active_project_id()`
    │       ▼
    ├── 2. Frontend SSE Event Reactivity (apps/frontend/src/composables/useTaskLifecycle.js)
    │       │ - Menambahkan penanganan `case "task_created"` pada `processEventCore`
    │       │ - Memperbarui `queueRefresh` dan memicu `refreshTaskHistory()`
    │       ▼
    ├── 3. Threads Panel & Drawer Auto-Focus (apps/frontend/src/components/sidebar/ThreadsHistoryPanel.vue & WorkbenchView.vue)
    │       │ - `ThreadsHistoryPanel.vue`: `loadThreads()` terpanggil saat `queueRefresh` naik
    │       │ - `WorkbenchView.vue`: saat remote task running terdeteksi, buka drawer dan set `assistantTab = 'agents'`
    │       ▼
    ├── 4. Dedicated Backend Test Suite (tests/test_telegram_companion/test_delegation_ide_sync.py)
    │       │ - Validasi auto-binding project ID
    │       │ - Validasi event `task_created` menyertakan `project_id` yang valid
    │       ▼
    └── 5. Regression Testing & Verification
            │ - Verifikasi seluruh test suite (`rtk pytest tests/test_telegram_companion/`)
            │ - Restart daemon companion
```

---

## Detailed Task Breakdown

### Task 1: Auto-Bind Active Project in `delegate_session_to_agent_task`
- Di `apps/django_app/api/services.py`, saat mengekstrak `pid`, jika `pid` bernilai None/kosong, baca fallback dari `self.project_store.get_active_project_id()`.
- Pastikan task yang dibuat terdaftar di bawah ID project aktif.

### Task 2: Frontend SSE Event Reactivity in `useTaskLifecycle.js`
- Di `apps/frontend/src/composables/useTaskLifecycle.js`, tambahkan `case "task_created"` pada `processEventCore(evt)` agar `queueRefresh.value += 1` dan `refreshTaskHistory()` terpanggil secara reaktif saat ada task baru dari remote.

### Task 3: Threads Panel Refresh & Drawer Focus
- Di `apps/frontend/src/components/sidebar/ThreadsHistoryPanel.vue`, pastikan `props.queueRefresh` memicu `loadThreads()`.
- Di `apps/frontend/src/pages/WorkbenchView.vue`, saat `isRunning` bernilai true atau ada remote task baru yang terdeteksi, buka right drawer (`assistantVisible.value = true`) dan arahkan `assistantTab.value = 'agents'`.

### Task 4: Dedicated Backend Test Suite
- Buat file tes baru `tests/test_telegram_companion/test_delegation_ide_sync.py` untuk menguji auto-binding active project ID pada delegasi task.

### Task 5: Verification & Daemon Restart
- Jalankan `rtk pytest tests/test_telegram_companion/` (memastikan seluruh 78+ tes lulus).
- Restart daemon Telegram Companion.
