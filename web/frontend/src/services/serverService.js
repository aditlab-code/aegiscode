/**
 * serverService.js - Layanan Manajemen Siklus Hidup Server AegisCode.
 *
 * Mengelola komunikasi HTTP untuk terminasi server secara aman (Zero-Zombie exit)
 * dan pemantauan status kesehatan server gateway.
 */

import { ref } from "vue";

export const isTerminating = ref(false);
export const serverTerminated = ref(false);
export const isServerOnline = ref(false);

/**
 * Mengirim permintaan penghentian server ke Django API Gateway.
 *
 * @param {boolean} [force=false] - Paksa terminasi segera bila true.
 * @returns {Promise<{success: boolean, data?: any, error?: string}>}
 */
export async function terminateServer(force = false) {
  isTerminating.value = true;
  try {
    const res = await fetch("/api/server/terminate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ force }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData?.error?.message || `HTTP ${res.status}`);
    }

    const data = await res.json();
    serverTerminated.value = true;
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || String(err) };
  } finally {
    isTerminating.value = false;
  }
}

/**
 * Memeriksa status kesehatan gateway server.
 *
 * @returns {Promise<boolean>} True jika server merespons normal.
 */
export async function checkServerHealth() {
  try {
    const res = await fetch("/api/health");
    const ok = Boolean(res && res.ok);
    isServerOnline.value = ok;
    return ok;
  } catch {
    isServerOnline.value = false;
    return false;
  }
}

/**
 * Memulai monitor periodik status kesehatan server gateway.
 *
 * @param {(online: boolean) => void} [callback] - Callback yang dipanggil setiap kali status diperiksa.
 * @param {number} [intervalMs=5000] - Interval waktu antar pengecekan dalam milidetik.
 * @returns {() => void} Fungsi pembersih pembatalan monitor (clearInterval).
 */
export function startServerHealthMonitor(callback = null, intervalMs = 5000) {
  let timer = null;
  const poll = async () => {
    const ok = await checkServerHealth();
    if (typeof callback === "function") {
      callback(ok);
    }
  };
  poll();
  if (typeof setInterval !== "undefined") {
    timer = setInterval(poll, intervalMs);
  }
  return () => {
    if (timer) clearInterval(timer);
  };
}
