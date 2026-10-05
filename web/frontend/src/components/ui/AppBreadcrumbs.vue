<script setup>
import { computed } from 'vue';

const props = defineProps({
  path: {
    type: String,
    default: ''
  },
  root: {
    type: String,
    default: 'AegisCode'
  },
  separator: {
    type: String,
    default: '›'
  }
});

defineEmits(['navigate', 'select-file']);

const segments = computed(() => {
  if (!props.path) return [];
  const parts = props.path.replace(/^\/+/, '').split('/').filter(Boolean);
  let curr = '';
  return parts.map((part, idx) => {
    curr = curr ? `${curr}/${part}` : part;
    const isFile = idx === parts.length - 1;
    return {
      label: part,
      path: curr,
      isFile
    };
  });
});
</script>

<template>
  <nav class="app-breadcrumbs" aria-label="Breadcrumbs">
    <span class="breadcrumb-crumb breadcrumb-root" @click="$emit('navigate', '.')">
      <span class="breadcrumb-icon" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
        </svg>
      </span>
      <span>{{ root }}</span>
    </span>
    <template v-for="(seg, idx) in segments" :key="seg.path">
      <span class="breadcrumb-sep" aria-hidden="true">{{ separator }}</span>
      <span
        class="breadcrumb-crumb"
        :class="{ 'breadcrumb-current': idx === segments.length - 1 }"
        @click="seg.isFile ? $emit('select-file', seg.path) : $emit('navigate', seg.path)"
      >
        {{ seg.label }}
      </span>
    </template>
  </nav>
</template>
