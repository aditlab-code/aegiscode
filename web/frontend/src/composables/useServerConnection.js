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

  let eventSource = null;
  let stopHealthMonitor = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  const maxReconnectDelay = 10000;

  function scheduleReconnect(customOnEvent) {
    if (reconnectTimer) return;
    // Exponential backoff: 1s, 2s, 4s, 8s, maks 10s
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), maxReconnectDelay);
    reconnectAttempt += 1;
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

    eventSource = openEventStream({
      lastEventId: lastReceivedEventId.value || null,
      onEvent: (evt) => {
        if (evt && typeof evt === "object") {
          const evtId = evt.lastEventId || evt.event_id || evt.id;
          if (evtId) {
            lastReceivedEventId.value = String(evtId);
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
      onError: () => {
        sseStreamConnected.value = false;
        scheduleReconnect(customOnEvent);
      },
    });

    eventSource.onopen = () => {
      sseStreamConnected.value = true;
      reconnectAttempt = 0;
    };
    eventSource.onerror = () => {
      sseStreamConnected.value = false;
      scheduleReconnect(customOnEvent);
    };
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
    connectStream,
    startHealthCheck,
    closeConnection,
  };
}
