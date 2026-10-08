<script setup>
// AETHER Task List / Queue panel (UI).
//
// Panel ini adalah SALAH SATU UI dari SATU queue GLOBAL AETHER. Sumber data =
// TaskRecord in-memory backend (GET /api/tasks/queue), sama dengan yang dibaca
// Agent Workbench nanti. TIDAK ada TaskManager/queue subsystem kedua.
//
// Pada tahap ini belum ada scheduler serial: queue_state (pending/running/
// disabled/done) adalah proyeksi UI + niat user (disable = jangan dieksekusi).
// Disable != Cancel: Stop task RUNNING tetap memakai cancel_task existing.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  clearTaskQueue,
  disableQueueTask,
  enableQueueTask,
  listTaskQueue,
  moveQueueTask,
  removeQueueTask,
} from "../api.js";

const props = defineProps({
  // Penanda refresh dari parent (mis. setelah Run Task / event terminal).
  refreshKey: { type: Number, default: 0 },
  // Project aktif; bila diset, panel hanya menampilkan task milik project ini.
  projectId: { type: String, default: null },
  // Default state collapsed saat komponen dipasang. Workbench memakai
  // `true` (TASK tertutup saat pertama dibuka); Consultant tetap `false`
  // agar perilaku panel TASKS di sana tidak berubah.
  defaultCollapsed: { type: Boolean, default: false },
  // Sembunyikan header section bila sudah berada di dalam tab Queue tersendiri
  hideHeader: { type: Boolean, default: false },
});

const emit = defineEmits(["stop-task", "view-task"]);

const tasks = ref([]);
const error = ref("");
// Default state collapse dikendalikan prop (lihat defaultCollapsed).
// State hanya di frontend selama sesi (tanpa persistence backend/localStorage).
const collapsed = ref(props.defaultCollapsed);
const loading = ref(false);
let loadGeneration = 0;

// Context menu state (reuse pola .ctx-menu existing di project).
const ctxOpen = ref(false);
const ctxMenu = ref(null);
const ctxTask = ref(null);

const runningCount = computed(
  () => tasks.value.filter((t) => t.queue_state === "running").length
);
const nonRunningCount = computed(
  () => tasks.value.filter((t) => t.queue_state !== "running").length
);
const clearing = ref(false);

function runLabel(t) {
  if (t.queue_state === "running") return "RUNNING";
  if (t.queue_state === "disabled") return "DISABLED";
  return "PENDING";
}

function stateIcon(t) {
  if (t.queue_state === "running") return "●";
  if (t.queue_state === "disabled") return "◌";
  return "①";
}

function queuePosition(t) {
  // Posisi 1,2,3... untuk item pending (urutan eksekusi antrian).
  let n = 0;
  for (const item of tasks.value) {
    if (item.queue_state === "pending") {
      n += 1;
      if (item.task_id === t.task_id) return n;
    }
  }
  return null;
}

function normalizeExecution(t) {
  const v = String((t && (t.execution_mode || t.executionMode)) || "").trim().toLowerCase();
  return v === "parallel" ? "Parallel" : "Queue";
}

function shortText(t) {
  const s = (t.task || "").replace(/\s+/g, " ").trim();
  if (!s) return "(no prompt)";
  return s.length > 80 ? s.slice(0, 80) + "…" : s;
}

// Feedback copy prompt
const copyFeedback = ref("");

async function copyPrompt(taskItem) {
  const text = taskItem.task || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    return;
  }
  copyFeedback.value = taskItem.task_id;
  setTimeout(() => {
    if (copyFeedback.value === taskItem.task_id) copyFeedback.value = "";
  }, 1200);
}

async function load() {
  const currentGen = ++loadGeneration;
  loading.value = true;
  try {
    const data = await listTaskQueue(props.projectId || null);
    if (currentGen !== loadGeneration) return;
    tasks.value = data.tasks || [];
    error.value = "";
  } catch (e) {
    if (currentGen !== loadGeneration) return;
    error.value = e?.message || "Failed to load task queue.";
  } finally {
    if (currentGen === loadGeneration) {
      loading.value = false;
    }
  }
}

