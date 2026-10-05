<script setup>
import { computed } from 'vue';

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

const formattedDuration = computed(() => {
  if (props.duration == null || props.duration === '') return '';
  const str = String(props.duration).trim();
  if (!str) return '';
  return str.endsWith('s') ? str : `${str}s`;
});

function toggle() {
  emit('update:collapsed', !props.collapsed);
  emit('toggle');
}
</script>

<template>
  <div class="app-thinking-block" :class="{ collapsed }">
    <div class="thinking-header" @click="toggle">
      <span class="sec-caret" aria-hidden="true">{{ collapsed ? '▸' : '▾' }}</span>
      <span class="thinking-icon" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9"/>
          <path d="M9 10h.01M15 10h.01M9 15c1.5 1 4.5 1 6 0"/>
        </svg>
      </span>
      <span class="thinking-title">{{ title }}</span>
      <span v-if="busy" class="reasoning-dots" aria-hidden="true"><i>.</i><i>.</i><i>.</i></span>
      <span v-if="formattedDuration" class="thinking-badge aether-badge">{{ formattedDuration }}</span>
    </div>
    <div v-show="!collapsed" class="thinking-body">
      <slot />
    </div>
  </div>
</template>
