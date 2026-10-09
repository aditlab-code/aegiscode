/**
 * portDiscoveryService.js - Passive Port Discovery & Status Bar Integration.
 *
 * Mendeteksi port dev server aktif dari stream keluaran PTY terminal
 * (mis. Vite, Next.js, Django, FastAPI, Express, uvicorn) dan menyediakan
 * reactive state untuk chips status bar dengan pembukaan tab terisolasi (rel=noopener).
 */
import { ref } from "vue";

// Reactive list of active discovered ports: { port: number, url: string, label: string, timestamp: number }
const discoveredPorts = ref([]);

// Regex untuk mendeteksi URL localhost/127.0.0.1/0.0.0.0 dengan nomor port
// Mengabaikan escape sequence ANSI (\x1b...) dan tanda baca penutup
const URL_PORT_REGEX = /https?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|::1):(\d{2,5})(?:[^\s\x1b"'\`<>()[\]{}]*)?/gi;

// Pola alternatif: "running on port 3000", "listening on port 8080"
const RUNNING_PORT_REGEX = /(?:running|listening|server(?:\s+started)?)\s+(?:at|on|port)\s+.*?(\d{2,5})/gi;

const GATEWAY_DEFAULT_PORT = 8478;

/**
 * Validasi port number: 1024 - 65535, bukan port internal gateway AegisCode (8478).
 */
export function isValidDevPort(port) {
  const p = Number(port);
  return Number.isInteger(p) && p >= 1024 && p <= 65535 && p !== GATEWAY_DEFAULT_PORT;
}

/**
 * Tambahkan port yang terdeteksi ke reactive list (deduplikasi by port).
 */
export function registerDiscoveredPort(port, rawUrl = "") {
  const p = Number(port);
  if (!isValidDevPort(p)) return;

  const url = rawUrl && rawUrl.startsWith("http")
    ? rawUrl.replace(/0\.0\.0\.0|\[::1\]|::1/, "localhost")
    : `http://localhost:${p}`;

  const existingIndex = discoveredPorts.value.findIndex((item) => item.port === p);
  const entry = {
    port: p,
    url,
    label: `:${p}`,
    timestamp: Date.now(),
  };

  if (existingIndex >= 0) {
    discoveredPorts.value[existingIndex] = entry;
  } else {
    discoveredPorts.value.push(entry);
    // Batasi maksimum 5 port aktif sekaligus di status bar
    if (discoveredPorts.value.length > 5) {
      discoveredPorts.value.shift();
    }
  }
}

/**
 * Hapus port dari daftar aktif (misal saat proses dihentikan atau di-dismiss).
 */
export function removeDiscoveredPort(port) {
  const p = Number(port);
  discoveredPorts.value = discoveredPorts.value.filter((item) => item.port !== p);
}

/**
 * Kosongkan seluruh port aktif (misal saat berganti workspace).
 */
export function clearDiscoveredPorts() {
  discoveredPorts.value = [];
}

/**
 * Buka URL port di tab peramban baru dengan proteksi aman (rel=noopener noreferrer).
 */
export function openPortSafely(url) {
  if (typeof window === "undefined" || !url) return;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      console.warn("Protokol tidak aman diblokir dari port chip:", parsed.protocol);
      return;
    }
    const win = window.open(parsed.href, "_blank", "noopener,noreferrer");
    if (win) {
      win.opener = null;
    }
  } catch (err) {
    console.warn("URL port tidak valid:", err);
  }
}

/**
 * Sniff potongan teks output dari PTY terminal secara pasif.
 */
export function sniffTerminalChunk(chunk) {
  if (!chunk || typeof chunk !== "string") return;

  // 1. Cek pola URL langsung
  let match;
  URL_PORT_REGEX.lastIndex = 0;
  while ((match = URL_PORT_REGEX.exec(chunk)) !== null) {
    const port = parseInt(match[1], 10);
    const fullUrl = match[0].replace(/[.,:;!?]+$/, "");
    registerDiscoveredPort(port, fullUrl);
  }

  // 2. Cek pola 'port XXXX'
  RUNNING_PORT_REGEX.lastIndex = 0;
  while ((match = RUNNING_PORT_REGEX.exec(chunk)) !== null) {
    const port = parseInt(match[1], 10);
    registerDiscoveredPort(port);
  }
}

/**
 * Vue 3 composable untuk komponen Status Bar atau UI lainnya.
 */
export function usePortDiscovery() {
  return {
    discoveredPorts,
    registerDiscoveredPort,
    removeDiscoveredPort,
    clearDiscoveredPorts,
    openPortSafely,
    sniffTerminalChunk,
  };
}
