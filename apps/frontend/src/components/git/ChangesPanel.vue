<script setup>
// Changes / Diff + Result with Git Staging (VS Code-like Source Control model).
import { computed, ref, watch, onMounted, onBeforeUnmount, inject } from "vue";
import {
  getProjectGitStatus,
  getProjectGitDiff,
  stageProjectGitChanges,
  unstageProjectGitChanges,
} from "../../api.js";

const props = defineProps({
  changes: { type: Array, default: () => [] },
  validation: { type: Object, default: () => ({}) },
  project: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 },
});

const emit = defineEmits([
  "open-file",
  "open-diff",
  "discard-change",
  "stage-change",
  "unstage-change",
  "changes-updated",
]);

const localGitChanges = ref([]);
const isRepository = ref(true);
const gitignoreRules = ref([]);

const confirmDiscardAll = ref(false);
const discardAllBusy = ref(false);

const confirmingFile = ref(null);
const discardingFile = ref(null);
const stagingFile = ref(null);
const unstagingFile = ref(null);
const stageAllBusy = ref(false);
const unstageAllBusy = ref(false);


function requestDiscardAll() {
  confirmDiscardAll.value = true;
  confirmingFile.value = null;
}

function cancelDiscardAll() {
  confirmDiscardAll.value = false;
}

async function executeDiscardAll() {
  discardAllBusy.value = true;
  try {
    emit("discard-change", null);
  } finally {
    confirmDiscardAll.value = false;
    discardAllBusy.value = false;
  }
}

function requestDiscardFile(path) {
  confirmingFile.value = path;
  confirmDiscardAll.value = false;
}

function cancelDiscardFile() {
  confirmingFile.value = null;
}

async function executeDiscardFile(path) {
  discardingFile.value = path;
  try {
    emit("discard-change", path);
  } finally {
    confirmingFile.value = null;
    discardingFile.value = null;
  }
}

async function handleStage(path) {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) return;
  stagingFile.value = path;
  try {
    await stageProjectGitChanges(pId, path);
    emit("stage-change", { path, unstage: false });
    await loadGitChanges();
  } catch (err) {
    console.error("Failed to stage changes:", err);
  } finally {
    stagingFile.value = null;
  }
}

async function handleStageAll() {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) return;
  stageAllBusy.value = true;
  try {
    await stageProjectGitChanges(pId, null);
    emit("stage-change", { path: null, unstage: false });
    await loadGitChanges();
  } catch (err) {
    console.error("Failed to stage all changes:", err);
  } finally {
    stageAllBusy.value = false;
  }
}

async function handleUnstage(path) {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) return;
  unstagingFile.value = path;
  try {
    await unstageProjectGitChanges(pId, path);
    emit("unstage-change", { path, unstage: true });
    await loadGitChanges();
  } catch (err) {
    console.error("Failed to unstage changes:", err);
  } finally {
    unstagingFile.value = null;
  }
}

async function handleUnstageAll() {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) return;
  unstageAllBusy.value = true;
  try {
    await unstageProjectGitChanges(pId, null);
    emit("unstage-change", { path: null, unstage: true });
    await loadGitChanges();
  } catch (err) {
    console.error("Failed to unstage all changes:", err);
  } finally {
    unstageAllBusy.value = false;
  }
}

function onPanelKeyDown(e) {
  if (e.key === "Escape") {
    if (confirmDiscardAll.value || confirmingFile.value) {
      e.stopPropagation();
      confirmDiscardAll.value = false;
      confirmingFile.value = null;
    }
  }
}

function onGlobalClick(e) {
  if (confirmDiscardAll.value && !e.target.closest(".sc-discard-all-confirm")) {
    confirmDiscardAll.value = false;
  }
  if (confirmingFile.value && !e.target.closest(".file-row-discard-confirm")) {
    confirmingFile.value = null;
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onPanelKeyDown);
    window.addEventListener("click", onGlobalClick);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onPanelKeyDown);
    window.removeEventListener("click", onGlobalClick);
  }
});

