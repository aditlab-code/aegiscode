# Spec: IDE Real-Time Synchronization for Remote Task Delegation

## Objective
Menjamin sinkronisasi dua arah seketika (*real-time synchronization*) antara aksi pendelegasian tugas dari Telegram (`[🚀 Delegasikan ke Agen IDE]`) dengan antarmuka IDE workstation. Task yang didelegasikan harus otomatis terikat pada project aktif (*Active Project*), memperbarui daftar thread pada panel samping (*Threads panel*), membuka laci asisten (*Right Assistant Drawer*), dan mengarahkan fokus pengguna langsung ke tab *Agents* dengan pembaruan status dan milestone subagen secara live.

### User Stories & Acceptance Criteria
1. **Active Project Auto-Binding**:
   - Sebagai pengguna yang mendelegasikan tugas dari Telegram, task yang dibuat harus otomatis menggunakan `project_id` dari repositori/project yang sedang aktif dibuka di IDE jika `project_id` sesi bernilai kosong/None.
   - Hasil task dan sesi terdaftar pada filter project aktif sehingga tidak tersembunyi dari antarmuka IDE.
2. **Threads Panel Auto-Refresh**:
   - Sebagai pengembang di IDE workstation, ketika task didelegasikan dari Telegram, panel *Threads* (`ThreadsHistoryPanel.vue`) harus otomatis memuat ulang sesi dan menampilkan thread percakapan baru tanpa perlu klik manual atau reload halaman.
3. **Automatic Drawer & Agents Tab Activation**:
   - Saat event `task_created` atau `task_started` tiba dari task yang didelegasikan, IDE harus otomatis membuka right drawer (`assistantVisible = true`) jika sedang tertutup, dan mengalihkan tab aktif ke `assistantTab = 'agents'`.
   - Komponen `AgentDrawerPanel.vue` langsung menampilkan judul task, indikator status running, dan aktivitas subagen secara dinamis.
4. **SSE Event Stream Propagation**:
   - `task_created` harus memicu peningkatan `queueRefresh` dan pemanggilan `refreshTaskHistory()` pada frontend, memastikan sinkronisasi instan melalui pipeline Server-Sent Events (`/api/events`) yang sudah ada.

---

## Tech Stack
- **Backend**: Python 3.10+, Django (`GatewayService`, `SessionStore`, `ProjectStore`, SSE stream `/api/events`)
- **Frontend**: Vue 3 (Composition API), Vite 5 (`App.vue`, `WorkbenchView.vue`, `ThreadsHistoryPanel.vue`, `useTaskLifecycle.js`)
- **Transport**: Server-Sent Events (`EventSource` ke `/api/events`)

---

## Commands
- **Targeted Backend Test**: `rtk pytest tests/test_telegram_companion/test_delegation_ide_sync.py -v`
- **Full Companion Test Suite**: `rtk pytest tests/test_telegram_companion/ -q`
- **Restart Companion Daemon**: `PYTHONPATH=src:apps/django_app python3 -m agent_ai.runtime.telegram.companion`

---

## Project Structure
```
apps/django_app/api/
└── services.py                         # delegate_session_to_agent_task auto-bind active project_id
apps/frontend/src/
├── composables/useTaskLifecycle.js     # trigger queueRefresh on task_created & auto-follow remote task
├── components/sidebar/ThreadsHistoryPanel.vue  # reload sessions on task_created / queueRefresh
└── pages/WorkbenchView.vue             # auto-open drawer & switch to 'agents' tab on remote task start
tests/test_telegram_companion/
└── test_delegation_ide_sync.py         # Dedicated test suite untuk validasi binding project dan event SSE
```

---

## Code Style & Architectural Conventions
1. **Active Project Fallback**:
   Di `delegate_session_to_agent_task`:
   ```python
   pid = project_id or sess.project_id
   if not pid:
       pid = self.project_store.get_active_project_id()
   ```
2. **Frontend Event Reactivity**:
   Event `task_created` memicu `queueRefresh.value += 1` dan `refreshTaskHistory()`:
   ```javascript
   case "task_created":
     queueRefresh.value += 1;
     refreshTaskHistory();
     break;
   ```
3. **Auto Focus Agents Tab**:
   Saat remote task dimulai, emit/panggil aktivasi drawer dan set `assistantTab.value = 'agents'`.

---

## Testing Strategy
- File pengujian baru non-redundan: `tests/test_telegram_companion/test_delegation_ide_sync.py`.
- Memverifikasi:
  1. `delegate_session_to_agent_task` menggunakan active project ID saat `sess.project_id` kosong.
  2. `create_task` memancarkan event `task_created` dengan `project_id` yang terikat.
  3. Seluruh 78 pengujian lama tetap lulus 100%.

---

## Boundaries
- **Always do**:
  - Gunakan `rtk` untuk seluruh eksekusi bash/test.
  - Pertahankan kelulusan seluruh tes unit backend dan frontend.
- **Never do**:
  - Menulis silent catch `except Exception: pass`.
  - Mengubah API contracts public yang sudah ada.
  - Memaksa reload halaman penuh (*full page reload*) di peramban.

---

## Success Criteria
- [ ] Task dari Telegram otomatis terikat ke active project ID yang valid.
- [ ] Panel *Threads* dan *Agents* di IDE otomatis ter-update dan beralih fokus saat delegasi terjadi.
- [ ] 100% tes lulus via `rtk pytest`.

---

## Open Questions
- *Nihil* (semua detail arsitektural telah disetujui pada tahap interview).
