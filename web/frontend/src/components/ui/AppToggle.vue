<script setup>
const props = defineProps({
  type: {
    type: String,
    default: 'switch',
    validator: (v) => ['switch', 'tabs'].includes(v)
  },
  modelValue: {
    type: [Boolean, String, Number],
    default: false
  },
  label: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  options: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue', 'change']);

function onSwitchChange(e) {
  const val = e.target.checked;
  emit('update:modelValue', val);
  emit('change', val);
}

function onTabSelect(val) {
  emit('update:modelValue', val);
  emit('change', val);
}
</script>

<template>
  <!-- Switch mode -->
  <label v-if="type === 'switch'" class="slider-toggle">
    <input
      type="checkbox"
      :checked="!!modelValue"
      :disabled="disabled"
      @change="onSwitchChange"
    />
    <span class="slider-track"><span class="slider-thumb"></span></span>
    <span v-if="label" class="slider-label">{{ label }}</span>
  </label>

  <!-- Segmented Tabs mode -->
  <div v-else class="seg-tabs">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="seg-tab"
      :class="{ active: modelValue === opt.value }"
      @click="onTabSelect(opt.value)"
    >
      <span>{{ opt.label }}</span>
      <span
        v-if="opt.badge != null"
        class="seg-badge aether-badge"
        :class="{ 'seg-badge-err': opt.error }"
      >{{ opt.badge }}</span>
    </button>
  </div>
</template>
