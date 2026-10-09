<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  maxWidth: {
    type: String,
    default: '460px'
  },
  closeOnEsc: {
    type: Boolean,
    default: true
  },
  closeOnClickOutside: {
    type: Boolean,
    default: true
  },
  modalClass: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'close']);

const isMounted = ref(false);

function close() {
  emit('update:modelValue', false);
  emit('close');
}

function onBackdropClick() {
  if (props.closeOnClickOutside) {
    close();
  }
}

function onKeyDown(e) {
  if (props.closeOnEsc && e.key === 'Escape') {
    close();
  }
}

onMounted(() => {
  isMounted.value = true;
  if (typeof window !== 'undefined' && props.modelValue) {
    window.addEventListener('keydown', onKeyDown);
  }
});

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', onKeyDown);
  }
});

watch(() => props.modelValue, (val) => {
  if (typeof window === 'undefined') return;
  if (val) {
    window.addEventListener('keydown', onKeyDown);
  } else {
    window.removeEventListener('keydown', onKeyDown);
  }
});
</script>

<template>
  <Teleport to="body" :disabled="!isMounted">
    <div
      v-if="modelValue"
      class="modal-backdrop"
      @click.self="onBackdropClick"
      role="dialog"
      aria-modal="true"
    >
      <div class="modal" :class="modalClass" :style="{ maxWidth }">
        <div v-if="title || $slots.header" class="modal-title">
          <slot name="header">{{ title }}</slot>
        </div>
        <div class="modal-body">
          <slot />
        </div>
        <div v-if="$slots.actions || $slots.footer" class="modal-actions">
          <slot name="actions">
            <slot name="footer" />
          </slot>
        </div>
      </div>
    </div>
  </Teleport>
</template>
