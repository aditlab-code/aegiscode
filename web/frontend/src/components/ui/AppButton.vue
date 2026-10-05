<script setup>
import { computed } from 'vue';

const props = defineProps({
  variant: {
    type: String,
    default: 'ghost',
    validator: (v) => ['primary', 'ghost', 'danger', 'icon'].includes(v)
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md'].includes(v)
  },
  busy: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  type: {
    type: String,
    default: 'button'
  },
  title: {
    type: String,
    default: ''
  },
  active: {
    type: Boolean,
    default: false
  }
});

defineEmits(['click']);

const computedClasses = computed(() => {
  const classes = [];
  if (props.variant === 'icon') {
    classes.push('icon-btn');
  } else {
    classes.push('btn-aether');
    if (props.variant === 'primary') classes.push('btn-primary', 'btn-primary-a');
    else if (props.variant === 'danger') classes.push('btn-danger', 'btn-danger-a');
    else classes.push('btn-ghost', 'btn-ghost-a');
  }
  if (props.size === 'sm') classes.push('btn-sm');
  if (props.active) classes.push('active');
  if (props.busy) classes.push('is-busy');
  return classes;
});
</script>

<template>
  <button
    :type="type"
    :title="title"
    :disabled="disabled || busy"
    :class="computedClasses"
    @click="$emit('click', $event)"
  >
    <svg v-if="busy" class="btn-spinner" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="2" stroke-dasharray="28" stroke-dashoffset="10" />
    </svg>
    <slot v-else-if="$slots.icon" name="icon" />
    <slot />
    <slot v-if="$slots['icon-right']" name="icon-right" />
  </button>
</template>
