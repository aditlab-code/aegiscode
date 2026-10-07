<script setup>
import { ref, computed, watch, nextTick } from "vue";
import AppCard from "../ui/AppCard.vue";
import AgentActivity from "../AgentActivity.vue";
import ConsultantChat from "../ConsultantChat.vue";
import PromptAutocompletePopover from "../ui/PromptAutocompletePopover.vue";
import { usePromptAutocomplete } from "../../services/promptSuggestionService.js";
import { getTaskReport } from "../../api.js";
import { renderMarkdown } from "../../markdown.js";

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

const isAgentsTab = computed(() => props.activeTab === "agents" || props.activeTab === "activity");
const isAskTab = computed(() => props.activeTab === "ask" || props.activeTab === "consultant");

const providerOptions = computed(() =>
  (props.providers || []).filter((p) => p.enabled !== false)
);

const modelOptions = computed(() => {
  const inst = providerOptions.value.find((p) => p.id === props.providerInstanceId);
  return inst ? (inst.models || []).filter((m) => m.enabled !== false) : [];
});

watch(
  () => [props.providers, props.providerInstanceId],
  () => {
    const en = (props.providers || []).filter((p) => p.enabled !== false);
    if (!en.length) return;
    if (!props.providerInstanceId || !en.some((p) => p.id === props.providerInstanceId)) {
      const first = en.find((p) => (p.models || []).some((m) => m.enabled !== false)) || en[0];
      emit("update:provider-instance-id", first.id);
      const ms = (first.models || []).filter((m) => m.enabled !== false);
      if (ms.length > 0) emit("update:model-id", ms[0].id);
    } else {
      const inst = en.find((p) => p.id === props.providerInstanceId);
      const ms = inst ? (inst.models || []).filter((m) => m.enabled !== false) : [];
      if (ms.length > 0 && (!props.modelId || !ms.some((m) => m.id === props.modelId))) {
        emit("update:model-id", ms[0].id);
      }
    }
  },
  { immediate: true }
);

function handleProviderChange(e) {
  const nextId = String(e.target.value || "");
  emit("update:provider-instance-id", nextId);
  const inst = providerOptions.value.find((p) => p.id === nextId);
  const models = inst ? (inst.models || []).filter((m) => m.enabled !== false) : [];
  emit("update:model-id", models[0] ? models[0].id : "");
}

function handleModelChange(e) {
  emit("update:model-id", String(e.target.value || ""));
}

const promptText = ref("");
const promptTextarea = ref(null);
const inlineReport = ref(null);
const loadingReport = ref(false);
const activeReportTaskId = ref("");

const {
  popoverVisible,
  popoverType,
  popoverItems,
  popoverIndex,
  updateSuggestions,
  applySelectedItem,
  handleKeydown: autocompleteKeydown,
  pushHistory,
  seedHistory,
  closePopover,
} = usePromptAutocomplete({
  storageKey: "aegis_task_prompt_history",
  onUpdateText: (val) => {
    promptText.value = val;
  },
});

watch(
  [() => props.task, () => props.taskHistory],
  ([curTask, curHist]) => {
    const seeds = [];
    if (curTask?.text) seeds.push(curTask.text);
    if (curTask?.title && curTask.title !== curTask?.text) seeds.push(curTask.title);
    if (Array.isArray(curHist)) {
      for (const item of curHist) {
        const t = item?.task || item?.text || item?.title;
        if (t) seeds.push(t);
      }
    }
    if (seeds.length > 0) {
      seedHistory(seeds);
    }
  },
  { immediate: true }
);

function onPromptInput() {
  const el = promptTextarea.value;
  const pos = el ? el.selectionStart : promptText.value.length;
  updateSuggestions(promptText.value, pos);
}

function onPromptKeydown(e) {
  const res = autocompleteKeydown(e, promptText.value, promptTextarea.value);
  if (res.handled) {
    if (res.text !== undefined) {
      promptText.value = res.text;
    }
    return;
  }
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
}

function onSelectPromptSuggestion(item) {
  promptText.value = applySelectedItem(item, promptText.value, promptTextarea.value);
}

function setTab(tab) {
  emit("update:activeTab", tab);
}

function handleSubmit() {
  const text = promptText.value.trim();
  if (!text || props.isSubmitting) return;
  pushHistory(text);
  emit("submit-task", text);
  promptText.value = "";
}

