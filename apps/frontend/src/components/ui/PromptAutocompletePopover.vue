<script setup>
import { computed, ref, watch, nextTick } from "vue";

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  type: {
    type: String,
    default: "mention", // "mention" | "template"
    validator: (v) => ["mention", "template"].includes(v),
  },
  items: {
    type: Array,
    default: () => [],
  },
  selectedIndex: {
    type: Number,
    default: 0,
  },
  placement: {
    type: String,
    default: "top", // "top" | "bottom"
    validator: (v) => ["top", "bottom"].includes(v),
  },
});

const emit = defineEmits(["select", "close"]);

const listRef = ref(null);

function scrollToSelected() {
  nextTick(() => {
    if (!listRef.value) return;
    const container = listRef.value;
    const items = container.querySelectorAll(".popover-item");
    const activeEl = items[props.selectedIndex];
    if (!activeEl) return;

    if (
      typeof activeEl.getBoundingClientRect === "function" &&
      typeof container.getBoundingClientRect === "function"
    ) {
      const activeRect = activeEl.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      if (activeRect.top < containerRect.top) {
        container.scrollTop -= (containerRect.top - activeRect.top);
      } else if (activeRect.bottom > containerRect.bottom) {
        container.scrollTop += (activeRect.bottom - containerRect.bottom);
      }
    } else if (typeof activeEl.scrollIntoView === "function") {
      activeEl.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  });
}

watch(
  () => props.selectedIndex,
  () => {
    scrollToSelected();
  }
);

watch(
  () => props.visible,
  (val) => {
    if (val) {
      scrollToSelected();
    }
  }
);

watch(
  () => props.items,
  () => {
    scrollToSelected();
  }
);

function selectItem(item) {
  emit("select", item);
}

function fileName(path) {
  if (typeof path !== "string") return path?.name || "";
  const parts = path.split("/");
  return parts[parts.length - 1];
}

function dirName(path) {
  if (typeof path !== "string") return "";
  const parts = path.split("/");
  if (parts.length <= 1) return "";
  return parts.slice(0, -1).join("/");
}
</script>

<template>
  <div
    v-if="visible"
    class="prompt-autocomplete-popover"
    :class="`placement-${placement}`"
    role="listbox"
    :aria-label="type === 'mention' ? 'Mention workspace file' : 'Prompt templates'"
  >
    <div class="popover-header">
      <span class="popover-title">
        <template v-if="type === 'mention'">
          <svg class="popover-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          Mention File
        </template>
        <template v-else>
          <svg class="popover-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
          Prompt Templates
        </template>
      </span>
      <span class="popover-count" v-if="items.length">{{ items.length }} suggestion{{ items.length > 1 ? 's' : '' }}</span>
    </div>

    <div v-if="items.length" ref="listRef" class="popover-list">
      <div
        v-for="(item, idx) in items"
        :key="typeof item === 'string' ? item : item.id || idx"
        class="popover-item"
        :class="{ active: idx === selectedIndex }"
        role="option"
        :aria-selected="idx === selectedIndex ? 'true' : 'false'"
        @mousedown.prevent="selectItem(item)"
      >
        <!-- Mention file item -->
        <template v-if="type === 'mention'">
          <div class="item-file-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
              <polyline points="13 2 13 9 20 9" />
            </svg>
          </div>
          <div class="item-file-content">
            <span class="file-name">{{ fileName(item) }}</span>
            <span v-if="dirName(item)" class="file-dir">{{ dirName(item) }}</span>
          </div>
        </template>

        <!-- Template shortcut item -->
        <template v-else>
          <span class="template-cmd">{{ item.command }}</span>
          <div class="item-template-content">
            <span class="template-label">{{ item.label }}</span>
            <span class="template-desc">{{ item.description }}</span>
          </div>
        </template>
      </div>
    </div>

    <div v-else class="popover-empty">
      No matching {{ type === 'mention' ? 'files' : 'templates' }} found
    </div>

    <div class="popover-footer">
      <span class="shortcut-tip">
        <kbd>↑</kbd><kbd>↓</kbd> navigate · <kbd>↵</kbd> or <kbd>Tab</kbd> insert · <kbd>Esc</kbd> dismiss
      </span>
    </div>
  </div>
</template>

<style scoped>
.prompt-autocomplete-popover {
  position: absolute;
  left: 0;
  right: 0;
  max-height: 250px;
  background: var(--panel-bg, #1e1e1e);
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.12));
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  z-index: 1050;
  font-family: inherit;
  overflow: hidden;
  backdrop-filter: blur(12px);
}

.prompt-autocomplete-popover.placement-top {
  bottom: calc(100% + 8px);
  top: auto;
}

.prompt-autocomplete-popover.placement-bottom {
  top: calc(100% + 6px);
  bottom: auto;
}

.popover-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: var(--header-bg, rgba(255, 255, 255, 0.03));
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted, #8b949e);
}

.popover-title {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.popover-icon {
  color: var(--accent-color, #4a9eff);
}

.popover-count {
  font-size: 10px;
  opacity: 0.75;
}

.popover-list {
  flex: 1;
  overflow-y: auto;
  max-height: 175px;
  padding: 4px;
  position: relative;
  scroll-behavior: auto;
}

.popover-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  color: var(--text-main, #c9d1d9);
  transition: background-color 0.1s ease;
}

.popover-item:hover,
.popover-item.active {
  background: var(--hover-bg, rgba(74, 158, 255, 0.15));
  color: #fff;
}

.item-file-icon {
  display: flex;
  align-items: center;
  color: var(--text-muted, #8b949e);
  flex-shrink: 0;
}

.popover-item.active .item-file-icon {
  color: var(--accent-color, #4a9eff);
}

.item-file-content {
  display: flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
  white-space: nowrap;
}

.file-name {
  font-weight: 500;
  color: var(--text-main, #e6edf3);
}

.file-dir {
  font-size: 11px;
  color: var(--text-muted, #8b949e);
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
}

.template-cmd {
  font-family: monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-color, #58a6ff);
  background: rgba(56, 139, 253, 0.15);
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}

.item-template-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  white-space: nowrap;
}

.template-label {
  font-weight: 500;
  color: var(--text-main, #e6edf3);
}

.template-desc {
  font-size: 11px;
  color: var(--text-muted, #8b949e);
  text-overflow: ellipsis;
  overflow: hidden;
}

.popover-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted, #8b949e);
}

.popover-footer {
  padding: 4px 10px;
  border-top: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  background: var(--header-bg, rgba(255, 255, 255, 0.02));
  font-size: 10px;
  color: var(--text-muted, #8b949e);
  display: flex;
  justify-content: flex-end;
}

.shortcut-tip kbd {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 3px;
  padding: 1px 3px;
  font-size: 9px;
  font-family: monospace;
}
</style>
