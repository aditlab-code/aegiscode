<script setup>
import { ref, computed } from "vue";
import AgentDrawerPanel from "../AgentDrawerPanel.vue";
import ConsultantChat from "../ConsultantChat.vue";

const props = defineProps({
  activeTab: {
    type: String,
    default: "agents",
    validator: (v) => ["agents", "ask", "activity", "consultant"].includes(v),
  },
  task: {
    type: Object,
    default: () => ({}),
  },
  taskHistory: {
    type: Array,
    default: () => [],
  },
  taskTag: {
    type: Object,
    default: () => ({ cls: "", label: "" }),
  },
  showTaskMeta: {
    type: Boolean,
    default: false,
  },
  taskProvider: {
    type: String,
    default: "",
  },
  taskModel: {
    type: String,
    default: "",
  },
  taskExecutionLabel: {
    type: String,
    default: "Queue",
  },
  taskRoundLabel: {
    type: String,
    default: "",
  },
  taskDurationLabel: {
    type: String,
    default: "",
  },
  taskTimerLive: {
    type: Boolean,
    default: false,
  },
  showTaskTelemetry: {
    type: Boolean,
    default: false,
  },
  taskLlmRounds: {
    type: Number,
    default: 0,
  },
  taskToolCalls: {
    type: Number,
    default: 0,
  },
  taskTokensLabel: {
    type: String,
    default: "",
  },
  taskTokensTooltip: {
    type: String,
    default: "",
  },
  lifecycleSteps: {
    type: Array,
    default: () => [],
  },
  lifecyclePct: {
    type: Number,
    default: 0,
  },
  activityPhase: {
    type: String,
    default: "",
  },
  activityEvents: {
    type: Array,
    default: () => [],
  },
  showReasoning: {
    type: Boolean,
    default: false,
  },
  activityCopied: {
    type: Boolean,
    default: false,
  },
  isRunning: {
    type: Boolean,
    default: false,
  },
  isSubmitting: {
    type: Boolean,
    default: false,
  },
  stopInProgress: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: "",
  },
  consultantOpen: {
    type: Boolean,
    default: false,
  },
  consultantProps: {
    type: Object,
    default: () => ({}),
  },
  providers: {
    type: Array,
    default: () => [],
  },
  providerInstanceId: {
    type: String,
    default: "",
  },
  modelId: {
    type: String,
    default: "",
  },
  mode: {
    type: String,
    default: "balanced",
  },
  activeTabPath: {
    type: String,
    default: "",
  },
  activeFile: {
    type: Object,
    default: () => null,
  },
});

const emit = defineEmits([
  "update:activeTab",
  "close",
  "open-report",
  "copy-activity",
  "open-composer",
  "request-stop",
  "submit-task",
  "open-settings",
  "run-consultant-task",
  "consultant-event",
  "apply-to-editor",
  "update:provider-instance-id",
  "update:model-id",
  "update:mode",
  "update:active-session-id",
]);

const agentPanelRef = ref(null);

const isAgentsTab = computed(() => props.activeTab === "agents" || props.activeTab === "activity");
const isAskTab = computed(() => props.activeTab === "ask" || props.activeTab === "consultant");

function setTab(tab) {
  emit("update:activeTab", tab);
}

function focusPrompt() {
  agentPanelRef.value?.focusPrompt?.();
}

function handleSubmit() {
  agentPanelRef.value?.handleSubmit?.();
}

async function viewReport(taskId) {
  return agentPanelRef.value?.viewReport?.(taskId);
}

defineExpose({
  focusPrompt,
  handleSubmit,
  viewReport,
});
</script>

