/**
 * useConsultantSessions.js
 *
 * Logika manajemen multi-sesi Consultant (membuat, beralih sesi, menghapus sesi, dan mengubah nama sesi).
 */
import { ref, computed } from "vue";
import {
  listConsultantSessions,
  createConsultantSession,
  renameConsultantSession,
  deleteConsultantSession,
} from "../api.js";

export function useConsultantSessions({ projectId = null, initialSessionId = "", emit = null } = {}) {
  const sessionId = ref(initialSessionId);
  const sessions = ref([]);
  const sessionsLoading = ref(false);
  const switchingSession = ref(false);
  const sessionError = ref("");
  const renamingSessionId = ref(null);
  const renameInput = ref("");

  const activeSession = computed(() => {
    return sessions.value.find((s) => s.session_id === sessionId.value) || null;
  });

  const activeSessionTitle = computed(() => {
    return activeSession.value?.title || "New Chat";
  });

  async function loadSessions() {
    sessionsLoading.value = true;
    try {
      const pId = typeof projectId === "function" ? projectId() : (projectId?.value ?? projectId);
      const data = await listConsultantSessions(pId || null);
      sessions.value = data?.sessions || [];
      if (!sessionId.value && sessions.value.length > 0) {
        sessionId.value = sessions.value[0].session_id;
        if (emit) emit("update:activeSessionId", sessionId.value);
      }
    } catch (err) {
      sessionError.value = err.message || "Failed to load sessions.";
    } finally {
      sessionsLoading.value = false;
    }
  }

  async function createSession(title = null) {
    sessionError.value = "";
    try {
      const pId = typeof projectId === "function" ? projectId() : (projectId?.value ?? projectId);
      const sess = await createConsultantSession({
        projectId: pId || null,
        title,
      });
      sessionId.value = sess.session_id;
      if (emit) emit("update:activeSessionId", sess.session_id);
      await loadSessions();
      return sess;
    } catch (err) {
      sessionError.value = err.message || "Failed to create session.";
      throw err;
    }
  }

  async function removeSession(id) {
    try {
      const pId = typeof projectId === "function" ? projectId() : (projectId?.value ?? projectId);
      await deleteConsultantSession(id, pId || null);
      if (sessionId.value === id) {
        sessionId.value = "";
        if (emit) emit("update:activeSessionId", "");
      }
      await loadSessions();
    } catch (err) {
      sessionError.value = err.message || "Failed to delete session.";
      throw err;
    }
  }

  function startRename(session) {
    renamingSessionId.value = session.session_id;
    renameInput.value = session.title || "New Chat";
  }

  async function saveRename(id, explicitTitle = null) {
    const newTitle = (explicitTitle !== null ? explicitTitle : renameInput.value).trim();
    renamingSessionId.value = null;
    if (!newTitle || !id) return;
    try {
      const pId = typeof projectId === "function" ? projectId() : (projectId?.value ?? projectId);
      await renameConsultantSession(id, newTitle, pId || null);
      await loadSessions();
    } catch (err) {
      sessionError.value = err.message || "Failed to rename session.";
    }
  }

  function promptRenameActiveSession() {
    const current = activeSessionTitle.value;
    const newTitle = prompt("Rename conversation:", current);
    if (!newTitle || newTitle.trim() === "" || newTitle.trim() === current) return;
    saveRename(sessionId.value, newTitle.trim());
  }

  return {
    sessionId,
    sessions,
    sessionsLoading,
    switchingSession,
    sessionError,
    renamingSessionId,
    renameInput,
    activeSession,
    activeSessionTitle,
    loadSessions,
    createSession,
    removeSession,
    startRename,
    saveRename,
    promptRenameActiveSession,
  };
}
