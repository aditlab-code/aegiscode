import { ref } from "vue";
import {
  getTelegramStatus,
  getTelegramPairingQr,
  postTelegramUnlink,
  postTelegramStartPoller,
  postTelegramStopPoller,
} from "../api.js";

const status = ref({
  configured: false,
  is_paired: false,
  bot_username: "",
  paired_user: null,
  is_running: false,
});

const qrData = ref({
  token: "",
  deep_link: "",
  qr_svg: "",
  expires_in: 300,
});

const loading = ref(false);
const error = ref("");
const isToggling = ref(false);
const activeNotification = ref(null);

export function setTelegramNotification(message, type = "info") {
  activeNotification.value = {
    message,
    type,
    id: Date.now(),
  };
}

export function dismissTelegramNotification() {
  activeNotification.value = null;
}

export async function checkTelegramStatus() {
  try {
    const data = await getTelegramStatus();
    status.value = data;
    return data;
  } catch (err) {
    error.value = err.message || "Gagal memeriksa status";
    return status.value;
  }
}

export async function fetchTelegramPairingQr() {
  loading.value = true;
  error.value = "";
  try {
    const data = await getTelegramPairingQr();
    qrData.value = data;
    return data;
  } catch (err) {
    error.value = err.message || "Gagal membuat sesi pairing";
    throw err;
  } finally {
    loading.value = false;
  }
}

export async function unlinkTelegramUser() {
  loading.value = true;
  error.value = "";
  try {
    await postTelegramUnlink();
    await checkTelegramStatus();
    setTelegramNotification("Hubungan akun Telegram berhasil diputuskan", "info");
    return true;
  } catch (err) {
    error.value = err.message || "Gagal memutuskan hubungan Telegram";
    return false;
  } finally {
    loading.value = false;
  }
}

export async function startTelegramPoller() {
  if (isToggling.value) {
    return false;
  }
  isToggling.value = true;
  loading.value = true;
  error.value = "";
  try {
    const res = await postTelegramStartPoller();
    if (res?.is_running !== undefined) {
      status.value.is_running = res.is_running;
    }
    await checkTelegramStatus();
    setTelegramNotification("Telegram Companion aktif mendengarkan", "success");
    return true;
  } catch (err) {
    error.value = err.message || "Gagal mengaktifkan bot poller";
    setTelegramNotification(error.value, "error");
    return false;
  } finally {
    loading.value = false;
    isToggling.value = false;
  }
}

export async function stopTelegramPoller() {
  if (isToggling.value) {
    return false;
  }
  isToggling.value = true;
  loading.value = true;
  error.value = "";
  try {
    const res = await postTelegramStopPoller();
    if (res?.is_running !== undefined) {
      status.value.is_running = res.is_running;
    }
    await checkTelegramStatus();
    setTelegramNotification("Telegram Companion dinonaktifkan (Standby)", "info");
    return true;
  } catch (err) {
    error.value = err.message || "Gagal menghentikan bot poller";
    setTelegramNotification(error.value, "error");
    return false;
  } finally {
    loading.value = false;
    isToggling.value = false;
  }
}

export function useTelegramCompanion() {
  return {
    status,
    qrData,
    loading,
    error,
    isToggling,
    activeNotification,
    setTelegramNotification,
    dismissTelegramNotification,
    checkTelegramStatus,
    fetchTelegramPairingQr,
    unlinkTelegramUser,
    startTelegramPoller,
    stopTelegramPoller,
  };
}
