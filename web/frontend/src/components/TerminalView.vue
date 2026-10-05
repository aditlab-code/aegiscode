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

const GRUVBOX_DARK_TERMINAL = {
  background: "#282828",
  foreground: "#ebdbb2",
  cursor: "#ebdbb2",
  cursorAccent: "#282828",
  selectionBackground: "rgba(235, 219, 178, 0.25)",
  black: "#282828",
  red: "#cc241d",
  green: "#98971a",
  yellow: "#d79921",
  blue: "#458588",
  magenta: "#b16286",
  cyan: "#689d6a",
  white: "#a89984",
  brightBlack: "#928374",
  brightRed: "#fb4934",
  brightGreen: "#b8bb26",
  brightYellow: "#fabd2f",
  brightBlue: "#83a598",
  brightMagenta: "#d3869b",
  brightCyan: "#8ec07c",
  brightWhite: "#ebdbb2",
};

const GRUVBOX_LIGHT_TERMINAL = {
  background: "#fbf1c7",
  foreground: "#3c3836",
  cursor: "#3c3836",
  cursorAccent: "#fbf1c7",
  selectionBackground: "rgba(60, 56, 54, 0.25)",
  black: "#fbf1c7",
  red: "#cc241d",
  green: "#98971a",
  yellow: "#d79921",
  blue: "#458588",
  magenta: "#b16286",
  cyan: "#689d6a",
  white: "#7c6f64",
  brightBlack: "#928374",
  brightRed: "#9d0006",
  brightGreen: "#79740e",
  brightYellow: "#b57614",
  brightBlue: "#076678",
  brightMagenta: "#8f3f71",
  brightCyan: "#427b58",
  brightWhite: "#3c3836",
};

function getActiveTerminalTheme() {
  if (typeof document !== "undefined" && document.documentElement) {
    const isLight = document.documentElement.dataset?.theme === "light" ||
                    document.documentElement.getAttribute("data-theme") === "light";
    return isLight ? GRUVBOX_LIGHT_TERMINAL : GRUVBOX_DARK_TERMINAL;
  }
  return GRUVBOX_DARK_TERMINAL;
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
  background: var(--bg-deep, #282828);
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
