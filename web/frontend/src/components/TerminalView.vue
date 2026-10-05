<script setup>
// TerminalView — agent output viewer + interactive shell input.
// Keyboard shortcuts:
//   Ctrl+C          → abort running command (emit abort-command)
//   Ctrl+Shift+C    → copy selected text in output area
//   Ctrl+Shift+V    → paste clipboard text into input field
//   ↑ / ↓           → command history navigation
import { computed, nextTick, ref, watch } from "vue";

const MAX_ENTRIES = 200;
const MAX_HISTORY = 50;

const props = defineProps({
  lines:    { type: Array,   default: () => [] },
  running:  { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
});

const emit = defineEmits(["run-command", "abort-command"]);

// --- refs -------------------------------------------------------------------
const wrapEl   = ref(null);   // .term-wrap (keyboard listener target)
const scroller = ref(null);   // .term-body scroll container
const inputEl  = ref(null);   // <input> field ref
const copyFlash = ref(false); // brief flash on copy button

// --- output -----------------------------------------------------------------
const visibleLines = computed(() => props.lines.slice(-MAX_ENTRIES));

function lineClass(line) {
  if (line.kind === "call")   return "run";
  if (line.kind === "result") return line.success ? "ok" : "err";
  if (line.kind === "input")  return "inp";
  return "warn";
}

async function scrollToLatest() {
  await nextTick();
  const el = scroller.value;
  if (el) el.scrollTop = el.scrollHeight;
}
watch(visibleLines, scrollToLatest, { flush: "post" });

// --- input / history --------------------------------------------------------
const inputValue = ref("");
const history    = ref([]);
const histIdx    = ref(-1);

function navigateHistory(dir) {
  const len = history.value.length;
  if (!len) return;
  const next = histIdx.value + dir;
  if (next < 0) {
    histIdx.value = -1;
    inputValue.value = "";
    return;
  }
  if (next >= len) return;
  histIdx.value = next;
  inputValue.value = history.value[len - 1 - next];
}

function submitCommand() {
  const cmd = inputValue.value.trim();
  if (!cmd || props.running) return;
  if (history.value[history.value.length - 1] !== cmd) {
    history.value.push(cmd);
    if (history.value.length > MAX_HISTORY) history.value.shift();
  }
  histIdx.value = -1;
  inputValue.value = "";
  emit("run-command", cmd);
}

// --- keyboard shortcuts -----------------------------------------------------

// Handle keys from the input field (Enter / ↑ / ↓ / Ctrl+C while running)
function onInputKeyDown(e) {
  // Ctrl+C while running → abort (prevent browser copy)
  if (e.ctrlKey && !e.shiftKey && e.key === "c" && props.running) {
    e.preventDefault();
    abortCommand();
    return;
  }
  if (e.key === "Enter") {
    submitCommand();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    navigateHistory(1);
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    navigateHistory(-1);
  }
}

// Handle keys on the outer .term-wrap wrapper (captures shortcuts not in input)
function onWrapKeyDown(e) {
  // Ctrl+C while running (focus anywhere in terminal) → abort
  if (e.ctrlKey && !e.shiftKey && e.key === "c" && props.running) {
    e.preventDefault();
    abortCommand();
    return;
  }
  // Ctrl+Shift+C → copy selected text
  if (e.ctrlKey && e.shiftKey && e.key === "C") {
    e.preventDefault();
    copySelected();
    return;
  }
  // Ctrl+Shift+V → paste clipboard into input
  if (e.ctrlKey && e.shiftKey && e.key === "V") {
    e.preventDefault();
    pasteToInput();
    return;
  }
}

function abortCommand() {
  emit("abort-command");
}

async function copySelected() {
  const sel = window.getSelection?.();
  const text = sel ? sel.toString() : "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copyFlash.value = true;
    setTimeout(() => { copyFlash.value = false; }, 600);
  } catch {
    // Clipboard API not available — silently ignore
  }
}

async function pasteToInput() {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      inputValue.value += text;
      await nextTick();
      inputEl.value?.focus();
    }
  } catch {
    // Permission denied or API not available — silently ignore
  }
}
</script>

<template>
  <div
    ref="wrapEl"
    class="term-wrap"
    tabindex="0"
    @keydown="onWrapKeyDown"
  >
    <!-- Output area -->
    <div ref="scroller" class="term-body">
      <div
        v-for="(line, i) in visibleLines"
        :key="i"
        class="log-line"
        :class="lineClass(line)"
      >
        <!-- User input echo -->
        <template v-if="line.kind === 'input'">
          <span class="msg"><span class="term-prompt">$</span> {{ line.text }}</span>
        </template>
        <!-- Tool call -->
        <template v-else-if="line.kind === 'call'">
          <span class="msg"
            ><span class="fn">{{ line.tool }}</span
            ><template v-if="line.target"> {{ line.target }}</template></span
          >
        </template>
        <!-- Tool result -->
        <template v-else-if="line.kind === 'result'">
          <span class="msg"
            >{{ line.success ? "✓" : "✗" }} {{ line.target || line.tool
            }}<template v-if="!line.success && line.error"> — {{ line.error }}</template></span
          >
        </template>
        <!-- Plain text output -->
        <template v-else>
          <span class="msg">{{ line.text }}</span>
        </template>
      </div>
      <div v-if="!visibleLines.length" class="dock-empty">No terminal output yet.</div>
    </div>

    <!-- Input row -->
    <div v-if="!readOnly" class="term-input-row" :class="{ busy: running }">
      <span class="term-prompt">$</span>
      <input
        ref="inputEl"
        class="term-input"
        type="text"
        v-model="inputValue"
        :placeholder="running ? 'Running… (Ctrl+C to abort)' : 'Enter command…'"
        :disabled="running"
        autocomplete="off"
        autocorrect="off"
        spellcheck="false"
        @keydown="onInputKeyDown"
      />
      <!-- Abort button (visible while running) -->
      <button
        v-if="running"
        class="term-send-btn term-abort-btn"
        type="button"
        title="Abort (Ctrl+C)"
        aria-label="Abort command"
        @click="abortCommand"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
          stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
        </svg>
      </button>
      <!-- Send button (visible while idle) -->
      <button
        v-else
        class="term-send-btn"
        :class="{ copied: copyFlash }"
        type="button"
        :disabled="!inputValue.trim()"
        title="Run (Enter)"
        aria-label="Run command"
        @click="submitCommand"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round"
          stroke-linejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
  </div>
</template>
