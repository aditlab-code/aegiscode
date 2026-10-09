<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AppLeftSidebar from "../components/layout/AppLeftSidebar.vue";
import AppRightDrawer from "../components/layout/AppRightDrawer.vue";
import AppBottomDrawer from "../components/layout/AppBottomDrawer.vue";
import AppSplitter from "../components/ui/AppSplitter.vue";
import AppModal from "../components/ui/AppModal.vue";
import CodeEditor from "../components/editor/CodeEditor.vue";
import MonacoDiffEditor from "../components/editor/MonacoDiffEditor.vue";
import WelcomeView from "../components/editor/WelcomeView.vue";
import EditorTabBar from "../components/editor/EditorTabBar.vue";
import EditorBreadcrumbs from "../components/editor/EditorBreadcrumbs.vue";
import EditorConfirmCloseModal from "../components/editor/EditorConfirmCloseModal.vue";
import SettingsOverlay from "./SettingsOverlay.vue";

import { useWorkbenchLayout } from "../composables/useWorkbenchLayout.js";
import { useWorkbenchEditorFacade } from "../composables/workbench/useWorkbenchEditorFacade.js";
import { useWorkbenchAssistantFacade } from "../composables/workbench/useWorkbenchAssistantFacade.js";
import { useWorkbenchDockFacade } from "../composables/workbench/useWorkbenchDockFacade.js";

const props = defineProps({
  config: { type: Object, default: () => ({}) }, taskHistory: { type: Array, default: () => [] }, settingsTab: { type: String, default: "providers" },
  activeProject: { type: Object, default: null }, projects: { type: Array, default: () => [] }, selectedProjectId: { type: String, default: "" },
  activeNav: { type: String, default: "explorer" }, changes: { type: Array, default: () => [] }, validation: { type: Object, default: () => ({}) },
  explorerRefresh: { type: Number, default: 0 }, liveFsChange: { type: Object, default: null }, queueRefresh: { type: Number, default: 0 },
  connected: { type: Boolean, default: false }, gatewayAddress: { type: String, default: "" }, agentStatus: { type: Object, default: () => ({ label: "idle", cls: "status-off" }) },
  task: { type: Object, default: () => ({}) }, taskTag: { type: Object, default: () => ({ cls: "", label: "" }) }, showTaskMeta: { type: Boolean, default: false },
  taskProvider: { type: String, default: "" }, taskModel: { type: String, default: "" }, taskExecutionLabel: { type: String, default: "Queue" },
  taskRoundLabel: { type: String, default: "" }, taskDurationLabel: { type: String, default: "" }, taskTimerLive: { type: Boolean, default: false },
  showTaskTelemetry: { type: Boolean, default: false }, taskLlmRounds: { type: Number, default: 0 }, taskToolCalls: { type: Number, default: 0 },
  taskTokensLabel: { type: String, default: "" }, taskTokensTooltip: { type: String, default: "" }, lifecycleSteps: { type: Array, default: () => [] },
  lifecyclePct: { type: Number, default: 0 }, activityPhase: { type: String, default: "" }, activityEvents: { type: Array, default: () => [] },
  showReasoning: { type: Boolean, default: false }, activityCopied: { type: Boolean, default: false }, isRunning: { type: Boolean, default: false },
  stopInProgress: { type: Boolean, default: false }, isSubmitting: { type: Boolean, default: false }, error: { type: String, default: "" },
  consultantProps: { type: Object, default: () => ({}) }, runningTaskId: { type: String, default: "" }, terminalLines: { type: Array, default: () => [] },
  outputLines: { type: Array, default: () => [] }, problems: { type: Array, default: () => [] }, tier: { type: String, default: "desktop" },
  activeOverlay: { type: String, default: null }, sidebarVisible: { type: Boolean, default: true }, assistantVisible: { type: Boolean, default: true },
  initialTabs: { type: Array, default: () => [] }, initialActiveTab: { type: String, default: "" }, initialSplitActive: { type: Boolean, default: false },
  initialSplitDirection: { type: String, default: "vertical" }, initialSplitTab: { type: String, default: "" }, providers: { type: Array, default: () => [] },
  providerInstanceId: { type: String, default: "" }, modelId: { type: String, default: "" }, mode: { type: String, default: "balanced" },
});