function toggleCollapse() {
  collapsed.value = !collapsed.value;
}

// --- Context menu ----------------------------------------------------------
function openContext(e, t) {
  e.preventDefault();
  e.stopPropagation();
  // Menu mengikuti posisi kursor; tetap dalam viewport.
  const x = Math.min(e.clientX, window.innerWidth - 190);
  const y = Math.min(e.clientY, window.innerHeight - 200);
  ctxMenu.value = { x, y };
  ctxTask.value = t;
  ctxOpen.value = true;
}

function closeContextMenu() {
  ctxOpen.value = false;
  ctxTask.value = null;
}

function onDocumentClick(e) {
  if (ctxOpen.value && !e.target.closest(".ctx-menu")) closeContextMenu();
}
function onDocumentKeydown(e) {
  if (e.key === "Escape" && ctxOpen.value) closeContextMenu();
}

// --- Aksi queue ------------------------------------------------------------
async function ctxMove(direction) {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t) return;
  try {
    const data = await moveQueueTask(t.task_id, direction);
    tasks.value = data.tasks || tasks.value;
  } catch (e) {
    error.value = e.message || "Gagal menggeser task.";
  }
}

async function ctxDisable() {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t) return;
  try {
    await disableQueueTask(t.task_id);
    await load();
  } catch (e) {
    error.value = e.message || "Gagal men-disable task.";
  }
}

async function ctxEnable() {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t) return;
  try {
    await enableQueueTask(t.task_id);
    await load();
  } catch (e) {
    error.value = e.message || "Gagal meng-enable task.";
  }
}

async function onRemoveSingle(t) {
  if (!t) return;
  const msg =
    t.queue_state === "disabled"
      ? `Remove disabled task "${shortText(t)}"? This task has not started yet.`
      : `Remove task "${shortText(t)}"? This task has not started yet.`;
  if (!window.confirm(msg)) return;
  try {
    await removeQueueTask(t.task_id);
    await load();
  } catch (e) {
    error.value = e.message || "Gagal menghapus task.";
  }
}

function onViewTask(t) {
  if (!t) return;
  emit("view-task", t);
}

async function ctxRemove() {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t) return;
  await onRemoveSingle(t);
}

async function onClearQueue() {
  closeContextMenu();
  if (clearing.value) return;
  const count = nonRunningCount.value;
  if (!count) return;
  const msg = `Clear all ${count} non-running task(s) from queue? Running tasks will not be affected.`;
  if (!window.confirm(msg)) return;
  clearing.value = true;
  try {
    await clearTaskQueue(props.projectId || null);
    await load();
  } catch (e) {
    error.value = e.message || "Gagal mengosongkan antrian.";
  } finally {
    clearing.value = false;
  }
}

function ctxCopyPrompt() {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t || !t.task) return;
  try {
    navigator.clipboard.writeText(t.task);
  } catch (e) {
    // clipboard tidak tersedia
  }
}

function ctxStop() {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t) return;
  emit("stop-task", t.task_id);
}

function ctxView() {
  const t = ctxTask.value;
  closeContextMenu();
  if (!t) return;
  emit("view-task", t);
}

let poll = null;
onMounted(() => {
  load();
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onDocumentKeydown);
  // Refresh ringan berkala (tidak ada event queue khusus di tahap ini).
  // Event terminal task (SSE) juga memicu refresh via prop refreshKey.
  poll = setInterval(load, 5000);
});
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocumentClick);
  document.removeEventListener("keydown", onDocumentKeydown);
  if (poll) clearInterval(poll);
});

watch(
  () => props.refreshKey,
  () => load()
);

watch(
  () => props.projectId,
  () => load()
);
</script>

