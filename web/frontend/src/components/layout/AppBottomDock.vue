<script setup>
import { ref, computed } from "vue";
import TerminalView from "../TerminalView.vue";
import AppBadge from "../ui/AppBadge.vue";
import { classifyDiagnostic, summarizeDiagnostics } from "../../services/diagnosticService.js";

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  height: {
    type: Number,
    default: 220,
  },
  activeTab: {
    type: String,
    default: "terminal",
    validator: (v) => ["terminal", "output", "problems"].includes(v),
  },
  terminalLines: {
    type: Array,
    default: () => [],
  },
  outputLines: {
    type: Array,
    default: () => [],
  },
  editorDiagnostics: {
    type: Array,
    default: () => [],
  },
  problems: {
    type: Array,
    default: () => [],
  },
  terminalRunning: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "update:open",
  "update:activeTab",
  "clear",
  "close",
  "run-command",
  "abort-command",
  "navigate-to-location",
]);

const activeFilter = ref("all");

const processedOutputItems = computed(() => {
  return (props.outputLines || []).map((line, idx) => classifyDiagnostic(line, idx));
});

const allDiagnostics = computed(() => {
  return [...processedOutputItems.value, ...(props.editorDiagnostics || [])];
});

const diagnosticsSummary = computed(() => {
  return summarizeDiagnostics(allDiagnostics.value);
});

const displayedOutputLines = computed(() => {
  if (activeFilter.value === "all") {
    return processedOutputItems.value;
  }
  return processedOutputItems.value.filter((item) => item.type === activeFilter.value);
});

const formattedProblems = computed(() => {
  return (props.problems || [])
    .map((prob, idx) => {
      if (!prob) return null;
      if (typeof prob === "object" && prob.label && prob.type) {
        return prob;
      }
      const rawText =
        typeof prob === "string" ? prob : prob.text || prob.message || JSON.stringify(prob);
      const parsed = classifyDiagnostic(rawText, idx);
      return {
        id: prob.id || parsed.id,
        text: rawText,
        type: prob.type || parsed.type || "error",
        severity: prob.severity || parsed.severity || "error",
        label: prob.label || parsed.label || "Error",
        file: prob.file || parsed.file || "",
        line: prob.line || parsed.line || null,
        col: prob.col || parsed.col || null,
        source: prob.source || "system",
      };
    })
    .filter(Boolean);
});

function handleLineClick(item) {
  if (item?.file && item?.line) {
    emit("navigate-to-location", {
      file: item.file,
      line: item.line,
      col: item.col || 1,
    });
  }
}

function setTab(tab) {
  if (props.open && props.activeTab === tab) {
    emit("update:open", false);
  } else {
    emit("update:activeTab", tab);
    if (!props.open) {
      emit("update:open", true);
    }
  }
}

function toggleOpen() {
  emit("update:open", !props.open);
}

function handleClear() {
  emit("clear", props.activeTab);
}

function handleClose() {
  emit("update:open", false);
  emit("close");
}
</script>

