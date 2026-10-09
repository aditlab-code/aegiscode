# Task Breakdown: Aegis IDE Active Project Binding for `/repo`

- [x] Task 1: Enforce strict active project in `apps/django_app/api/services.py`
  - Acceptance: `get_active_repository_info()` tidak lagi memiliki fallback ke `parents[3]`. Jika tidak ada project aktif, mengembalikan `{"has_active_project": False, "is_repo": False}`. Jika ada, menargetkan path project aktif.
  - Verify: `./venv/bin/pytest tests/test_telegram_companion/test_repo_review.py -k test_get_active_repository_info_strict -v`
  - Files: `apps/django_app/api/services.py`

- [x] Task 2: Implement `get_changed_files_summary()` on `GitRepositoryFacade` in `src/agent_ai/git/repository.py`
  - Acceptance: `get_changed_files_summary()` tersedia di `GitRepositoryFacade`, mengembalikan `[]` jika bukan repo git atau clean, dan mengembalikan `[{"path": str, "lines": int, "status": str}]` jika ada perubahan.
  - Verify: `./venv/bin/pytest tests/test_telegram_companion/test_repo_review.py -k test_get_changed_files_summary -v`
  - Files: `src/agent_ai/git/repository.py`

- [x] Task 3: Views for Project Selector, Non-Git Repo, and Switcher in `src/agent_ai/runtime/telegram/views.py`
  - Acceptance: `render_project_selector_view` merender daftar project dengan tombol `project:select:<id>`. `render_repo_view` menampilkan tombol `[⚙️ Inisialisasi Git]` jika non-git, dan selalu menyertakan tombol `[🔄 Ganti Project]`.
  - Verify: `./venv/bin/pytest tests/test_telegram_companion/test_repo_review.py -k test_render_views -v`
  - Files: `src/agent_ai/runtime/telegram/views.py`

- [x] Task 4: Companion Logic & Active Project Binding in `src/agent_ai/runtime/telegram/companion.py`
  - Acceptance: `companion.py` memiliki method `list_projects()`, `set_active_project()`, `init_repo()`, dan membatasi `get_changed_files()`, `accept_repo_changes()`, `discard_repo_changes()` strictly pada path project aktif.
  - Verify: `./venv/bin/pytest tests/test_telegram_companion/test_repo_review.py -k test_companion_project_binding -v`
  - Files: `src/agent_ai/runtime/telegram/companion.py`

- [x] Task 5: Handler Command Routing & Callbacks in `src/agent_ai/runtime/telegram/handler.py`
  - Acceptance: `/repo` mengarahkan ke project selector jika tidak ada project aktif. Callbacks `repo:init`, `repo:switch_project`, dan `project:select:` terdaftar dan berfungsi dengan baik.
  - Verify: `./venv/bin/pytest tests/test_telegram_companion/test_repo_review.py -k test_handler_project_switcher -v`
  - Files: `src/agent_ai/runtime/telegram/handler.py`

- [x] Task 6: Comprehensive Test Suite & Regression Verification in `tests/test_telegram_companion/test_repo_review.py`
  - Acceptance: Seluruh skenario (tanpa active project, switch project, non-git init, accept/discard pada active project) lulus 100%, dan test suite eksisting lulus tanpa regresi.
  - Verify: `./venv/bin/pytest tests/test_telegram_companion/ -v`
  - Files: `tests/test_telegram_companion/test_repo_review.py`
