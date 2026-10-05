<script setup>
/**
 * WorkbenchView.vue — AI-First Modern Center Workbench, Bottom Dock & Right Assistant (Phase 5).
 *
 * Implements:
 *   1. 3-column resizable IDE surface with AppSplitter dividers.
 *   2. File opening from Left Sidebar into center Monaco tabs via editorTabsService.
 *   3. Monaco editor tab strip with dirty indicator and AppBreadcrumbs hierarchy.
 *   4. Collapsible and resizable AppBottomDock (Terminal, Output, Problems).
 *   5. Task composition & stop controls in AppRightDrawer.
 *   6. 1-click "Apply to Editor" from ConsultantChat into Monaco editor.
 *   7. Responsive layout tiers (desktop, compact, mobile) with overlay backdrop.
 */
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import AppSplitter from "../components/ui/AppSplitter.vue";
import AppBreadcrumbs from "../components/ui/AppBreadcrumbs.vue";
import AppLeftSidebar from "../components/layout/AppLeftSidebar.vue";
import AppRightDrawer from "../components/layout/AppRightDrawer.vue";
import AppBottomDock from "../components/layout/AppBottomDock.vue";
import CodeEditor from "../components/CodeEditor.vue";
import MonacoDiffEditor from "../components/MonacoDiffEditor.vue";
import SettingsOverlay from "./SettingsOverlay.vue";
import WelcomeView from "../components/WelcomeView.vue";
import AppModal from "../components/ui/AppModal.vue";
import { streamTerminalCommand, discardProjectGitChanges } from "../api.js";
import {
  createEditorTabsState,
  openTab,
  openDiffTab,
  closeTab,
  selectTab,
  setTabDirty,
  setTabSaved,
  getActiveTab,
} from "../services/editorTabsService.js";
import { mapMonacoMarkersToDiagnostics, classifyDiagnostic } from "../services/diagnosticService.js";

