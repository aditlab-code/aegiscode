<script setup>
import { computed, ref, watch } from "vue";
import FileExplorer from "../FileExplorer.vue";
import ChangesPanel from "../ChangesPanel.vue";
import GithubBackupPanel from "../GithubBackupPanel.vue";
import QueuePanel from "../QueuePanel.vue";
import { formatProjectOption } from "../../services/projectService.js";
import { listConsultantSessions } from "../../api.js";

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
  "open-consultant-session",
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

// 3-way subtab in Task view: Queue | History | Sessions
const taskSubTab = ref("queue");
const sessions = ref([]);
const sessionsLoading = ref(false);

async function loadConsultantSessions() {
  if (sessionsLoading.value) return;
  sessionsLoading.value = true;
  try {
    const projId = props.selectedProjectId || props.activeProject?.id || null;
    const res = await listConsultantSessions(projId);
    sessions.value = res?.sessions || [];
  } catch (err) {
    sessions.value = [];
  } finally {
    sessionsLoading.value = false;
  }
}

watch(
  () => [taskSubTab.value, props.activeProject?.id, props.queueRefresh],
  ([tab]) => {
    if (tab === "sessions") {
      loadConsultantSessions();
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
    <!-- Header: Workspace & Project Switcher -->
    <div class="sidebar-header">
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
        <button
          type="button"
          class="collapse-sidebar-btn"
          title="Collapse Sidebar"
          aria-label="Collapse Sidebar"
          @click="emit('collapse-sidebar')"
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
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="9" y1="3" x2="9" y2="21"/>
          </svg>
        </button>
        <button
          type="button"
          class="close-project-btn"
          title="Close Workspace"
          aria-label="Close Project"
          @click="emit('close-project')"
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
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
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

      <!-- 3. Task Queue / History / Sessions Section -->
      <section v-else-if="activeNav === 'queue'" class="sidebar-panel queue-panel task-multitab-panel">
        <div class="task-subtabs-bar" role="tablist" aria-label="Task Subtabs">
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
            @click="taskSubTab = 'history'"
          >
            History
            <span v-if="taskHistory.length" class="subtab-count">{{ taskHistory.length }}</span>
          </button>
          <button
            type="button"
            class="task-subtab-pill"
            :class="{ active: taskSubTab === 'sessions' }"
            role="tab"
            :aria-selected="taskSubTab === 'sessions'"
            @click="taskSubTab = 'sessions'"
          >
            Sessions
            <span v-if="sessions.length" class="subtab-count">{{ sessions.length }}</span>
          </button>
        </div>

        <div class="task-subtab-body">
          <!-- Subtab 1: Queue -->
          <div v-show="taskSubTab === 'queue'" class="task-subpane">
            <QueuePanel
              :hide-header="true"
              :project-id="selectedProjectId || (activeProject ? activeProject.id : null)"
              :refresh-key="queueRefresh"
              @stop-task="emit('stop-task', $event)"
              @view-task="emit('view-task', $event)"
            />
          </div>

          <!-- Subtab 2: Task History -->
          <div v-if="taskSubTab === 'history'" class="task-subpane sidebar-history-pane">
            <div v-if="!taskHistory.length" class="side-task-empty">
              <span>No recorded task history</span>
              <small>Completed tasks will appear here</small>
            </div>
            <div v-else class="side-hist-list">
              <div
                v-for="t in taskHistory"
                :key="t.task_id"
                class="side-hist-item"
                role="button"
                tabindex="0"
                @click="emit('open-history-task', t.task_id)"
                @keydown.enter="emit('open-history-task', t.task_id)"
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

          <!-- Subtab 3: Consultant Sessions -->
          <div v-if="taskSubTab === 'sessions'" class="task-subpane sidebar-sessions-pane">
            <div class="side-sess-head">
              <span class="side-sess-title">Consultant Sessions</span>
              <button
                type="button"
                class="side-sess-new-btn"
                title="Start New Chat in Consultant"
                @click="emit('open-consultant-session', '')"
              >
                + New Chat
              </button>
            </div>

            <div v-if="sessionsLoading && !sessions.length" class="side-task-loading">
              Loading sessions…
            </div>

            <div v-else-if="!sessions.length" class="side-task-empty">
              <span>No saved chat sessions</span>
              <small>Start chatting in Consultant to create one</small>
            </div>

            <div v-else class="side-sess-list">
              <div
                v-for="s in sessions"
                :key="s.session_id"
                class="side-sess-item"
                :class="{ active: s.session_id === activeSessionId }"
                role="button"
                tabindex="0"
                @click="emit('open-consultant-session', s.session_id)"
                @keydown.enter="emit('open-consultant-session', s.session_id)"
              >
                <div class="side-sess-main">
                  <div class="side-sess-name" :title="s.title || 'New Chat'">
                    {{ s.title || "New Chat" }}
                  </div>
                  <div class="side-sess-meta">
                    <span>{{ formatSessionTime(s.updated_at) }}</span>
                    <span v-if="s.turn_count"> · {{ s.turn_count }} turns</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </aside>
</template>
