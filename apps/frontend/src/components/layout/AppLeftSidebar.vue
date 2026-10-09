<script setup>
import { computed } from "vue";
import ExplorerSidebarPanel from "../sidebar/ExplorerSidebarPanel.vue";
import GitSidebarPanel from "../sidebar/GitSidebarPanel.vue";
import ThreadsHistoryPanel from "../sidebar/ThreadsHistoryPanel.vue";
import { formatProjectOption } from "../../services/projectService.js";

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
  "delete-history",
  "open-consultant-session",
  "open-session",
  "select-tab",
  "close-tab",
  "clear-tabs",
  "collapse-sidebar",
  "open-diff",
  "discard-change",
  "stage-change",
  "unstage-change",
  "checkpoint-created",
  "branch-info-updated",
  "changes-updated",
]);

const projectOptions = computed(() => {
  return props.projects.map((p) => formatProjectOption(p));
});

const navDisplayLabel = computed(() => ({
  explorer: 'EXPLORER',
  git: 'SOURCE CONTROL',
  queue: 'THREADS & HISTORY',
  settings: 'SETTINGS',
}[props.activeNav] ?? props.activeNav.toUpperCase()));

function onProjectChange(event) {
  const newId = event.target.value;
  if (newId) {
    emit("select-project", newId);
  }
}
</script>

<template>
  <aside class="app-left-sidebar" aria-label="Tool Sidebar">
    <!-- Header: Section Title & Project Switcher -->
    <div class="sidebar-header">
      <div class="sidebar-section-title-row">
        <span class="sidebar-section-title">{{ navDisplayLabel }}</span>
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
      <ExplorerSidebarPanel
        v-if="activeNav === 'explorer'"
        :active-project="activeProject"
        :explorer-refresh="explorerRefresh"
        :live-fs-change="liveFsChange"
        :open-tabs="openTabs"
        :active-tab-path="activeTabPath"
        :open-tabs2="openTabs2"
        :active-tab-path2="activeTabPath2"
        :split-active="splitActive"
        :active-pane="activePane"
        @open-file="emit('open-file', $event)"
        @open-file-editor="emit('open-file', $event)"
        @select-tab="(path, pane) => emit('select-tab', path, pane)"
        @close-tab="(path, pane) => emit('close-tab', path, pane)"
        @clear-tabs="(pane) => emit('clear-tabs', pane)"
        @open-folder="emit('open-folder')"
      />

      <!-- 2. Git & Source Control Section -->
      <GitSidebarPanel
        v-else-if="activeNav === 'git'"
        :active-project="activeProject"
        :explorer-refresh="explorerRefresh"
        :changes="changes"
        :validation="validation"
        @open-file="emit('open-file', $event)"
        @open-diff="emit('open-diff', $event)"
        @discard-change="emit('discard-change', $event)"
        @stage-change="emit('stage-change', $event)"
        @unstage-change="emit('unstage-change', $event)"
        @checkpoint-created="emit('checkpoint-created', $event)"
        @branch-info-updated="emit('branch-info-updated', $event)"
        @changes-updated="emit('changes-updated', $event)"
      />

      <!-- 3. Threads / History Section -->
      <ThreadsHistoryPanel
        v-else-if="activeNav === 'queue'"
        :selected-project-id="selectedProjectId"
        :active-project="activeProject"
        :active-session-id="activeSessionId"
        :task-history="taskHistory"
        :queue-refresh="queueRefresh"
        @open-session="emit('open-session', $event)"
        @open-consultant-session="emit('open-consultant-session', $event)"
        @view-task="emit('view-task', $event)"
        @open-history-task="emit('open-history-task', $event)"
        @refresh-history="emit('refresh-history')"
        @delete-history="emit('delete-history', $event)"
      />
    </div>
  </aside>
</template>
