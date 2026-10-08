<script setup>
import { onMounted, ref } from "vue";
import { useTelegramCompanion } from "../../services/telegramService.js";
import AppCard from "../ui/AppCard.vue";
import AppButton from "../ui/AppButton.vue";
import TelegramPairingPopover from "../layout/TelegramPairingPopover.vue";

const {
  status,
  loading,
  error,
  checkTelegramStatus,
  unlinkTelegramUser,
} = useTelegramCompanion();

const showPopover = ref(false);

onMounted(() => {
  checkTelegramStatus();
});

async function handleUnlink() {
  if (confirm("Apakah Anda yakin ingin memutuskan hubungan akun Telegram ini?")) {
    await unlinkTelegramUser();
  }
}
</script>

<template>
  <div class="remote-companion-settings">
    <!-- Panel Status Koneksi -->
    <AppCard variant="panel" class="settings-panel">
      <template #header>
        <div class="panel-header-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="telegram-icon">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <span>Telegram Remote Companion</span>
        </div>
      </template>

      <div class="companion-body">
        <div v-if="error" class="alert-banner error-banner">
          {{ error }}
        </div>

        <div class="status-summary-grid">
          <div class="summary-item">
            <span class="label">Status Gateway:</span>
            <span class="value" :class="status.configured ? 'status-online' : 'status-offline'">
              {{ status.configured ? "Aktif (Bot Token Terpasang)" : "Nonaktif (Token Kosong)" }}
            </span>
          </div>

          <div v-if="status.configured" class="summary-item">
            <span class="label">Nama Bot:</span>
            <span class="value font-mono">@{{ status.bot_username || "AegisCode_bot" }}</span>
          </div>

          <div class="summary-item">
            <span class="label">Status Pairing:</span>
            <span class="value" :class="status.is_paired ? 'status-online' : 'status-warning'">
              {{ status.is_paired ? "Terhubung" : "Menunggu Pairing" }}
            </span>
          </div>

          <div v-if="status.is_paired && status.paired_user" class="summary-item">
            <span class="label">Pengguna Terhubung:</span>
            <span class="value">
              <b>@{{ status.paired_user.username || status.paired_user.first_name }}</b>
              <span class="user-id"> (ID: {{ status.paired_user.user_id }})</span>
            </span>
          </div>
        </div>

        <div class="actions-toolbar">
          <AppButton
            v-if="!status.is_paired"
            variant="primary"
            :disabled="!status.configured"
            @click="showPopover = true"
          >
            Pindai QR Code Pairing
          </AppButton>

          <AppButton
            v-else
            variant="danger"
            :disabled="loading"
            @click="handleUnlink"
          >
            Putuskan Hubungan Akun
          </AppButton>
        </div>
      </div>
    </AppCard>

    <!-- Panel Petunjuk Penggunaan & Keamanan -->
    <AppCard variant="panel" class="settings-panel info-panel">
      <template #header>
        <span>Keamanan & Panduan Penggunaan</span>
      </template>

      <div class="info-body">
        <div class="info-section">
          <h4>🔒 Keamanan Zero-Trust & Outbound Polling</h4>
          <p>
            Gateway menggunakan metode <i>long-polling outbound</i> langsung ke server Telegram. Komputer Anda tidak memerlukan port publik atau IP statis.
            Hanya User ID yang berhasil melakukan scan QR yang diizinkan memberi instruksi; akun tak dikenal langsung ditolak.
          </p>
        </div>

        <div class="info-section">
          <h4>📱 Fitur Remote Steering</h4>
          <ul>
            <li><b>Notifikasi Getar & Suara:</b> Ponsel bergetar otomatis saat agen membutuhkan konfirmasi (HITL).</li>
            <li><b>Tombol Persetujuan Cepat:</b> Tekan <code>[Approve]</code> atau <code>[Reject]</code> langsung pada chat Telegram.</li>
            <li><b>Steering Percakapan:</b> Balas pesan bot untuk memberikan instruksi pengarah ke agen.</li>
          </ul>
        </div>
      </div>
    </AppCard>

    <!-- Modal Popover -->
    <TelegramPairingPopover
      v-if="showPopover"
      @close="showPopover = false"
    />
  </div>
</template>

<style scoped>
.remote-companion-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.telegram-icon {
  color: #38bdf8;
}

.companion-body, .info-body {
  padding: 16px;
}

.status-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  background: var(--bg-elevated, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 16px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-item .label {
  font-size: 12px;
  color: var(--text-muted, #a6adc8);
}

.summary-item .value {
  font-size: 14px;
  font-weight: 500;
}

.status-online {
  color: #4ade80;
}

.status-offline {
  color: #f87171;
}

.status-warning {
  color: #facc15;
}

.font-mono {
  font-family: monospace;
}

.user-id {
  font-size: 12px;
  color: var(--text-muted, #a6adc8);
}

.actions-toolbar {
  display: flex;
  gap: 12px;
}

.info-section {
  margin-bottom: 14px;
}

.info-section h4 {
  margin: 0 0 6px 0;
  font-size: 13px;
  color: var(--text-primary, #ffffff);
}

.info-section p, .info-section ul {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted, #a6adc8);
  line-height: 1.5;
}

.info-section ul {
  padding-left: 20px;
}

.info-section li {
  margin-top: 4px;
}
</style>
