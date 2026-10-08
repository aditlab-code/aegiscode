import { ref } from "vue";
import {
  getTelegramStatus,
  getTelegramPairingQr,
  postTelegramUnlink,
} from "../api.js";

const status = ref({
  configured: false,
  is_paired: false,
  bot_username: "",
  paired_user: null,
});

const qrData = ref({
  token: "",
  deep_link: "",
  qr_svg: "",
  expires_in: 300,
});

const loading = ref(false);
const error = ref("");

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
    return true;
  } catch (err) {
    error.value = err.message || "Gagal memutuskan hubungan Telegram";
    return false;
  } finally {
    loading.value = false;
  }
}

export function useTelegramCompanion() {
  return {
    status,
    qrData,
    loading,
    error,
    checkTelegramStatus,
    fetchTelegramPairingQr,
    unlinkTelegramUser,
  };
}
