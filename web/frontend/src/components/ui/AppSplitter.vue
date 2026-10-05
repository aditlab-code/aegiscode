<script setup>
import { ref, onUnmounted } from 'vue';

const props = defineProps({
  direction: {
    type: String,
    default: 'vertical',
    validator: (v) => ['vertical', 'horizontal'].includes(v)
  },
  modelValue: {
    type: Number,
    required: true
  },
  min: {
    type: Number,
    default: 150
  },
  max: {
    type: Number,
    default: 700
  },
  defaultSize: {
    type: Number,
    default: null
  },
  inverted: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'drag-start', 'drag-end', 'reset']);

const isDragging = ref(false);
let startPos = 0;
let startSize = 0;

function onMouseDown(e) {
  e.preventDefault();
  if (typeof window === 'undefined') return;
  startPos = props.direction === 'vertical' ? e.clientX : e.clientY;
  startSize = props.modelValue;
  isDragging.value = true;
  emit('drag-start');
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function onMouseMove(e) {
  if (!isDragging.value) return;
  const currentPos = props.direction === 'vertical' ? e.clientX : e.clientY;
  const delta = props.inverted ? (startPos - currentPos) : (currentPos - startPos);
  const clamped = Math.max(props.min, Math.min(props.max, Math.round(startSize + delta)));
  emit('update:modelValue', clamped);
}

function onMouseUp() {
  if (!isDragging.value) return;
  if (typeof window !== 'undefined') {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }
  isDragging.value = false;
  emit('drag-end');
}

function onDblClick() {
  if (props.defaultSize != null) {
    emit('update:modelValue', props.defaultSize);
    emit('reset');
  }
}

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }
});
</script>

<template>
  <div
    class="app-splitter"
    :class="[
      direction === 'vertical' ? 'splitter-vertical' : 'splitter-horizontal',
      { 'splitter-dragging': isDragging }
    ]"
    role="separator"
    :aria-orientation="direction"
    @mousedown="onMouseDown"
    @dblclick="onDblClick"
  ></div>
</template>
