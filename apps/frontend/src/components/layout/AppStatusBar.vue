<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from "vue";
import { usePortDiscovery } from "../../services/portDiscoveryService.js";
import { useTelegramCompanion } from "../../services/telegramService.js";
import { getOperationalMode, setOperationalMode } from "../../api.js";
import TelegramPairingPopover from "./TelegramPairingPopover.vue";

const { discoveredPorts, openPortSafely, removeDiscoveredPort } = usePortDiscovery();
const showTelegramPopover = ref(false);
const { status: telegramStatus, checkTelegramStatus } = useTelegramCompanion();

const props = defineProps({
  cursor: {
    type: Object,
    default: () => ({ ln: 1, col: 1 }),
  },
  spaces: {
    type: Number,
    default: 2,
  },
  encoding: {
    type: String,
    default: "UTF-8",
  },
  language: {
    type: String,
    default: "",
  },
  modelLabel: {
    type: String,
    default: "",
  },
  providerLabel: {
    type: String,
    default: "",
  },
  taskStatus: {
    type: String,
    default: "idle",
  },
  connected: {
    type: Boolean,
    default: false,
  },
  gatewayAddress: {
    type: String,
    default: "",
  },
  agentStatus: {
    type: Object,
    default: () => ({ label: "idle", cls: "status-off" }),
  },
  aegisVersion: {
    type: String,
    default: "0.2.05",
  },
  bottomDockOpen: {
    type: Boolean,
    default: false,
  },
  activeDockTab: {
    type: String,
    default: "terminal",
  },
  problemsCount: {
    type: Number,
    default: 0,
  },
  tier: {
    type: String,
    default: "desktop",
    validator: (v) => ["desktop", "compact", "mobile"].includes(v),
  },
  gitBranchInfo: {
    type: Object,
    default: null,
  },
  operationalMode: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["toggle-dock", "open-git", "mode-changed"]);

const operationalMode = ref(props.operationalMode || "ask");
const isTogglingMode = ref(false);

watch(() => props.operationalMode, (newVal) => {
  if (newVal) {
    operationalMode.value = newVal;
  }
});

async function fetchMode() {
  try {
    const res = await getOperationalMode();
    if (res?.mode) {
      operationalMode.value = res.mode;
    }
  } catch (_) {
    // Graceful fallback to default
  }
}

async function toggleMode() {
  if (isTogglingMode.value) return;
  const nextMode = operationalMode.value === "agents" ? "ask" : "agents";
  isTogglingMode.value = true;
  try {
    const res = await setOperationalMode(nextMode);
    if (res?.mode) {
      operationalMode.value = res.mode;
    } else {
      operationalMode.value = nextMode;
    }
    emit("mode-changed", operationalMode.value);
  } catch (err) {
    console.error("Failed to toggle operational mode:", err);
  } finally {
    isTogglingMode.value = false;
  }
}

function onModeUpdatedEvent(e) {
  const modeVal = e.detail?.mode || e.detail?.data?.mode || e.detail?.payload?.mode || e.detail;
  if (typeof modeVal === "string" && ["ask", "agents"].includes(modeVal.toLowerCase())) {
    operationalMode.value = modeVal.toLowerCase();
  }
}

onMounted(() => {
  checkTelegramStatus();
  fetchMode();
  if (typeof window !== "undefined") {
    window.addEventListener("aegis:mode_updated", onModeUpdatedEvent);
  }
});

onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("aegis:mode_updated", onModeUpdatedEvent);
  }
});

const branchTooltip = computed(() => {
  if (!props.gitBranchInfo?.current) return "Git Source Control";
  const curr = props.gitBranchInfo.current;
  const up = props.gitBranchInfo.upstream;
  if (!up) return `On branch ${curr} (local only / no upstream). Click to open Source Control.`;
  const ahead = props.gitBranchInfo.ahead || 0;
  const behind = props.gitBranchInfo.behind || 0;
  return `On branch ${curr} -> tracking ${up} (${ahead} ahead, ${behind} behind). Click to open Source Control.`;
});
</script>

