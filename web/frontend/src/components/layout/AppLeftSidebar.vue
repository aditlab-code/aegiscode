<script setup>
import { computed, ref, watch } from "vue";
import FileExplorer from "../FileExplorer.vue";
import ChangesPanel from "../ChangesPanel.vue";
import GithubBackupPanel from "../GithubBackupPanel.vue";
import QueuePanel from "../QueuePanel.vue";
import { formatProjectOption } from "../../services/projectService.js";
import {
  listSessions,
  createSession,
  renameSession,
  deleteSession,
} from "../../api.js";

const props = defineProps({
  activeNav: {
    type: String,
    default: "explorer",
  },
  activeProject: {
    type: Object,
    default: null,
  },
  projects: {
    type: Array,
    default: () => [],
  },
  changes: {
    type: Array,
    default: () => [],
  },
  validation: {
    type: Object,
    default: () => ({}),
  },
  explorerRefresh: {
    type: Number,
    default: 0,
  },
  liveFsChange: {
    type: Object,
    default: null,
  },
  queueRefresh: {
    type: Number,
    default: 0,
  },
  taskHistory: {
    type: Array,
    default: () => [],
  },
  activeSessionId: {
    type: String,
    default: "",
  },
  selectedProjectId: {
    type: String,
    default: "",
  },
  connected: {
    type: Boolean,
    default: false,
  },
  gatewayAddress: {
    type: String,
    default: "",
  },
  agentStatus: {
    type: Object,
    default: () => ({ label: "idle", cls: "status-off" }),
  },
  openTabs: {
    type: Array,
    default: () => [],
  },
  activeTabPath: {
    type: String,
    default: "",
  },
  openTabs2: {
    type: Array,
    default: () => [],
  },
  activeTabPath2: {
    type: String,
    default: "",
  },
  splitActive: {
    type: Boolean,
    default: false,
  },
  activePane: {
    type: String,
    default: "pane1",
  },
});

const emit = defineEmits([
  "open-file",
  "select-project",
  "close-project",
  "open-folder",
  "stop-task",
  "view-task",
  "open-history-task",
  "refresh-history",
  "open-consultant-session",
  "open-session",
  "select-tab",
  "close-tab",
  "clear-tabs",
  "collapse-sidebar",
  "open-diff",
  "discard-change",
  "branch-info-updated",
]);

const projectOptions = computed(() => {
  return props.projects.map((p) => formatProjectOption(p));
});

function onProjectChange(event) {
  const newId = event.target.value;
  if (newId) {
    emit("select-project", newId);
  }
}

function handleOpenFile(file) {
  emit("open-file", file);
}

function handleOpenDiff(file) {
  emit("open-diff", file);
}

// Task/Thread view subtab: Threads | Queue | History
const taskSubTab = ref("threads");
const sessions = ref([]);
const sessionsLoading = ref(false);
const renamingSessionId = ref("");
const renameTitleInput = ref("");

async function loadThreads() {
  if (sessionsLoading.value) return;
  sessionsLoading.value = true;
  try {
    const projId = props.selectedProjectId || props.activeProject?.id || null;
    const res = await listSessions(projId);
    sessions.value = res?.sessions || [];
  } catch (err) {
    sessions.value = [];
  } finally {
    sessionsLoading.value = false;
  }
}

function selectSession(sessionId) {
  emit("open-session", sessionId);
  emit("open-consultant-session", sessionId);
}

async function handleNewThread() {
  try {
    const projId = props.selectedProjectId || props.activeProject?.id || null;
    const res = await createSession({ projectId: projId, title: "New Thread" });
    if (res?.session_id) {
      await loadThreads();
      selectSession(res.session_id);
    }
  } catch (err) {
    selectSession("");
  }
}

function startRename(s, event) {
  event?.stopPropagation?.();
  renamingSessionId.value = s.session_id;
  renameTitleInput.value = s.title || "";
}

async function saveRename(s, event) {
  event?.stopPropagation?.();
  const nextTitle = renameTitleInput.value.trim();
  if (!nextTitle) {
    renamingSessionId.value = "";
    return;
  }
  try {
    const projId = props.selectedProjectId || props.activeProject?.id || null;
    await renameSession(s.session_id, nextTitle, projId);
    await loadThreads();
  } catch (err) {
    console.error("Gagal mengubah judul sesi:", err);
  } finally {
    renamingSessionId.value = "";
  }
}

async function handleDeleteSession(s, event) {
  event?.stopPropagation?.();
  if (!confirm(`Hapus thread "${s.title || s.session_id}"?`)) return;
  try {
    const projId = props.selectedProjectId || props.activeProject?.id || null;
    await deleteSession(s.session_id, projId);
    if (props.activeSessionId === s.session_id) {
      selectSession("");
    }
    await loadThreads();
  } catch (err) {
    console.error("Gagal menghapus sesi:", err);
  }
}