const props = defineProps({
  config: {
    type: Object,
    default: () => ({}),
  },
  taskHistory: {
    type: Array,
    default: () => [],
  },
  settingsTab: {
    type: String,
    default: "providers",
  },
  activeProject: {
    type: Object,
    default: null,
  },
  projects: {
    type: Array,
    default: () => [],
  },
  selectedProjectId: {
    type: String,
    default: "",
  },
  activeNav: {
    type: String,
    default: "explorer",
  },
  changes: {
    type: Array,
    default: () => [],
  },
  validation: {
    type: Object,
    default: () => ({}),
  },
  explorerRefresh: {
    type: Number,
    default: 0,
  },
  liveFsChange: {
    type: Object,
    default: null,
  },
  queueRefresh: {
    type: Number,
    default: 0,
  },
  connected: {
    type: Boolean,
    default: false,
  },
  gatewayAddress: {
    type: String,
    default: "",
  },
  agentStatus: {
    type: Object,
    default: () => ({ label: "idle", cls: "status-off" }),
  },
  task: {
    type: Object,
    default: () => ({}),
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
  stopInProgress: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: "",
  },
  consultantProps: {
    type: Object,
    default: () => ({}),
  },
  terminalLines: {
    type: Array,
    default: () => [],
  },
  outputLines: {
    type: Array,
    default: () => [],
  },
  problems: {
    type: Array,
    default: () => [],
  },
  tier: {
    type: String,
    default: "desktop",
  },
  activeOverlay: {
    type: String,
    default: null,
  },
  sidebarVisible: {
    type: Boolean,
    default: true,
  },
  assistantVisible: {
    type: Boolean,
    default: true,
  },
  initialTabs: {
    type: Array,
    default: () => [],
  },
  initialActiveTab: {
    type: String,
    default: "",
  },
  initialSplitActive: {
    type: Boolean,
    default: false,
  },
  initialSplitDirection: {
    type: String,
    default: "vertical",
  },
  initialSplitTab: {
    type: String,
    default: "",
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
});

const emit = defineEmits([
  "select-project",
  "close-project",
  "open-file",
  "active-file-change",
  "stop-task",
  "view-task",
  "open-composer",
  "request-stop",
  "submit-task",
  "open-settings",
  "open-report",
  "copy-activity",
  "run-consultant-task",
  "consultant-event",
  "apply-to-editor",
  "toggle-dock",
  "cursor-change",
  "close-overlay",
  "toggle-assistant",
  "toggle-sidebar",
  "update:provider-instance-id",
  "update:model-id",
  "update:mode",
  "refresh-config",
  "open-history-task",
  "open-consultant-session",
  "open-folder",
  "delete-project",
  "open-path",
  "open-explorer",
  "branch-info-updated",
]);

// 1. Column Sizing & Visibility State
const sidebarWidth = ref(260);
const sidebarVisible = ref(props.sidebarVisible ?? true);
const assistantWidth = ref(380);
const assistantVisible = ref(props.assistantVisible ?? true);
const assistantTab = ref("agents");

watch(
  () => props.sidebarVisible,
  (val) => {
    if (typeof val === "boolean") sidebarVisible.value = val;
  }
);

watch(
  () => props.assistantVisible,
  (val) => {
    if (typeof val === "boolean") assistantVisible.value = val;
  }
);

function toggleSidebar(forceState) {
  if (typeof forceState === "boolean") {
    sidebarVisible.value = forceState;
  } else {
    sidebarVisible.value = !sidebarVisible.value;
  }
  emit("toggle-sidebar", sidebarVisible.value);
}

function toggleAssistant(forceState) {
  if (typeof forceState === "boolean") {
    assistantVisible.value = forceState;
  } else {
    assistantVisible.value = !assistantVisible.value;
  }
  emit("toggle-assistant", assistantVisible.value);
}

const activeConsultantSessionId = ref("");

function handleOpenConsultantSession(sessionId) {
  assistantTab.value = "consultant";
  if (!assistantVisible.value) {
    toggleAssistant(true);
  }
  activeConsultantSessionId.value = sessionId || "";
  emit("open-consultant-session", sessionId);
}

function handleRunConsultantTask(taskPayload) {
  assistantTab.value = "agents";
  emit("run-consultant-task", taskPayload);
}

const consultantBusy = ref(false);
const bgToast = ref(null);
let bgToastTimer = null;

function showBgToast(opts) {
  if (bgToastTimer) {
    clearTimeout(bgToastTimer);
    bgToastTimer = null;
  }
  bgToast.value = opts;
  bgToastTimer = setTimeout(() => {
    bgToast.value = null;
  }, 6000);
}

function handleOpenToastAction() {
  if (bgToast.value?.tab) {
    assistantTab.value = bgToast.value.tab;
  }
  if (!assistantVisible.value) {
    toggleAssistant(true);
  }
  bgToast.value = null;
}

function handleConsultantEvent(event) {
  if (event?.type === "sending_started") {
    consultantBusy.value = true;
  } else if (event?.type === "sending_completed") {
    consultantBusy.value = false;
    if (!assistantVisible.value) {
      showBgToast({
        type: event.error ? "error" : "success",
        title: event.error ? "Consultant Error" : "Consultant Response Ready",
        message: event.error || (event.prompt ? (event.prompt.length > 40 ? event.prompt.slice(0, 40) + "…" : event.prompt) : "New analysis available"),
        tab: "consultant",
      });
    }
  }
  emit("consultant-event", event);
}

watch(
  () => props.isRunning,
  (running, prevRunning) => {
    if (prevRunning && !running) {
      if (!assistantVisible.value) {
        const isCompleted = props.task?.status === "completed";
        const promptPreview = props.task?.prompt
          ? (props.task.prompt.length > 40 ? props.task.prompt.slice(0, 40) + "…" : props.task.prompt)
          : "";
        showBgToast({
          type: isCompleted ? "success" : "warning",
          title: isCompleted ? "Task Completed" : `Task ${props.task?.status || "Finished"}`,
          message: promptPreview,
          tab: "agents",
        });
      }
    }
  }
);

const effectiveProviderList = computed(() => {
  return props.providers?.length ? props.providers : (props.config?.provider_instances || []);
});

const effectiveProviderInstanceId = computed(() => {
  return props.providerInstanceId || props.config?.provider_instance_id || "";
});

const effectiveModelId = computed(() => {
  return props.modelId || props.config?.model_id || props.config?.model || "";
});

const activeProviderInstance = computed(() => {
  const id = effectiveProviderInstanceId.value;
  return effectiveProviderList.value.find((p) => p.id === id) || null;
});

const effectiveTaskProvider = computed(() => {
  if (props.taskProvider) return props.taskProvider;
  return activeProviderInstance.value?.name || props.config?.provider || "";
});

const effectiveTaskModel = computed(() => {
  if (props.taskModel) return props.taskModel;
  const inst = activeProviderInstance.value;
  const m = (inst?.models || []).find((x) => x.id === effectiveModelId.value);
  return m ? m.model_name : (props.config?.model || "");
});

const effectiveConsultantProps = computed(() => {
  const base = props.consultantProps || {};
  return {
    ...base,
    activeSessionId: activeConsultantSessionId.value || base.activeSessionId || "",
    providers: base.providers?.length ? base.providers : effectiveProviderList.value,
    providerInstanceId: base.providerInstanceId || effectiveProviderInstanceId.value,
    modelId: base.modelId || effectiveModelId.value,
    projectId: base.projectId || props.activeProject?.id || "",
    running: typeof base.running === "boolean" ? base.running : props.isRunning,
    runningTaskId: base.runningTaskId || props.task?.id || "",
    providerLabel: effectiveTaskProvider.value,
    modelLabel: effectiveTaskModel.value,
  };
});

// 2. Bottom Dock State & Live Buffers
const bottomDockOpen = ref(false);
const dockHeight = ref(220);
const dockActiveTab = ref("terminal");

const localTerminalLines = ref([]);
const localOutputLines = ref([]);
const localProblems = ref([]);

const activeEditorMarkers = ref([]);
const activeEditorSyntaxErrors = ref([]);

const activeEditorDiagnostics = computed(() => {
  const merged = [...activeEditorMarkers.value, ...activeEditorSyntaxErrors.value];
  const seen = new Set();
  const unique = [];
  for (const d of merged) {
    const key = `${d.file}:${d.line}:${d.col}:${d.text}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(d);
    }
  }
  return unique;
});

const effectiveTerminalLines = computed(() => {
  return props.terminalLines && props.terminalLines.length
    ? props.terminalLines
    : localTerminalLines.value;
});

const effectiveOutputLines = computed(() => {
  return props.outputLines && props.outputLines.length
    ? props.outputLines
    : localOutputLines.value;
});

const effectiveProblems = computed(() => {
  const list = [];
  const seen = new Set();

  function addProblem(item) {
    if (!item) return;
    const text = typeof item === "string" ? item : (item.text || item.message || JSON.stringify(item));
    const file = item.file || "";
    const line = item.line || null;
    const col = item.col || null;
    const key = `${file}:${line}:${text}`;
    if (seen.has(key)) return;
    seen.add(key);

    const parsed = classifyDiagnostic(text);
    list.push({
      id: item.id || `prob-${list.length}-${Date.now()}`,
      text,
      type: item.type || parsed.type || "error",
      severity: item.severity || parsed.severity || "error",
      label: item.label || parsed.label || "Error",
      file: file || parsed.file || "",
      line: line || parsed.line || null,
      col: col || parsed.col || null,
      source: item.source || "system",
    });
  }

  // 1. Editor diagnostics (Syntax errors, type errors, lints from open editor)
  if (Array.isArray(activeEditorDiagnostics.value)) {
    for (const d of activeEditorDiagnostics.value) {
      if (d.type !== "info") {
        addProblem(d);
      }
    }
  }

  // 2. Output stream errors & syntax errors
  if (Array.isArray(effectiveOutputLines.value)) {
    for (let i = 0; i < effectiveOutputLines.value.length; i++) {
      const line = effectiveOutputLines.value[i];
      const parsed = classifyDiagnostic(line, i);
      if (parsed.type === "syntax" || parsed.type === "type" || parsed.type === "error") {
        addProblem(parsed);
      }
    }
  }

  // 3. Props / Local problems
  const explicitProblems = props.problems && props.problems.length
    ? props.problems
    : localProblems.value;
  for (const p of explicitProblems) {
    addProblem(p);
  }

  return list;
});

let lastProcessedEventCount = 0;
watch(
  () => props.activityEvents,
  (events) => {
    if (!events || !events.length) {
      lastProcessedEventCount = 0;
      return;
    }
    const newEvents = events.slice(lastProcessedEventCount);
    lastProcessedEventCount = events.length;

    for (const evt of newEvents) {
      // Backend emits `event_type`; fallback to `type`/`event` for compatibility.
      const type = evt.event_type || evt.type || evt.event || "";
      const p = evt.payload || evt.data || evt;
      const ts = evt.timestamp || Date.now();

      if (type === "tool_called") {
        localTerminalLines.value.push({
          kind: "call",
          tool: p.tool || "tool",
          target: p.path || p.command || p.query || "",
          ts,
        });
        localOutputLines.value.push({
          text: `[tool:call] ${p.tool || "tool"} ${p.path || p.command || p.query || ""}`.trim(),
          ts,
        });
      } else if (type === "tool_completed") {
        const isSuccess = p.success !== false && !p.error;
        localTerminalLines.value.push({
          kind: "result",
          tool: p.tool || "tool",
          success: isSuccess,
          error: p.error,
          ts,
        });
        if (!isSuccess) {
          localProblems.value.push({
            text: `Tool '${p.tool || "tool"}' error: ${p.error || "Execution failed"}`,
            ts,
          });
        }
      } else if (type === "validation_completed") {
        if (p.success === false || p.passed === false || p.error) {
          localProblems.value.push({
            text: `Validation failed: ${p.error || p.message || "Checks did not pass"}`,
            ts,
          });
        }
      } else if (type === "task_failed") {
        localProblems.value.push({
          text: `Task failed: ${p.error || "Unknown error"}`,
          ts,
        });
        localOutputLines.value.push({
          text: `[task:failed] ${p.error || "Unknown error"}`,
          ts,
        });
      }
    }
  },
  { deep: true }
);

// Auto-open dock and switch to Problems tab when a new problem arrives.
let lastProblemCount = 0;
watch(effectiveProblems, (problems) => {
  if (problems.length > lastProblemCount) {
    lastProblemCount = problems.length;
    bottomDockOpen.value = true;
    dockActiveTab.value = "problems";
  } else if (problems.length === 0) {
    lastProblemCount = 0;
  }
});

watch(
  () => props.error,
  (newErr) => {
    if (newErr) {
      localProblems.value.push({ text: newErr, ts: Date.now() });
      localOutputLines.value.push({ text: `[error] ${newErr}`, ts: Date.now() });
    }
  }
);
// 3. Multi-Tab Monaco Editor State (Dual-Window Architecture)
const pane1TabsState = createEditorTabsState();
const pane2TabsState = createEditorTabsState();
// Aliased for single-pane backward compatibility
const editorTabsState = pane1TabsState;

const activeCodeEditorRef = ref(null);
const splitCodeEditorRef = ref(null);

// Split Tab State (Responsive Side-by-Side or Stacked)
const splitActive = ref(Boolean(props.initialSplitActive));
const splitDirection = ref(props.initialSplitDirection || "vertical");
const splitRatio = ref(50);
const activePane = ref("pane1"); // "pane1" (Tab 1 / Left) or "pane2" (Tab 2 / Right)

// Initialize initial tabs if provided for Pane 1
if (props.initialTabs && props.initialTabs.length > 0) {
  for (const t of props.initialTabs) {
    const tab = openTab(pane1TabsState, t);
    if (tab && t && typeof t === "object" && t.dirty) {
      tab.dirty = true;
    }
  }
  if (props.initialActiveTab) {
    selectTab(pane1TabsState, props.initialActiveTab);
  }
}

watch(
  () => props.initialActiveTab,
  (newTab) => {
    if (newTab) {
      selectTab(pane1TabsState, newTab);
    }
  }
);

// Pane 1 Computeds
const pane1ActiveTab = computed(() => getActiveTab(pane1TabsState));
const pane1ActiveTabPath = computed(() => (pane1ActiveTab.value ? pane1ActiveTab.value.path : ""));
const isPane1TabDirty = computed(() => Boolean(pane1ActiveTab.value?.dirty));

// Pane 2 Computeds
const pane2ActiveTab = computed(() => getActiveTab(pane2TabsState));
const pane2ActiveTabPath = computed(() => (pane2ActiveTab.value ? pane2ActiveTab.value.path : ""));
const isPane2TabDirty = computed(() => Boolean(pane2ActiveTab.value?.dirty));

// Overall Active Tab (tracks focused pane)
const activeTab = computed(() => {
  if (splitActive.value && activePane.value === "pane2") {
    return pane2ActiveTab.value || pane1ActiveTab.value;
  }
  return pane1ActiveTab.value || pane2ActiveTab.value;
});
const activeTabPath = computed(() => (activeTab.value ? activeTab.value.path : ""));

// Compatibility aliases for splitTab and splitTabPath
const splitTab = computed(() => pane2ActiveTab.value);
const splitTabPath = computed(() => pane2ActiveTabPath.value);

// Initialize split pane if requested via props
if (splitActive.value) {
  if (props.initialSplitTab) {
    openTab(pane2TabsState, props.initialSplitTab);
  } else {
    const other = pane1TabsState.tabs.value.find((t) => t.path !== pane1ActiveTabPath.value);
    if (other) {
      openTab(pane2TabsState, other);
    } else if (pane1ActiveTabPath.value) {
      const activeT = pane1TabsState.tabs.value.find((t) => t.path === pane1ActiveTabPath.value);
      if (activeT) openTab(pane2TabsState, activeT);
    }
  }
}

function toggleSplitEditor() {
  if (splitActive.value) {
    closeSplitEditor(false);
    return;
  }
  splitActive.value = true;
  splitRatio.value = 50;

  // Initialize Pane 2 with a tab if empty
  if (pane2TabsState.tabs.value.length === 0) {
    if (pane1TabsState.tabs.value.length > 1) {
      const other = pane1TabsState.tabs.value.find((t) => t.path !== pane1ActiveTabPath.value);
      if (other) {
        openTab(pane2TabsState, other);
      } else if (pane1ActiveTabPath.value) {
        const activeT = pane1TabsState.tabs.value.find((t) => t.path === pane1ActiveTabPath.value);
        if (activeT) openTab(pane2TabsState, activeT);
      }
    } else if (pane1ActiveTabPath.value) {
      const activeT = pane1TabsState.tabs.value.find((t) => t.path === pane1ActiveTabPath.value);
      if (activeT) openTab(pane2TabsState, activeT);
    }
  }
  activePane.value = "pane2";

  nextTick(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  });
  setTimeout(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  }, 80);
}

function toggleSplitDirection() {
  splitDirection.value = splitDirection.value === "vertical" ? "horizontal" : "vertical";
  nextTick(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  });
  setTimeout(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  }, 80);
}

function closeSplitEditor(force = false) {
  if (!force && hasDirtyTabs(pane2TabsState)) {
    const dirtyTab = pane2TabsState.tabs.value.find((t) => t.dirty);
    closingTab.value = dirtyTab;
    closingTabPane.value = "pane2";
    closingSplitEntirely.value = true;
    confirmCloseOpen.value = true;
    return;
  }
  pane2TabsState.tabs.value = [];
  pane2TabsState.activeTab.value = "";
  splitActive.value = false;
  activePane.value = "pane1";
  closingSplitEntirely.value = false;
  nextTick(() => {
    activeCodeEditorRef.value?.layout();
  });
}

function handleSelectSplitTab(path) {
  handleSelectTab(path, "pane2");
}

let isDraggingSplit = false;
function onSplitDividerMouseDown(e) {
  e.preventDefault();
  if (typeof window === "undefined") return;
  isDraggingSplit = true;
  const container = e.currentTarget.parentElement;
  if (!container) return;
  const rect = container.getBoundingClientRect();
  const isVert = splitDirection.value === "vertical";

  function onMouseMove(moveEvt) {
    if (!isDraggingSplit) return;
    let pct;
    if (isVert) {
      pct = ((moveEvt.clientX - rect.left) / rect.width) * 100;
    } else {
      pct = ((moveEvt.clientY - rect.top) / rect.height) * 100;
    }
    splitRatio.value = Math.max(20, Math.min(80, Math.round(pct)));
    nextTick(() => {
      activeCodeEditorRef.value?.layout();
      splitCodeEditorRef.value?.layout();
    });
  }

  function onMouseUp() {
    isDraggingSplit = false;
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  }

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);
}

function onSplitDividerDblClick() {
  splitRatio.value = 50;
  nextTick(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  });
}

// Project Root Display Name for Breadcrumbs
const projectRootName = computed(() => {
  if (props.activeProject) {
    return (
      props.activeProject.name ||
      String(props.activeProject.path || "").split("/").pop() ||
      "Project"
    );
  }
  return "Workspace";
});

// File Opening Handlers
function handleOpenFile(fileOrPath, targetPane) {
  const pane = targetPane || (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const tab = openTab(state, fileOrPath);
  if (tab) {
    activePane.value = pane;
    emit("open-file", tab);
    emit("active-file-change", tab);
    nextTick(() => {
      if (pane === "pane2") {
        splitCodeEditorRef.value?.layout();
      } else {
        activeCodeEditorRef.value?.layout();
      }
    });
  }
}

function handleOpenDiff(fileOrPath, targetPane) {
  const pane = targetPane || (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const tab = openDiffTab(state, fileOrPath);
  if (tab) {
    activePane.value = pane;
    emit("open-file", tab);
    emit("active-file-change", tab);
  }
}

function handleSelectTab(path, targetPane) {
  let pane = targetPane;
  if (!pane) {
    if (splitActive.value && activePane.value === "pane2" && pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else if (pane1TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane1";
    } else if (pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else {
      pane = "pane1";
    }
  }
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  selectTab(state, path);
  activePane.value = pane;
  const tab = getActiveTab(state);
  emit("active-file-change", tab);
  nextTick(() => {
    if (pane === "pane2") {
      splitCodeEditorRef.value?.layout();
    } else {
      activeCodeEditorRef.value?.layout();
    }
  });
}

const closingTab = ref(null);
const closingTabPane = ref("pane1");
const closingSplitEntirely = ref(false);
const confirmCloseOpen = ref(false);

function handleCloseTab(path, targetPane) {
  let pane = targetPane;
  if (!pane) {
    if (splitActive.value && activePane.value === "pane2" && pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else if (pane1TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane1";
    } else if (pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else {
      pane = "pane1";
    }
  }

  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const tab = state.tabs.value.find((t) => t.path === path);
  if (tab && tab.dirty) {
    closingTab.value = tab;
    closingTabPane.value = pane;
    closingSplitEntirely.value = false;
    confirmCloseOpen.value = true;
    return;
  }

  const result = closeTab(state, path);
  if (result.closed) {
    if (pane === "pane2" && pane2TabsState.tabs.value.length === 0 && splitActive.value) {
      splitActive.value = false;
      activePane.value = "pane1";
    }
    const newActive = getActiveTab(state);
    emit("active-file-change", newActive);
  }
}

async function handleConfirmCloseSave() {
  if (!closingTab.value) return;
  const targetTab = closingTab.value;
  const pane = closingTabPane.value;
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;

  if (editorRef?.save) {
    try {
      await editorRef.save();
    } catch (e) {
      // save error handled in editor
    }
  }

  closeTab(state, targetTab.path, { force: true });
  confirmCloseOpen.value = false;
  closingTab.value = null;

  if (closingSplitEntirely.value) {
    closeSplitEditor(false);
    return;
  }

  if (pane === "pane2" && pane2TabsState.tabs.value.length === 0 && splitActive.value) {
    splitActive.value = false;
    activePane.value = "pane1";
  }

  const newActive = getActiveTab(state);
  emit("active-file-change", newActive);
}

function handleConfirmCloseDiscard() {
  if (!closingTab.value) return;
  const targetPath = closingTab.value.path;
  const pane = closingTabPane.value;
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;

  closeTab(state, targetPath, { force: true });
  confirmCloseOpen.value = false;
  closingTab.value = null;

  if (closingSplitEntirely.value) {
    closeSplitEditor(true);
    return;
  }

  if (pane === "pane2" && pane2TabsState.tabs.value.length === 0 && splitActive.value) {
    splitActive.value = false;
    activePane.value = "pane1";
  }

  const newActive = getActiveTab(state);
  emit("active-file-change", newActive);
}

function handleConfirmCloseCancel() {
  confirmCloseOpen.value = false;
  closingTab.value = null;
  closingSplitEntirely.value = false;
}

function onEditorClose(path, targetPane) {
  handleCloseTab(path, targetPane);
}

function onEditorSaved(evt, pane = "pane1") {
  const path = evt?.path || (pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value);
  setTabSaved(pane1TabsState, path);
  setTabSaved(pane2TabsState, path);
}

function onEditorDirtyChange(evt, pane = "pane1") {
  const path = evt?.path || (pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value);
  const isDirty = evt?.dirty !== undefined ? evt.dirty : true;
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  setTabDirty(state, path, isDirty);
}

function onCursorChange(pos) {
  emit("cursor-change", pos);
}

function onEditorError(err) {
  // Bubbled or displayed by CodeEditor
}

// --- Git Discard Changes Mechanism (Direct Non-Overlay with Toast Notification) ---
const localGitRefresh = ref(0);

async function handleDirectDiscard(filePath = null) {
  const pId = props.activeProject?.id || props.activeProject?.project_id;
  if (!pId) return;

  try {
    const res = await discardProjectGitChanges(pId, filePath);
    if (!res?.ok && res?.error) {
      showBgToast({
        type: "error",
        title: "Discard Failed",
        message: res.error,
      });
      return;
    }

    if (filePath) {
      // 1. Close diff tab if open for this file in either pane
      closeTab(pane1TabsState, `diff://${filePath}`, { force: true });
      closeTab(pane2TabsState, `diff://${filePath}`, { force: true });

      // 2. If standard editor tab for this file is open, reload it
      const regularTab1 = pane1TabsState.tabs.value.find((t) => t.path === filePath);
      if (regularTab1) {
        setTabDirty(pane1TabsState, filePath, false);
        if (pane1ActiveTabPath.value === filePath && activeCodeEditorRef.value?.reload) {
          activeCodeEditorRef.value.reload();
        }
      }
      const regularTab2 = pane2TabsState.tabs.value.find((t) => t.path === filePath);
      if (regularTab2) {
        setTabDirty(pane2TabsState, filePath, false);
        if (pane2ActiveTabPath.value === filePath && splitCodeEditorRef.value?.reload) {
          splitCodeEditorRef.value.reload();
        }
      }

      showBgToast({
        type: "success",
        title: "Changes Discarded",
        message: `Reverted ${filePath} to HEAD.`,
      });
    } else {
      // Discard all: close all diff tabs in both panes
      pane1TabsState.tabs.value.filter((t) => t.isDiff).forEach((t) => closeTab(pane1TabsState, t.path, { force: true }));
      pane2TabsState.tabs.value.filter((t) => t.isDiff).forEach((t) => closeTab(pane2TabsState, t.path, { force: true }));

      // Clean dirty state and reload active editors if regular
      pane1TabsState.tabs.value.forEach((t) => {
        if (!t.isDiff) setTabDirty(pane1TabsState, t.path, false);
      });
      pane2TabsState.tabs.value.forEach((t) => {
        if (!t.isDiff) setTabDirty(pane2TabsState, t.path, false);
      });
      if (activeCodeEditorRef.value?.reload) {
        activeCodeEditorRef.value.reload();
      }
      if (splitCodeEditorRef.value?.reload) {
        splitCodeEditorRef.value.reload();
      }

      showBgToast({
        type: "success",
        title: "All Changes Discarded",
        message: "Reverted working tree to HEAD.",
      });
    }

    // 3. Trigger git refresh across FileExplorer and ChangesPanel
    localGitRefresh.value++;
    const newActive = activeTab.value;
    emit("active-file-change", newActive);
  } catch (e) {
    showBgToast({
      type: "error",
      title: "Discard Failed",
      message: e.message || "Failed to discard changes.",
    });
  }
}

function onMarkersChange(payload) {
  if (payload?.markers) {
    activeEditorMarkers.value = mapMonacoMarkersToDiagnostics(
      payload.markers,
      payload.path || activeTabPath.value
    );
  }
}

function onSyntaxChange(payload) {
  if (payload?.errors) {
    activeEditorSyntaxErrors.value = payload.errors;
  }
}

watch(activeTabPath, () => {
  activeEditorMarkers.value = [];
  activeEditorSyntaxErrors.value = [];
});

async function handleNavigateToLocation(loc) {
  if (!loc) return;
  const targetFile = loc.file;
  const line = loc.line || 1;
  const col = loc.col || 1;

  if (targetFile && targetFile !== activeTabPath.value) {
    handleOpenFile(targetFile);
    await nextTick();
  }

  activeCodeEditorRef.value?.revealPosition(line, col);
}

const settingsSubTab = ref(props.settingsTab || "providers");
watch(
  () => props.settingsTab,
  (val) => {
    if (val) settingsSubTab.value = val;
  }
);

function openSettings(tabName = "providers") {
  settingsSubTab.value = tabName;
  openTab(editorTabsState, {
    path: "aether://settings",
    name: "Settings",
  });
}

function openWelcomeTab() {
  openTab(editorTabsState, {
    path: "aether://welcome",
    name: "Welcome",
  });
}

function clearAllTabs() {
  editorTabsState.tabs.value = [];
  editorTabsState.activeTab.value = "";
}

watch(
  () => props.activeProject?.id,
  (newId, oldId) => {
    if (!newId && oldId) {
      clearAllTabs();
    }
  }
);

const cloneGitModalOpen = ref(false);
const cloneGitUrl = ref("");
const cloneGitBusy = ref(false);
const cloneGitNotice = ref("");

function handleOpenCloneGitModal() {
  cloneGitModalOpen.value = true;
  cloneGitNotice.value = "";
  cloneGitUrl.value = "";
}

function handleCloneGitSubmit() {
  if (!cloneGitUrl.value.trim()) return;
  cloneGitBusy.value = true;
  cloneGitNotice.value = "Connecting to repository…";
  setTimeout(() => {
    cloneGitBusy.value = false;
    cloneGitNotice.value = "Git Clone pipeline initialized. Full background sync will connect in the next milestone.";
  }, 1000);
}

const isCurrentTabDirty = computed(() => {
  if (splitActive.value && activePane.value === "pane2") {
    return isPane2TabDirty.value;
  }
  return isPane1TabDirty.value;
});

async function handleSaveActiveFile(targetPane) {
  const pane = targetPane || (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
  const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;
  if (editorRef?.save) {
    await editorRef.save();
  }
}

// 1-Click "Apply to Editor" Wiring
async function handleApplyToEditor(payload) {
  const code = payload?.code ?? "";
  const targetPath = payload?.path || activeTabPath.value || "scratchpad.js";
  const pane = splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1";
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;

  const currentPath = pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value;
  if (!currentPath || (payload?.path && currentPath !== payload.path)) {
    openTab(state, targetPath);
    await nextTick();
  }

  if (editorRef?.applyContent) {
    editorRef.applyContent(code);
    setTabDirty(state, targetPath, true);
  }

  emit("apply-to-editor", {
    code,
    path: targetPath,
    message: payload?.message,
  });
}

// Breadcrumb Navigation
function handleBreadcrumbNavigate(path) {
  if (!path) return;
  emit("open-path", path);
  emit("open-explorer");
}

function handleBreadcrumbSelect(path) {
  handleOpenFile(path);
}

// Bottom Dock Controls
function handleClearDock(tab) {
  if (tab === "terminal") {
    localTerminalLines.value = [];
  } else if (tab === "output") {
    localOutputLines.value = [];
  } else if (tab === "problems") {
    localProblems.value = [];
  } else {
    localTerminalLines.value = [];
    localOutputLines.value = [];
    localProblems.value = [];
  }
}

// Interactive terminal: user-submitted commands streamed from backend.
const terminalRunning = ref(false);
let _terminalAbortController = null;

async function handleTerminalCommand(command) {
  if (!command || terminalRunning.value) return;

  // Open and focus terminal dock.
  bottomDockOpen.value = true;
  dockActiveTab.value = "terminal";

  // Echo the command as an input line.
  localTerminalLines.value.push({ kind: "input", text: command, ts: Date.now() });

  terminalRunning.value = true;
  const projectId = props.activeProject?.id || "";
  let exitCode = null;
  let aborted = false;
  let success = true;

  _terminalAbortController = new AbortController();
  const signal = _terminalAbortController.signal;

  try {
    await streamTerminalCommand(projectId, command, (eventType, data) => {
      if (eventType === "terminal_output") {
        localTerminalLines.value.push({ kind: "text", text: data.text ?? "", ts: Date.now() });
      } else if (eventType === "terminal_done") {
        exitCode = data.exit_code ?? null;
        success = data.success !== false;
      } else if (eventType === "terminal_error") {
        localTerminalLines.value.push({ kind: "text", text: `✗ ${data.error}`, ts: Date.now() });
        success = false;
      }
    }, signal);
  } catch (err) {
    if (signal.aborted) {
      aborted = true;
    } else {
      localTerminalLines.value.push({ kind: "text", text: `✗ ${err.message}`, ts: Date.now() });
      success = false;
    }
  } finally {
    _terminalAbortController = null;
  }

  if (aborted) {
    // ^C echo already added by TerminalView; just reset state.
  } else {
    // Append result line.
    localTerminalLines.value.push({
      kind: "result",
      tool: command.split(" ")[0],
      target: "",
      success,
      error: success ? undefined : `exit ${exitCode ?? "?"}`,
      ts: Date.now(),
    });
  }
  terminalRunning.value = false;
}

function handleAbortCommand() {
  if (_terminalAbortController) {
    // Echo ^C to terminal before aborting stream.
    localTerminalLines.value.push({ kind: "text", text: "^C", ts: Date.now() });
    _terminalAbortController.abort();
  }
}

function toggleBottomDock(tab = "terminal") {
  if (!bottomDockOpen.value) {
    bottomDockOpen.value = true;
    if (tab) dockActiveTab.value = tab;
  } else if (tab && dockActiveTab.value !== tab) {
    dockActiveTab.value = tab;
  } else {
    bottomDockOpen.value = false;
  }
  emit("toggle-dock", tab);
}

function closeOverlay() {
  emit("close-overlay");
}

// Global Keyboard Shortcuts
function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "`") {
    e.preventDefault();
    toggleBottomDock();
    return;
  }
  if (e.key === "Escape") {
    if (props.tier !== "desktop" && props.activeOverlay) {
      e.preventDefault();
      closeOverlay();
    }
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onKeyDown);
  }
});

