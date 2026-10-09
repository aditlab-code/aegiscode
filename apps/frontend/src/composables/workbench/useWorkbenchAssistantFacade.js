/**
 * useWorkbenchAssistantFacade.js
 *
 * Facade composable mengelola state asisten AI (Agent Drawer & Consultant Chat),
 * penanganan sesi konsultasi, delegasi task proposal, notifikasi floating toast,
 * dan kalkulasi provider/model aktif.
 */
import { ref, computed, watch, nextTick } from "vue";

export function useWorkbenchAssistantFacade(props, emit, options = {}) {
  const {
    assistantTab,
    assistantVisible,
    toggleAssistant,
    activeTab,
  } = options;

  const activeConsultantSessionId = ref("");
  const consultantBusy = ref(false);
  const bgToast = ref(null);
  let bgToastTimer = null;
  const rightDrawerRef = ref(null);

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
    if (bgToast.value?.tab && assistantTab) {
      assistantTab.value = bgToast.value.tab;
    }
    if (assistantVisible && !assistantVisible.value && toggleAssistant) {
      toggleAssistant(true);
    }
    bgToast.value = null;
  }

  function handleOpenConsultantSession(sessionId) {
    if (assistantTab) assistantTab.value = "consultant";
    if (assistantVisible && !assistantVisible.value && toggleAssistant) {
      toggleAssistant(true);
    }
    activeConsultantSessionId.value = sessionId || "";
    emit("open-session", sessionId);
    emit("open-consultant-session", sessionId);
  }

  function handleRunConsultantTask(taskPayload) {
    if (assistantTab) assistantTab.value = "agents";
    emit("run-consultant-task", taskPayload);
  }

  function handleOpenAgentComposer() {
    if (assistantTab) assistantTab.value = "agents";
    if (assistantVisible && !assistantVisible.value && toggleAssistant) {
      toggleAssistant(true);
    }
    nextTick(() => {
      rightDrawerRef.value?.focusPrompt?.();
      if (typeof document !== "undefined") {
        const ta = document.querySelector(".chat-prompt-textarea");
        if (ta) ta.focus();
      }
    });
  }

  function handleConsultantEvent(event) {
    if (event?.type === "sending_started") {
      consultantBusy.value = true;
    } else if (event?.type === "sending_completed") {
      consultantBusy.value = false;
      if (assistantVisible && !assistantVisible.value) {
        showBgToast({
          type: event.error ? "error" : "success",
          title: event.error ? "Consultant Error" : "Consultant Response Ready",
          message:
            event.error ||
            (event.prompt
              ? event.prompt.length > 40
                ? event.prompt.slice(0, 40) + "…"
                : event.prompt
              : "New analysis available"),
          tab: "consultant",
        });
      }
    }
    emit("consultant-event", event);
  }

  // Watch background task completion for floating notification toast
  watch(
    () => props.isRunning,
    (running, prevRunning) => {
      if (prevRunning && !running) {
        if (assistantVisible && !assistantVisible.value) {
          const isCompleted = props.task?.status === "completed";
          const promptPreview = props.task?.prompt
            ? props.task.prompt.length > 40
              ? props.task.prompt.slice(0, 40) + "…"
              : props.task.prompt
            : "";
          showBgToast({
            type: isCompleted ? "success" : "warning",
            title: isCompleted
              ? "Task Completed"
              : `Task ${props.task?.status || "Finished"}`,
            message: promptPreview,
            tab: "agents",
          });
        }
      }
    }
  );

  const effectiveProviderList = computed(() => {
    return props.providers?.length
      ? props.providers
      : props.config?.provider_instances || [];
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
    return m ? m.model_name : props.config?.model || "";
  });

  const effectiveConsultantProps = computed(() => {
    const base = props.consultantProps || {};
    const cur = activeTab ? activeTab.value : null;
    return {
      ...base,
      activeSessionId:
        activeConsultantSessionId.value || base.activeSessionId || "",
      providers: base.providers?.length
        ? base.providers
        : effectiveProviderList.value,
      providerInstanceId:
        base.providerInstanceId || effectiveProviderInstanceId.value,
      modelId: base.modelId || effectiveModelId.value,
      projectId: base.projectId || props.activeProject?.id || "",
      running:
        typeof base.running === "boolean" ? base.running : props.isRunning,
      runningTaskId:
        props.runningTaskId || base.runningTaskId || props.task?.id || "",
      providerLabel: effectiveTaskProvider.value,
      modelLabel: effectiveTaskModel.value,
      activeTabPath: cur ? cur.path : "",
      activeFile: cur
        ? {
            path: cur.path,
            content: cur.content || null,
          }
        : null,
    };
  });

  return {
    activeConsultantSessionId,
    consultantBusy,
    bgToast,
    rightDrawerRef,
    showBgToast,
    handleOpenToastAction,
    handleOpenConsultantSession,
    handleRunConsultantTask,
    handleOpenAgentComposer,
    handleConsultantEvent,
    effectiveProviderList,
    effectiveProviderInstanceId,
    effectiveModelId,
    activeProviderInstance,
    effectiveTaskProvider,
    effectiveTaskModel,
    effectiveConsultantProps,
  };
}