const emit = defineEmits([
  "select-project", "close-project", "open-file", "active-file-change",
  "stop-task", "view-task", "open-composer", "request-stop", "submit-task",
  "open-settings", "open-report", "copy-activity", "run-consultant-task",
  "consultant-event", "apply-to-editor", "toggle-dock", "cursor-change",
  "close-overlay", "toggle-assistant", "toggle-sidebar",
  "update:provider-instance-id", "update:model-id", "update:mode",
  "refresh-config", "refresh-history", "open-history-task",
  "open-consultant-session", "open-session", "open-folder", "delete-project",
  "open-path", "open-explorer", "branch-info-updated", "checkpoint-created",
]);

// Layout, Editor, Assistant, & Dock Coordinators
const {
  sidebarWidth, sidebarVisible, assistantWidth, assistantVisible,
  assistantTab, bottomDockOpen, dockHeight, dockActiveTab,
  toggleSidebar, toggleAssistant, toggleBottomDock,
} = useWorkbenchLayout(props, emit);

const editorFacade = useWorkbenchEditorFacade(props, emit, {
  showBgToast: (opts) => assistantFacade.showBgToast(opts),
  restoreLayout: (layout) => {
    if (typeof layout.bottomDockOpen === "boolean") bottomDockOpen.value = layout.bottomDockOpen;
    if (layout.dockActiveTab) dockActiveTab.value = layout.dockActiveTab;
    if (typeof layout.dockHeight === "number") dockHeight.value = layout.dockHeight;
    if (layout.assistantTab) assistantTab.value = layout.assistantTab;
  },
});

const assistantFacade = useWorkbenchAssistantFacade(props, emit, {
  assistantTab, assistantVisible, toggleAssistant,
  activeTab: editorFacade.activeTab,
});

const dockFacade = useWorkbenchDockFacade(props, emit, {
  activeEditorDiagnostics: editorFacade.activeEditorDiagnostics,
  checkAndHandleAgentFileConflict: editorFacade.checkAndHandleAgentFileConflict,
  bottomDockOpen, dockActiveTab,
});

const cloneGitModalOpen = ref(false), cloneGitUrl = ref(""), cloneGitBusy = ref(false), cloneGitNotice = ref("");
function handleOpenCloneGitModal() {
  cloneGitModalOpen.value = true; cloneGitNotice.value = ""; cloneGitUrl.value = "";
}
function handleCloneGitSubmit() {
  const url = cloneGitUrl.value.trim();
  if (!url) return;
  const command = `git clone ${url}`;
  if (typeof navigator !== "undefined" && navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(command)
      .then(() => { cloneGitNotice.value = `Command copied: "${command}". Run in terminal, then Open Folder.`; })
      .catch(() => { cloneGitNotice.value = `Run this in terminal: "${command}", then Open Folder.`; });
  } else {
    cloneGitNotice.value = `Run this in terminal: "${command}", then Open Folder.`;
  }
}

function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "`") { e.preventDefault(); toggleBottomDock(); return; }
  if (e.key === "Escape" && props.tier !== "desktop" && props.activeOverlay) { e.preventDefault(); emit("close-overlay"); }
}

watch([() => props.tier, editorFacade.effectiveSplitDirection], () => { nextTick(() => editorFacade.triggerEditorLayout()); });

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", editorFacade.triggerEditorLayout);
  }
});
onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("resize", editorFacade.triggerEditorLayout);
  }
});

defineExpose({
  editorTabsState: editorFacade.editorTabsState, pane1TabsState: editorFacade.pane1TabsState,
  pane2TabsState: editorFacade.pane2TabsState, activePane: editorFacade.activePane,
  activeTabPath: editorFacade.activeTabPath, activeCodeEditorRef: editorFacade.activeCodeEditorRef,
  splitActive: editorFacade.splitActive, splitDirection: editorFacade.splitDirection,
  splitTabPath: editorFacade.splitTabPath, splitCodeEditorRef: editorFacade.splitCodeEditorRef,
  toggleSplitEditor: editorFacade.toggleSplitEditor, toggleSplitDirection: editorFacade.toggleSplitDirection,
  closeSplitEditor: editorFacade.closeSplitEditor, bottomDockOpen, dockHeight, dockActiveTab,
  sidebarWidth, sidebarVisible, assistantWidth, assistantVisible, assistantTab,
  terminalLines: dockFacade.effectiveTerminalLines, outputLines: dockFacade.effectiveOutputLines,
  problems: dockFacade.effectiveProblems, terminalRunning: dockFacade.terminalRunning,
  toggleSidebar, toggleAssistant, toggleBottomDock,
  handleOpenFile: editorFacade.handleOpenFile, handleOpenDiff: editorFacade.handleOpenDiff,
  handleCloseTab: editorFacade.handleCloseTab, handleApplyToEditor: editorFacade.handleApplyToEditor,
  handleClearDock: dockFacade.handleClearDock, handleTerminalCommand: dockFacade.handleTerminalCommand,
  handleAbortCommand: dockFacade.handleAbortCommand, openSettings: editorFacade.openSettings,
  openWelcomeTab: editorFacade.openWelcomeTab, clearAllTabs: editorFacade.clearAllTabs,
  handleOpenAgentComposer: assistantFacade.handleOpenAgentComposer, openComposer: assistantFacade.handleOpenAgentComposer,
});
</script>

