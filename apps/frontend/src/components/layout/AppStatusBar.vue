<script setup>
import { computed, ref, onMounted } from "vue";
import { usePortDiscovery } from "../../services/portDiscoveryService.js";
import { useTelegramCompanion } from "../../services/telegramService.js";
import TelegramPairingPopover from "./TelegramPairingPopover.vue";

const { discoveredPorts, openPortSafely, removeDiscoveredPort } = usePortDiscovery();
const showTelegramPopover = ref(false);
const {
  status: telegramStatus,
  checkTelegramStatus,
  startTelegramPoller,
  stopTelegramPoller,
  isToggling,
  activeNotification,
  dismissTelegramNotification,
} = useTelegramCompanion();

let notificationTimer = null;

function triggerToastDismiss() {
  if (notificationTimer) clearTimeout(notificationTimer);
  notificationTimer = setTimeout(() => {
    dismissTelegramNotification();
  }, 3500);
}

async function handleTelegramToggle() {
  if (isToggling.value) return;

  // 1. Jika belum dikonfigurasi di .env -> buka modal edukasi instruksi
  if (!telegramStatus.value?.configured) {
    showTelegramPopover.value = true;
    return;
  }

  // 2. Jika sedang berjalan aktif -> matikan poller (toggle off), jangan buka modal
  if (telegramStatus.value?.is_running) {
    await stopTelegramPoller();
    triggerToastDismiss();
    return;
  }

  // 3. Jika standby & sudah terhubung (paired) -> nyalakan poller (toggle on), jangan buka modal
  if (telegramStatus.value?.is_paired) {
    await startTelegramPoller();
    triggerToastDismiss();
    return;
  }

  // 4. Jika standby & belum terhubung -> nyalakan poller (idle on pairing) & buka modal QR
  await startTelegramPoller();
  showTelegramPopover.value = true;
  triggerToastDismiss();
}

const telegramBadgeText = computed(() => {
  if (isToggling.value) return "Companion: ...";
  if (!telegramStatus.value?.configured) return "Companion: Off";
  if (!telegramStatus.value?.is_running) {
    return telegramStatus.value?.is_paired ? "Companion: Standby" : "Companion: Standby";
  }
  return telegramStatus.value?.is_paired ? "Companion: Active" : "Companion: Pairing";
});

const telegramBadgeTitle = computed(() => {
  if (!telegramStatus.value?.configured) {
    return "Telegram Companion Belum Dikonfigurasi (Klik untuk panduan setup BotFather & konfigurasi .env)";
  }
  if (telegramStatus.value?.is_running) {
    return telegramStatus.value?.is_paired
      ? "Telegram Companion Aktif Mendengarkan (Klik untuk mematikan bot)"
      : "Telegram Companion Menunggu Pairing (Klik untuk mematikan bot)";
  }
  return telegramStatus.value?.is_paired
    ? "Telegram Companion Standby (Klik untuk menyalakan bot langsung)"
    : "Telegram Companion Standby (Klik untuk membuka QR pairing & menyalakan bot)";
});

const telegramBadgeClass = computed(() => {
  if (!telegramStatus.value?.configured) return "badge-telegram-off";
  if (!telegramStatus.value?.is_running) return "badge-telegram-ready";
  return telegramStatus.value?.is_paired ? "badge-telegram-paired" : "badge-telegram-idle";
});

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
  connected: {
    type: Boolean,
    default: false,
  },
  gatewayAddress: {
    type: String,
    default: "",
  },
  aegisVersion: {
    type: String,
    default: "0.2.05",
  },
  gitBranchInfo: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["open-git"]);

onMounted(() => {
  checkTelegramStatus();
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

      <!-- Telegram Remote Companion Badge -->
      <button
        type="button"
        class="status-badge badge-telegram"
        :class="telegramBadgeClass"
        :title="telegramBadgeTitle"
        :disabled="isToggling"
        @click="handleTelegramToggle"
      >
        <span class="badge-dot">●</span>
        <span class="badge-text">{{ telegramBadgeText }}</span>
      </button>

      <!-- Status Bar Telegram Toast Notification -->
      <transition name="status-toast-fade">
        <div
          v-if="activeNotification"
          class="status-toast-pill"
          :class="`toast-${activeNotification.type}`"
          role="status"
        >
          <span class="status-toast-text">{{ activeNotification.message }}</span>
          <button
            type="button"
            class="status-toast-close"
            title="Tutup notifikasi"
            aria-label="Tutup notifikasi"
            @click="dismissTelegramNotification"
          >
            &times;
          </button>
        </div>
      </transition>

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

    <!-- Right Section: Cursor, Spaces, Encoding, Language, Version -->
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
.app-footer {
  position: relative;
}
.badge-telegram {
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  transition: all 0.15s ease;
}
.badge-telegram:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.badge-telegram:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--border-focus, rgba(255, 255, 255, 0.2));
}
.badge-telegram-paired .badge-dot {
  color: var(--ok);
}
.badge-telegram-idle .badge-dot {
  color: var(--warn);
}
.badge-telegram-ready .badge-dot {
  color: var(--accent);
}
.badge-telegram-off .badge-dot {
  color: var(--text-faint);
}

.status-toast-pill {
  position: absolute;
  bottom: 28px;
  left: 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 4px;
  background: var(--bg-surface);
  border: 1px solid var(--border-soft);
  color: var(--text);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  z-index: 1000;
  pointer-events: auto;
}
.status-toast-pill.toast-success {
  border-left: 3px solid var(--ok);
}
.status-toast-pill.toast-info {
  border-left: 3px solid var(--accent);
}
.status-toast-pill.toast-error {
  border-left: 3px solid var(--err);
}
.status-toast-close {
  background: transparent;
  border: none;
  color: var(--text-faint);
  cursor: pointer;
  padding: 0 2px;
  font-size: 13px;
  line-height: 1;
}
.status-toast-close:hover {
  color: var(--text);
}
.status-toast-fade-enter-active,
.status-toast-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.status-toast-fade-enter-from,
.status-toast-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>


