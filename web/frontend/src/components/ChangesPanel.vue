<script setup>
// Changes / Diff + Result. Data dari event SSE Aegis.
// TIDAK ada diff engine di frontend: hanya menampilkan perubahan yang
// dilaporkan Aegis. Diff detail ditampilkan bila payload menyediakannya.
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
import { getProjectGitStatus } from "../api.js";

const props = defineProps({
  changes: { type: Array, default: () => [] },
  validation: { type: Object, default: () => ({}) },
  project: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 },
});

const emit = defineEmits(["open-file", "open-diff", "discard-change"]);

const localGitChanges = ref([]);

const confirmDiscardAll = ref(false);
const discardAllBusy = ref(false);

const confirmingFile = ref(null);
const discardingFile = ref(null);

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
    first === ".aether" ||
    first === ".git" ||
    first === ".gemini" ||
    first === ".continue" ||
    first === ".ipynb_checkpoints" ||
    first === "__pycache__"
  ) {
    return true;
  }
  if (first.startsWith(".aegis") || first.startsWith(".aether")) return true;
  if (last.startsWith(".aegis_tmp_") || last.startsWith(".aether_tmp_") || last.endsWith(".swp")) return true;
  if (p === "data/aegis.db" || p === "data/aether.db" || p.startsWith("data/aegis.db-") || p.startsWith("data/aether.db-")) return true;
  return false;
}

async function loadGitChanges() {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) {
    localGitChanges.value = [];
    return;
  }
  try {
    const res = await getProjectGitStatus(pId);
    if (res?.is_repository && Array.isArray(res.files)) {
      localGitChanges.value = res.files
        .filter((f) => !isInternalOrIgnored(f?.path))
        .map((f) => ({
          path: f.path,
          kind: f.status.includes("?")
            ? "untracked"
            : f.status.includes("D")
            ? "deleted"
            : f.status.includes("A")
            ? "added"
            : "modified",
          status: f.status,
        }));
    } else {
      localGitChanges.value = [];
    }
  } catch (e) {
    localGitChanges.value = [];
  }
}

watch(
  () => [props.project && (props.project.id || props.project.project_id), props.refreshKey],
  () => {
    loadGitChanges();
  },
  { immediate: true }
);

const displayChanges = computed(() => {
  const raw =
    props.changes && props.changes.length > 0
      ? props.changes
      : localGitChanges.value;
  return (raw || []).filter((c) => !isInternalOrIgnored(c?.path || c?.detail));
});

function onRowClick(c) {
  emit("open-diff", c);
}

// Collapsible section (Aegis Workbench right column).
// Default: CHANGES tertutup. State hanya di frontend selama sesi aktif.
const collapsed = ref(false);
function toggleCollapse() {
  collapsed.value = !collapsed.value;
}

// Accordion: hanya SATU baris terbuka pada satu waktu (index terpilih).
// -1 = semua tertutup (diff TIDAK dirender secara default).
const expandedIndex = ref(-1);
function toggleRow(i) {
  expandedIndex.value = expandedIndex.value === i ? -1 : i;
}

// Klasifikasi kind perubahan (created/added/new, deleted/removed, modified/...).
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
// Kode pendek untuk indikator status pada kartu satu-baris.
function tagCode(c) {
  const k = kindOf(c);
  if (k.includes("move") || k.includes("renam")) return "R";
  const cls = tagClass(c);
  if (cls === "created") return "A";
  if (cls === "failed") return "D";
  if (cls === "modified") return "M";
  return "•";
}

// Judul baris: path + asal (untuk move/rename).
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
  <section class="sc-changes-section changes-block" :class="{ collapsed }">
    <div class="drawer-sec-head sc-sec-head" @click="toggleCollapse">
      <span class="sec-caret sc-caret" aria-hidden="true">{{ collapsed ? "▸" : "▾" }}</span>
      <span class="drawer-sec-title sc-sec-title">CHANGES</span>
      <!-- Discard all confirmation or default actions -->
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
      <div v-else-if="displayChanges.length > 0" class="drawer-sec-actions">
        <button
          type="button"
          class="sc-discard-all-btn"
          title="Discard all uncommitted changes"
          @click.stop="requestDiscardAll"
        >
          Discard All
        </button>
        <span class="drawer-badge sc-sec-badge">{{ displayChanges.length }}</span>
      </div>
    </div>

    <!-- Body = SATU scroll owner: header tetap, kartu perubahan + diff mengalir di area ini -->
    <div v-show="!collapsed" class="sc-changes-body changes-body">
      <div v-if="!displayChanges.length" class="sc-empty-hint">No changes yet.</div>

      <template v-else>
        <div class="changes-list">
          <template v-for="(c, i) in displayChanges" :key="i">
            <!-- Kartu satu baris: caret + status + nama file (ellipsis) + +/- -->
            <div class="file-row" :class="{ open: expandedIndex === i }" @click="onRowClick(c)">
              <span class="file-caret" aria-hidden="true" title="Toggle inline preview" @click.stop="toggleRow(i)">{{ expandedIndex === i ? "▾" : "▸" }}</span>
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
              <template v-else>
                <button class="file-diff-btn" type="button" title="Open Monaco Diff" @click.stop="emit('open-diff', c)">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/></svg>
                </button>
                <button class="file-edit" type="button" title="Edit" @click.stop="emit('open-file', c)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>
                </button>
                <button
                  class="file-discard-btn"
                  type="button"
                  title="Discard changes to this file"
                  @click.stop="requestDiscardFile(c.path)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                    <path d="M3 3v5h5"/>
                  </svg>
                </button>
              </template>
            </div>

            <!-- Diff muncul saat caret diklik (accordion) -->
            <div v-if="expandedIndex === i" class="file-diff">
              <div v-if="c.diff" class="file-diff-body"><pre>{{ c.diff }}</pre></div>
              <div v-else class="file-diff-note">Diff detail is not available from AEGIS. Click row to open Monaco Diff.</div>
            </div>
          </template>
        </div>

        <!-- Result ringkas. -->
        <div class="cp-result">
          <span class="cp-result-label">Result</span>
          <span class="cp-result-val">
            {{ displayChanges.length }} file(s) changed
            <span v-if="validation && validation.state" class="cp-result-validation" :class="validationClass">· Validation {{ validationLabel }}</span>
          </span>
        </div>
      </template>
    </div>
  </section>
</template>
