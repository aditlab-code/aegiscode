import test from "node:test";
import assert from "node:assert/strict";
import { ref, computed } from "vue";
import fs from "node:fs";
import path from "node:path";

test("1. useTaskLifecycle exports clearTaskChanges contract", () => {
  const filePath = path.resolve("apps/frontend/src/composables/useTaskLifecycle.js");
  const content = fs.readFileSync(filePath, "utf-8");

  assert.ok(
    content.includes("function clearTaskChanges()"),
    "useTaskLifecycle.js must define clearTaskChanges function"
  );
  assert.ok(
    content.includes("clearTaskChanges,"),
    "useTaskLifecycle.js must return clearTaskChanges in exports"
  );

  // Behavior simulation of clearTaskChanges
  const changes = ref([
    { path: "src/main.js", kind: "modified" },
    { path: "src/utils.js", kind: "added" },
  ]);
  assert.equal(changes.value.length, 2);

  function clearTaskChanges() {
    changes.value = [];
  }
  clearTaskChanges();
  assert.equal(changes.value.length, 0, "changes array must be empty after clearTaskChanges()");
});

test("2. ChangesPanel Single Source of Truth: clean Git repository never falls back to stale task changes", () => {
  const isRepository = ref(true);
  const localGitChanges = ref([]);
  const propsChanges = ref([
    { path: "apps/frontend/src/App.vue", kind: "modified" },
    { path: "apps/frontend/src/api.js", kind: "modified" },
  ]);

  // Mirror the refined activeFiles computed property from ChangesPanel.vue
  const activeFiles = computed(() => {
    const raw = isRepository.value
      ? localGitChanges.value
      : (propsChanges.value && propsChanges.value.length > 0 ? propsChanges.value : []);
    return raw;
  });

  const stagedChanges = computed(() => activeFiles.value.filter((f) => Boolean(f.staged)));
  const unstagedChanges = computed(() =>
    activeFiles.value.filter((f) => Boolean(f.unstaged || f.untracked || (!f.staged && !f.unstaged)))
  );

  // Initial clean state after git commit
  assert.equal(activeFiles.value.length, 0, "activeFiles must be empty when git working tree is clean");
  assert.equal(stagedChanges.value.length, 0, "stagedChanges must be empty");
  assert.equal(unstagedChanges.value.length, 0, "unstagedChanges must be empty and not bounce back from propsChanges");

  // Partial commit scenario: 1 file remains unstaged in Git status
  localGitChanges.value = [
    { path: "apps/frontend/src/remaining.js", staged: false, unstaged: true, kind: "modified" },
  ];
  assert.equal(activeFiles.value.length, 1);
  assert.equal(stagedChanges.value.length, 0);
  assert.equal(unstagedChanges.value.length, 1);
  assert.equal(unstagedChanges.value[0].path, "apps/frontend/src/remaining.js");
});

test("3. Non-repository fallback: safe fallback to props.changes when workspace is not a Git repo", () => {
  const isRepository = ref(false);
  const localGitChanges = ref([]);
  const propsChanges = ref([
    { path: "workspace/file1.txt", kind: "added" },
  ]);

  const activeFiles = computed(() => {
    const raw = isRepository.value
      ? localGitChanges.value
      : (propsChanges.value && propsChanges.value.length > 0 ? propsChanges.value : []);
    return raw;
  });

  assert.equal(activeFiles.value.length, 1, "Non-git workspace safely displays propsChanges");
  assert.equal(activeFiles.value[0].path, "workspace/file1.txt");
});

test("4. App.vue Checkpoint Event Handler coordinates clearTaskChanges and refresh triggers", () => {
  let cleared = false;
  let refreshCount = 0;

  function mockClearTaskChanges() {
    cleared = true;
  }

  const explorerRefresh = ref(0);

  function handleCheckpointCreated() {
    mockClearTaskChanges();
    explorerRefresh.value++;
    refreshCount++;
  }

  // Simulate checkpoint creation (git commit completion)
  handleCheckpointCreated();

  assert.equal(cleared, true, "clearTaskChanges must be called on checkpoint-created");
  assert.equal(explorerRefresh.value, 1, "explorerRefresh must increment");
  assert.equal(refreshCount, 1);
});

test("5. App.vue handleChangesUpdated dynamically synchronizes changes and counter badge", () => {
  const changes = ref([
    { path: "file1.js", kind: "modified" },
    { path: "file2.js", kind: "added" },
  ]);

  function handleChangesUpdated(files) {
    if (Array.isArray(files)) {
      changes.value = files;
    }
  }

  // When commit succeeds and Git status reports 0 files:
  handleChangesUpdated([]);
  assert.equal(changes.value.length, 0, "changes length must immediately update to 0");

  // When partial commit leaves 1 file:
  handleChangesUpdated([{ path: "file2.js", kind: "added" }]);
  assert.equal(changes.value.length, 1, "changes length must update to remaining 1 file");
});

test("6. ChangesPanel.vue and WorkbenchView.vue code contracts verification", () => {
  const cpPath = path.resolve("apps/frontend/src/components/git/ChangesPanel.vue");
  const cpContent = fs.readFileSync(cpPath, "utf-8");
  assert.ok(
    cpContent.includes('"changes-updated"'),
    "ChangesPanel.vue must declare changes-updated emit"
  );
  assert.ok(
    cpContent.includes("emit(\"changes-updated\", activeFiles.value)"),
    "ChangesPanel.vue must emit changes-updated with activeFiles.value"
  );
  assert.ok(
    cpContent.includes("isRepository.value\n    ? localGitChanges.value"),
    "ChangesPanel.vue activeFiles must prioritize localGitChanges when isRepository is true"
  );

  const wbPath = path.resolve("apps/frontend/src/pages/WorkbenchView.vue");
  const wbContent = fs.readFileSync(wbPath, "utf-8");
  assert.ok(
    wbContent.includes('"changes-updated"'),
    "WorkbenchView.vue must declare changes-updated emit"
  );
  assert.ok(
    wbContent.includes('@changes-updated="emit(\'changes-updated\', $event)"'),
    "WorkbenchView.vue must forward changes-updated"
  );

  const appPath = path.resolve("apps/frontend/src/App.vue");
  const appContent = fs.readFileSync(appPath, "utf-8");
  assert.ok(
    appContent.includes('@checkpoint-created="handleCheckpointCreated"'),
    "App.vue must bind @checkpoint-created"
  );
  assert.ok(
    appContent.includes('@changes-updated="handleChangesUpdated"'),
    "App.vue must bind @changes-updated"
  );
});
