<script setup>
import { computed } from "vue";

const props = defineProps({
  tabs: {
    type: Array,
    default: () => [],
  },
  activeTabPath: {
    type: String,
    default: "",
  },
  pane: {
    type: String,
    default: "pane1",
  },
  splitActive: {
    type: Boolean,
    default: false,
  },
  splitDirection: {
    type: String,
    default: "vertical",
  },
  isPaneDirty: {
    type: Boolean,
    default: false,
  },
  conflictFile: {
    type: String,
    default: null,
  },
  conflictAddedLines: {
    type: Number,
    default: 0,
  },
  conflictRemovedLines: {
    type: Number,
    default: 0,
  },
  closingTab: {
    type: Object,
    default: null,
  },
  closingTabPane: {
    type: String,
    default: "",
  },
  ariaLabel: {
    type: String,
    default: "Editor Tabs",
  },
});

const emit = defineEmits([
  "select-tab",
  "close-tab",
  "save-tab",
  "toggle-split",
  "toggle-orient",
  "close-split",
  "resolve-keep-mine",
  "resolve-accept-agent",
  "resolve-review-diff",
  "confirm-close-save",
  "confirm-close-discard",
  "confirm-close-cancel",
]);

const tabList = computed(() => {
  if (Array.isArray(props.tabs)) return props.tabs;
  if (props.tabs?.value && Array.isArray(props.tabs.value)) return props.tabs.value;
  return [];
});

const showSaveButton = computed(() => {
  return (
    props.activeTabPath &&
    !["aegis://settings", "aegis://welcome"].includes(props.activeTabPath)
  );
});
</script>

<template>
  <div class="wb-editor-tabs-bar" :class="{ 'wb-pane-tabs-bar': splitActive }">
    <div class="wb-editor-tabs" role="tablist" :aria-label="ariaLabel">
      <div
        v-for="tab in tabList"
        :key="pane + '-' + tab.path"
        class="wb-tab-item"
        :class="{ active: tab.path === activeTabPath, dirty: tab.dirty }"
        role="tab"
        :aria-selected="tab.path === activeTabPath"
        @click.stop="emit('select-tab', tab.path, pane)"
      >
        <span class="tab-icon" aria-hidden="true">
          <!-- Settings Icon -->
          <svg
            v-if="tab.path === 'aegis://settings'"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
            />
          </svg>
          <!-- Welcome Canvas Icon -->
          <svg
            v-else-if="tab.path === 'aegis://welcome'"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
          <!-- Diff Icon -->
          <svg
            v-else-if="tab.isDiff || tab.path.startsWith('diff://')"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="12" y1="3" x2="12" y2="21" />
          </svg>
          <!-- Standard File Icon -->
          <svg
            v-else
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </span>
        <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
        <span
          v-if="tab.conflict"
          class="tab-conflict-dot"
          title="Agent modified this file while you have unsaved edits"
        >!</span>
        <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
        <button
          type="button"
          class="tab-close-btn"
          title="Close Tab"
          aria-label="Close Tab"
          @click.stop="emit('close-tab', tab.path, pane)"
        >
          ×
        </button>

        <!-- Inline Popover for Agent Dirty Conflict -->
        <div
          v-if="conflictFile && tab.path === conflictFile"
          class="wb-conflict-popover"
          @click.stop
        >
          <div class="conflict-header">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"
              />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>Agent modified this file</span>
          </div>
          <div class="conflict-diff-preview">
            <span class="diff-stat-add">+{{ conflictAddedLines }} lines</span>
            <span class="diff-stat-del">-{{ conflictRemovedLines }} lines</span>
          </div>
          <div class="conflict-actions">
            <button
              type="button"
              class="conf-btn conf-keep"
              @click="emit('resolve-keep-mine', tab.path)"
            >
              Keep Mine
            </button>
            <button
              type="button"
              class="conf-btn conf-accept"
              @click="emit('resolve-accept-agent', tab.path)"
            >
              Accept Agent
            </button>
            <button
              type="button"
              class="conf-btn conf-diff"
              @click="emit('resolve-review-diff', tab.path)"
            >
              Review Diff
            </button>
          </div>
        </div>

        <!-- Inline Popover for Unsaved Changes -->
        <div
          v-if="closingTab && closingTabPane === pane && closingTab.path === tab.path"
          class="wb-tab-inline-popover"
          @click.stop
        >
          <div class="pop-msg">Save changes?</div>
          <div class="pop-actions">
            <button
              type="button"
              class="pop-btn pop-save"
              @click="emit('confirm-close-save')"
            >
              Save
            </button>
            <button
              type="button"
              class="pop-btn pop-discard"
              @click="emit('confirm-close-discard')"
            >
              Don't Save
            </button>
            <button
              type="button"
              class="pop-btn pop-cancel"
              @click="emit('confirm-close-cancel')"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Actions toolbar: Save and Split/Orient/Close Controls -->
    <div class="wb-tab-actions">
      <!-- Save File Button -->
      <button
        v-if="showSaveButton"
        type="button"
        class="wb-tab-save-btn"
        :class="{ dirty: isPaneDirty }"
        :disabled="!isPaneDirty"
        :title="isPaneDirty ? 'Save (⌘S)' : 'All changes saved'"
        aria-label="Save File"
        @click.stop="emit('save-tab', pane)"
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
          <polyline points="17 21 17 13 7 13 7 21" />
          <polyline points="7 3 7 8 15 8" />
        </svg>
        <span v-if="isPaneDirty" class="save-dot">●</span>
      </button>

      <!-- Single Window Mode: Split Editor Toggle Button -->
      <button
        v-if="!splitActive"
        type="button"
        class="wb-tab-action-btn wb-tab-split-btn"
        :class="{ active: splitActive }"
        :title="splitActive ? 'Close Split Editor' : 'Split Editor Right'"
        aria-label="Split Editor"
        @click.stop="emit('toggle-split')"
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
        >
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="12" y1="3" x2="12" y2="21" />
        </svg>
      </button>

      <!-- Split Window Mode (Pane 1): Orientation Toggle -->
      <button
        v-else-if="pane === 'pane1'"
        type="button"
        class="wb-tab-action-btn wb-tab-orient-btn"
        :title="splitDirection === 'vertical' ? 'Switch to Horizontal Split (Stacked)' : 'Switch to Vertical Split (Side by Side)'"
        aria-label="Toggle Split Direction"
        @click.stop="emit('toggle-orient')"
      >
        <svg
          v-if="splitDirection === 'vertical'"
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="3" y1="12" x2="21" y2="12" />
        </svg>
        <svg
          v-else
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="12" y1="3" x2="12" y2="21" />
        </svg>
      </button>

      <!-- Split Window Mode (Pane 2): Close Split Pane Button -->
      <button
        v-else-if="pane === 'pane2'"
        type="button"
        class="wb-tab-action-btn split-pane-close-btn"
        title="Close Split Editor"
        aria-label="Close Split Editor"
        @click.stop="emit('close-split', false)"
      >
        <span style="font-size: 16px; line-height: 1;">×</span>
      </button>
    </div>
  </div>
</template>