defineExpose({
  editorTabsState,
  pane1TabsState,
  pane2TabsState,
  activePane,
  activeTabPath,
  activeCodeEditorRef,
  splitActive,
  splitDirection,
  splitTabPath,
  splitCodeEditorRef,
  toggleSplitEditor,
  toggleSplitDirection,
  closeSplitEditor,
  bottomDockOpen,
  dockHeight,
  dockActiveTab,
  sidebarWidth,
  sidebarVisible,
  assistantWidth,
  assistantVisible,
  assistantTab,
  terminalLines: effectiveTerminalLines,
  outputLines: effectiveOutputLines,
  problems: effectiveProblems,
  terminalRunning,
  toggleSidebar,
  toggleAssistant,
  toggleBottomDock,
  handleOpenFile,
  handleOpenDiff,
  handleCloseTab,
  handleApplyToEditor,
  handleClearDock,
  handleTerminalCommand,
  handleAbortCommand,
  openSettings,
  openWelcomeTab,
  clearAllTabs,
});
</script>

<template>
  <div
    class="workbench-view"
    :class="[`tier-${tier}`, { 'dock-open': bottomDockOpen }]"
  >
    <div class="workbench-columns">
      <!-- 1. Left Column: Project, Explorer & Source Control Sidebar -->
      <aside
        v-if="sidebarVisible"
        class="wb-left-column"
        :style="tier !== 'mobile' ? { width: `${sidebarWidth}px` } : {}"
      >
        <AppLeftSidebar
          :active-nav="activeNav"
          :active-project="activeProject"
          :projects="projects"
          :changes="changes"
          :validation="validation"
          :explorer-refresh="explorerRefresh + localGitRefresh"
          :live-fs-change="liveFsChange"
          :queue-refresh="queueRefresh"
          :task-history="taskHistory"
          :active-session-id="activeConsultantSessionId"
          :selected-project-id="selectedProjectId"
          :connected="connected"
          :gateway-address="gatewayAddress"
          :agent-status="agentStatus"
          :open-tabs="pane1TabsState.tabs.value"
          :active-tab-path="pane1TabsState.activeTab.value"
          :open-tabs2="pane2TabsState.tabs.value"
          :active-tab-path2="pane2TabsState.activeTab.value"
          :split-active="splitActive"
          :active-pane="activePane"
          @open-file="handleOpenFile"
          @open-diff="handleOpenDiff"
          @discard-change="handleDirectDiscard"
          @select-project="emit('select-project', $event)"
          @close-project="emit('close-project')"
          @collapse-sidebar="emit('toggle-sidebar', false)"
          @stop-task="emit('stop-task', $event)"
          @view-task="emit('view-task', $event)"
          @open-history-task="emit('open-history-task', $event)"
          @open-consultant-session="handleOpenConsultantSession"
          @open-folder="emit('open-folder')"
          @select-tab="(path, pane) => handleSelectTab(path, pane)"
          @close-tab="(path, pane) => handleCloseTab(path, pane)"
          @clear-tabs="(pane) => clearAllTabs(pane)"
          @branch-info-updated="emit('branch-info-updated', $event)"
        />
      </aside>

      <!-- Left Splitter (Desktop only) -->
      <AppSplitter
        v-if="tier === 'desktop' && sidebarVisible"
        direction="vertical"
        v-model="sidebarWidth"
        :min="200"
        :max="450"
        :default-size="260"
      />

      <!-- 2. Center Column: Monaco Tabs Strip, Breadcrumbs, Editor, Settings & Bottom Dock -->
      <main class="wb-center-column">
        <!-- Monaco Editor Tab Strip Bar (Single-window mode only) -->
        <div v-if="!splitActive && (activeProject || pane1TabsState.tabs.value.length > 0)" class="wb-editor-tabs-bar">
          <div class="wb-editor-tabs" role="tablist" aria-label="Editor Tabs">
            <div
              v-for="tab in pane1TabsState.tabs.value"
              :key="'single-' + tab.path"
              class="wb-tab-item"
              :class="{ active: tab.path === pane1ActiveTabPath, dirty: tab.dirty }"
              role="tab"
              :aria-selected="tab.path === pane1ActiveTabPath"
              @click="handleSelectTab(tab.path, 'pane1')"
            >
              <span class="tab-icon" aria-hidden="true">
                <svg
                  v-if="tab.path === 'aether://settings'"
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                <svg
                  v-else-if="tab.path === 'aether://welcome'"
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
                <svg
                  v-else-if="tab.isDiff || tab.path.startsWith('diff://')"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M12 3v18" />
                </svg>
                <svg
                  v-else
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
              </span>
              <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
              <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
              <button
                type="button"
                class="tab-close-btn"
                title="Close Tab"
                aria-label="Close Tab"
                @click.stop="handleCloseTab(tab.path, 'pane1')"
              >
                ×
              </button>

              <!-- Inline Popover for Unsaved Changes -->
              <div
                v-if="closingTab && closingTabPane === 'pane1' && closingTab.path === tab.path"
                class="wb-tab-inline-popover"
                @click.stop
              >
                <div class="pop-msg">Save changes?</div>
                <div class="pop-actions">
                  <button type="button" class="pop-btn pop-save" @click="handleConfirmCloseSave">Save</button>
                  <button type="button" class="pop-btn pop-discard" @click="handleConfirmCloseDiscard">Don't Save</button>
                  <button type="button" class="pop-btn pop-cancel" @click="handleConfirmCloseCancel">Cancel</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions toolbar: Compact Save and Split Buttons -->
          <div v-if="pane1ActiveTabPath && !['aether://settings', 'aether://welcome'].includes(pane1ActiveTabPath)" class="wb-tab-actions">
            <button
              type="button"
              class="wb-tab-save-btn"
              :class="{ dirty: isPane1TabDirty }"
              :disabled="!isPane1TabDirty"
              :title="isPane1TabDirty ? 'Save (⌘S)' : 'All changes saved'"
              aria-label="Save File"
              @click="handleSaveActiveFile('pane1')"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                <polyline points="17 21 17 13 7 13 7 21"/>
                <polyline points="7 3 7 8 15 8"/>
              </svg>
              <span v-if="isPane1TabDirty" class="save-dot">●</span>
            </button>

            <!-- Split Editor Toggle Button -->
            <button
              type="button"
              class="wb-tab-action-btn wb-tab-split-btn"
              :class="{ active: splitActive }"
              :title="splitActive ? 'Close Split Editor' : 'Split Editor Right'"
              aria-label="Split Editor"
              @click="toggleSplitEditor"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <line x1="12" y1="3" x2="12" y2="21"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Breadcrumbs Navigation Bar (Single-window mode only) -->
        <div v-if="!splitActive && pane1ActiveTabPath" class="wb-breadcrumbs-bar">
          <div v-if="pane1ActiveTabPath === 'aether://settings'" class="breadcrumbs-list" aria-label="Settings Breadcrumbs">
            <span class="crumb-item crumb-root">Preferences</span>
            <span class="crumb-separator" aria-hidden="true">›</span>
            <span class="crumb-item crumb-file current">Settings</span>
          </div>
          <div v-else-if="pane1ActiveTabPath === 'aether://welcome'" class="breadcrumbs-list" aria-label="Welcome Breadcrumbs">
            <span class="crumb-item crumb-root">AEGIS</span>
            <span class="crumb-separator" aria-hidden="true">›</span>
            <span class="crumb-item crumb-file current">Welcome</span>
          </div>
          <div v-else-if="pane1ActiveTab?.isDiff || pane1ActiveTabPath.startsWith('diff://')" class="breadcrumbs-list" aria-label="Diff Breadcrumbs">
            <span class="crumb-item crumb-root">{{ projectRootName }}</span>
            <span class="crumb-separator" aria-hidden="true">›</span>
            <span class="crumb-item crumb-file current">{{ pane1ActiveTab?.name || 'Diff' }}</span>
          </div>
          <AppBreadcrumbs
            v-else
            :path="pane1ActiveTabPath"
            :root="projectRootName"
            @navigate="handleBreadcrumbNavigate"
            @select-file="(p) => handleOpenFile(p, 'pane1')"
          />
        </div>

        <!-- Central Editor Surface / Settings Tab / Welcome / Empty State Canvas -->
        <div class="wb-editor-canvas">
          <!-- 1. Settings tab -->
          <div v-if="!splitActive && pane1ActiveTabPath === 'aether://settings'" class="wb-settings-tab">
            <SettingsOverlay
              embedded
              :open="true"
              :config="config"
              :projects="projects"
              :task-history="taskHistory"
              :active-project="activeProject"
              :provider-instance-id="providerInstanceId"
              :model-id="modelId"
              :mode="config?.mode"
              v-model:active-tab="settingsSubTab"
              @close="handleCloseTab('aether://settings', 'pane1')"
              @refresh-config="emit('refresh-config')"
              @update:provider-instance-id="emit('update:provider-instance-id', $event)"
              @update:model-id="emit('update:model-id', $event)"
              @update:mode="emit('update:mode', $event)"
              @open-report="emit('open-report', $event)"
              @open-history-task="emit('open-history-task', $event)"
              @delete-history="emit('delete-history', $event)"
              @clear-history="emit('clear-history')"
              @open-project-policy="emit('open-project-policy', $event)"
              @delete-project="emit('delete-project', $event)"
              @open-project="emit('open-project', $event)"
            />
          </div>

          <!-- 2. Dual-Window Split Editor (Side-by-side or Stacked) -->
          <div
            v-else-if="splitActive"
            class="wb-split-editor-container"
            :class="[
              `split-${splitDirection}`,
              `split-tier-${tier}`,
              { 'pane-primary-active': activePane === 'pane1', 'pane-split-active': activePane === 'pane2' }
            ]"
          >
            <!-- Primary Editor Pane (Tab 1 / Left) -->
            <div
              class="wb-split-pane wb-split-pane-primary"
              :class="{ 'is-focused-pane': activePane === 'pane1' }"
              :style="splitDirection === 'vertical'
                ? { width: `calc(${splitRatio}% - 2px)`, height: '100%', flex: `0 0 calc(${splitRatio}% - 2px)` }
                : { height: `calc(${splitRatio}% - 2px)`, width: '100%', flex: `0 0 calc(${splitRatio}% - 2px)` }"
              @click="activePane = 'pane1'"
            >
              <!-- Primary Pane Tab Strip -->
              <div class="wb-editor-tabs-bar wb-pane-tabs-bar">
                <div class="wb-editor-tabs" role="tablist" aria-label="Editor Tabs 1">
                  <div
                    v-for="tab in pane1TabsState.tabs.value"
                    :key="'p1-' + tab.path"
                    class="wb-tab-item"
                    :class="{ active: tab.path === pane1ActiveTabPath, dirty: tab.dirty }"
                    role="tab"
                    :aria-selected="tab.path === pane1ActiveTabPath"
                    @click.stop="handleSelectTab(tab.path, 'pane1')"
                  >
                    <span class="tab-icon" aria-hidden="true">
                      <svg
                        v-if="tab.isDiff || tab.path.startsWith('diff://')"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M12 3v18" />
                      </svg>
                      <svg
                        v-else
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6" />
                      </svg>
                    </span>
                    <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
                    <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
                    <button
                      type="button"
                      class="tab-close-btn"
                      title="Close Tab"
                      aria-label="Close Tab"
                      @click.stop="handleCloseTab(tab.path, 'pane1')"
                    >
                      ×
                    </button>

                    <!-- Inline Popover for Unsaved Changes -->
                    <div
                      v-if="closingTab && closingTabPane === 'pane1' && closingTab.path === tab.path"
                      class="wb-tab-inline-popover"
                      @click.stop
                    >
                      <div class="pop-msg">Save changes?</div>
                      <div class="pop-actions">
                        <button type="button" class="pop-btn pop-save" @click="handleConfirmCloseSave">Save</button>
                        <button type="button" class="pop-btn pop-discard" @click="handleConfirmCloseDiscard">Don't Save</button>
                        <button type="button" class="pop-btn pop-cancel" @click="handleConfirmCloseCancel">Cancel</button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Primary Pane Actions Toolbar -->
                <div class="wb-tab-actions">
                  <button
                    v-if="pane1ActiveTabPath && !['aether://settings', 'aether://welcome'].includes(pane1ActiveTabPath)"
                    type="button"
                    class="wb-tab-save-btn"
                    :class="{ dirty: isPane1TabDirty }"
                    :disabled="!isPane1TabDirty"
                    :title="isPane1TabDirty ? 'Save (⌘S)' : 'All changes saved'"
                    aria-label="Save File"
                    @click.stop="handleSaveActiveFile('pane1')"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                      <polyline points="17 21 17 13 7 13 7 21"/>
                      <polyline points="7 3 7 8 15 8"/>
                    </svg>
                    <span v-if="isPane1TabDirty" class="save-dot">●</span>
                  </button>

                  <!-- Split Direction Toggle -->
                  <button
                    type="button"
                    class="wb-tab-action-btn wb-tab-orient-btn"
                    :title="splitDirection === 'vertical' ? 'Switch to Horizontal Split (Stacked)' : 'Switch to Vertical Split (Side by Side)'"
                    aria-label="Toggle Split Direction"
                    @click.stop="toggleSplitDirection"
                  >
                    <svg v-if="splitDirection === 'vertical'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                      <line x1="3" y1="12" x2="21" y2="12"/>
                    </svg>
                    <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                      <line x1="12" y1="3" x2="12" y2="21"/>
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Primary Breadcrumbs Bar -->
              <div v-if="pane1ActiveTabPath" class="wb-breadcrumbs-bar">
                <AppBreadcrumbs
                  :path="pane1ActiveTabPath"
                  :root="projectRootName"
                  @navigate="handleBreadcrumbNavigate"
                  @select-file="(p) => handleOpenFile(p, 'pane1')"
                />
              </div>

              <!-- Primary Editor Canvas -->
              <div class="wb-pane-editor-canvas">
                <MonacoDiffEditor
                  v-if="pane1ActiveTab?.isDiff || pane1ActiveTabPath.startsWith('diff://')"
                  :key="'p1-diff-' + pane1ActiveTabPath"
                  :path="pane1ActiveTabPath"
                  :file-path="pane1ActiveTab?.filePath"
                  :name="pane1ActiveTab?.name"
                  :project="activeProject"
                  instance-id="primary"
                  embedded
                  @edit-file="(f) => handleOpenFile(f, 'pane1')"
                  @discard="handleDirectDiscard"
                  @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
                />
                <CodeEditor
                  v-else-if="pane1ActiveTabPath"
                  ref="activeCodeEditorRef"
                  :key="'p1-code-' + pane1ActiveTabPath"
                  :path="pane1ActiveTabPath"
                  instance-id="primary"
                  embedded
                  @saved="(e) => onEditorSaved(e, 'pane1')"
                  @dirty-change="(e) => onEditorDirtyChange(e, 'pane1')"
                  @cursor-change="onCursorChange"
                  @markers-change="onMarkersChange"
                  @syntax-change="onSyntaxChange"
                  @error="onEditorError"
                  @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
                />
                <div v-else class="empty-split-pane">
                  <p>No open tabs in Tab 1</p>
                  <span>Select a file from Explorer to open</span>
                </div>
              </div>
            </div>

            <!-- Draggable / Responsive Split Divider -->
            <div
              class="wb-split-divider"
              :class="[`divider-${splitDirection}`]"
              role="separator"
              :aria-orientation="splitDirection"
              title="Drag to resize split, double click to center"
              @mousedown="onSplitDividerMouseDown"
              @dblclick="onSplitDividerDblClick"
            >
              <div class="divider-handle"></div>
            </div>

            <!-- Secondary Editor Pane (Tab 2 / Right) -->
            <div
              class="wb-split-pane wb-split-pane-secondary"
              :class="{ 'is-focused-pane': activePane === 'pane2' }"
              :style="splitDirection === 'vertical'
                ? { width: `calc(${100 - splitRatio}% - 2px)`, height: '100%', flex: `0 0 calc(${100 - splitRatio}% - 2px)` }
                : { height: `calc(${100 - splitRatio}% - 2px)`, width: '100%', flex: `0 0 calc(${100 - splitRatio}% - 2px)` }"
              @click="activePane = 'pane2'"
            >
              <!-- Secondary Pane Tab Strip -->
              <div class="wb-editor-tabs-bar wb-pane-tabs-bar">
                <div class="wb-editor-tabs" role="tablist" aria-label="Editor Tabs 2">
                  <div
                    v-for="tab in pane2TabsState.tabs.value"
                    :key="'p2-' + tab.path"
                    class="wb-tab-item"
                    :class="{ active: tab.path === pane2ActiveTabPath, dirty: tab.dirty }"
                    role="tab"
                    :aria-selected="tab.path === pane2ActiveTabPath"
                    @click.stop="handleSelectTab(tab.path, 'pane2')"
                  >
                    <span class="tab-icon" aria-hidden="true">
                      <svg
                        v-if="tab.isDiff || tab.path.startsWith('diff://')"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M12 3v18" />
                      </svg>
                      <svg
                        v-else
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6" />
                      </svg>
                    </span>
                    <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
                    <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
                    <button
                      type="button"
                      class="tab-close-btn"
                      title="Close Tab"
                      aria-label="Close Tab"
                      @click.stop="handleCloseTab(tab.path, 'pane2')"
                    >
                      ×
                    </button>

                    <!-- Inline Popover for Unsaved Changes -->
                    <div
                      v-if="closingTab && closingTabPane === 'pane2' && closingTab.path === tab.path"
                      class="wb-tab-inline-popover"
                      @click.stop
                    >
                      <div class="pop-msg">Save changes?</div>
                      <div class="pop-actions">
                        <button type="button" class="pop-btn pop-save" @click="handleConfirmCloseSave">Save</button>
                        <button type="button" class="pop-btn pop-discard" @click="handleConfirmCloseDiscard">Don't Save</button>
                        <button type="button" class="pop-btn pop-cancel" @click="handleConfirmCloseCancel">Cancel</button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Secondary Pane Actions Toolbar -->
                <div class="wb-tab-actions">
                  <button
                    v-if="pane2ActiveTabPath"
                    type="button"
                    class="wb-tab-save-btn"
                    :class="{ dirty: isPane2TabDirty }"
                    :disabled="!isPane2TabDirty"
                    :title="isPane2TabDirty ? 'Save (⌘S)' : 'All changes saved'"
                    aria-label="Save File"
                    @click.stop="handleSaveActiveFile('pane2')"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                      <polyline points="17 21 17 13 7 13 7 21"/>
                      <polyline points="7 3 7 8 15 8"/>
                    </svg>
                    <span v-if="isPane2TabDirty" class="save-dot">●</span>
                  </button>

                  <!-- Close Split Pane Button -->
                  <button
                    type="button"
                    class="wb-tab-action-btn split-pane-close-btn"
                    title="Close Split Editor"
                    aria-label="Close Split Editor"
                    @click.stop="closeSplitEditor(false)"
                  >
                    <span style="font-size: 16px; line-height: 1;">×</span>
                  </button>
                </div>
              </div>

              <!-- Secondary Breadcrumbs Bar -->
              <div v-if="pane2ActiveTabPath" class="wb-breadcrumbs-bar split-breadcrumbs">
                <AppBreadcrumbs
                  :path="pane2ActiveTabPath"
                  :root="projectRootName"
                  @navigate="handleBreadcrumbNavigate"
                  @select-file="(p) => handleOpenFile(p, 'pane2')"
                />
              </div>

              <!-- Secondary Editor Canvas -->
              <div class="wb-pane-editor-canvas">
                <MonacoDiffEditor
                  v-if="pane2ActiveTab?.isDiff || pane2ActiveTabPath.startsWith('diff://')"
                  :key="'p2-diff-' + pane2ActiveTabPath"
                  :path="pane2ActiveTabPath"
                  :file-path="pane2ActiveTab?.filePath"
                  :name="pane2ActiveTab?.name"
                  :project="activeProject"
                  instance-id="split"
                  embedded
                  @edit-file="(f) => handleOpenFile(f, 'pane2')"
                  @discard="handleDirectDiscard"
                  @close="handleCloseTab(pane2ActiveTabPath, 'pane2')"
                />
                <CodeEditor
                  v-else-if="pane2ActiveTabPath"
                  ref="splitCodeEditorRef"
                  :key="'p2-code-' + pane2ActiveTabPath"
                  :path="pane2ActiveTabPath"
                  instance-id="split"
                  embedded
                  @saved="(e) => onEditorSaved(e, 'pane2')"
                  @dirty-change="(e) => onEditorDirtyChange(e, 'pane2')"
                  @cursor-change="onCursorChange"
                  @markers-change="onMarkersChange"
                  @syntax-change="onSyntaxChange"
                  @error="onEditorError"
                  @close="handleCloseTab(pane2ActiveTabPath, 'pane2')"
                />
                <div v-else class="empty-split-pane">
                  <p>No open tabs in Tab 2</p>
                  <span>Select a file from Explorer to open</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 3. Monaco Diff Editor (Git Working Tree vs HEAD - Read Only, Single Pane) -->
          <MonacoDiffEditor
            v-else-if="pane1ActiveTab?.isDiff || pane1ActiveTabPath.startsWith('diff://')"
            :key="'single-diff-' + pane1ActiveTabPath"
            :path="pane1ActiveTabPath"
            :file-path="pane1ActiveTab?.filePath"
            :name="pane1ActiveTab?.name"
            :project="activeProject"
            instance-id="primary"
            embedded
            @edit-file="(f) => handleOpenFile(f, 'pane1')"
            @discard="handleDirectDiscard"
            @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
          />

          <!-- 4. Code Editor (Monaco, Single Pane) -->
          <CodeEditor
            v-else-if="pane1ActiveTabPath"
            ref="activeCodeEditorRef"
            :key="'single-code-' + pane1ActiveTabPath"
            :path="pane1ActiveTabPath"
            instance-id="primary"
            embedded
            @saved="(e) => onEditorSaved(e, 'pane1')"
            @dirty-change="(e) => onEditorDirtyChange(e, 'pane1')"
            @cursor-change="onCursorChange"
            @markers-change="onMarkersChange"
            @syntax-change="onSyntaxChange"
            @error="onEditorError"
            @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
          />

          <!-- 5. Active Workspace Empty Canvas (Zero tabs open, project active) -->
          <div v-else-if="activeProject" class="wb-welcome">
            <div class="welcome-card">
              <div class="welcome-logo">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="m4.5 8.5-3 3.5 3 3.5" />
                  <path d="m19.5 8.5 3 3.5-3 3.5" />
                  <path d="M12 3c.4 3.8 2.2 5.6 6 6-3.8.4-5.6 2.2-6 6-.4-3.8-2.2-5.6-6-6 3.8-.4 5.6-2.2 6-6Z" />
                  <circle cx="12" cy="12" r="1.5" fill="currentColor" />
                </svg>
              </div>
              <h2 class="welcome-title">Welcome to AEGIS</h2>
              <div class="welcome-project">{{ activeProject?.path || activeProject?.root || '' }}</div>
              <div class="welcome-shortcuts">
                <div class="shortcut-row">
                  <span class="sc-label">Quick Open</span>
                  <span class="sc-kbd-group"><kbd>Cmd</kbd> + <kbd>P</kbd></span>
                </div>
                <div class="shortcut-row">
                  <span class="sc-label">Command Palette</span>
                  <span class="sc-kbd-group"><kbd>Cmd</kbd> + <kbd>K</kbd></span>
                </div>
                <div class="shortcut-row">
                  <span class="sc-label">Toggle Terminal Dock</span>
                  <span class="sc-kbd-group"><kbd>Ctrl</kbd> + <kbd>`</kbd></span>
                </div>
              </div>
            </div>
          </div>

          <!-- 4. Standalone Fullscreen Getting Started View (No Active Project) -->
          <div v-else class="wb-getting-started-wrapper">
            <WelcomeView
              :projects="projects"
              :last-project="projects[0] || null"
              :active-project="null"
              @open-folder="emit('open-folder')"
              @clone-git="handleOpenCloneGitModal"
              @new-task="emit('open-composer')"
              @open-project="emit('select-project', $event)"
              @delete-project="emit('delete-project', $event)"
              @open-settings="openSettings('providers')"
            />
          </div>
        </div>

        <!-- Bottom Dock Splitter -->
        <AppSplitter
          v-if="bottomDockOpen"
          direction="horizontal"
          v-model="dockHeight"
          :min="150"
          :max="400"
          :default-size="220"
          inverted
        />

        <!-- Collapsible Bottom Dock -->
        <AppBottomDock
          :open="bottomDockOpen"
          :height="dockHeight"
          :active-tab="dockActiveTab"
          :terminal-lines="effectiveTerminalLines"
          :output-lines="effectiveOutputLines"
          :editor-diagnostics="activeEditorDiagnostics"
          :problems="effectiveProblems"
          :terminal-running="terminalRunning"
          :project-id="activeProject?.id || ''"
          @update:open="bottomDockOpen = $event"
          @update:active-tab="dockActiveTab = $event"
          @clear="handleClearDock"
          @close="bottomDockOpen = false"
          @run-command="handleTerminalCommand"
          @abort-command="handleAbortCommand"
          @navigate-to-location="handleNavigateToLocation"
        />
      </main>

      <!-- Right Splitter (Desktop only) -->
      <AppSplitter
        v-if="tier === 'desktop' && assistantVisible"
        direction="vertical"
        v-model="assistantWidth"
        :min="320"
        :max="650"
        :default-size="380"
        inverted
      />

      <!-- 3. Right Column: AI Assistant Drawer -->
      <aside
        v-show="assistantVisible"
        class="wb-right-column"
        :style="tier !== 'mobile' ? { width: `${assistantWidth}px` } : {}"
      >
        <AppRightDrawer
          v-model:active-tab="assistantTab"
          :task="task"
          :task-history="taskHistory"
          :task-tag="taskTag"
          :show-task-meta="showTaskMeta"
          :task-provider="effectiveTaskProvider"
          :task-model="effectiveTaskModel"
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
          :stop-in-progress="stopInProgress"
          :error="error"
          :consultant-props="effectiveConsultantProps"
          :providers="effectiveProviderList"
          :provider-instance-id="effectiveProviderInstanceId"
          :model-id="effectiveModelId"
          @close="toggleAssistant(false)"
          @open-composer="emit('open-composer')"
          @request-stop="emit('request-stop')"
          @submit-task="emit('submit-task', $event)"
          @open-settings="emit('open-settings', $event)"
          @open-report="emit('open-report', $event)"
          @copy-activity="emit('copy-activity')"
          @run-consultant-task="handleRunConsultantTask"
          @consultant-event="handleConsultantEvent"
          @apply-to-editor="handleApplyToEditor"
          @update:provider-instance-id="emit('update:provider-instance-id', $event)"
          @update:model-id="emit('update:model-id', $event)"
          @update:active-session-id="activeConsultantSessionId = $event"
        />
      </aside>
    </div>

    <!-- Clone Git Repository Modal -->
    <AppModal
      v-if="cloneGitModalOpen"
      :model-value="cloneGitModalOpen"
      title="Clone Git Repository"
      max-width="480px"
      @close="cloneGitModalOpen = false"
    >
      <div class="clone-git-dialog">
        <p class="clone-git-desc">
          Enter a remote Git repository URL to clone into your local workspace.
        </p>
        <div class="form-group">
          <label class="form-label" for="git-repo-url">Repository URL</label>
          <input
            id="git-repo-url"
            v-model="cloneGitUrl"
            type="text"
            class="form-control mono"
            placeholder="https://github.com/username/repository.git"
            :disabled="cloneGitBusy"
            @keydown.enter="handleCloneGitSubmit"
          />
        </div>
        <div v-if="cloneGitNotice" class="clone-git-notice">
          {{ cloneGitNotice }}
        </div>
        <div class="clone-git-actions">
          <button
            type="button"
            class="btn btn-ghost"
            :disabled="cloneGitBusy"
            @click="cloneGitModalOpen = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!cloneGitUrl.trim() || cloneGitBusy"
            @click="handleCloneGitSubmit"
          >
            <span v-if="cloneGitBusy">Connecting…</span>
            <span v-else>Clone Repository</span>
          </button>
        </div>
      </div>
    </AppModal>

    <!-- Background Task Completion Toast Notification -->
    <transition name="toast-slide">
      <div
        v-if="bgToast"
        class="wb-bg-toast"
        :class="`toast-${bgToast.type}`"
        role="alert"
      >
        <div class="toast-dot" :class="`dot-${bgToast.type}`"></div>
        <div class="toast-body">
          <div class="toast-title">{{ bgToast.title }}</div>
          <div v-if="bgToast.message" class="toast-msg">{{ bgToast.message }}</div>
        </div>
        <div class="toast-actions">
          <button
            type="button"
            class="toast-btn-action"
            @click="handleOpenToastAction"
          >
            Open
          </button>
          <button
            type="button"
            class="toast-btn-dismiss"
            title="Dismiss notification"
            aria-label="Dismiss notification"
            @click="bgToast = null"
          >
            ✕
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<style>
.clone-git-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0;
}
.clone-git-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-dim, #888888);
  line-height: 1.4;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text, #cccccc);
}
.form-control {
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--bg-surface, #252526);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  color: var(--text-bright, #ffffff);
  font-size: 13px;
  outline: none;
}
.form-control:focus {
  border-color: var(--accent, #10f09a);
}
.clone-git-notice {
  font-size: 12px;
  color: var(--accent, #10f09a);
  background: rgba(16, 240, 154, 0.08);
  border: 1px solid rgba(16, 240, 154, 0.25);
  padding: 8px 12px;
  border-radius: 6px;
}
.clone-git-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

/* Background Process Toast Notification */
.wb-bg-toast {
  position: absolute;
  bottom: 24px;
  right: 24px;
  z-index: 1050;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 280px;
  max-width: 420px;
  padding: 10px 14px;
  background: var(--bg-surface, #1e1d24);
  border: 1px solid var(--border-soft, #383447);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  font-size: 13px;
  color: var(--text-bright, #ffffff);
}

.toast-success {
  border-left: 4px solid var(--accent, #10f09a);
}

.toast-warning {
  border-left: 4px solid var(--color-warning, #f59e0b);
}

.toast-error {
  border-left: 4px solid var(--color-danger, #ef4444);
}

.toast-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-success {
  background: var(--accent, #10f09a);
  box-shadow: 0 0 6px var(--accent, #10f09a);
}

.dot-warning {
  background: var(--color-warning, #f59e0b);
  box-shadow: 0 0 6px var(--color-warning, #f59e0b);
}

.dot-error {
  background: var(--color-danger, #ef4444);
  box-shadow: 0 0 6px var(--color-danger, #ef4444);
}

.toast-body {
  flex: 1;
  min-width: 0;
}

.toast-title {
  font-weight: 600;
  font-size: 13px;
  line-height: 1.2;
}

.toast-msg {
  font-size: 11px;
  color: var(--text-dim, #999999);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toast-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toast-btn-action {
  padding: 4px 10px;
  border-radius: 4px;
  background: var(--accent, #10f09a);
  color: #0b0f19;
  font-size: 11px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.toast-btn-action:hover {
  opacity: 0.9;
}

.toast-btn-dismiss {
  background: none;
  border: none;
  color: var(--text-dim, #888888);
  font-size: 13px;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  transition: color 0.15s ease;
}

.toast-btn-dismiss:hover {
  color: var(--text-bright, #ffffff);
}

.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.96);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
</style>