<template>
  <aside class="app-right-drawer" aria-label="AI Assistant Panel">
    <!-- Header with Aegis Assistant Branding, Dual-Tab Switcher & Close Button -->
    <div class="right-drawer-header">
      <div class="rd-header-title-box">
        <svg class="rd-sparkle-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"></path>
        </svg>
        <span class="rd-main-title">Aegis Assistant</span>
        <span class="rd-badge-pill">ACTIVE</span>
      </div>

      <div class="right-drawer-tabs" role="tablist">
        <button
          type="button"
          class="rd-tab-btn"
          :class="{ active: isAgentsTab }"
          role="tab"
          :aria-selected="isAgentsTab"
          aria-label="Agent Activity"
          title="Agent: autonomous task execution"
          @click="setTab(activeTab === 'activity' ? 'activity' : 'agents')"
        >
          <span class="rd-tab-title">Agent</span>
        </button>
        <button
          type="button"
          class="rd-tab-btn"
          :class="{ active: isAskTab }"
          role="tab"
          :aria-selected="isAskTab"
          aria-label="Consultant Chat"
          title="Ask: Quick or Deep project consultation"
          @click="setTab(activeTab === 'consultant' ? 'consultant' : 'ask')"
        >
          <span class="rd-tab-title">Ask</span>
        </button>
      </div>

      <div class="rd-header-actions">
        <button
          type="button"
          class="rd-close-btn"
          title="Collapse Assistant (Cmd+J)"
          aria-label="Close Assistant Panel"
          @click="emit('close')"
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- Body Area -->
    <div class="right-drawer-body">
      <!-- 1. Agent Activity Tab -->
      <AgentDrawerPanel
        v-if="isAgentsTab"
        ref="agentPanelRef"
        :task="task"
        :task-history="taskHistory"
        :task-tag="taskTag"
        :show-task-meta="showTaskMeta"
        :task-provider="taskProvider"
        :task-model="taskModel"
        :task-execution-label="taskExecutionLabel"
        :task-round-label="taskRoundLabel"
        :task-duration-label="taskDurationLabel"
        :task-timer-live="taskTimerLive"
        :show-task-telemetry="showTaskTelemetry"
        :task-llm-rounds="taskLlmRounds"
        :task-tool-calls="taskToolCalls"
        :task-tokens-label="taskTokensLabel"
        :task-tokens-tooltip="taskTokensTooltip"
        :lifecycle-steps="lifecycleSteps"
        :lifecycle-pct="lifecyclePct"
        :activity-phase="activityPhase"
        :activity-events="activityEvents"
        :show-reasoning="showReasoning"
        :activity-copied="activityCopied"
        :is-running="isRunning"
        :is-submitting="isSubmitting"
        :stop-in-progress="stopInProgress"
        :error="error"
        :providers="providers"
        :provider-instance-id="providerInstanceId"
        :model-id="modelId"
        :mode="mode"
        :active-tab-path="activeTabPath"
        :active-file="activeFile"
        @open-report="emit('open-report', $event)"
        @copy-activity="emit('copy-activity')"
        @request-stop="emit('request-stop')"
        @submit-task="emit('submit-task', $event)"
        @open-settings="emit('open-settings', $event)"
        @update:provider-instance-id="emit('update:provider-instance-id', $event)"
        @update:model-id="emit('update:model-id', $event)"
        @update:mode="emit('update:mode', $event)"
      />

      <!-- 2. Consultant Chat Tab -->
      <div v-else-if="isAskTab" class="rd-consultant-view">
        <ConsultantChat
          :embedded="true"
          v-bind="consultantProps"
          @close="emit('close')"
          @run-task="emit('run-consultant-task', $event)"
          @stop-task="emit('request-stop', $event)"
          @consultant-event="emit('consultant-event', $event)"
          @apply-to-editor="emit('apply-to-editor', $event)"
          @open-settings="emit('open-settings', $event)"
          @update:provider-instance-id="emit('update:provider-instance-id', $event)"
          @update:model-id="emit('update:model-id', $event)"
          @update:active-session-id="emit('update:active-session-id', $event)"
        />
      </div>
    </div>
  </aside>
</template>

<style scoped>
.rd-tab-title {
  font-weight: 500;
}
.rd-tab-sub {
  font-size: 11px;
  color: var(--text-faint);
  opacity: 0.8;
}
.rd-tab-btn.active .rd-tab-sub {
  color: var(--text-dim);
}
</style>
