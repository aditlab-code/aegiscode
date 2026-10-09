<script setup>
import { computed } from "vue";
import AppModal from "../ui/AppModal.vue";
import AppButton from "../ui/AppButton.vue";

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  closingTab: {
    type: Object,
    default: null,
  },
  closingSplitEntirely: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "update:modelValue",
  "confirm-save",
  "confirm-discard",
  "cancel",
]);

const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit("update:modelValue", val),
});

const modalTitle = computed(() => {
  if (props.closingSplitEntirely) {
    return "Close Split Window";
  }
  return "Unsaved Changes";
});

const message = computed(() => {
  if (props.closingSplitEntirely) {
    return "The split window has files with unsaved changes. Do you want to save them before closing?";
  }
  const name = props.closingTab?.name || props.closingTab?.path || "this file";
  return `Do you want to save changes made to "${name}" before closing?`;
});

function onSave() {
  emit("confirm-save");
}

function onDiscard() {
  emit("confirm-discard");
}

function onCancel() {
  emit("cancel");
  isOpen.value = false;
}
</script>

<template>
  <AppModal
    v-model="isOpen"
    :title="modalTitle"
    max-width="440px"
    @close="onCancel"
  >
    <div class="confirm-close-content">
      <p class="confirm-close-msg">{{ message }}</p>
      <div class="confirm-close-actions">
        <AppButton variant="ghost" size="sm" @click="onCancel">
          Cancel
        </AppButton>
        <AppButton variant="danger" size="sm" @click="onDiscard">
          Don't Save
        </AppButton>
        <AppButton variant="primary" size="sm" @click="onSave">
          Save
        </AppButton>
      </div>
    </div>
  </AppModal>
</template>

<style scoped>
.confirm-close-content {
  padding: 4px 0 0 0;
}

.confirm-close-msg {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.5;
  margin: 0 0 16px 0;
}

.confirm-close-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
