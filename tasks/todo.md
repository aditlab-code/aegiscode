# Daftar Tugas Atomik (Todo)

- [x] Task 1: Daftarkan handler `skills_catalog` dan URL `api/skills/catalog` di Django backend
  - Acceptance: `GET /api/skills/catalog` mengembalikan JSON `{"status": "ok", "skills": [...]}` dengan minimal 9 skill resmi dari workspace.
  - Verify: Jalankan `pytest tests/test_skills_api_endpoint.py -v`.
  - Files: `apps/django_app/api/views.py`, `apps/django_app/api/urls.py`, `tests/test_skills_api_endpoint.py`.

- [x] Task 2: Perbarui `PROMPT_TEMPLATES` dan tambahkan pemuatan dinamis pada frontend
  - Acceptance: `PROMPT_TEMPLATES` memuat 9 skill resmi Addy Osmani dengan placeholder ringkas, dan fungsi `fetchSkillTemplates` dapat memuat skill tambahan secara dinamis.
  - Verify: Jalankan `node --check apps/frontend/src/services/promptSuggestionService.js`.
  - Files: `apps/frontend/src/services/promptSuggestionService.js`.

- [x] Task 3: Verifikasi regresi penuh dan kelulusan seluruh test suite
  - Acceptance: 100% tes pytest lulus (exit code 0), tidak ada sintaks error di frontend, alur `/` di composer siap digunakan.
  - Verify: Jalankan `pytest tests/test_native_skills_and_olympus.py tests/test_olympus_lifecycle_hooks.py tests/test_skills_api_endpoint.py -v`.
  - Files: Seluruh berkas terkait.
