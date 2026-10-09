<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import AppModal from "./AppModal.vue";
import AppButton from "./AppButton.vue";
import { listApprovals, resolveApproval } from "../../api.js";

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  approval: {
    type: Object,
    default: null,
  },
  taskId: {
    type: String,
    default: "",
  },
  autoPoll: {
    type: Boolean,
    default: true,
  },
  pollIntervalMs: {
    type: Number,
    default: 5000,
  },
});

const emit = defineEmits(["update:modelValue", "close", "resolved"]);

const internalApproval = ref(null);
const isResolving = ref(false);
const resolvingAction = ref(null);
const resolveError = ref("");
let pollTimer = null;

const currentApproval = computed(() => props.approval || internalApproval.value || null);
const isOpen = computed({
  get: () => Boolean(props.modelValue || currentApproval.value),
  set: (val) => emit("update:modelValue", val),
});

const toolName = computed(() => {
  const a = currentApproval.value;
  return a?.tool || a?.tool_name || "Unknown Tool";
});

const targetText = computed(() => {
  const a = currentApproval.value;
  return a?.target || a?.command || a?.path || "";
});

const reasonText = computed(() => {
  const a = currentApproval.value;
  return a?.reason || a?.message || "Action requires human approval under current operational policy.";
});

const requestId = computed(() => {
  const a = currentApproval.value;
  return a?.request_id || a?.id || "";
});

const sessionId = computed(() => {
  const a = currentApproval.value;
  return a?.session_id || "";
});

const taskIdText = computed(() => {
  const a = currentApproval.value;
  return a?.task_id || props.taskId || "";
});

async function fetchPendingApprovals() {
  try {
    const res = await listApprovals(props.taskId || null);
    const pendingList = Array.isArray(res?.approvals) ? res.approvals : [];
    if (pendingList.length > 0) {
      internalApproval.value = pendingList[0];
      emit("update:modelValue", true);
    } else if (internalApproval.value && !props.approval) {
      internalApproval.value = null;
      emit("update:modelValue", false);
    }
  } catch (err) {
    // Silent catch on polling failure to not disrupt user experience
  }
}

async function handleResolve(allow) {
  const reqId = requestId.value;
  if (!reqId || isResolving.value) return;

  isResolving.value = true;
  resolvingAction.value = allow ? "approve" : "reject";
  resolveError.value = "";

  try {
    await resolveApproval(reqId, allow);
    emit("resolved", { requestId: reqId, allow, approval: currentApproval.value });
    internalApproval.value = null;
    emit("update:modelValue", false);
    emit("close");
  } catch (err) {
    resolveError.value = err.message || "Failed to resolve approval request.";
  } finally {
    isResolving.value = false;
    resolvingAction.value = null;
  }
}

function handleClose() {
  if (isResolving.value) return;
  emit("update:modelValue", false);
  emit("close");
}

function onApprovalRequestedEvent(e) {
  const payload = e.detail?.data || e.detail?.payload || e.detail || {};
  if (payload.request_id || payload.tool) {
    internalApproval.value = payload;
    emit("update:modelValue", true);
  }
}

function onApprovalResolvedEvent(e) {
  const payload = e.detail?.data || e.detail?.payload || e.detail || {};
  const resId = payload.request_id || payload.id;
  if (!resId || resId === requestId.value) {
    internalApproval.value = null;
    emit("update:modelValue", false);
    emit("close");
  }
}

onMounted(() => {
  if (props.autoPoll) {
    fetchPendingApprovals();
    pollTimer = setInterval(fetchPendingApprovals, props.pollIntervalMs);
  }
  if (typeof window !== "undefined") {
    window.addEventListener("aegis:approval_requested", onApprovalRequestedEvent);
    window.addEventListener("aegis:approval_resolved", onApprovalResolvedEvent);
  }
});

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (typeof window !== "undefined") {
    window.removeEventListener("aegis:approval_requested", onApprovalRequestedEvent);
    window.removeEventListener("aegis:approval_resolved", onApprovalResolvedEvent);
  }
});

