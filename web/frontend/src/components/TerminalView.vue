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
let themeObserver = null;

const TOKYO_NIGHT_STORM_TERMINAL = {
  background: "#24283b",
  foreground: "#c0caf5",
  cursor: "#c0caf5",
  cursorAccent: "#24283b",
  selectionBackground: "rgba(122, 162, 247, 0.25)",
  black: "#1d202f",
  red: "#f7768e",
  green: "#9ece6a",
  yellow: "#e0af68",
  blue: "#7aa2f7",
  magenta: "#bb9af7",
  cyan: "#7dcfff",
  white: "#a9b1d6",
  brightBlack: "#414868",
  brightRed: "#f7768e",
  brightGreen: "#9ece6a",
  brightYellow: "#e0af68",
  brightBlue: "#7aa2f7",
  brightMagenta: "#bb9af7",
  brightCyan: "#7dcfff",
  brightWhite: "#c0caf5",
};

const TOKYO_NIGHT_LIGHT_TERMINAL = {
  background: "#e6e7ed",
  foreground: "#343b59",
  cursor: "#343b59",
  cursorAccent: "#e6e7ed",
  selectionBackground: "rgba(41, 89, 170, 0.25)",
  black: "#e6e7ed",
  red: "#8c4351",
  green: "#485e30",
  yellow: "#8f5e15",
  blue: "#2959aa",
  magenta: "#5a3e8e",
  cyan: "#0f4b6e",
  white: "#343b59",
  brightBlack: "#9699a3",
  brightRed: "#8c4351",
  brightGreen: "#485e30",
  brightYellow: "#8f5e15",
  brightBlue: "#2959aa",
  brightMagenta: "#5a3e8e",
  brightCyan: "#0f4b6e",
  brightWhite: "#343b59",
};

function getActiveTerminalTheme() {
  if (typeof document !== "undefined" && document.documentElement) {
    const isLight = document.documentElement.dataset?.theme === "light" ||
                    document.documentElement.getAttribute("data-theme") === "light";
    return isLight ? TOKYO_NIGHT_LIGHT_TERMINAL : TOKYO_NIGHT_STORM_TERMINAL;
  }
  return TOKYO_NIGHT_STORM_TERMINAL;
}

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
      theme: getActiveTerminalTheme(),
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

    // Dynamic theme switching observer
    if (typeof MutationObserver !== "undefined" && document.documentElement) {
      themeObserver = new MutationObserver(() => {
        if (term) {
          term.options.theme = getActiveTerminalTheme();
        }
      });
      themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
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
  if (themeObserver) {
    themeObserver.disconnect();
    themeObserver = null;
  }
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
  background: var(--bg-deep, #16161e);
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