async function viewReport(taskId) {
  if (!taskId || loadingReport.value) return;
  // Laporan dibuka in-drawer saja; TIDAK memancarkan open-report global agar
  // modal overlay ReportViewer tidak ikut muncul (race condition).
  activeReportTaskId.value = taskId;
  loadingReport.value = true;
  try {
    const data = await getTaskReport(taskId);
    inlineReport.value = data?.report || "";
  } catch (e) {
    inlineReport.value = "Failed to load report: " + (e.message || "");
  } finally {
    loadingReport.value = false;
  }
}

function closeInlineReport() {
  activeReportTaskId.value = "";
  inlineReport.value = null;
}

// Compact header strip helpers
const taskMetaTooltip = computed(() => {
  const parts = [];
  if (props.taskProvider) parts.push(`Provider: ${props.taskProvider}`);
  if (props.taskModel) parts.push(`Model: ${props.taskModel}`);
  if (props.taskExecutionLabel) parts.push(`Execution: ${props.taskExecutionLabel}`);
  if (props.taskRoundLabel) parts.push(`Round: ${props.taskRoundLabel}`);
  if (props.showTaskTelemetry) {
    if (props.taskLlmRounds) parts.push(`LLM: ${props.taskLlmRounds} rounds`);
    if (props.taskToolCalls) parts.push(`Tools: ${props.taskToolCalls} calls`);
    if (props.taskTokensLabel) parts.push(`Tokens: ${props.taskTokensLabel}`);
  }
  return parts.length ? parts.join(" · ") : (props.task?.id ? "Hover for task info" : "No task info");
});

// Path SVG terpadu untuk badge status (pengganti glyph/emotikon).
const statusIconPath = computed(() => {
  const s = props.task?.status || "idle";
  if (s === "running") return '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>';
  if (s === "done" || s === "completed") return '<path d="M20 6L9 17l-5-5"/>';
  if (s === "failed") return '<path d="M18 6L6 18M6 6l12 12"/>';
  if (s === "cancelled") return '<circle cx="12" cy="12" r="10"/><line x1="4.9" y1="4.9" x2="19.1" y2="19.1"/>';
  return '<circle cx="12" cy="12" r="9"/>';
});

function focusPrompt() {
  nextTick(() => {
    if (promptTextarea.value) {
      promptTextarea.value.focus();
    }
  });
}

