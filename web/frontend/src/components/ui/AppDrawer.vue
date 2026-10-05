<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true
  },
  sub: {
    type: String,
    default: ''
  },
  collapsed: {
    type: Boolean,
    default: false
  },
  collapsible: {
    type: Boolean,
    default: true
  },
  headerClass: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:collapsed', 'toggle']);

function handleToggle() {
  if (!props.collapsible) return;
  const next = !props.collapsed;
  emit('update:collapsed', next);
  emit('toggle');
}
</script>

<template>
  <section class="block drawer-block" :class="{ collapsed }">
    <div class="drawer-sec-head" :class="headerClass" @click="handleToggle">
      <span v-if="collapsible" class="sec-caret" aria-hidden="true">{{ collapsed ? '▸' : '▾' }}</span>
      <span class="drawer-sec-title">
        <slot name="title">{{ title }}</slot>
      </span>
      <span v-if="sub" class="drawer-sec-sub" :title="sub">{{ sub }}</span>
      <div class="drawer-sec-actions" @click.stop>
        <slot name="badge" />
        <slot name="actions" />
      </div>
    </div>
    <div v-show="!collapsed" class="drawer-content">
      <slot />
    </div>
  </section>
</template>