watch(() => props.approval, (newVal) => {
  if (newVal) {
    internalApproval.value = newVal;
    resolveError.value = "";
  }
});
</script>

<template>
  <AppModal
    v-if="isOpen && currentApproval"
    :model-value="isOpen"
    max-width="520px"
    modal-class="approval-modal-dialog"
    @close="handleClose"
  >
    <template #header>
      <div class="approval-modal-header">
        <div class="approval-header-title">
          <svg class="approval-shield-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <span>Human Approval Required</span>
        </div>
        <span class="approval-tool-badge" :title="`Tool: ${toolName}`">
          Tool: <strong>{{ toolName }}</strong>
        </span>
      </div>
    </template>

    <div class="approval-modal-body">
      <div v-if="targetText" class="approval-item">
        <div class="approval-item-label">Target / Command:</div>
        <div class="approval-code-block" :title="targetText">
          <code>{{ targetText }}</code>
        </div>
      </div>

      <div class="approval-item">
        <div class="approval-item-label">Reason:</div>
        <div class="approval-item-reason">
          {{ reasonText }}
        </div>
      </div>

      <div class="approval-metadata-grid">
        <div v-if="requestId" class="metadata-cell">
          <span class="metadata-label">Request ID:</span>
          <span class="metadata-val" :title="requestId">{{ requestId }}</span>
        </div>
        <div v-if="sessionId" class="metadata-cell">
          <span class="metadata-label">Session ID:</span>
          <span class="metadata-val" :title="sessionId">{{ sessionId }}</span>
        </div>
        <div v-if="taskIdText" class="metadata-cell">
          <span class="metadata-label">Task ID:</span>
          <span class="metadata-val" :title="taskIdText">{{ taskIdText }}</span>
        </div>
      </div>

      <div v-if="resolveError" class="approval-error-banner" role="alert">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span>{{ resolveError }}</span>
      </div>
    </div>

    <template #actions>
      <div class="approval-modal-actions">
        <AppButton
          variant="danger"
          size="sm"
          :disabled="isResolving"
          :busy="isResolving && resolvingAction === 'reject'"
          @click="handleResolve(false)"
        >
          Reject
        </AppButton>
        <AppButton
          variant="primary"
          size="sm"
          :disabled="isResolving"
          :busy="isResolving && resolvingAction === 'approve'"
          @click="handleResolve(true)"
        >
          Approve
        </AppButton>
      </div>
    </template>
  </AppModal>
</template>

<style scoped>
.approval-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.approval-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14.5px;
  color: var(--text);
}

.approval-shield-icon {
  color: var(--warn);
  flex-shrink: 0;
}

.approval-tool-badge {
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(229, 160, 13, 0.15);
  border: 1px solid rgba(229, 160, 13, 0.35);
  color: var(--warn);
  white-space: nowrap;
}

.approval-modal-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 6px 0;
  font-size: 13px;
  color: var(--text-dim);
}

.approval-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.approval-item-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-faint);
}

.approval-code-block {
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--bg-surface-2, rgba(0, 0, 0, 0.3));
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  line-height: 1.45;
  color: var(--text);
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}

.approval-item-reason {
  line-height: 1.45;
  color: var(--text);
  background: rgba(255, 255, 255, 0.03);
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.05));
}

.approval-metadata-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg-surface, rgba(255, 255, 255, 0.02));
  border: 1px dashed var(--border-soft, rgba(255, 255, 255, 0.07));
  border-radius: 6px;
  font-size: 11px;
}

.metadata-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}

.metadata-label {
  font-weight: 500;
  color: var(--text-faint);
  flex-shrink: 0;
}

.metadata-val {
  font-family: var(--font-mono, monospace);
  color: var(--text-dim);
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.approval-error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid rgba(220, 38, 38, 0.3);
  color: var(--err);
  border-radius: 6px;
  font-size: 12px;
}

.approval-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
}
</style>