<template>
  <div class="workbench-view" :class="[`tier-${tier}`, { 'dock-open': bottomDockOpen }]">
    <div class="workbench-columns">
      <!-- 1. Left Sidebar -->
      <aside v-show="sidebarVisible" class="wb-left-column" :style="tier !== 'mobile' ? { width: `${sidebarWidth}px` } : {}">
        <AppLeftSidebar
          :active-nav="activeNav" :active-project="activeProject" :projects="projects"
          :selected-project-id="selectedProjectId" :changes="changes" :validation="validation"
          :explorer-refresh="explorerRefresh + editorFacade.localGitRefresh.value"
          :live-fs-change="liveFsChange" :queue-refresh="queueRefresh" :connected="connected"
          :gateway-address="gatewayAddress" :agent-status="agentStatus" :task-id="task?.id || ''"
          @open-file="(f) => editorFacade.handleOpenFile(f, 'pane1')" @open-diff="(f) => editorFacade.handleOpenDiff(f, 'pane1')"
          @select-project="emit('select-project', $event)" @open-project="emit('open-project', $event)" @close-project="emit('close-project')"
          @discard-change="editorFacade.handleDirectDiscard" @stage-change="editorFacade.handleStageChange"
          @checkpoint-created="editorFacade.handleCheckpointCreated" @view-task="emit('view-task', $event)"
          @open-composer="assistantFacade.handleOpenAgentComposer" @open-settings="editorFacade.openSettings('providers')"
          @open-session="assistantFacade.handleOpenConsultantSession" @branch-info-updated="emit('branch-info-updated', $event)"
        />
      </aside>

      <AppSplitter v-if="tier === 'desktop' && sidebarVisible" direction="vertical" v-model="sidebarWidth" :min="200" :max="450" :default-size="260" />

      <!-- 2. Center Column -->
      <main class="wb-center-column">
        <!-- Single Mode Tab Bar & Breadcrumbs -->
        <EditorTabBar
          v-if="!editorFacade.splitActive.value && (activeProject || editorFacade.pane1TabsState.tabs.value.length > 0)"
          :tabs="editorFacade.pane1TabsState.tabs.value" :active-tab-path="editorFacade.pane1ActiveTabPath.value" pane="pane1"
          :split-active="false" :is-pane-dirty="editorFacade.isPane1TabDirty.value" :conflict-file="editorFacade.conflictFile.value"
          :conflict-added-lines="editorFacade.conflictAddedLines.value" :conflict-removed-lines="editorFacade.conflictRemovedLines.value"
          :closing-tab="editorFacade.closingTab.value" :closing-tab-pane="editorFacade.closingTabPane.value"
          @select-tab="editorFacade.handleSelectTab" @close-tab="editorFacade.handleCloseTab" @save-tab="editorFacade.handleSaveActiveFile"
          @toggle-split="editorFacade.toggleSplitEditor" @resolve-keep-mine="editorFacade.resolveKeepMine"
          @resolve-accept-agent="editorFacade.resolveAcceptAgent" @resolve-review-diff="editorFacade.resolveReviewDiff"
          @confirm-close-save="editorFacade.handleConfirmCloseSave" @confirm-close-discard="editorFacade.handleConfirmCloseDiscard"
          @confirm-close-cancel="editorFacade.handleConfirmCloseCancel"
        />
        <EditorBreadcrumbs
          v-if="!editorFacade.splitActive.value && editorFacade.pane1ActiveTabPath.value"
          :active-tab-path="editorFacade.pane1ActiveTabPath.value" :active-tab="editorFacade.pane1ActiveTab.value"
          :project-root-name="editorFacade.projectRootName.value" @navigate="editorFacade.handleBreadcrumbNavigate"
          @select-file="(p) => editorFacade.handleOpenFile(p, 'pane1')"
        />

        <!-- Central Canvas -->
        <div class="wb-editor-canvas">
          <div v-if="!editorFacade.splitActive.value && editorFacade.pane1ActiveTabPath.value === 'aegis://settings'" class="wb-settings-tab">
            <SettingsOverlay
              embedded :open="true" :config="config" :projects="projects" :task-history="taskHistory"
              :active-project="activeProject" :provider-instance-id="providerInstanceId" :model-id="modelId" :mode="config?.mode"
              v-model:active-tab="editorFacade.settingsSubTab.value" @close="editorFacade.handleCloseTab('aegis://settings', 'pane1')"
              @refresh-config="emit('refresh-config')" @update:provider-instance-id="emit('update:provider-instance-id', $event)"
              @update:model-id="emit('update:model-id', $event)" @update:mode="emit('update:mode', $event)"
              @open-report="emit('open-report', $event)" @open-history-task="emit('open-history-task', $event)"
              @delete-history="emit('delete-history', $event)" @clear-history="emit('clear-history')"
              @open-project-policy="emit('open-project-policy', $event)" @delete-project="emit('delete-project', $event)"
              @open-project="emit('open-project', $event)"
            />
          </div>

          <!-- Dual-Window Split Editor -->
          <div
            v-else-if="editorFacade.splitActive.value" class="wb-split-editor-container"
            :class="[`split-${editorFacade.effectiveSplitDirection.value}`, `split-tier-${tier}`, { 'pane-primary-active': editorFacade.activePane.value === 'pane1', 'pane-split-active': editorFacade.activePane.value === 'pane2' }]"
          >
            <!-- Primary Pane (Window 1) -->
            <div class="wb-split-pane wb-split-pane-primary" :class="{ 'is-focused-pane': editorFacade.activePane.value === 'pane1' }" :style="editorFacade.pane1Style.value" @click="editorFacade.activePane.value = 'pane1'">
              <EditorTabBar
                :tabs="editorFacade.pane1TabsState.tabs.value" :active-tab-path="editorFacade.pane1ActiveTabPath.value" pane="pane1"
                :split-active="true" :split-direction="editorFacade.splitDirection.value" :is-pane-dirty="editorFacade.isPane1TabDirty.value"
                :conflict-file="editorFacade.conflictFile.value" :conflict-added-lines="editorFacade.conflictAddedLines.value"
                :conflict-removed-lines="editorFacade.conflictRemovedLines.value" :closing-tab="editorFacade.closingTab.value"
                :closing-tab-pane="editorFacade.closingTabPane.value" aria-label="Editor Window 1"
                @select-tab="editorFacade.handleSelectTab" @close-tab="editorFacade.handleCloseTab" @save-tab="editorFacade.handleSaveActiveFile"
                @toggle-orient="editorFacade.toggleSplitDirection" @resolve-keep-mine="editorFacade.resolveKeepMine"
                @resolve-accept-agent="editorFacade.resolveAcceptAgent" @resolve-review-diff="editorFacade.resolveReviewDiff"
                @confirm-close-save="editorFacade.handleConfirmCloseSave" @confirm-close-discard="editorFacade.handleConfirmCloseDiscard"
                @confirm-close-cancel="editorFacade.handleConfirmCloseCancel"
              />
              <EditorBreadcrumbs
                v-if="editorFacade.pane1ActiveTabPath.value" :active-tab-path="editorFacade.pane1ActiveTabPath.value"
                :active-tab="editorFacade.pane1ActiveTab.value" :project-root-name="editorFacade.projectRootName.value"
                @navigate="editorFacade.handleBreadcrumbNavigate" @select-file="(p) => editorFacade.handleOpenFile(p, 'pane1')"
              />
              <div class="wb-pane-editor-canvas">
                <div v-if="editorFacade.pane1ActiveTabPath.value === 'aegis://settings'" class="wb-settings-tab">
                  <SettingsOverlay
                    embedded :open="true" :config="config" :projects="projects" :task-history="taskHistory" :active-project="activeProject"
                    :provider-instance-id="providerInstanceId" :model-id="modelId" :mode="config?.mode"
                    v-model:active-tab="editorFacade.settingsSubTab.value" @close="editorFacade.handleCloseTab('aegis://settings', 'pane1')"
                    @refresh-config="emit('refresh-config')" @update:provider-instance-id="emit('update:provider-instance-id', $event)"
                    @update:model-id="emit('update:model-id', $event)" @update:mode="emit('update:mode', $event)"
                    @open-report="emit('open-report', $event)" @open-history-task="emit('open-history-task', $event)"
                    @delete-history="emit('delete-history', $event)" @clear-history="emit('clear-history')"
                    @open-project-policy="emit('open-project-policy', $event)" @delete-project="emit('delete-project', $event)"
                  />
                </div>
                <MonacoDiffEditor
                  v-else-if="editorFacade.pane1ActiveTab.value?.isDiff || editorFacade.pane1ActiveTabPath.value.startsWith('diff://')"
                  :key="'p1-diff-' + editorFacade.pane1ActiveTabPath.value" :path="editorFacade.pane1ActiveTabPath.value"
                  :file-path="editorFacade.pane1ActiveTab.value?.filePath" :name="editorFacade.pane1ActiveTab.value?.name"
                  :project="activeProject" instance-id="primary" embedded @edit-file="(f) => editorFacade.handleOpenFile(f, 'pane1')"
                  @discard="editorFacade.handleDirectDiscard" @stage-change="editorFacade.handleStageChange"
                  @git-refresh="() => editorFacade.localGitRefresh.value++" @close="editorFacade.handleCloseTab(editorFacade.pane1ActiveTabPath.value, 'pane1')"
                />
                <CodeEditor
                  v-else-if="editorFacade.pane1ActiveTabPath.value" :ref="(el) => { editorFacade.activeCodeEditorRef.value = el }"
                  :path="editorFacade.pane1ActiveTabPath.value" :project-id="activeProject?.id || ''" instance-id="primary" embedded
                  @saved="(e) => editorFacade.onEditorSaved(e, 'pane1')" @dirty-change="(e) => editorFacade.onEditorDirtyChange(e, 'pane1')"
                  @cursor-change="editorFacade.onCursorChange" @markers-change="editorFacade.onMarkersChange"
                  @syntax-change="editorFacade.onSyntaxChange" @diagnostics-updated="editorFacade.onDiagnosticsUpdated"
                  @error="editorFacade.onEditorError" @close="editorFacade.handleCloseTab(editorFacade.pane1ActiveTabPath.value, 'pane1')"
                />
                <div v-else class="empty-split-pane">
                  <p>No open tabs in Window 1</p>
                  <span>Select a file from Explorer to open</span>
                </div>
              </div>
            </div>

            <!-- Divider -->
            <div
              class="wb-split-divider" :class="[`divider-${editorFacade.effectiveSplitDirection.value}`]"
              role="separator" :aria-orientation="editorFacade.effectiveSplitDirection.value"
              title="Drag to resize split, double click to center"
              @mousedown="editorFacade.onSplitDividerMouseDown" @dblclick="editorFacade.onSplitDividerDblClick"
            >
              <div class="divider-handle"></div>
            </div>

            <!-- Secondary Pane (Window 2) -->
            <div class="wb-split-pane wb-split-pane-secondary" :class="{ 'is-focused-pane': editorFacade.activePane.value === 'pane2' }" :style="editorFacade.pane2Style.value" @click="editorFacade.activePane.value = 'pane2'">
              <EditorTabBar
                :tabs="editorFacade.pane2TabsState.tabs.value" :active-tab-path="editorFacade.pane2ActiveTabPath.value" pane="pane2"
                :split-active="true" :split-direction="editorFacade.splitDirection.value" :is-pane-dirty="editorFacade.isPane2TabDirty.value"
                :conflict-file="editorFacade.conflictFile.value" :conflict-added-lines="editorFacade.conflictAddedLines.value"
                :conflict-removed-lines="editorFacade.conflictRemovedLines.value" :closing-tab="editorFacade.closingTab.value"
                :closing-tab-pane="editorFacade.closingTabPane.value" aria-label="Editor Window 2"
                @select-tab="editorFacade.handleSelectTab" @close-tab="editorFacade.handleCloseTab" @save-tab="editorFacade.handleSaveActiveFile"
                @close-split="editorFacade.closeSplitEditor" @resolve-keep-mine="editorFacade.resolveKeepMine"
                @resolve-accept-agent="editorFacade.resolveAcceptAgent" @resolve-review-diff="editorFacade.resolveReviewDiff"
                @confirm-close-save="editorFacade.handleConfirmCloseSave" @confirm-close-discard="editorFacade.handleConfirmCloseDiscard"
                @confirm-close-cancel="editorFacade.handleConfirmCloseCancel"
              />
              <EditorBreadcrumbs
                v-if="editorFacade.pane2ActiveTabPath.value" :active-tab-path="editorFacade.pane2ActiveTabPath.value"
                :active-tab="editorFacade.pane2ActiveTab.value" :project-root-name="editorFacade.projectRootName.value" :is-split="true"
                @navigate="editorFacade.handleBreadcrumbNavigate" @select-file="(p) => editorFacade.handleOpenFile(p, 'pane2')"
              />
              <div class="wb-pane-editor-canvas">
                <div v-if="editorFacade.pane2ActiveTabPath.value === 'aegis://settings'" class="wb-settings-tab">
                  <SettingsOverlay
                    embedded :open="true" :config="config" :projects="projects" :task-history="taskHistory" :active-project="activeProject"
                    :provider-instance-id="providerInstanceId" :model-id="modelId" :mode="config?.mode"
                    v-model:active-tab="editorFacade.settingsSubTab.value" @close="editorFacade.handleCloseTab('aegis://settings', 'pane2')"
                    @refresh-config="emit('refresh-config')" @update:provider-instance-id="emit('update:provider-instance-id', $event)"
                    @update:model-id="emit('update:model-id', $event)" @update:mode="emit('update:mode', $event)"
                    @open-report="emit('open-report', $event)" @open-history-task="emit('open-history-task', $event)"
                    @delete-history="emit('delete-history', $event)" @clear-history="emit('clear-history')"
                    @open-project-policy="emit('open-project-policy', $event)" @delete-project="emit('delete-project', $event)"
                  />
                </div>
                <MonacoDiffEditor
                  v-else-if="editorFacade.pane2ActiveTab.value?.isDiff || editorFacade.pane2ActiveTabPath.value.startsWith('diff://')"
                  :key="'p2-diff-' + editorFacade.pane2ActiveTabPath.value" :path="editorFacade.pane2ActiveTabPath.value"
                  :file-path="editorFacade.pane2ActiveTab.value?.filePath" :name="editorFacade.pane2ActiveTab.value?.name"
                  :project="activeProject" instance-id="split" embedded @edit-file="(f) => editorFacade.handleOpenFile(f, 'pane2')"
                  @discard="editorFacade.handleDirectDiscard" @stage-change="editorFacade.handleStageChange"
                  @git-refresh="() => editorFacade.localGitRefresh.value++" @close="editorFacade.handleCloseTab(editorFacade.pane2ActiveTabPath.value, 'pane2')"
                />
                <CodeEditor
                  v-else-if="editorFacade.pane2ActiveTabPath.value" :ref="(el) => { editorFacade.splitCodeEditorRef.value = el }"
                  :path="editorFacade.pane2ActiveTabPath.value" :project-id="activeProject?.id || ''" instance-id="split" embedded
                  @saved="(e) => editorFacade.onEditorSaved(e, 'pane2')" @dirty-change="(e) => editorFacade.onEditorDirtyChange(e, 'pane2')"
                  @cursor-change="editorFacade.onCursorChange" @markers-change="editorFacade.onMarkersChange"
                  @syntax-change="editorFacade.onSyntaxChange" @diagnostics-updated="editorFacade.onDiagnosticsUpdated"
                  @error="editorFacade.onEditorError" @close="editorFacade.handleCloseTab(editorFacade.pane2ActiveTabPath.value, 'pane2')"
                />
                <div v-else class="empty-split-pane">
                  <p>No open tabs in Window 2</p>
                  <span>Select a file from Explorer to open</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Single Diff Editor -->
          <MonacoDiffEditor
            v-else-if="editorFacade.pane1ActiveTab.value?.isDiff || editorFacade.pane1ActiveTabPath.value.startsWith('diff://')"
            :key="'single-diff-' + editorFacade.pane1ActiveTabPath.value" :path="editorFacade.pane1ActiveTabPath.value"
            :file-path="editorFacade.pane1ActiveTab.value?.filePath" :name="editorFacade.pane1ActiveTab.value?.name"
            :project="activeProject" instance-id="primary" embedded @edit-file="(f) => editorFacade.handleOpenFile(f, 'pane1')"
            @discard="editorFacade.handleDirectDiscard" @stage-change="editorFacade.handleStageChange"
            @git-refresh="() => editorFacade.localGitRefresh.value++" @close="editorFacade.handleCloseTab(editorFacade.pane1ActiveTabPath.value, 'pane1')"
          />

          <!-- Single Code Editor -->
          <CodeEditor
            v-else-if="editorFacade.pane1ActiveTabPath.value" :ref="(el) => { editorFacade.activeCodeEditorRef.value = el }"
            :path="editorFacade.pane1ActiveTabPath.value" :project-id="activeProject?.id || ''" instance-id="primary" embedded
            @saved="(e) => editorFacade.onEditorSaved(e, 'pane1')" @dirty-change="(e) => editorFacade.onEditorDirtyChange(e, 'pane1')"
            @cursor-change="editorFacade.onCursorChange" @markers-change="editorFacade.onMarkersChange"
            @syntax-change="editorFacade.onSyntaxChange" @diagnostics-updated="editorFacade.onDiagnosticsUpdated"
            @error="editorFacade.onEditorError" @close="editorFacade.handleCloseTab(editorFacade.pane1ActiveTabPath.value, 'pane1')"
          />

          <!-- Active Workspace Empty Canvas -->
          <div v-else-if="activeProject" class="wb-welcome welcome-view-root">
            <WelcomeView
              :projects="projects" :last-project="projects[0] || null" :active-project="activeProject"
              @open-folder="emit('open-folder')" @clone-git="handleOpenCloneGitModal"
              @new-task="assistantFacade.handleOpenAgentComposer" @open-composer="assistantFacade.handleOpenAgentComposer"
              @open-project="emit('select-project', $event)" @delete-project="emit('delete-project', $event)"
              @open-settings="editorFacade.openSettings('providers')" @open-terminal="toggleBottomDock()"
            />
          </div>

          <!-- Standalone Getting Started View -->
          <div v-else class="wb-getting-started-wrapper">
            <WelcomeView
              :projects="projects" :last-project="projects[0] || null" :active-project="null"
              @open-folder="emit('open-folder')" @clone-git="handleOpenCloneGitModal" @new-task="emit('open-folder')"
              @open-project="emit('select-project', $event)" @delete-project="emit('delete-project', $event)"
              @open-settings="editorFacade.openSettings('providers')"
            />
          </div>
        </div>

        <!-- Bottom Dock Splitter & Drawer -->
        <AppSplitter v-if="bottomDockOpen" direction="horizontal" v-model="dockHeight" :min="150" :max="400" :default-size="220" inverted />
        <AppBottomDrawer
          :open="bottomDockOpen" :height="dockHeight" :active-tab="dockActiveTab"
          :terminal-lines="dockFacade.effectiveTerminalLines.value" :output-lines="dockFacade.effectiveOutputLines.value"
          :editor-diagnostics="editorFacade.activeEditorDiagnostics.value" :problems="dockFacade.effectiveProblems.value"
          :terminal-running="dockFacade.terminalRunning.value" :project-id="activeProject?.id || ''"
          @update:open="bottomDockOpen = $event" @update:active-tab="dockActiveTab = $event"
          @clear="dockFacade.handleClearDock" @close="bottomDockOpen = false" @navigate-to-location="editorFacade.handleNavigateToLocation"
        />
      </main>

      <!-- Right Splitter & AI Assistant Drawer -->
      <AppSplitter v-if="tier === 'desktop' && assistantVisible" direction="vertical" v-model="assistantWidth" :min="320" :max="650" :default-size="380" inverted />
      <aside v-show="assistantVisible" class="wb-right-column" :style="tier !== 'mobile' ? { width: `${assistantWidth}px` } : {}">
        <AppRightDrawer
          :ref="(el) => { assistantFacade.rightDrawerRef.value = el }" v-model:active-tab="assistantTab"
          :task="task" :task-history="taskHistory" :task-tag="taskTag" :show-task-meta="showTaskMeta"
          :task-provider="assistantFacade.effectiveTaskProvider.value" :task-model="assistantFacade.effectiveTaskModel.value"
          :task-execution-label="taskExecutionLabel" :task-round-label="taskRoundLabel" :task-duration-label="taskDurationLabel"
          :task-timer-live="taskTimerLive" :show-task-telemetry="showTaskTelemetry" :task-llm-rounds="taskLlmRounds"
          :task-tool-calls="taskToolCalls" :task-tokens-label="taskTokensLabel" :task-tokens-tooltip="taskTokensTooltip"
          :lifecycle-steps="lifecycleSteps" :lifecycle-pct="lifecyclePct" :activity-phase="activityPhase"
          :activity-events="activityEvents" :show-reasoning="showReasoning" :activity-copied="activityCopied"
          :is-running="isRunning" :is-submitting="isSubmitting" :stop-in-progress="stopInProgress" :error="error"
          :consultant-props="assistantFacade.effectiveConsultantProps.value" :providers="assistantFacade.effectiveProviderList.value"
          :provider-instance-id="assistantFacade.effectiveProviderInstanceId.value" :model-id="assistantFacade.effectiveModelId.value"
          :mode="props.mode || props.config?.mode || 'balanced'" :active-tab-path="editorFacade.activeTabPath.value"
          :active-file="editorFacade.activeFile.value" @close="toggleAssistant(false)" @open-composer="assistantFacade.handleOpenAgentComposer"
          @request-stop="emit('request-stop')" @submit-task="emit('submit-task', $event)" @open-settings="emit('open-settings', $event)"
          @open-report="emit('open-report', $event)" @copy-activity="emit('copy-activity')"
          @run-consultant-task="assistantFacade.handleRunConsultantTask" @consultant-event="assistantFacade.handleConsultantEvent"
          @apply-to-editor="editorFacade.handleApplyToEditor" @update:provider-instance-id="emit('update:provider-instance-id', $event)"
          @update:model-id="emit('update:model-id', $event)" @update:mode="emit('update:mode', $event)"
          @update:active-session-id="assistantFacade.activeConsultantSessionId.value = $event"
        />
      </aside>
    </div>

    <!-- Confirm Close Modal -->
    <EditorConfirmCloseModal
      v-model="editorFacade.confirmCloseOpen.value" :closing-tab="editorFacade.closingTab.value"
      :closing-split-entirely="editorFacade.closingSplitEntirely.value" @confirm-save="editorFacade.handleConfirmCloseSave"
      @confirm-discard="editorFacade.handleConfirmCloseDiscard" @cancel="editorFacade.handleConfirmCloseCancel"
    />

    <!-- Clone Git Modal -->
    <AppModal v-if="cloneGitModalOpen" :model-value="cloneGitModalOpen" title="Clone Git Repository" max-width="480px" @close="cloneGitModalOpen = false">
      <div class="clone-git-dialog">
        <p class="clone-git-desc">Direct Git clone via UI is coming soon. Enter a remote Git repository URL below to generate and copy the clone command.</p>
        <div class="form-group">
          <label class="form-label" for="git-repo-url">Repository URL</label>
          <input id="git-repo-url" v-model="cloneGitUrl" type="text" class="form-control mono" placeholder="https://github.com/username/repository.git" :disabled="cloneGitBusy" @keydown.enter="handleCloneGitSubmit" />
        </div>
        <div v-if="cloneGitNotice" class="clone-git-notice">{{ cloneGitNotice }}</div>
        <div class="clone-git-actions">
          <button type="button" class="btn btn-ghost" :disabled="cloneGitBusy" @click="cloneGitModalOpen = false">Close</button>
          <button type="button" class="btn btn-primary" :disabled="!cloneGitUrl.trim() || cloneGitBusy" @click="handleCloneGitSubmit">
            <span>Copy Clone Command</span>
          </button>
        </div>
      </div>
    </AppModal>

    <!-- Floating Background Task Completion Toast -->
    <transition name="toast-slide">
      <div v-if="assistantFacade.bgToast.value" class="wb-bg-toast" :class="`toast-${assistantFacade.bgToast.value.type}`" role="alert">
        <div class="toast-dot" :class="`dot-${assistantFacade.bgToast.value.type}`"></div>
        <div class="toast-body">
          <div class="toast-title">{{ assistantFacade.bgToast.value.title }}</div>
          <div v-if="assistantFacade.bgToast.value.message" class="toast-msg">{{ assistantFacade.bgToast.value.message }}</div>
        </div>
        <div class="toast-actions">
          <button type="button" class="toast-btn-action" @click="assistantFacade.handleOpenToastAction">Open</button>
          <button type="button" class="toast-btn-dismiss" title="Dismiss notification" aria-label="Dismiss notification" @click="assistantFacade.bgToast.value = null">✕</button>
        </div>
      </div>
    </transition>
  </div>
</template>
