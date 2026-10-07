<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'files',
    validator: (v) => ['files', 'commands'].includes(v)
  },
  files: {
    type: Array,
    default: () => []
  },
  commands: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits([
  'update:modelValue',
  'update:mode',
  'select-file',
  'select-command',
  'close'
]);

const isMounted = ref(false);
const query = ref('');
const selectedIndex = ref(0);
const inputRef = ref(null);

const currentMode = ref(props.mode);

watch(() => props.mode, (newMode) => {
  currentMode.value = newMode;
});

const filteredItems = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (currentMode.value === 'files') {
    if (!q) return props.files.slice(0, 50);
    return props.files.filter((f) => f.toLowerCase().includes(q)).slice(0, 50);
  } else {
    if (!q) return props.commands.slice(0, 50);
    return props.commands.filter((c) => {
      const matchTitle = c.title && c.title.toLowerCase().includes(q);
      const matchCat = c.category && c.category.toLowerCase().includes(q);
      return matchTitle || matchCat;
    }).slice(0, 50);
  }
});

watch(filteredItems, () => {
  selectedIndex.value = 0;
});

function close() {
  emit('update:modelValue', false);
  emit('close');
}

function selectItem(item) {
  if (currentMode.value === 'files') {
    emit('select-file', item);
  } else {
    emit('select-command', item);
  }
  close();
}

function selectCurrent() {
  const items = filteredItems.value;
  if (items.length > 0 && selectedIndex.value >= 0 && selectedIndex.value < items.length) {
    selectItem(items[selectedIndex.value]);
  }
}

function navigateUp() {
  const len = filteredItems.value.length;
  if (len === 0) return;
  selectedIndex.value = (selectedIndex.value - 1 + len) % len;
}

function navigateDown() {
  const len = filteredItems.value.length;
  if (len === 0) return;
  selectedIndex.value = (selectedIndex.value + 1) % len;
}

function onGlobalKeyDown(e) {
  const isMeta = e.metaKey || e.ctrlKey;
  if (isMeta && e.key.toLowerCase() === 'p') {
    e.preventDefault();
    currentMode.value = 'files';
    emit('update:mode', 'files');
    emit('update:modelValue', true);
  } else if (isMeta && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    currentMode.value = 'commands';
    emit('update:mode', 'commands');
    emit('update:modelValue', true);
  }
}

watch(() => props.modelValue, (open) => {
  if (open) {
    query.value = '';
    selectedIndex.value = 0;
    nextTick(() => {
      if (inputRef.value) {
        inputRef.value.focus();
      }
    });
  }
});

onMounted(() => {
  isMounted.value = true;
  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', onGlobalKeyDown);
  }
});

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', onGlobalKeyDown);
  }
});
</script>

<template>
  <Teleport to="body" :disabled="!isMounted">
    <div v-if="modelValue" class="cmd-palette-backdrop" @click.self="close">
      <div class="cmd-palette-modal">
        <div class="cmd-palette-input-wrap">
          <span class="cmd-palette-mode-pill aegis-badge">{{ currentMode === 'files' ? '⌘P Files' : '⌘K Commands' }}</span>
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            class="cmd-palette-input"
            :placeholder="currentMode === 'files' ? 'Type to search files...' : 'Type a command or prompt...'"
            @keydown.up.prevent="navigateUp"
            @keydown.down.prevent="navigateDown"
            @keydown.enter.prevent="selectCurrent"
            @keydown.esc.prevent="close"
          />
        </div>
        <ul v-if="filteredItems.length" class="cmd-palette-list">
          <li
            v-for="(item, idx) in filteredItems"
            :key="item.id || item.key || item"
            class="cmd-palette-item"
            :class="{ active: idx === selectedIndex }"
            @click="selectItem(item)"
            @mouseenter="selectedIndex = idx"
          >
            <span class="cmd-item-main">
              <span class="cmd-item-icon">
                <svg v-if="currentMode === 'files'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
              </span>
              <span class="cmd-item-title">{{ currentMode === 'files' ? item : item.title }}</span>
            </span>
            <span v-if="item.shortcut || item.category" class="cmd-item-meta aegis-badge">
              {{ item.shortcut || item.category }}
            </span>
          </li>
        </ul>
        <div v-else class="cmd-palette-empty">No results found</div>
        <div class="cmd-palette-footer">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>esc Close</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
