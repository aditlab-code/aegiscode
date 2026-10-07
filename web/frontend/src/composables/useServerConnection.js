/**
 * useServerConnection.js
 *
 * Mengelola status konektivitas HTTP gateway, koneksi aliran SSE (Server-Sent Events),
 * serta health monitor berkala gateway server.
 */
import { ref, computed } from "vue";
import { openEventStream } from "../api.js";
import { startServerHealthMonitor } from "../services/serverService.js";

export function useServerConnection(options = {}) {
  const gatewayHttpConnected = ref(false);
  const sseStreamConnected = ref(false);
  const connected = computed(() => gatewayHttpConnected.value && sseStreamConnected.value);
  const lastReceivedEventId = ref("");
  const lastReceivedSequence = ref(0);

  let eventSource = null;
  let stopHealthMonitor = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  const maxReconnectDelay = 10000;

  function calculateBackoffDelay(attempt) {
    const baseDelay = Math.min(1000 * Math.pow(2, attempt), maxReconnectDelay);
    return Math.floor(baseDelay * 0.5 + Math.random() * (baseDelay * 0.5));
  }

  function scheduleReconnect(customOnEvent) {
    if (reconnectTimer) return;
    // Exponential backoff dengan blended jitter (50% base + 50% randomized jitter)
    const delay = calculateBackoffDelay(reconnectAttempt);
    reconnectAttempt = Math.min(reconnectAttempt + 1, 10);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (gatewayHttpConnected.value && (!eventSource || eventSource.readyState === 2 || !sseStreamConnected.value)) {
        connectStream(customOnEvent);
      }
    }, delay);
  }

  function connectStream(customOnEvent) {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (eventSource) {
      try {
        eventSource.close();
      } catch (_) {}
      eventSource = null;
    }

    const onEventHandler = customOnEvent || options.onEvent;

    const handleStreamError = () => {
      sseStreamConnected.value = false;
      if (eventSource) {
        try {
          eventSource.close();
        } catch (_) {}
        eventSource = null;
      }
      scheduleReconnect(customOnEvent);
    };

    eventSource = openEventStream({
      lastEventId: lastReceivedEventId.value || null,
      onEvent: (evt) => {
        if (evt && typeof evt === "object") {
          const evtId = evt.lastEventId || evt.event_id || evt.id || (evt.sequence ? String(evt.sequence) : "");
          if (evtId) {
            lastReceivedEventId.value = String(evtId);
          }
          if (typeof evt.sequence === "number") {
            lastReceivedSequence.value = Math.max(lastReceivedSequence.value, evt.sequence);
          }
        }
        if (typeof onEventHandler === "function") {
          onEventHandler(evt);
        }
      },
      onOpen: () => {
        sseStreamConnected.value = true;
        reconnectAttempt = 0;
      },
      onError: handleStreamError,
    });

    eventSource.onopen = () => {
      sseStreamConnected.value = true;
      reconnectAttempt = 0;
    };
    eventSource.onerror = handleStreamError;
    return eventSource;
  }

  function startHealthCheck(intervalMs = 5000, customOnEvent) {
    if (stopHealthMonitor) {
      stopHealthMonitor();
      stopHealthMonitor = null;
    }
    stopHealthMonitor = startServerHealthMonitor((ok) => {
      gatewayHttpConnected.value = Boolean(ok);
      if (ok) {
        if (!eventSource || eventSource.readyState === 2 || !sseStreamConnected.value) {
          connectStream(customOnEvent);
        }
      } else {
        sseStreamConnected.value = false;
      }
    }, intervalMs);
    return stopHealthMonitor;
  }

  function closeConnection() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (stopHealthMonitor) {
      stopHealthMonitor();
      stopHealthMonitor = null;
    }
    if (eventSource) {
      try {
        eventSource.close();
      } catch (_) {}
      eventSource = null;
    }
    sseStreamConnected.value = false;
    reconnectAttempt = 0;
  }

  return {
    gatewayHttpConnected,
    sseStreamConnected,
    connected,
    lastReceivedEventId,
    lastReceivedSequence,
    connectStream,
    startHealthCheck,
    closeConnection,
    scheduleReconnect,
    calculateBackoffDelay,
    getReconnectAttempt: () => reconnectAttempt,
  };
}