defineExpose({
  focusPrompt,
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
      <div v-if="isAgentsTab" class="rd-activity-view">
        <!-- Inline Report View (if active) -->
        <div v-if="activeReportTaskId" class="drawer-inline-report">
          <div class="inline-report-header">
            <button type="button" class="inline-report-back-btn" @click="closeInlineReport">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
              </svg>
              <span>Back to Activity</span>
            </button>
            <span class="report-badge mono">{{ activeReportTaskId }}</span>
          </div>
          <div class="inline-report-body">
            <div v-if="loadingReport" class="wb-empty">Loading report…</div>
            <div v-else-if="!inlineReport" class="wb-empty">No report available for this task.</div>
            <div v-else class="md" v-html="renderMarkdown(inlineReport)"></div>
          </div>
        </div>

        <template v-else>
          <!-- ── Compact Task Header Strip ── -->
          <div class="task-hstrip" :title="taskMetaTooltip">
            <span class="sr-only">Latest Task</span>
            <span class="ths-badge" :class="`ths-${task.status || 'idle'}`" aria-label="`Status: ${task.status || 'idle'}`">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" v-html="statusIconPath"></svg>
            </span>
            <span v-if="task.id" class="ths-id mono">{{ task.id }}</span>
            <span class="ths-prompt" :title="task.text || 'No task yet'">
              {{ task.text || "No task yet" }}
            </span>
            <span v-if="taskProvider" class="sr-only">{{ taskProvider }}</span>
            <span v-if="taskModel" class="sr-only">{{ taskModel }}</span>
            <span v-if="taskExecutionLabel" class="sr-only">{{ taskExecutionLabel }}</span>
            <span v-if="taskRoundLabel" class="sr-only">{{ taskRoundLabel }}</span>
            <span v-if="taskLlmRounds" class="sr-only">{{ taskLlmRounds }} LLM Rounds</span>
            <span v-if="taskToolCalls" class="sr-only">{{ taskToolCalls }} Tool Calls</span>
            <span v-if="taskTokensLabel" class="sr-only">{{ taskTokensLabel }}</span>
            <span v-if="lifecyclePct !== undefined" class="sr-only">{{ lifecyclePct }}% complete</span>
            <span v-if="activityPhase" class="sr-only">{{ activityPhase }}</span>
            <span v-if="taskDurationLabel" class="ths-dur" :class="{ live: taskTimerLive }">
              {{ taskDurationLabel }}
            </span>
            <!-- Copy activity -->
            <button
              class="ths-icon-btn"
              :class="{ copied: activityCopied }"
              type="button"
              :title="activityCopied ? 'Copied' : 'Copy activity log'"
              :aria-label="activityCopied ? 'Copied' : 'Copy activity log'"
              @click="emit('copy-activity')"
            >
              <svg v-if="activityCopied" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M20 6L9 17l-5-5" />
              </svg>
              <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="9" y="9" width="12" height="12" rx="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            </button>
            <!-- Report -->
            <button
              v-if="task.id"
              class="ths-icon-btn"
              type="button"
              title="View Agent Report"
              aria-label="View Agent Report"
              @click="viewReport(task.id)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6M9 13h6M9 17h4" />
              </svg>
            </button>
            <span v-if="taskTag.label" class="tag ths-tag" :class="taskTag.cls">{{ taskTag.label }}</span>
          </div>

          <!-- ── Unified Vertical Timeline ── -->
          <div class="rd-scroll-area">
            <span class="sr-only">aegis — agent activity</span>
            <AgentActivity
              :events="activityEvents"
              :status="task.status"
              :is-reasoning="showReasoning"
              :lifecycle-steps="lifecycleSteps"
              :activity-phase="activityPhase"
            />
          </div>
        </template>

        <!-- Integrated Interactive Chat Card -->
        <div class="drawer-chat-card" style="position: relative; overflow: visible;">
          <PromptAutocompletePopover
            :visible="popoverVisible"
            :type="popoverType"
            :items="popoverItems"
            :selected-index="popoverIndex"
            placement="top"
            @select="onSelectPromptSuggestion"
            @close="closePopover"
          />
          <div class="chat-card-header">
            <div class="chat-provider-controls" :title="`Provider: ${taskProvider} · Model: ${taskModel}`">
              <span class="badge-dot">●</span>
              <select
                class="chat-header-select"
                :value="providerInstanceId"
                title="Select Provider"
                aria-label="Select Provider"
                :disabled="isRunning"
                @change="handleProviderChange"
              >
                <option v-if="!providerOptions.length" value="">{{ taskProvider || "No provider" }}</option>
                <option v-for="p in providerOptions" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select>
              <span class="chat-sep">/</span>
              <select
                class="chat-header-select"
                :value="modelId"
                title="Select Model"
                aria-label="Select Model"
                :disabled="isRunning || !providerInstanceId"
                @change="handleModelChange"
              >
                <option v-if="!modelOptions.length" value="">{{ taskModel || "No model" }}</option>
                <option v-for="m in modelOptions" :key="m.id" :value="m.id">
                  {{ m.model_name }}
                </option>
              </select>
            </div>
            <button
              type="button"
              class="chat-settings-btn"
              title="Configure Provider (AegisCode)"
              aria-label="Configure Provider"
              @click="emit('open-settings', 'providers')"
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
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </div>
          <div class="chat-card-body">
            <textarea
              ref="promptTextarea"
              v-model="promptText"
              class="chat-prompt-textarea"
              rows="2"
              placeholder="Ask AegisCode to build something… (@ for file, / for template)"
              :disabled="isRunning"
              @input="onPromptInput"
              @keydown="onPromptKeydown"
              @click="onPromptInput"
            ></textarea>
          </div>
          <div class="chat-card-actions">
            <div class="chat-card-actions-left">
              <select
                :value="mode"
                class="agent-mode-select consultant-mode-select"
                title="Execution Policy Mode: Fast, Balanced, or Deep"
                aria-label="Execution Policy Mode"
                :disabled="isRunning"
                @change="emit('update:mode', $event.target.value)"
              >
                <option value="fast">Fast</option>
                <option value="balanced">Balanced</option>
                <option value="deep">Deep</option>
              </select>
            </div>
            <div class="chat-card-actions-right">
              <button
                v-if="isRunning"
                type="button"
                class="chat-stop-btn"
                title="Stop running task"
                :disabled="stopInProgress"
                @click="emit('request-stop')"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
                <span>Stop</span>
              </button>
              <button
                type="button"
                class="chat-send-btn"
                :disabled="isSubmitting || !promptText.trim()"
                :title="isRunning ? 'Enqueue task to queue (Enter)' : 'Send prompt to AegisCode (Enter)'"
                aria-label="Send Task"
                @click="handleSubmit"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
                <span>{{ isRunning ? 'Enqueue' : 'Send' }}</span>
              </button>
            </div>
          </div>
          <div v-if="error" class="wb-error">{{ error }}</div>
        </div>
      </div>

      <!-- 2. Consultant Chat Tab -->
      <div v-else-if="isAskTab" class="rd-consultant-view">
        <ConsultantChat
          :embedded="true"
          v-bind="consultantProps"
          @close="emit('close')"
          @run-task="emit('run-consultant-task', $event)"
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
/* ── Compact Task Header Strip ── */
.task-hstrip {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-soft);
  background: transparent;
  min-height: 36px;
  cursor: default;
  overflow: hidden;
}

.ths-badge {
  flex: 0 0 auto;
  font-size: 11px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid var(--border-soft);
  color: var(--text-faint);
  line-height: 1;
}
.ths-badge.ths-running {
  background: rgba(45, 125, 78, 0.2);
  border-color: rgba(45, 125, 78, 0.5);
  color: var(--accent-muted);
}
.ths-badge.ths-done,
.ths-badge.ths-completed {
  background: rgba(52, 211, 153, 0.14);
  border-color: rgba(52, 211, 153, 0.4);
  color: var(--ok);
}
.ths-badge.ths-failed {
  background: rgba(248, 113, 113, 0.14);
  border-color: rgba(248, 113, 113, 0.4);
  color: var(--err);
}
.ths-badge.ths-cancelled {
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.35);
  color: var(--warn);
}

