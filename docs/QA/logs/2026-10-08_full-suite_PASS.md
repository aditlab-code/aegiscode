# QA Test Run Log: Git Staging, Selective Checkpoints, & Monaco Diff Approval

- **Waktu Eksekusi**: 2026-10-08 00:00:00 (WIB)
- **Eksekutor**: thor-tester / odin-orchestrator
- **Branch / Commit**: master @ 7b78424
- **Runner**: pytest + node:test
- **Status Akhir**: PASS (Exit Code 0)

---

## 1. Ringkasan Eksekusi

### Backend Pytest (tests/test_git_local_gateway.py)
- **Total Pengujian**: 11
- **Lulus (Passed)**: 11
- **Gagal (Failed)**: 0
- **Dilewati (Skipped)**: 0
- **Durasi Eksekusi**: 3.45s

Pengujian mencakup:
1. `test_git_repository_facade_diff_detail`
2. `test_gateway_service_git_endpoints`
3. `test_gateway_service_git_diff_untracked_and_detail`
4. `test_django_http_git_endpoints`
5. `test_gateway_service_git_discard_endpoints`
6. `test_django_http_git_discard_endpoint`
7. `test_gateway_service_git_init_and_deinit`
8. `test_django_http_git_init_endpoint`
9. `test_gitignore_patterns_and_sync`
10. `test_git_repository_facade_stage_and_unstage` (Baru: validasi stage, unstage, dan flag staged)
11. `test_git_gateway_stage_and_unstage_endpoints` (Baru: POST /api/projects/<id>/git/stage & unstage)
12. `test_create_checkpoint_selective_staging` (Baru: verifikasi commit selective hanya untuk file staged, dan fallback auto-stage jika belum ada file staged)

### Frontend Unit & Contract Tests (node:test)
- **Total Pengujian**: 20
- **Lulus (Passed)**: 20
- **Gagal (Failed)**: 0
- **Dilewati (Skipped)**: 0
- **Durasi Eksekusi**: 84ms

Pengujian mencakup:
1. `parseGitRefs` badges formatting
2. `parseGitRefs` comma-separated parsing
3. `computeGitGraph` linear lane layout
4. `computeGitGraph` branching & merging
5. `computeGitGraph` empty/safe fallback
6. `openDiffTab` tab keying
7. `editorTabsService` activation & fallback
8. Git status badge classifier
9. `api.js` git client endpoint contract (termasuk `stageProjectGitChanges` & `unstageProjectGitChanges`)
10. Changes panel internal path filtering
11. Changes panel external/traversal filtering
12. Changes panel internal mechanisms filtering (.aegis, .aether, swap, db)
13. Diff editor read-only & edit transitions
14. Discard changes cleanup logic
15. Non-overlay inline discard confirmation machine
16. Conflict tracking
17. Monaco model registry lifecycle
18. Changes panel separation of `stagedChanges` vs `unstagedChanges`
19. MonacoDiffEditor toolbar contract (ikon murni tanpa label teks, aksesibilitas, approval stage toggle)
20. Checkpoint commit lifecycle refresh signaling (`checkpoint-created` event)

---

## 2. Kepatuhan Aturan QA
1. **no-orphan-code**: Seluruh metode baru (`stage`, `unstage`, `git_stage`, `git_unstage`, `stageProjectGitChanges`, `unstageProjectGitChanges`, `checkpoint-created`) terhubung end-to-end dari Facade -> Gateway Service -> View -> API -> UI -> Test.
2. **no-spaghetti-code**: Alur state perubahan terlokalisasi di Facade dan sinkron via ref + reactive event emits tanpa mutasi global.
3. **no-empty-catch-without-fallback**: Semua blok try-catch memiliki fallback aman (`_run` fallback ke `git reset HEAD`, logger/notification, dan feedback visual toast).
4. **no-dummy-pass**: Tidak ada stub atau placeholder fungsi kosong.
