<script setup>
import FileExplorer from "./FileExplorer.vue";

const props = defineProps({
  activeProject: {
    type: Object,
    default: null,
  },
  explorerRefresh: {
    type: Number,
    default: 0,
  },
  liveFsChange: {
    type: Object,
    default: null,
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
  "open-file-editor",
  "select-tab",
  "close-tab",
  "clear-tabs",
  "open-folder",
]);

function handleOpenFile(file) {
  emit("open-file", file);
}
</script>

<template>
  <section class="sidebar-panel explorer-panel" aria-label="EXPLORER">
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
</template>
