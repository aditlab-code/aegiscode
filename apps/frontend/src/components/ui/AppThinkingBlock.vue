<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  title: {
    type: String,
    default: 'Thinking...'
  },
  duration: {
    type: [Number, String],
    default: null
  },
  collapsed: {
    type: Boolean,
    default: true
  },
  busy: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:collapsed', 'toggle']);

const isCollapsed = ref(props.collapsed);
watch(
  () => props.collapsed,
  (val) => {
    isCollapsed.value = val;
  }
);

const formattedDuration = computed(() => {
  if (props.duration == null || props.duration === '') return '';
  const num = Number(props.duration);
  if (!isNaN(num)) {
    if (num >= 1000) return `${(num / 1000).toFixed(1)}s`;
    if (num > 60) return `${Math.round(num)}s`;
    return `${num}s`;
  }
  const str = String(props.duration).trim();
  return str.endsWith('s') ? str : `${str}s`;
});

function toggle() {
  isCollapsed.value = !isCollapsed.value;
  emit('update:collapsed', isCollapsed.value);
  emit('toggle');
}
</script>

<template>
  <div class="app-thinking-block" :class="{ collapsed: isCollapsed }">
    <div class="thinking-header" @click="toggle">
      <span class="sec-caret" aria-hidden="true">{{ isCollapsed ? '▸' : '▾' }}</span>
      <span class="thinking-icon" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9"/>
          <path d="M9 10h.01M15 10h.01M9 15c1.5 1 4.5 1 6 0"/>
        </svg>
      </span>
      <span class="thinking-title">{{ title }}</span>
      <span v-if="busy" class="reasoning-dots" aria-hidden="true"><i>.</i><i>.</i><i>.</i></span>
      <span v-if="formattedDuration" class="thinking-badge app-badge">{{ formattedDuration }}</span>
    </div>
    <div v-show="!isCollapsed" class="thinking-body">
      <slot />
    </div>
  </div>
</template>