<template>
  <footer class="app-footer" aria-label="Statusbar">
    <!-- Left Section: Online, Agent, and Git Branch Badges -->
    <div class="footer-left">
      <!-- Active Git Branch Badge -->
      <button
        v-if="gitBranchInfo && gitBranchInfo.current"
        type="button"
        class="status-badge badge-git-branch"
        :title="branchTooltip"
        @click="emit('open-git')"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="6" y1="3" x2="6" y2="15"/>
          <circle cx="18" cy="6" r="3"/>
          <circle cx="6" cy="18" r="3"/>
          <path d="M18 9a9 9 0 0 1-9 9"/>
        </svg>
        <span class="badge-branch-name">{{ gitBranchInfo.current }}</span>
        <span v-if="gitBranchInfo.upstream" class="badge-sync-counts" :title="`Tracking ${gitBranchInfo.upstream}`">
          <span v-if="gitBranchInfo.ahead > 0" class="sync-ahead">↑{{ gitBranchInfo.ahead }}</span>
          <span v-if="gitBranchInfo.behind > 0" class="sync-behind">↓{{ gitBranchInfo.behind }}</span>
          <span v-if="gitBranchInfo.ahead === 0 && gitBranchInfo.behind === 0" class="sync-synced">✓</span>
        </span>
      </button>

      <!-- System Connection Badge -->
      <span
        class="status-badge"
        :class="connected ? 'badge-online' : 'badge-offline'"
        :title="connected ? (gatewayAddress ? `System Online (${gatewayAddress})` : 'System Online') : 'System Offline'"
      >
        <span class="badge-dot">●</span>
        <span class="badge-text">{{ connected ? "Online" : "Offline" }}</span>
      </span>

      <!-- Agent Status Badge -->
      <span
        class="status-badge badge-agent"
        :class="agentStatus?.cls || 'status-off'"
        title="Agent Status"
      >
        <span class="badge-dot">●</span>
        <span class="badge-text">Agent: {{ agentStatus?.label || "idle" }}</span>
      </span>

      <!-- Operational Mode Badge (Ask ⏸️ vs Agents ⚡) -->
      <button
        type="button"
        class="status-badge badge-operational-mode"
        :class="operationalMode === 'agents' ? 'badge-mode-agents' : 'badge-mode-ask'"
        :title="`Operational Mode: ${operationalMode === 'agents' ? 'Agents (Autonomous ⚡)' : 'Ask (HITL Confirmation ⏸️)'}. Klik untuk beralih mode.`"
        :disabled="isTogglingMode"
        @click="toggleMode"
      >
        <span class="badge-dot">●</span>
        <span class="badge-text">
          Mode: {{ operationalMode === 'agents' ? 'Agents ⚡' : 'Ask ⏸️' }}
        </span>
      </button>

      <!-- Telegram Remote Companion Badge -->
      <button
        type="button"
        class="status-badge badge-telegram"
        :class="telegramStatus?.is_paired ? 'badge-telegram-paired' : (telegramStatus?.configured ? 'badge-telegram-ready' : 'badge-telegram-off')"
        title="Telegram Remote Companion (Klik untuk pairing QR / status)"
        @click="showTelegramPopover = true"
      >
        <span class="badge-dot">●</span>
        <span class="badge-text">
          Companion: {{ telegramStatus?.is_paired ? 'Active' : (telegramStatus?.configured ? 'Pairing' : 'Off') }}
        </span>
      </button>

      <!-- Discovered Active Dev Ports Chips -->
      <div v-if="discoveredPorts.length > 0" class="status-ports-group">
        <button
          v-for="p in discoveredPorts"
          :key="p.port"
          type="button"
          class="status-badge badge-dev-port"
          :title="`Dev Server aktif di ${p.url}. Klik untuk membuka di peramban.`"
          @click="openPortSafely(p.url)"
        >
          <svg class="port-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
          <span class="badge-port-label">{{ p.label }}</span>
          <span
            class="port-dismiss-btn"
            title="Tutup chip port"
            @click.stop="removeDiscoveredPort(p.port)"
          >
            &times;
          </span>
        </button>
      </div>
    </div>

    <!-- Center Section: Open Source MIT Copyright License -->
    <div class="footer-center">
      <span class="status-item license-item" title="Open Source License">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
          <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
          <path d="M7 21h10"/>
          <path d="M12 3v18"/>
          <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
        </svg>
        <span>Open Source · MIT License</span>
      </span>
    </div>

    <!-- Right Section: Model, Provider, Version -->
    <div class="footer-right">
      <!-- Editor Position & Language Metadata -->
      <span v-if="cursor" class="status-item cursor-item" title="Line and Column">
        Ln {{ cursor.ln || 1 }}, Col {{ cursor.col || 1 }}
      </span>
      <span class="status-item spaces-item" title="Indentation">
        Spaces: {{ spaces }}
      </span>
      <span class="status-item encoding-item" title="File Encoding">
        {{ encoding }}
      </span>
      <span v-if="language" class="status-item lang-item" title="File Language">
        {{ language }}
      </span>
      <!-- Model Label -->
      <span v-if="modelLabel" class="status-item model-item" title="Active AI Model">
        {{ modelLabel }}
      </span>

      <!-- Provider Label (Desktop & Compact only) -->
      <span
        v-if="tier !== 'mobile' && providerLabel"
        class="status-item provider-item"
        title="Active AI Provider"
      >
        {{ providerLabel }}
      </span>

      <!-- AegisCode Version -->
      <span class="status-item version-item" title="AegisCode Version">
        v{{ aegisVersion }}
      </span>
    </div>
  </footer>

  <TelegramPairingPopover
    v-if="showTelegramPopover"
    @close="showTelegramPopover = false"
  />
</template>

<style scoped>
.badge-operational-mode {
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  transition: all 0.15s ease;
}
.badge-operational-mode:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--border-focus, rgba(255, 255, 255, 0.2));
}
.badge-mode-agents .badge-dot {
  color: #38bdf8;
}
.badge-mode-ask .badge-dot {
  color: var(--warn, #e5a00d);
}
</style>