watch(
  () => [taskSubTab.value, props.activeProject?.id, props.queueRefresh],
  ([tab]) => {
    if (tab === "threads" || tab === "sessions") {
      loadThreads();
    } else if (tab === "history") {
      emit("refresh-history");
    }
  },
  { immediate: true }
);

function formatSessionTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "";
  }
}

function formatTaskTime(ts) {
  if (!ts) return "";
  try {
    const d = new Date(typeof ts === "number" ? ts * 1000 : ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return String(ts);
  }
}

function statusTagClass(st) {
  const s = String(st || "").toLowerCase();
  if (s === "done" || s === "success") return "tag-done";
  if (s === "running") return "tag-running";
  if (s === "failed" || s === "error") return "tag-err";
  return "tag-idle";
}
</script>

<template>
  <aside class="app-left-sidebar" aria-label="Tool Sidebar">
    <!-- Header: Section Title & Project Switcher -->
    <div class="sidebar-header">
      <div class="sidebar-section-title-row">
        <span class="sidebar-section-title">{{ activeNav.toUpperCase() }}</span>
        <div class="sidebar-header-actions">
          <button
            type="button"
            class="collapse-sidebar-btn"
            title="Collapse Sidebar"
            aria-label="Collapse Sidebar"
            @click="emit('collapse-sidebar')"
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
          <button
            v-if="activeProject"
            type="button"
            class="close-project-btn"
            title="Close Workspace"
            aria-label="Close Project"
            @click="emit('close-project')"
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <div class="project-switcher-row">
        <div class="project-select-wrapper">
          <select
            class="project-select"
            :value="activeProject ? activeProject.id : selectedProjectId"
            aria-label="Select Project"
            @change="onProjectChange"
          >
            <option
              v-for="opt in projectOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- Content Area: Dynamic Panels based on activeNav -->
    <div class="sidebar-content">
      <!-- 1. Explorer Section -->
      <section v-if="activeNav === 'explorer'" class="sidebar-panel explorer-panel" aria-label="EXPLORER">
        <span class="sr-only">EXPLORER</span>
        <FileExplorer
          v-if="activeProject"
          :project="activeProject"
          :refresh-key="explorerRefresh"
          :live-change="liveFsChange"
          :open-tabs="openTabs"
          :active-tab-path="activeTabPath"
          :open-tabs2="openTabs2"
          :active-tab-path2="activeTabPath2"
          :split-active="splitActive"
          :active-pane="activePane"
          @open-file="handleOpenFile"
          @open-file-editor="handleOpenFile"
          @select-tab="(path, pane) => emit('select-tab', path, pane)"
          @close-tab="(path, pane) => emit('close-tab', path, pane)"
          @clear-tabs="(pane) => emit('clear-tabs', pane)"
        />
        <div v-else class="sidebar-empty-workspace">
          <div class="empty-ws-content">
            <span class="empty-ws-title">No Folder Opened</span>
            <p class="empty-ws-desc">Open a folder to start inspecting and editing files.</p>
            <button
              type="button"
              class="sidebar-open-folder-btn"
              @click="emit('open-folder')"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <span>Open Folder…</span>
            </button>
          </div>
        </div>
      </section>

      <!-- 2. Git & Source Control Section -->
      <section v-else-if="activeNav === 'git'" class="sidebar-panel git-panel">
        <div class="backup-subpanel">
          <GithubBackupPanel
            :project="activeProject"
            :refresh-key="explorerRefresh"
            @branch-info-updated="emit('branch-info-updated', $event)"
          >
            <ChangesPanel
              :changes="changes"
              :validation="validation || {}"
              :project="activeProject"
              :refresh-key="explorerRefresh"
              @open-file="handleOpenFile"
              @open-diff="handleOpenDiff"
              @discard-change="emit('discard-change', $event)"
            />
          </GithubBackupPanel>
        </div>
      </section>

      <!-- 3. Task Queue / History / Threads Section -->
      <section v-else-if="activeNav === 'queue'" class="sidebar-panel queue-panel task-multitab-panel">
        <div class="task-subtabs-bar" role="tablist" aria-label="Task Subtabs">
          <button
            type="button"
            class="task-subtab-pill"
            :class="{ active: taskSubTab === 'threads' || taskSubTab === 'sessions' }"
            role="tab"
            :aria-selected="taskSubTab === 'threads' || taskSubTab === 'sessions'"
            @click="taskSubTab = 'threads'; loadThreads();"
          >
            Threads
            <span v-if="sessions.length" class="subtab-count">{{ sessions.length }}</span>
          </button>
          <button
            type="button"
            class="task-subtab-pill"
            :class="{ active: taskSubTab === 'queue' }"
            role="tab"
            :aria-selected="taskSubTab === 'queue'"
            @click="taskSubTab = 'queue'"
          >
            Queue
          </button>
          <button
            type="button"
            class="task-subtab-pill"
            :class="{ active: taskSubTab === 'history' }"
            role="tab"
            :aria-selected="taskSubTab === 'history'"
            @click="taskSubTab = 'history'; emit('refresh-history');"
          >
            History
            <span v-if="taskHistory.length" class="subtab-count">{{ taskHistory.length }}</span>
          </button>
        </div>

        <div class="task-subtab-body">
          <!-- Subtab 1: Threads / Sessions -->
          <div v-if="taskSubTab === 'threads' || taskSubTab === 'sessions'" class="task-subpane sidebar-sessions-pane">
            <div class="side-sess-head">
              <span class="side-sess-title">Threads</span>
              <button
                type="button"
                class="side-sess-new-btn"
                title="Start New Thread"
                @click="handleNewThread"
              >
                + New Thread
              </button>
            </div>

            <div v-if="sessionsLoading && !sessions.length" class="side-task-loading">
              Loading threads…
            </div>

            <div v-else-if="!sessions.length" class="side-task-empty">
              <span>No conversation threads</span>
              <small>Start a new thread to begin chatting or executing tasks</small>
            </div>

            <div v-else class="side-sess-list">
              <div
                v-for="s in sessions"
                :key="s.session_id"
                class="side-sess-item"
                :class="{ active: s.session_id === activeSessionId }"
                role="button"
                tabindex="0"
                @click="selectSession(s.session_id)"
                @keydown.enter="selectSession(s.session_id)"
              >
                <div class="side-sess-main">
                  <template v-if="renamingSessionId === s.session_id">
                    <input
                      v-model="renameTitleInput"
                      type="text"
                      class="side-sess-rename-input"
                      @click.stop
                      @keydown.enter.stop="saveRename(s, $event)"
                      @keydown.esc.stop="renamingSessionId = ''"
                    />
                  </template>
                  <template v-else>
                    <div class="side-sess-name-row">
                      <span class="side-sess-name" :title="s.title || 'New Thread'">
                        {{ s.title || "New Thread" }}
                      </span>
                      <span v-if="s.execution_state === 'running'" class="side-sess-running-tag">
                        Running
                      </span>
                    </div>
                    <div class="side-sess-meta">
                      <span>{{ formatSessionTime(s.updated_at) }}</span>
                      <span v-if="s.turn_count"> · {{ s.turn_count }} turns</span>
                    </div>
                  </template>
                </div>

                <div class="side-sess-actions" @click.stop>
                  <template v-if="renamingSessionId === s.session_id">
                    <button
                      type="button"
                      class="side-sess-action-btn"
                      title="Simpan"
                      @click="saveRename(s, $event)"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    </button>
                    <button
                      type="button"
                      class="side-sess-action-btn"
                      title="Batal"
                      @click="renamingSessionId = ''"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </template>
                  <template v-else>
                    <button
                      type="button"
                      class="side-sess-action-btn"
                      title="Ubah judul"
                      @click="startRename(s, $event)"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    </button>
                    <button
                      type="button"
                      class="side-sess-action-btn side-sess-delete-btn"
                      title="Hapus thread"
                      @click="handleDeleteSession(s, $event)"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- Subtab 2: Queue -->
          <div v-show="taskSubTab === 'queue'" class="task-subpane">
            <QueuePanel
              :hide-header="true"
              :project-id="selectedProjectId || (activeProject ? activeProject.id : null)"
              :refresh-key="queueRefresh"
              @stop-task="emit('stop-task', $event)"
              @view-task="emit('view-task', $event)"
            />
          </div>

          <!-- Subtab 3: Task History -->
          <div v-if="taskSubTab === 'history'" class="task-subpane sidebar-history-pane">
            <div v-if="!taskHistory.length" class="side-task-empty">
              <span>No recorded task history</span>
              <small>Active and completed tasks will appear here</small>
            </div>
            <div v-else class="side-hist-list">
              <div
                v-for="t in taskHistory"
                :key="t.task_id"
                class="side-hist-item"
                role="button"
                tabindex="0"
                @click="emit('open-history-task', t)"
                @keydown.enter="emit('open-history-task', t)"
              >
                <div class="side-hist-top">
                  <span class="status-tag" :class="statusTagClass(t.status)">{{ t.status }}</span>
                  <span class="side-hist-time">{{ formatTaskTime(t.last_timestamp) }}</span>
                </div>
                <div class="side-hist-prompt" :title="t.task || '(no prompt)'">
                  {{ t.task || "(no prompt)" }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </aside>
</template>
