# Spec: Git Source Control Commit & Staging Lifecycle Refinement

## Objective
Refine and fix the Git Source Control commit lifecycle in AegisCode Studio frontend (`apps/frontend`).
Currently, after files are added to Staged Changes and committed, they erroneously reappear in the "Changes" (unstaged) list because `ChangesPanel.vue` falls back to stale in-memory task lifecycle changes (`props.changes`) when Git status is clean, and the root application (`App.vue`) does not synchronize its `changes` state upon commit. Users are currently forced to manually refresh the browser window to see the clean state.

### User Stories
- **As a developer using AegisCode Studio**, when I stage changes and click commit, the committed files must immediately disappear from both "STAGED CHANGES" and "CHANGES" sections without needing to reload the browser.
- **As a developer committing only a subset of files (partial commit)**, the committed files must disappear, and only the remaining uncommitted changes must stay in the "CHANGES" list.
- **As a developer**, the badge counter on the Activity Bar Git icon and Navbar commit chip must immediately synchronize with the actual number of uncommitted files after a commit succeeds.

### Acceptance Criteria
1. When `isRepository` is true, Git status (`localGitChanges`) is the authoritative Single Source of Truth. If `localGitChanges` is empty (working tree clean), `activeFiles` evaluates to empty, displaying "No changes yet." It must NEVER fall back to stale `props.changes`.
2. When a commit succeeds in `GithubBackupPanel.vue`, the `checkpoint-created` event propagates through `GitSidebarPanel.vue` -> `WorkbenchView.vue` -> `App.vue`.
3. In `App.vue`, `checkpoint-created` triggers synchronization/clearing of stale task lifecycle changes and triggers `explorerRefresh`.
4. The Git changes count badge in `AppNavbar` and `AppActivityBar` updates reactively to 0 (or the remaining uncommitted count) without a page reload.
5. Monaco diff tabs for committed files remain closed or are automatically closed upon commit.

---

## Tech Stack
- Frontend: Vue 3 (Composition API, `<script setup>`), Vite 5
- Styles: CSS Design Tokens via `theme-presets.css`
- Test Runner: Node.js native test runner (`node --test`)
- Backend Interface: Django Gateway Git REST API (`/api/projects/:id/git/*`)

---

## Commands
All commands MUST be run with the `rtk` proxy prefix per repository policy:
- **Build**: `rtk npm --prefix apps/frontend run build`
- **Test**: `rtk node --test apps/frontend/tests/*.test.mjs`
- **Lint / Theming Gate 1**: `rtk grep -rn "data-theme" apps/frontend/src/ | grep "\.vue"` (0 in style blocks)
- **Lint / Theming Gate 2**: `rtk grep -rn ':style=".*color' apps/frontend/src/ | grep "\.vue"` (0 matches)
- **Lint / Theming Gate 3**: `rtk grep -rn "#[0-9a-fA-F]\{3,8\}" apps/frontend/src/styles/ | grep -v "theme-presets.css"` (0 matches)
- **Lint / Theming Gate 4**: `rtk grep -rn "#[0-9a-fA-F]\{3,8\}" apps/frontend/src/ | grep "\.vue"` (0 matches)

---

## Project Structure
Affected components and files:
```
apps/frontend/
├── src/
│   ├── App.vue                                  # Handles @checkpoint-created, synchronizes task changes
│   ├── composables/
│   │   ├── useTaskLifecycle.js                  # Exposes clearChanges / syncChanges helper
│   │   └── workbench/
│   │       └── useWorkbenchEditorFacade.js      # Closes diff tabs, emits checkpoint-created
│   ├── pages/
│   │   └── WorkbenchView.vue                    # Thin coordinator, emits checkpoint-created to App.vue
│   └── components/
│       ├── git/
│       │   ├── ChangesPanel.vue                 # Single source of truth fix in activeFiles computed
│       │   └── GithubBackupPanel.vue            # Emits checkpoint-created upon commit
│       └── sidebar/
│           └── GitSidebarPanel.vue              # Forwards checkpoint-created & triggers loadGitChanges
└── tests/
    └── gitCommitLifecycle.test.mjs              # Verification suite for commit and staging lifecycle
```

---

## Code Style
1. **ChangesPanel Single Source of Truth Convention**:
```javascript
// apps/frontend/src/components/git/ChangesPanel.vue
const activeFiles = computed(() => {
  // If repository is active, Git status is the authoritative source of truth.
  // Never fallback to task changes when isRepository is true (clean status = 0 changes).
  const raw = isRepository.value
    ? localGitChanges.value
    : (props.changes && props.changes.length > 0 ? props.changes : []);

  return (raw || []).filter(
    (c) =>
      !isInternalOrIgnored(c?.path || c?.detail) &&
      !matchesGitignore(c?.path || c?.detail, gitignoreRules.value)
  );
});
```

2. **App.vue Checkpoint Event Coordinator**:
```javascript
// apps/frontend/src/App.vue
function handleCheckpointCreated(result) {
  // Clear stale in-memory task changes or synchronize with remaining git status
  clearTaskChanges();
  explorerRefresh.value++;
}
```

3. **No Direct Hex Rule**:
All UI elements and badges strictly use CSS variables (`var(--accent)`, `var(--badge-bg)`, etc.).

---

## Testing Strategy
- **Framework**: Node.js Test Runner (`node:test`, `node:assert/strict`).
- **Location**: `apps/frontend/tests/gitCommitLifecycle.test.mjs`.
- **Test Scenarios**:
  1. `ChangesPanel activeFiles`: When `isRepository` is `true` and `localGitChanges` is empty, `activeFiles` must be empty even if `props.changes` has files.
  2. `ChangesPanel activeFiles`: When `isRepository` is `false`, `activeFiles` safely falls back to `props.changes`.
  3. `Commit Lifecycle Propagation`: `checkpoint-created` handler in `App.vue` resets `changes` and bumps `explorerRefresh`.
  4. `Badge Counter Synchronization`: `changes-count` updates reactively upon commit.
- **Coverage & Regressions**: Must pass all 145 existing unit tests + new git commit lifecycle tests.

---

## Boundaries
- **Always do**:
  - Prefix every shell command with `rtk`.
  - Maintain the Thin Layout Coordinator pattern in `WorkbenchView.vue` (< 450 lines).
  - Run all 6 mandatory frontend verification gates before concluding.
- **Ask first**:
  - Modifying backend Git API contracts or database models.
  - Adding new third-party libraries.
- **Never do**:
  - Never write hardcoded HEX codes in `.vue` or outside `theme-presets.css`.
  - Never suppress or skip failing test cases.
  - Never rely on browser window refresh (`location.reload()`) as a fix for reactive state desynchronization.

---

## Success Criteria
- [ ] Staging a file and committing it removes the file from both Staged and Changes sections immediately.
- [ ] No files bounce back to "Changes" without manual edits.
- [ ] "No changes yet" is shown when all staged files are committed.
- [ ] Navbar and Activity Bar badges update immediately to 0 (or remaining uncommitted count).
- [ ] 0 regressions in existing tests (`rtk node --test apps/frontend/tests/*.test.mjs`).
- [ ] Frontend build succeeds with 0 errors (`rtk npm --prefix apps/frontend run build`).

---

## Open Questions
- None. (Resolved in Phase 1 DEFINE interview: Git status is confirmed as single source of truth, and badges/changes synchronize immediately).
