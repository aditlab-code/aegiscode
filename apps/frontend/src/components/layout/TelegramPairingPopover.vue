<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { useTelegramCompanion } from "../../services/telegramService.js";

const emit = defineEmits(["close"]);
const {
  status,
  qrData,
  loading,
  error,
  checkTelegramStatus,
  fetchTelegramPairingQr,
  unlinkTelegramUser,
} = useTelegramCompanion();

let pollInterval = null;

onMounted(async () => {
  await checkTelegramStatus();
  if (status.value.configured && !status.value.is_paired) {
    await fetchTelegramPairingQr();
  }

  // Polling setiap 3 detik untuk deteksi pairing otomatis jika sedang menunggu scan
  pollInterval = setInterval(async () => {
    if (status.value.configured && !status.value.is_paired) {
      const prev = status.value.is_paired;
      await checkTelegramStatus();
      if (!prev && status.value.is_paired) {
        // Otomatis terhubung!
      }
    }
  }, 3000);
});

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});

const showQrWhenPaired = ref(false);

async function toggleShowQr() {
  showQrWhenPaired.value = !showQrWhenPaired.value;
  if (showQrWhenPaired.value && !qrData.value?.qr_svg) {
    await fetchTelegramPairingQr();
  }
}

async function handleRefreshQr() {
  await fetchTelegramPairingQr();
}

async function handleUnlink() {
  if (confirm("Apakah Anda yakin ingin memutuskan hubungan akun Telegram ini?")) {
    await unlinkTelegramUser();
    if (status.value.configured) {
      await fetchTelegramPairingQr();
    }
  }
}
</script>

<template>
  <div class="telegram-popover-overlay" @click.self="emit('close')">
    <div class="telegram-popover-card" role="dialog" aria-modal="true" aria-label="Telegram Remote Companion">
      <div class="popover-header">
        <div class="header-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="telegram-icon">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <h3>Telegram Remote Companion</h3>
        </div>
        <button type="button" class="close-btn" @click="emit('close')" aria-label="Tutup">&times;</button>
      </div>

      <div class="popover-body">
        <!-- Error Banner -->
        <div v-if="error" class="alert-banner error-banner">
          {{ error }}
        </div>

        <!-- 1. Kondisi: Token Belum Dikonfigurasi di .env -->
        <div v-if="!status.configured" class="state-container state-unconfigured">
          <div class="status-icon-bubble warning">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <h4>Bot Token Belum Diatur</h4>
          <p>
            Untuk mengaktifkan pendamping jarak jauh, buat bot di <b>@BotFather</b> lalu tambahkan ke <code>.env</code>:
          </p>
          <pre class="env-snippet">TELEGRAM_BOT_TOKEN="your_bot_token_here"</pre>
        </div>

        <!-- 2. Kondisi: Akun Sudah Terhubung (Paired) -->
        <div v-else-if="status.is_paired" class="state-container state-paired">
          <div class="status-icon-bubble success">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <h4>Perangkat Terhubung</h4>
          <p class="connected-info">
            Akun Telegram: <b>@{{ status.paired_user?.username || status.paired_user?.first_name || status.paired_user?.user_id }}</b>
          </p>

          <div class="poller-status-chip" :class="status.is_running ? 'status-chip-active' : 'status-chip-standby'">
            <span class="chip-dot">●</span>
            <span>{{ status.is_running ? "Poller Aktif (Mendengarkan)" : "Poller Standby" }}</span>
          </div>

          <p class="description">
            Ponsel Anda akan bergetar dan menerima pesan saat agen membutuhkan keputusan persetujuan (*Human-in-the-Loop*).
          </p>

          <div class="paired-actions-row">
            <button
              type="button"
              class="btn btn-secondary btn-inner"
              :disabled="loading"
              @click="toggleShowQr"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="3" width="7" height="7"/>
                <rect x="14" y="3" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/>
                <rect x="3" y="14" width="7" height="7"/>
              </svg>
              <span>{{ showQrWhenPaired ? "Sembunyikan QR Pairing" : "Tampilkan QR Code Pairing" }}</span>
            </button>
            <button type="button" class="btn btn-danger btn-unlink" :disabled="loading" @click="handleUnlink">
              Putuskan Hubungan
            </button>
          </div>

          <!-- Drawer QR Code saat akun terhubung -->
          <div v-if="showQrWhenPaired" class="paired-qr-drawer">
            <p class="qr-instructions">
              Pindai QR code ini untuk menghubungkan akun Telegram lain atau memperbarui sesi:
            </p>
            <div class="qr-display-box">
              <div v-if="loading" class="qr-loading">Memuat QR Code...</div>
              <div v-else-if="qrData.qr_svg" class="qr-svg-holder" v-html="qrData.qr_svg"></div>
            </div>

            <div v-if="qrData.deep_link" class="actions-group">
              <a :href="qrData.deep_link" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-inner">
                <span>Buka di Telegram</span>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                  <polyline points="15 3 21 3 21 9"/>
                  <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
              <button type="button" class="btn btn-secondary" :disabled="loading" @click="handleRefreshQr">
                Perbarui QR
              </button>
            </div>
          </div>
        </div>

        <!-- 3. Kondisi: Siap Pairing (Menampilkan QR Code) -->
        <div v-else class="state-container state-pairing">
          <p class="qr-instructions">
            Pindai QR code ini dengan kamera ponsel untuk menghubungkan akun Telegram Anda secara instan:
          </p>

          <div class="qr-display-box">
            <div v-if="loading" class="qr-loading">Memuat QR Code...</div>
            <div v-else-if="qrData.qr_svg" class="qr-svg-holder" v-html="qrData.qr_svg"></div>
          </div>

          <div v-if="qrData.deep_link" class="actions-group">
            <a :href="qrData.deep_link" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-inner">
              <span>Buka di Telegram</span>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </a>
            <button type="button" class="btn btn-secondary" :disabled="loading" @click="handleRefreshQr">
              Perbarui QR
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.telegram-popover-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.telegram-popover-card {
  width: 90%;
  max-width: 420px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.12));
  border-radius: 12px;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  color: var(--text);
  font-family: inherit;
}

.popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  background: var(--bg-elevated, rgba(255, 255, 255, 0.03));
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.telegram-icon {
  color: var(--accent);
}

.close-btn {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
}

.close-btn:hover {
  color: var(--text);
}

.popover-body {
  padding: 20px;
}

.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.status-icon-bubble {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-bottom: 12px;
}

.status-icon-bubble.warning {
  background: rgba(234, 179, 8, 0.15);
  color: var(--warn);
}

.status-icon-bubble.success {
  background: rgba(34, 197, 94, 0.15);
  color: var(--ok);
}

.btn-inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.env-snippet {
  background: rgba(0, 0, 0, 0.35);
  padding: 8px 12px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 12px;
  margin-top: 10px;
  user-select: all;
}

.qr-instructions {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 14px;
}

.qr-display-box {
  width: 200px;
  height: 200px;
  background: var(--bg-elev);
  padding: 12px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.qr-svg-holder {
  width: 100%;
  height: 100%;
}

.qr-svg-holder :deep(svg) {
  width: 100%;
  height: 100%;
}

.actions-group {
  display: flex;
  gap: 10px;
  width: 100%;
}

.btn {
  flex: 1;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  text-decoration: none;
  text-align: center;
  transition: all 0.15s ease;
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-elev);
}

.btn-primary:hover {
  filter: brightness(1.1);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.16);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  color: var(--err);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.3);
}

.btn-unlink {
  margin-top: 0;
}

.paired-actions-row {
  display: flex;
  gap: 10px;
  width: 100%;
  margin-top: 8px;
}

.paired-qr-drawer {
  width: 100%;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  display: flex;
  flex-direction: column;
  align-items: center;
}

.poller-status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 12px;
  margin-bottom: 12px;
}

.status-chip-active {
  background: rgba(34, 197, 94, 0.12);
  color: var(--ok);
  border: 1px solid rgba(34, 197, 94, 0.25);
}

.status-chip-active .chip-dot {
  color: var(--ok);
  font-size: 8px;
  line-height: 1;
}

.status-chip-standby {
  background: rgba(250, 204, 21, 0.12);
  color: var(--warn);
  border: 1px solid rgba(250, 204, 21, 0.25);
}

.status-chip-standby .chip-dot {
  color: var(--warn);
  font-size: 8px;
  line-height: 1;
}
</style>
