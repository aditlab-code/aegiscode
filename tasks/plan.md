# Rencana Implementasi: Integrasi 9 Skills Addy Osmani ke Slash Command Autocomplete

## Ringkasan Arsitektur
Menggantikan template prompt statis legacy pada composer frontend IDE Aegis dengan 9 skill resmi Addy Osmani dari `.agents/skills`, diperkuat dengan API backend Django untuk discovery dinamis terhadap skill baru.

## Graph Ketergantungan (Dependency Graph)
```
1. Backend Storage Layer (SkillStore di src/agent_ai/projects/skills.py) [SUDAH TERUJI]
       │
       ▼
2. API Layer (apps/django_app/api/views.py & urls.py)
       │ - Endpoint GET /api/skills/catalog
       │ - Mengembalikan metadata ringkas (id, name, description, command, scope)
       │
       ▼
3. Frontend Service Layer (apps/frontend/src/services/promptSuggestionService.js)
       │ - 9 Template resmi default (DEFAULT_SKILL_TEMPLATES) dengan placeholder ringkas
       │ - Fetcher dinamis asinkron (fetchSkillTemplates)
       │ - Filter autocompletion (filterTemplates)
       │
       ▼
4. Testing & Verifikasi
       │ - Unit test API Django (tests/test_skills_api_endpoint.py)
       │ - Evaluasi sintaks ESM frontend (node --check)
       │ - Menjalankan full pytest regression test suite
```

## Irisan Implementasi (Vertical Slices)
- **Slice 1: Backend API Discovery Endpoint**
  - Implementasi handler `skills_catalog` di Django API views.
  - Pendaftaran URL `api/skills/catalog`.
  - Unit test endpoint API Django.
- **Slice 2: Frontend Prompt Suggestion & Autocomplete Enhancement**
  - Pembaruan konstanta `PROMPT_TEMPLATES` / `DEFAULT_SKILL_TEMPLATES` dengan 9 skill resmi.
  - Penambahan `fetchSkillTemplates()` non-blocking.
  - Verifikasi integrasi komponen `usePromptAutocomplete`.
- **Slice 3: End-to-End Verification & Gate Transition**
  - Uji seluruh suite pytest dan validasi format command `/`.
  - Transisi lifecycle state ke BUILD.
