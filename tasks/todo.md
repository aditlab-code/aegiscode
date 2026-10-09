# Atomic Tasks: Git Source Control Commit & Staging Lifecycle Refinement

- [x] Task 1: Expose clearTaskChanges in useTaskLifecycle.js
  - Acceptance: Composable useTaskLifecycle mengekspor fungsi helper clearTaskChanges() yang mengosongkan array changes.value secara reaktif.
  - Verify: rtk node --test apps/frontend/tests/*.test.mjs
  - Files: apps/frontend/src/composables/useTaskLifecycle.js

- [x] Task 2: Strict Single Source of Truth in ChangesPanel.vue
  - Acceptance: activeFiles di ChangesPanel.vue hanya mengonsumsi localGitChanges saat isRepository bernilai true (tidak pernah fallback ke props.changes saat status Git kosong). Fallback ke props.changes hanya diizinkan saat isRepository false.
  - Verify: rtk npm --prefix apps/frontend run build
  - Files: apps/frontend/src/components/git/ChangesPanel.vue

- [x] Task 3: Event Pipeline & Badge Synchronization in App.vue & Layout
  - Acceptance: App.vue mendengarkan @checkpoint-created dari WorkbenchView, memanggil clearTaskChanges(), dan memicu explorerRefresh. Badge changes-count di AppNavbar dan AppActivityBar terbarukan secara instan tanpa browser reload.
  - Verify: rtk npm --prefix apps/frontend run build
  - Files: apps/frontend/src/App.vue, apps/frontend/src/composables/workbench/useWorkbenchEditorFacade.js, apps/frontend/src/components/sidebar/GitSidebarPanel.vue

- [x] Task 4: Unit Testing & Verification Gates
  - Acceptance: apps/frontend/tests/gitCommitLifecycle.test.mjs memverifikasi perilaku activeFiles, pembersihan event commit, serta seluruh 6 mandatory frontend verification gates terpenuhi 100%.
  - Verify: rtk node --test apps/frontend/tests/*.test.mjs && rtk npm --prefix apps/frontend run build
  - Files: apps/frontend/tests/gitCommitLifecycle.test.mjs
