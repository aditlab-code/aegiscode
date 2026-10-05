<script setup>
defineProps({
  variant: {
    type: String,
    default: 'block',
    validator: (v) => ['block', 'panel', 'task', 'card'].includes(v)
  },
  title: {
    type: String,
    default: ''
  },
  borderBottom: {
    type: Boolean,
    default: true
  }
});
</script>

<template>
  <section v-if="variant === 'block'" class="block" :style="{ borderBottom: borderBottom ? undefined : 'none' }">
    <div v-if="$slots.header || title || $slots.actions" class="block-head">
      <slot name="header">
        <span class="block-title"><slot name="title">{{ title }}</slot></span>
        <div v-if="$slots.actions" class="block-actions"><slot name="actions" /></div>
      </slot>
    </div>
    <slot />
    <slot v-if="$slots.footer" name="footer" />
  </section>
  <div v-else-if="variant === 'task'" class="task-card">
    <slot />
  </div>
  <div v-else-if="variant === 'panel'" class="panel-card">
    <div v-if="$slots.header || title" class="panel-head">
      <slot name="header">
        <span class="panel-title">{{ title }}</span>
      </slot>
    </div>
    <slot />
    <slot v-if="$slots.footer" name="footer" />
  </div>
  <div v-else-if="variant === 'card'" class="card">
    <div v-if="$slots.header || title" class="card-head">
      <slot name="header">
        <span class="card-title">{{ title }}</span>
      </slot>
    </div>
    <slot />
    <slot v-if="$slots.footer" name="footer" />
  </div>
</template>
