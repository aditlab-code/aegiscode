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

  function connectStream(customOnEvent) {
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
        if (typeof onEventHandler === "function") {
          onEventHandler(evt);
        }
      },
      onOpen: () => {
        sseStreamConnected.value = true;
      },
      onError: () => {
        sseStreamConnected.value = false;
      },
    });

    eventSource.onopen = () => {
      sseStreamConnected.value = true;
    };
    eventSource.onerror = () => {
      sseStreamConnected.value = false;
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