<template>
  <div
    class="app-bottom-dock"
    :class="{ open }"
    :style="open ? { height: height + 'px' } : { height: '32px' }"
    aria-label="Bottom Dock"
  >
    <!-- Dock Header Bar -->
    <div class="dock-header">
      <div class="dock-tabs" role="tablist">
        <!-- Tab 1: Terminal -->
        <button
          type="button"
          class="dock-tab-btn"
          :class="{ active: open && activeTab === 'terminal' }"
          role="tab"
          :aria-selected="open && activeTab === 'terminal'"
          @click="setTab('terminal')"
        >
          <svg
            class="dock-tab-ico"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <polyline points="4 17 10 11 4 5" />
            <line x1="12" y1="19" x2="20" y2="19" />
          </svg>
          <span>Terminal</span>
        </button>

        <!-- Tab 2: Output -->
        <button
          type="button"
          class="dock-tab-btn"
          :class="{ active: open && activeTab === 'output' }"
          role="tab"
          :aria-selected="open && activeTab === 'output'"
          @click="setTab('output')"
        >
          <svg
            class="dock-tab-ico"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <span>Output</span>
          <AppBadge v-if="diagnosticsSummary.total > 0" variant="count" class="dock-badge dock-badge-warn">
            {{ diagnosticsSummary.total }}
          </AppBadge>
        </button>

        <!-- Tab 3: Problems -->
        <button
          type="button"
          class="dock-tab-btn"
          :class="{ active: open && activeTab === 'problems' }"
          role="tab"
          :aria-selected="open && activeTab === 'problems'"
          @click="setTab('problems')"
        >
          <svg
            class="dock-tab-ico"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>Problems</span>
          <AppBadge v-if="problems.length > 0" variant="count" class="dock-badge">
            {{ problems.length }}
          </AppBadge>
        </button>
      </div>

      <!-- Dock Actions: Clear, Expand/Collapse & Close -->
      <div class="dock-actions">
        <button
          v-if="open"
          type="button"
          class="dock-act-btn"
          title="Clear"
          aria-label="Clear Output"
          @click="handleClear"
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
          </svg>
        </button>

        <button
          type="button"
          class="dock-act-btn"
          :title="open ? 'Collapse Dock' : 'Expand Dock'"
          :aria-label="open ? 'Collapse Dock' : 'Expand Dock'"
          @click="toggleOpen"
        >
          <svg
            v-if="!open"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <polyline points="18 15 12 9 6 15" />
          </svg>
          <svg
            v-else
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        <button
          type="button"
          class="dock-act-btn"
          title="Close Dock"
          aria-label="Close Dock"
          @click="handleClose"
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- Dock Content Body -->
    <div v-show="open" class="dock-body">
      <!-- 1. Terminal View -->
      <div v-if="activeTab === 'terminal'" class="dock-panel terminal-dock-panel">
        <TerminalView
          :lines="terminalLines"
          :running="terminalRunning"
          @run-command="emit('run-command', $event)"
          @abort-command="emit('abort-command')"
        />
      </div>

      <!-- 2. Output Stream -->
      <div v-else-if="activeTab === 'output'" class="dock-panel output-dock-panel">
        <!-- Diagnostic Summary Toolbar -->
        <div class="dock-output-toolbar">
          <div class="dock-toolbar-summary">
            <span class="dock-tb-title">Diagnostics:</span>
            <button
              type="button"
              class="dock-filter-pill"
              :class="{ active: activeFilter === 'all' }"
              @click="activeFilter = 'all'"
            >
              All ({{ processedOutputItems.length }})
            </button>
            <button
              v-if="diagnosticsSummary.syntax > 0"
              type="button"
              class="dock-filter-pill pill-syntax"
              :class="{ active: activeFilter === 'syntax' }"
              @click="activeFilter = activeFilter === 'syntax' ? 'all' : 'syntax'"
            >
              <span class="pill-dot dot-syntax">●</span>
              Syntax ({{ diagnosticsSummary.syntax }})
            </button>
            <button
              v-if="diagnosticsSummary.lint > 0"
              type="button"
              class="dock-filter-pill pill-lint"
              :class="{ active: activeFilter === 'lint' }"
              @click="activeFilter = activeFilter === 'lint' ? 'all' : 'lint'"
            >
              <span class="pill-dot dot-lint">▲</span>
              Lint ({{ diagnosticsSummary.lint }})
            </button>
            <button
              v-if="diagnosticsSummary.type > 0"
              type="button"
              class="dock-filter-pill pill-type"
              :class="{ active: activeFilter === 'type' }"
              @click="activeFilter = activeFilter === 'type' ? 'all' : 'type'"
            >
              <span class="pill-dot dot-type">●</span>
              Type ({{ diagnosticsSummary.type }})
            </button>
            <button
              v-if="diagnosticsSummary.error > 0"
              type="button"
              class="dock-filter-pill pill-error"
              :class="{ active: activeFilter === 'error' }"
              @click="activeFilter = activeFilter === 'error' ? 'all' : 'error'"
            >
              <span class="pill-dot dot-error">✖</span>
              Error ({{ diagnosticsSummary.error }})
            </button>
          </div>
          <div v-if="diagnosticsSummary.total === 0" class="dock-tb-clean">
            ✓ 0 issues detected
          </div>
        </div>

        <!-- Output Log Lines -->
        <div v-if="displayedOutputLines.length" class="dock-output-lines">
          <div
            v-for="(item, idx) in displayedOutputLines"
            :key="item.id || idx"
            class="dock-log-line"
            :class="[`line-${item.type}`, { clickable: item.file && item.line }]"
            @click="handleLineClick(item)"
          >
            <span v-if="item.type !== 'info'" class="dock-log-tag" :class="`tag-${item.type}`">
              [{{ item.label }}]
            </span>
            <span class="dock-log-text">{{ item.text }}</span>
            <span
              v-if="item.file && item.line"
              class="dock-log-loc"
              :title="`Jump to ${item.file}:${item.line}`"
            >
              {{ item.file }}:{{ item.line }}
            </span>
          </div>
        </div>
        <div v-else class="dock-empty">
          {{ activeFilter !== 'all' ? `No logs found for '${activeFilter}'.` : 'No output logs.' }}
        </div>
      </div>

      <!-- 3. Problems List -->
      <div v-else-if="activeTab === 'problems'" class="dock-panel problems-dock-panel">
        <div v-if="formattedProblems.length" class="dock-problems-list">
          <div
            v-for="(prob, idx) in formattedProblems"
            :key="prob.id || idx"
            class="dock-problem-row"
            :class="[`prob-${prob.type || 'error'}`, { clickable: prob.file && prob.line }]"
            @click="handleLineClick(prob)"
          >
            <!-- Severity Dot Indicator -->
            <span class="dock-prob-dot" :class="`dot-${prob.type || 'error'}`" aria-hidden="true">●</span>

            <!-- Problem Type Badge -->
            <span class="dock-prob-badge" :class="`badge-${prob.type || 'error'}`">
              [{{ prob.label || (prob.type === 'syntax' ? 'Syntax Error' : 'Error') }}]
            </span>

            <!-- Problem Text -->
            <span class="dock-prob-text">{{ prob.text }}</span>

            <!-- File Location -->
            <span
              v-if="prob.file && prob.line"
              class="dock-prob-loc"
              :title="`Jump to ${prob.file}:${prob.line}`"
            >
              {{ prob.file }}:{{ prob.line }}{{ prob.col ? `:${prob.col}` : '' }}
            </span>
          </div>
        </div>
        <div v-else class="dock-empty">No problems detected.</div>
      </div>
    </div>
  </div>
</template>
