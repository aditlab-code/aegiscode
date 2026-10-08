# Tasks: IDE Real-Time Synchronization for Remote Task Delegation

- [ ] Task 1: Auto-Bind Active Project in `delegate_session_to_agent_task` (`apps/django_app/api/services.py`)
  - Acceptance: `delegate_session_to_agent_task` otomatis menggunakan `project_store.get_active_project_id()` jika `sess.project_id` kosong.
  - Verify: Test memverifikasi `project_id` pada task yang dihasilkan cocok dengan project aktif.
  - Files: `apps/django_app/api/services.py`

- [ ] Task 2: Frontend SSE Event Reactivity in `useTaskLifecycle.js`
  - Acceptance: `useTaskLifecycle.js` menangani event `task_created` dengan memperbarui `queueRefresh` dan `refreshTaskHistory()`.
  - Verify: Inspeksi kode `processEventCore`.
  - Files: `apps/frontend/src/composables/useTaskLifecycle.js`

- [ ] Task 3: Threads Panel Refresh & Auto-Focus Agents Tab
  - Acceptance: `ThreadsHistoryPanel.vue` memuat ulang daftar thread saat task baru tiba, dan `WorkbenchView.vue` membuka drawer serta mengarahkan fokus ke tab 'agents' saat remote task running terdeteksi.
  - Verify: Inspeksi kode `ThreadsHistoryPanel.vue` dan `WorkbenchView.vue`.
  - Files: `apps/frontend/src/components/sidebar/ThreadsHistoryPanel.vue`, `apps/frontend/src/pages/WorkbenchView.vue`

- [ ] Task 4: Dedicated Backend Test Suite
  - Acceptance: File `tests/test_telegram_companion/test_delegation_ide_sync.py` memvalidasi auto-binding project ID dan delegasi tanpa redundansi dengan tes lama.
  - Verify: `rtk pytest tests/test_telegram_companion/test_delegation_ide_sync.py` lulus 100%.
  - Files: `tests/test_telegram_companion/test_delegation_ide_sync.py`

- [ ] Task 5: Full Regression Testing & Daemon Restart
  - Acceptance: Seluruh test suite (`rtk pytest tests/test_telegram_companion/`) lulus 100%, daemon restart berhasil.
  - Verify: `rtk pytest tests/test_telegram_companion/` -> 100% pass, log daemon aktif.
  - Files: Runtime daemon
