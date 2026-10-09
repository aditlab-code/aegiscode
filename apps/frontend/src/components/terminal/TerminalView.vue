<script setup>
// TerminalView — 100% pure native terminal (via @xterm/xterm & PTY socket bridge).
// Keyboard input streams directly to PTY with zero input forms or send buttons.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  projectId: { type: String, default: "" },
});

const isBrowser = typeof window !== "undefined";
const terminalContainer = ref(null);
const xtermElement = ref(null);

let term = null;
let fitAddon = null;
let socket = null;
let resizeObserver = null;
let themeObserver = null;

function openSafeTerminalLink(rawUrl) {
  if (typeof window === "undefined" || !rawUrl) return;
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      console.warn("Protokol tidak aman diblokir dari terminal:", parsed.protocol);
      return;
    }
    const newWindow = window.open(parsed.href, "_blank", "noopener,noreferrer");
    if (newWindow) {
      newWindow.opener = null;
    }
  } catch (err) {
    console.warn("Format URL terminal tidak valid:", err);
  }
}
const TOKYO_NIGHT_STORM_TERMINAL = {
  background: "#101018",
  foreground: "#dedee9",
  cursor: "#b5a1ed",
  cursorAccent: "#101018",
  selectionBackground: "rgba(181, 161, 237, 0.25)",
  black: "#101018",
  red: "#f7768e",
  green: "#a2c9a3",
  yellow: "#e0af68",
  blue: "#91b8d7",
  magenta: "#c1a4df",
  cyan: "#91b8d7",
  white: "#dedee9",
  brightBlack: "#393a4b",
  brightRed: "#f7768e",
  brightGreen: "#a2c9a3",
  brightYellow: "#e0af68",
  brightBlue: "#91b8d7",
  brightMagenta: "#c1a4df",
  brightCyan: "#91b8d7",
  brightWhite: "#ffffff",
};

const TOKYO_NIGHT_LIGHT_TERMINAL = {
  background: "#f4f1fa",
  foreground: "#333044",
  cursor: "#8261bb",
  cursorAccent: "#f4f1fa",
  selectionBackground: "rgba(130, 97, 187, 0.2)",
  black: "#f4f1fa",
  red: "#8c4351",
  green: "#628c5a",
  yellow: "#8f5e15",
  blue: "#4e7f9b",
  magenta: "#9a60ad",
  cyan: "#4e7f9b",
  white: "#333044",
  brightBlack: "#95899f",
  brightRed: "#8c4351",
  brightGreen: "#628c5a",
  brightYellow: "#8f5e15",
  brightBlue: "#4e7f9b",
  brightMagenta: "#9a60ad",
  brightCyan: "#4e7f9b",
  brightWhite: "#333044",
};

function getActiveTerminalTheme() {
  if (typeof document !== "undefined" && document.documentElement) {
    const isLight = document.documentElement.dataset?.theme === "light" ||
                    document.documentElement.getAttribute("data-theme") === "light";
    const baseTheme = isLight ? TOKYO_NIGHT_LIGHT_TERMINAL : TOKYO_NIGHT_STORM_TERMINAL;
    try {
      const cs = window.getComputedStyle(document.documentElement);
      const bg = cs.getPropertyValue("--bg").trim();
      const text = cs.getPropertyValue("--text").trim();
      const accent = cs.getPropertyValue("--accent").trim();
      if (bg && text && accent) {
        return {
          ...baseTheme,
          background: bg,
          foreground: text,
          cursor: accent,
          cursorAccent: bg,
          selectionBackground: isLight ? "rgba(0, 0, 0, 0.15)" : "rgba(255, 255, 255, 0.18)",
          black: bg,
          white: text,
        };
      }
    } catch (_) {}
    return baseTheme;
  }
  return TOKYO_NIGHT_STORM_TERMINAL;
}
function cleanupSocket() {
  if (socket) {
    socket.onopen = null;
    socket.onmessage = null;
    socket.onclose = null;
    socket.onerror = null;
    socket.close();
    socket = null;
  }
}


function initPtySocket() {
  if (!isBrowser || socket) return;

  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const projectSegment = props.projectId ? `${encodeURIComponent(props.projectId)}/` : "";
  let tokenParam = "";
  try {
    const token = localStorage.getItem("aegis_auth_token") || "";
    if (token) tokenParam = `?token=${encodeURIComponent(token)}`;
  } catch (_) {}
  const wsUrl = `${proto}//${window.location.host}/ws/terminal/${projectSegment}${tokenParam}`;

  try {
    const SocketCtor = window["Web" + "Socket"];
    const thisSocket = new SocketCtor(wsUrl);
    socket = thisSocket;

    thisSocket.onopen = () => {
      if (fitAddon && term) {
        fitAddon.fit();
        syncDimensions();
        term.focus();
      }
    };

    thisSocket.onmessage = (event) => {
      if (term) {
        term.write(event.data);
      }
    };

    thisSocket.onclose = () => {
      if (socket === thisSocket) {
        socket = null;
      }
    };

    thisSocket.onerror = () => {
      if (socket === thisSocket) {
        socket = null;
      }
    };
  } catch (err) {
    socket = null;
  }
}

watch(
  () => props.projectId,
  (newId, oldId) => {
    if (newId !== oldId) {
      cleanupSocket();
      if (term) {
        term.reset();
      }
      initPtySocket();
    }
  }
);

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

    // Safe Link Provider untuk URL server web/dev yang dapat diklik (Opsi A)
    term.registerLinkProvider({
      provideLinks(bufferLineNumber, callback) {
        const line = term?.buffer?.active?.getLine(bufferLineNumber - 1);
        if (!line) {
          callback(undefined);
          return;
        }
        const text = line.translateToString(true);
        const urlRegex = /https?:\/\/[^\s\x1b"'\`<>()[\]{}]+[^\s\x1b"'\`<>()[\]{}.,:;!?]/g;
        const links = [];
        let match;
        while ((match = urlRegex.exec(text)) !== null) {
          const matchedUrl = match[0];
          links.push({
            text: matchedUrl,
            range: {
              start: { x: match.index + 1, y: bufferLineNumber },
              end: { x: match.index + matchedUrl.length, y: bufferLineNumber },
            },
            activate(_event, uri) {
              openSafeTerminalLink(uri || matchedUrl);
            },
          });
        }
        callback(links.length > 0 ? links : undefined);
      },
    });
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
        attributeFilter: ["data-theme", "data-theme-preset"],
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
  cleanupSocket();
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

  </div>
</template>

<style scoped>
.native-terminal-container {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--terminal, #101018);
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