function isInternalOrIgnored(path) {
  const p = String(path || "").trim().replace(/\\/g, "/").replace(/^\.\//, "");
  if (!p || p === ".." || p.startsWith("../") || p.includes("/../")) return true;
  const parts = p.split("/").filter(Boolean);
  if (!parts.length) return true;
  const first = parts[0];
  const last = parts[parts.length - 1];
  if (
    first === ".aegis" ||
    first === ".git" ||
    first === ".gemini" ||
    first === ".continue" ||
    first === ".ipynb_checkpoints" ||
    first === "__pycache__"
  ) {
    return true;
  }
  if (first.startsWith(".aegis")) return true;
  if (last.startsWith(".aegis_tmp_") || last.endsWith(".swp")) return true;
  if (p === "data/aegis.db" || p.startsWith("data/aegis.db-")) return true;
  return false;
}

function matchesGitignore(path, rules) {
  if (!rules || !rules.length || !path) return false;
  const p = String(path).trim().replace(/\\/g, "/").replace(/^\.\//, "");
  for (const raw of rules) {
    let r = String(raw).trim();
    if (!r || r.startsWith("#")) continue;
    if (r.endsWith("/")) {
      const dirName = r.slice(0, -1);
      if (p === dirName || p.startsWith(`${dirName}/`) || p.includes(`/${dirName}/`)) {
        return true;
      }
      continue;
    }
    if (r.startsWith("*.")) {
      const ext = r.slice(1);
      if (p.endsWith(ext)) return true;
      continue;
    }
    if (p === r || p.endsWith(`/${r}`) || p.startsWith(`${r}/`) || p.includes(`/${r}/`)) {
      return true;
    }
  }
  return false;
}

async function loadGitChanges() {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) {
    localGitChanges.value = [];
    isRepository.value = true;
    gitignoreRules.value = [];
    return;
  }
  try {
    const res = await getProjectGitStatus(pId);
    isRepository.value = res?.is_repository !== false;
    gitignoreRules.value = Array.isArray(res?.gitignore_rules) ? res.gitignore_rules : [];
    if (res?.is_repository && Array.isArray(res.files)) {
      localGitChanges.value = res.files
        .filter((f) => !isInternalOrIgnored(f?.path))
        .map((f) => {
          const isUntracked = Boolean(f.untracked || f.status?.includes("?"));
          const isDeleted = Boolean(f.status?.includes("D"));
          const isAdded = Boolean(f.status?.includes("A"));
          const isRenamed = Boolean(f.status?.includes("R"));
          const kind = isUntracked
            ? "untracked"
            : isDeleted
            ? "deleted"
            : isAdded
            ? "added"
            : isRenamed
            ? "renamed"
            : "modified";
          return {
            path: f.path,
            kind,
            status: f.status,
            staged: Boolean(f.staged),
            unstaged: Boolean(f.unstaged),
            untracked: isUntracked,
          };
        });
    } else {
      localGitChanges.value = [];
    }
  } catch (e) {
    localGitChanges.value = [];
    gitignoreRules.value = [];
  } finally {
    emit("changes-updated", activeFiles.value);
  }
}

watch(
  () => [props.project && (props.project.id || props.project.project_id), props.refreshKey],
  () => {
    loadGitChanges();
  },
  { immediate: true }
);

const activeFiles = computed(() => {
  // Bila repositori aktif, status Git riil adalah Single Source of Truth mutlak.
  // Jangan pernah fallback ke props.changes saat status Git bersih (localGitChanges kosong).
  const raw = isRepository.value
    ? localGitChanges.value
    : (props.changes && props.changes.length > 0 ? props.changes : []);
  return (raw || []).filter(
    (c) =>
      !isInternalOrIgnored(c?.path || c?.detail) &&
      !matchesGitignore(c?.path || c?.detail, gitignoreRules.value)
  );
});

watch(activeFiles, (files) => {
  emit("changes-updated", files);
});

const stagedChanges = computed(() => activeFiles.value.filter((f) => Boolean(f.staged)));
const unstagedChanges = computed(() =>
  activeFiles.value.filter((f) => Boolean(f.unstaged || f.untracked || (!f.staged && !f.unstaged)))
);

function onRowClick(c) {
  emit("open-diff", c);
}

// Collapsible sections
const stagedCollapsed = ref(false);
const changesCollapsed = ref(false);

function toggleStagedCollapse() {
  stagedCollapsed.value = !stagedCollapsed.value;
}

function toggleChangesCollapse() {
  changesCollapsed.value = !changesCollapsed.value;
}

// Accordion preview
const expandedPath = ref("");
const loadingDiff = ref({});

async function toggleRow(c) {
  const path = c?.path || c?.detail;
  if (!path) return;
  if (expandedPath.value === path) {
    expandedPath.value = "";
    return;
  }
  expandedPath.value = path;
  if (!c.diff && props.project) {
    const projectId = props.project.id || props.project.project_id;
    if (projectId) {
      loadingDiff.value[path] = true;
      try {
        const res = await getProjectGitDiff(projectId, path);
        if (res && typeof res.diff === "string") {
          c.diff = res.diff;
        }
      } catch (err) {
        console.warn("Failed to fetch git diff for", path, err);
      } finally {
        loadingDiff.value[path] = false;
      }
    }
  }
}

function kindOf(c) {
  return (c.kind || "change").toLowerCase();
}

function tagClass(c) {
  const k = kindOf(c);
  if (k.includes("creat") || k.includes("add") || k.includes("new")) return "created";
  if (k.includes("delet") || k.includes("remov")) return "failed";
  if (k.includes("move") || k.includes("renam")) return "modified";
  if (k.includes("modif") || k.includes("edit") || k.includes("updat")) return "modified";
  return "idle";
}

function tagLabel(c) {
  const k = kindOf(c);
  if (k.includes("creat") || k.includes("add") || k.includes("new")) return "added";
  if (k.includes("delet") || k.includes("remov")) return "removed";
  if (k.includes("move")) return "moved";
  if (k.includes("renam")) return "renamed";
  if (k.includes("modif") || k.includes("edit") || k.includes("updat")) return "modified";
  return k;
}

function tagCode(c) {
  const k = kindOf(c);
  if (k.includes("move") || k.includes("renam")) return "R";
  const cls = tagClass(c);
  if (cls === "created") return "A";
  if (cls === "failed") return "D";
  if (cls === "modified") return "M";
  return "•";
}

function rowTitle(c) {
  const base = c.path || c.detail || "(unknown)";
  return c.old_path ? `${base} (dari ${c.old_path})` : base;
}

const validationLabel = computed(() => {
  const s = props.validation.state;
  if (s === "ok") return "Passed";
  if (s === "err") return "Failed";
  if (s === "running") return "Running";
  return "Pending";
});

const validationClass = computed(() => {
  const s = props.validation.state;
  if (s === "ok") return "ok";
  if (s === "err") return "err";
  if (s === "running") return "running";
  return "";
});

defineExpose({ loadGitChanges });
</script>

<template>
  <div class="sc-changes-container">
    <!-- 1. STAGED CHANGES SECTION (tampil bila repositori aktif atau ada berkas staged) -->
    <section v-if="isRepository || stagedChanges.length > 0" class="sc-changes-section changes-block staged-block" :class="{ collapsed: stagedCollapsed }">
      <div class="drawer-sec-head sc-sec-head" @click="toggleStagedCollapse">
        <span class="sec-caret sc-caret" aria-hidden="true">{{ stagedCollapsed ? "▸" : "▾" }}</span>
        <span class="drawer-sec-title sc-sec-title">STAGED CHANGES</span>
        <div class="sc-header-actions-row" @click.stop>
          <button
            v-if="stagedChanges.length > 0"
            type="button"
            class="sc-action-icon-btn unstage-all"
            :disabled="unstageAllBusy"
            title="Unstage all changes"
            aria-label="Unstage all changes"
            @click="handleUnstageAll"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <span class="drawer-badge sc-sec-badge">{{ stagedChanges.length }}</span>
        </div>
      </div>

      <div v-show="!stagedCollapsed" class="sc-changes-body changes-body">
        <div v-if="!stagedChanges.length" class="sc-empty-hint">No staged changes yet. Use + to stage changes.</div>
        <div v-else class="changes-list">
          <template v-for="c in stagedChanges" :key="'staged-' + (c.path || c.detail)">
            <div class="file-row" :class="{ open: expandedPath === (c.path || c.detail) }" @click="onRowClick(c)">
              <span class="file-caret" aria-hidden="true" title="Toggle inline preview" @click.stop="toggleRow(c)">
                {{ expandedPath === (c.path || c.detail) ? "▾" : "▸" }}
              </span>
              <span class="file-status" :class="tagClass(c)" :title="tagLabel(c)">{{ tagCode(c) }}</span>
              <span class="file-name" :title="rowTitle(c)">{{ c.path || c.detail || "(unknown)" }}</span>
              <span class="file-stat">
                <span v-if="c.additions != null" class="st-add">+{{ c.additions }}</span>
                <span v-if="c.deletions != null" class="st-del">-{{ c.deletions }}</span>
              </span>

              <div class="file-row-actions" @click.stop>
                <button
                  class="file-unstage-btn"
                  type="button"
                  :disabled="unstagingFile === c.path"
                  title="Unstage changes"
                  aria-label="Unstage changes"
                  @click="handleUnstage(c.path)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                </button>
                <button class="file-diff-btn" type="button" title="Open Monaco Diff" @click="emit('open-diff', c)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/></svg>
                </button>
                <button class="file-edit" type="button" title="Edit" @click="emit('open-file', c)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>
                </button>
              </div>
            </div>

            <div v-if="expandedPath === (c.path || c.detail)" class="file-diff">
              <div v-if="loadingDiff[c.path || c.detail]" class="file-diff-note">Loading diff…</div>
              <div v-else-if="c.diff" class="file-diff-body"><pre>{{ c.diff }}</pre></div>
              <div v-else class="file-diff-note">Diff detail is not available. Click row to open Monaco Diff.</div>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- 2. CHANGES SECTION (unstaged / untracked) -->
    <section class="sc-changes-section changes-block unstaged-block" :class="{ collapsed: changesCollapsed }">
      <div class="drawer-sec-head sc-sec-head" @click="toggleChangesCollapse">
        <span class="sec-caret sc-caret" aria-hidden="true">{{ changesCollapsed ? "▸" : "▾" }}</span>
        <span class="drawer-sec-title sc-sec-title">CHANGES</span>

        <!-- Discard all confirmation -->
        <div v-if="confirmDiscardAll" class="sc-discard-all-confirm" @click.stop>
          <span class="sc-confirm-text">Discard all?</span>
          <button
            type="button"
            class="sc-confirm-yes-btn"
            :disabled="discardAllBusy"
            title="Confirm discard all changes across repository"
            @click.stop="executeDiscardAll"
          >
            {{ discardAllBusy ? "Discarding…" : "Yes, Discard All" }}
          </button>
          <button
            type="button"
            class="sc-confirm-no-btn"
            :disabled="discardAllBusy"
            title="Cancel"
            @click.stop="cancelDiscardAll"
          >
            Cancel
          </button>
        </div>
        <!-- Actions default -->
        <div v-else-if="isRepository && unstagedChanges.length > 0" class="sc-header-actions-row" @click.stop>
          <button
            type="button"
            class="sc-action-icon-btn stage-all"
            :disabled="stageAllBusy"
            title="Stage all changes (Approve all)"
            aria-label="Stage all changes (Approve all)"
            @click="handleStageAll"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <button
            type="button"
            class="sc-discard-all-btn"
            title="Discard all uncommitted changes"
            @click.stop="requestDiscardAll"
          >
            Discard All
          </button>
          <span class="drawer-badge sc-sec-badge">{{ unstagedChanges.length }}</span>
        </div>
      </div>

      <div v-show="!changesCollapsed" class="sc-changes-body changes-body">
        <div v-if="!isRepository" class="sc-empty-hint">Not a Git repository.</div>
        <div v-else-if="!unstagedChanges.length && !stagedChanges.length" class="sc-empty-hint">No changes yet.</div>
        <div v-else-if="!unstagedChanges.length && stagedChanges.length" class="sc-empty-hint">No unstaged changes.</div>

        <template v-else>
          <div class="changes-list">
            <template v-for="c in unstagedChanges" :key="'unstaged-' + (c.path || c.detail)">
              <div class="file-row" :class="{ open: expandedPath === (c.path || c.detail) }" @click="onRowClick(c)">
                <span class="file-caret" aria-hidden="true" title="Toggle inline preview" @click.stop="toggleRow(c)">
                  {{ expandedPath === (c.path || c.detail) ? "▾" : "▸" }}
                </span>
                <span class="file-status" :class="tagClass(c)" :title="tagLabel(c)">{{ tagCode(c) }}</span>
                <span class="file-name" :title="rowTitle(c)">{{ c.path || c.detail || "(unknown)" }}</span>
                <span class="file-stat">
                  <span v-if="c.additions != null" class="st-add">+{{ c.additions }}</span>
                  <span v-if="c.deletions != null" class="st-del">-{{ c.deletions }}</span>
                </span>

                <!-- Inline file discard confirmation -->
                <div v-if="confirmingFile === c.path" class="file-row-discard-confirm" @click.stop>
                  <span class="row-confirm-text">Discard?</span>
                  <button
                    class="row-confirm-btn confirm-yes"
                    type="button"
                    :disabled="discardingFile === c.path"
                    title="Confirm discard file"
                    @click.stop="executeDiscardFile(c.path)"
                  >
                    <span v-if="discardingFile === c.path">…</span>
                    <span v-else>✓</span>
                  </button>
                  <button
                    class="row-confirm-btn confirm-no"
                    type="button"
                    :disabled="discardingFile === c.path"
                    title="Cancel"
                    @click.stop="cancelDiscardFile"
                  >
                    ✕
                  </button>
                </div>
                <div v-else class="file-row-actions" @click.stop>
                  <button
                    class="file-stage-btn"
                    type="button"
                    :disabled="stagingFile === c.path"
                    title="Stage changes (Approve)"
                    aria-label="Stage changes (Approve)"
                    @click="handleStage(c.path)"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19"/>
                      <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                  </button>
                  <button class="file-diff-btn" type="button" title="Open Monaco Diff" @click="emit('open-diff', c)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/></svg>
                  </button>
                  <button class="file-edit" type="button" title="Edit" @click="emit('open-file', c)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>
                  </button>
                  <button
                    class="file-discard-btn"
                    type="button"
                    title="Discard changes to this file"
                    @click="requestDiscardFile(c.path)"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                      <path d="M3 3v5h5"/>
                    </svg>
                  </button>
                </div>
              </div>

              <div v-if="expandedPath === (c.path || c.detail)" class="file-diff">
                <div v-if="loadingDiff[c.path || c.detail]" class="file-diff-note">Loading diff…</div>
                <div v-else-if="c.diff" class="file-diff-body"><pre>{{ c.diff }}</pre></div>
                <div v-else class="file-diff-note">Diff detail is not available. Click row to open Monaco Diff.</div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </section>

    <!-- 3. RESULT SUMMARY -->
    <div v-if="stagedChanges.length + unstagedChanges.length > 0" class="cp-result">
      <span class="cp-result-label">Result</span>
      <span class="cp-result-val">
        {{ stagedChanges.length + unstagedChanges.length }} file(s) changed
        <span v-if="stagedChanges.length">({{ stagedChanges.length }} staged)</span>
        <span v-if="validation && validation.state" class="cp-result-validation" :class="validationClass">· Validation {{ validationLabel }}</span>
      </span>
    </div>
  </div>
</template>
