<script setup>
defineProps({
  variant: {
    type: String,
    default: 'count',
    validator: (v) => ['count', 'status', 'drawer', 'chip', 'seg'].includes(v)
  },
  status: {
    type: String,
    default: ''
  },
  dot: {
    type: Boolean,
    default: false
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md'].includes(v)
  }
});
</script>

<template>
  <span v-if="variant === 'count'" class="aegis-badge aether-badge q-badge"><slot /></span>
  <span v-else-if="variant === 'drawer'" class="drawer-badge"><slot /></span>
  <span v-else-if="variant === 'status'" :class="['status-tag', status ? `status-${status}` : '']">
    <span v-if="dot" class="status-dot">●</span><slot />
  </span>
  <span v-else-if="variant === 'chip'" :class="['chip', size === 'sm' ? 'chip-sm' : '', status]">
    <span v-if="dot" class="dot">●</span><slot />
  </span>
  <span v-else-if="variant === 'seg'" class="seg-badge aegis-badge aether-badge"><slot /></span>
</template>