<template>
  <section class="block queue-block" :class="{ collapsed, 'no-header': hideHeader }">
    <div v-if="!hideHeader" class="drawer-sec-head q-head" @click="toggleCollapse">
      <span class="sec-caret" aria-hidden="true">{{ collapsed ? "▸" : "▾" }}</span>
      <span class="drawer-sec-title">TASK</span>
      <div class="drawer-sec-actions">
        <span v-if="tasks.length > 0" class="q-badge">{{ tasks.length }}</span>
        <span v-if="runningCount" class="q-running-dot" title="Task running">●</span>
        <button
          v-if="nonRunningCount > 0"
          type="button"
          class="q-clear-btn"
          title="Clear non-running tasks"
          aria-label="Clear non-running tasks"
          :disabled="clearing"
          @click.stop="onClearQueue"
        >
          {{ clearing ? "…" : "Clear" }}
        </button>
      </div>
    </div>

    <div v-show="hideHeader || !collapsed" class="q-body">
      <div v-if="error" class="q-error-banner" role="alert">
        <span>{{ error }}</span>
        <button type="button" class="q-retry-btn" @click="load">Retry</button>
      </div>
      <div v-if="!tasks.length && !error" class="side-task-empty q-empty">
        <span>No tasks in queue</span>
        <small>Submitted tasks waiting for execution will appear here</small>
      </div>
      <ul v-else class="q-list">
        <li
          v-for="t in tasks"
          :key="t.task_id"
          class="q-item"
          :class="t.queue_state"
          :title="t.task || ''"
          @contextmenu="openContext($event, t)"
        >
          <span class="q-ico" :class="t.queue_state">{{ stateIcon(t) }}</span>
          <div class="q-text-wrap">
            <span class="q-text">{{ shortText(t) }}</span>
            <span class="q-meta-line">
              <span class="q-state-sm" :class="t.queue_state">{{ runLabel(t) }}</span>
              <span v-if="t.queue_state === 'pending' && queuePosition(t)" class="q-pos">&middot; #{{ queuePosition(t) }}</span>
              <span v-if="t.queue_state === 'disabled'" class="q-pos">disabled</span>
              <span class="q-exec" :class="String((t.execution_mode || '')).toLowerCase() === 'parallel' ? 'parallel' : 'queue'">&middot; {{ normalizeExecution(t) }}</span>
            </span>
          </div>
          <div class="q-actions">
            <button
              type="button"
              class="q-copy-btn"
              :class="{ copied: copyFeedback === t.task_id }"
              :title="copyFeedback === t.task_id ? 'Copied' : 'Copy prompt'"
              :aria-label="copyFeedback === t.task_id ? 'Copied' : 'Copy prompt'"
              @click.stop="copyPrompt(t)"
            >
              <svg v-if="copyFeedback === t.task_id" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
              <svg v-else width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button
              type="button"
              class="q-icon-btn q-view-btn"
              title="View task"
              aria-label="View task"
              @click.stop="onViewTask(t)"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
            <button
              v-if="t.queue_state !== 'running'"
              type="button"
              class="q-icon-btn q-del-btn"
              title="Remove task from queue"
              aria-label="Remove task from queue"
              @click.stop="onRemoveSingle(t)"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </li>
      </ul>
      <div v-if="error" class="q-err">{{ error }}</div>
    </div>

    <!-- Context Menu (pola .ctx-menu existing) -->
    <div
      v-if="ctxOpen && ctxMenu && ctxTask"
      class="ctx-menu"
      :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
      @click.stop
      @contextmenu.prevent
    >
      <div class="ctx-item" @click="ctxCopyPrompt()">Copy Prompt</div>
      <div class="ctx-sep"></div>
      <template v-if="ctxTask.queue_state === 'running'">
        <div class="ctx-item" @click="ctxStop()">Stop</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxView()">View Task</div>
      </template>
      <template v-else>
        <div class="ctx-item" @click="ctxMove('up')">Move Up</div>
        <div class="ctx-item" @click="ctxMove('down')">Move Down</div>
        <div class="ctx-sep"></div>
        <div v-if="ctxTask.queue_state === 'disabled'" class="ctx-item" @click="ctxEnable()">Enable</div>
        <div v-else class="ctx-item" @click="ctxDisable()">Disable</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxView()">View Task</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item ctx-danger" @click="ctxRemove()">Remove</div>
      </template>
        <template v-if="nonRunningCount > 1">
          <div class="ctx-sep"></div>
          <div class="ctx-item ctx-danger" @click="onClearQueue()">Clear Queue</div>
        </template>
    </div>
  </section>
</template>