.ths-prompt {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 11.5px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--mono);
}

.ths-dur {
  flex: 0 0 auto;
  font-size: 10.5px;
  color: var(--text-faint);
  font-family: var(--mono);
  white-space: nowrap;
}
.ths-dur.live {
  color: var(--accent-muted);
}

.ths-icon-btn {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}
.ths-icon-btn:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.ths-icon-btn.copied {
  color: var(--ok);
}

.ths-tag {
  flex: 0 0 auto;
  font-size: 10px;
}

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
.drawer-chat-card {
  flex: 0 0 auto;
  margin: 8px 12px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: visible;
  position: relative;
}
.chat-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--bg-deep);
  border-bottom: 1px solid var(--border-soft);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}
.chat-provider-controls {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  flex: 1 1 auto;
}
.chat-provider-controls .badge-dot {
  color: var(--accent);
  font-size: 9px;
  flex: 0 0 auto;
}
.chat-header-select {
  height: 22px;
  padding: 0 4px;
  font-size: 11px;
  background: transparent;
  color: var(--text);
  border: 1px solid transparent;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
  max-width: 120px;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.chat-header-select:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--border-soft);
}
.chat-header-select:focus {
  border-color: var(--accent);
  background: var(--bg-card);
}
.chat-header-select option {
  background: var(--bg-card);
  color: var(--text);
}
.chat-header-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.chat-sep {
  color: var(--text-faint);
  font-size: 10px;
  flex: 0 0 auto;
}
.chat-provider-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  line-height: 1;
}
.chat-provider-badge .badge-dot {
  color: var(--accent);
  font-size: 9px;
}
.chat-provider-badge .badge-brand {
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.2px;
}
.chat-provider-badge .badge-sep {
  color: var(--text-faint);
}
.chat-provider-badge .badge-model {
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 10.5px;
}
.chat-settings-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}
.chat-settings-btn:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.chat-card-body {
  padding: 8px 10px 4px;
}
.chat-prompt-textarea {
  width: 100%;
  min-height: 48px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-family: inherit;
  font-size: 12.5px;
  line-height: 1.45;
  resize: none;
  box-sizing: border-box;
}
.chat-prompt-textarea::placeholder {
  color: var(--text-faint);
}
.chat-prompt-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.chat-card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 4px 10px 8px;
}
.chat-card-actions-left,
.chat-card-actions-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.chat-card-actions-right {
  margin-left: auto;
}
.chat-stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: var(--alert-err-bg, rgba(248, 113, 113, 0.14));
  color: var(--err);
  border: 1px solid var(--alert-err-border, rgba(248, 113, 113, 0.45));
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.chat-stop-btn:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.25);
  border-color: var(--err);
}
.chat-stop-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.chat-send-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: var(--accent);
  color: #ffffff;
  border: none;
  cursor: pointer;
  transition: filter 0.15s ease, opacity 0.15s ease;
}
.chat-send-btn:hover:not(:disabled) {
  filter: brightness(1.1);
}
.chat-send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.drawer-inline-report {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-surface);
}
.inline-report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-soft);
}
.inline-report-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  background: transparent;
  border: 1px solid var(--border-soft);
  color: var(--text-dim);
  font-size: 11px;
  cursor: pointer;
  transition: color 0.12s ease, background 0.12s ease;
}
.inline-report-back-btn:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.report-badge {
  font-size: 11px;
  color: var(--text-dim);
}
.inline-report-body {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 12px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text);
}
</style>
