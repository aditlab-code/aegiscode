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
          <div class="status-icon-bubble warning">⚠️</div>
          <h4>Bot Token Belum Diatur</h4>
          <p>
            Untuk mengaktifkan pendamping jarak jauh, buat bot di <b>@BotFather</b> lalu tambahkan ke <code>.env</code>:
          </p>
          <pre class="env-snippet">TELEGRAM_BOT_TOKEN="your_bot_token_here"</pre>
        </div>

        <!-- 2. Kondisi: Akun Sudah Terhubung (Paired) -->
        <div v-else-if="status.is_paired" class="state-container state-paired">
          <div class="status-icon-bubble success">✅</div>
          <h4>Perangkat Terhubung</h4>
          <p class="connected-info">
            Akun Telegram: <b>@{{ status.paired_user?.username || status.paired_user?.first_name || status.paired_user?.user_id }}</b>
          </p>
          <p class="description">
            Ponsel Anda akan bergetar dan menerima pesan saat agen membutuhkan keputusan persetujuan (*Human-in-the-Loop*).
          </p>
          <button type="button" class="btn btn-danger" :disabled="loading" @click="handleUnlink">
            Putuskan Hubungan
          </button>
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
            <a :href="qrData.deep_link" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
              Buka di Telegram ↗
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
  background: var(--bg-surface, #1e1e2e);
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.12));
  border-radius: 12px;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  color: var(--text-primary, #cdd6f4);
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
  color: #38bdf8;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted, #a6adc8);
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
}

.close-btn:hover {
  color: var(--text-primary, #ffffff);
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
}

.status-icon-bubble.success {
  background: rgba(34, 197, 94, 0.15);
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
  color: var(--text-muted, #a6adc8);
  margin-bottom: 14px;
}

.qr-display-box {
  width: 200px;
  height: 200px;
  background: #ffffff;
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
  background: #0284c7;
  color: #ffffff;
}

.btn-primary:hover {
  background: #0369a1;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #cdd6f4);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.16);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.3);
}
</style>
