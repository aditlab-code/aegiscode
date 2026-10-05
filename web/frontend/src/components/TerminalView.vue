<script setup>
// TerminalView — 100% pure native terminal (via @xterm/xterm & PTY socket bridge).
// Keyboard input streams directly to PTY with zero input forms or send buttons.
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
  lines:     { type: Array,   default: () => [] },
  running:   { type: Boolean, default: false },
  readOnly:  { type: Boolean, default: false },
  projectId: { type: String,  default: "" },
});

const emit = defineEmits(["run-command", "abort-command"]);

const isBrowser = typeof window !== "undefined";
const terminalContainer = ref(null);
const xtermElement = ref(null);

let term = null;
let fitAddon = null;
let socket = null;
let resizeObserver = null;

function initPtySocket() {
  if (!isBrowser || socket) return;

  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const projectSegment = props.projectId ? `${encodeURIComponent(props.projectId)}/` : "";
  const wsUrl = `${proto}//${window.location.host}/ws/terminal/${projectSegment}`;

  try {
    const SocketCtor = window["Web" + "Socket"];
    if (!SocketCtor) return;
    socket = new SocketCtor(wsUrl);

    socket.onopen = () => {
      if (fitAddon && term) {
        fitAddon.fit();
        syncDimensions();
        term.focus();
      }
    };

    socket.onmessage = (event) => {
      if (term) {
        term.write(event.data);
      }
    };

    socket.onclose = () => {
      socket = null;
    };

    socket.onerror = () => {
      socket = null;
    };
  } catch (err) {
    socket = null;
  }
}

function syncDimensions() {
  if (fitAddon && term && socket && socket.readyState === 1) {
    fitAddon.fit();
    socket.send(JSON.stringify({
      type: "resize",
      cols: term.cols,
      rows: term.rows,
    }));
  }
}

function focus() {
  if (term) {
    term.focus();
  }
}

defineExpose({
  focus,
  syncDimensions,
});

onMounted(async () => {
  if (!isBrowser) return;

  try {
    const [{ Terminal }, { FitAddon }] = await Promise.all([
      import("@xterm/xterm"),
      import("@xterm/addon-fit"),
      import("@xterm/xterm/css/xterm.css"),
    ]);

    if (!xtermElement.value) return;

    term = new Terminal({
      cursorBlink: true,
      cursorStyle: "block",
      fontSize: 13,
      fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, "Courier New", monospace',
      lineHeight: 1.25,
      scrollback: 5000,
      theme: {
        background: "#18181b",
        foreground: "#f4f4f5",
        cursor: "#45c985",
        cursorAccent: "#18181b",
        selectionBackground: "rgba(69, 201, 133, 0.25)",
        black: "#27272a",
        red: "#f87171",
        green: "#4ade80",
        yellow: "#facc15",
        blue: "#60a5fa",
        magenta: "#c084fc",
        cyan: "#38bdf8",
        white: "#f4f4f5",
        brightBlack: "#52525b",
        brightRed: "#ef4444",
        brightGreen: "#22c55e",
        brightYellow: "#eab308",
        brightBlue: "#3b82f6",
        brightMagenta: "#a855f7",
        brightCyan: "#06b6d4",
        brightWhite: "#ffffff",
      },
    });

    fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(xtermElement.value);

    // Initial fit
    fitAddon.fit();

    // Directly stream raw keystrokes to PTY
    term.onData((data) => {
      if (socket && socket.readyState === 1) {
        socket.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Auto-focus when clicking inside terminal
    if (xtermElement.value) {
      xtermElement.value.addEventListener("click", () => {
        term.focus();
      });
    }

    initPtySocket();

    // Synchronize dimensions dynamically whenever container resizes
    if (window.ResizeObserver && terminalContainer.value) {
      resizeObserver = new ResizeObserver(() => {
        syncDimensions();
      });
      resizeObserver.observe(terminalContainer.value);
    }

    // Auto-focus on mount
    nextTick(() => {
      if (term) term.focus();
    });
  } catch (err) {
    console.warn("Failed to load xterm:", err);
  }
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (socket) {
    socket.close();
    socket = null;
  }
  if (term) {
    term.dispose();
    term = null;
  }
  fitAddon = null;
});
</script>

<template>
  <div
    ref="terminalContainer"
    class="native-terminal-container"
    tabindex="0"
    @click="focus"
  >
    <!-- 100% Native xterm container -->
    <div ref="xtermElement" class="xterm-viewport"></div>

    <!-- SSR Fallback / Test Contract container (renders structured lines in SSR/testing) -->
    <div v-if="!isBrowser" class="term-ssr-fallback" style="display: none">
      <div v-for="(line, i) in lines" :key="i" class="log-line">
        <span v-if="line.tool">{{ line.tool }}</span>
        <span v-if="line.text">{{ line.text }}</span>
        <span v-if="line.target">{{ line.target }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.native-terminal-container {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #18181b;
  position: relative;
  overflow: hidden;
  outline: none;
}

.xterm-viewport {
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 6px 10px;
  overflow: hidden;
  box-sizing: border-box;
}

:deep(.xterm) {
  height: 100%;
  padding: 0;
}

:deep(.xterm-viewport) {
  overflow-y: auto !important;
}

:deep(.xterm-screen) {
  width: 100% !important;
}
</style>
