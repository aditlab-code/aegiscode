import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

import {
  useTelegramCompanion,
  checkTelegramStatus,
  fetchTelegramPairingQr,
  unlinkTelegramUser,
} from "../src/services/telegramService.js";

describe("telegramService", () => {
  const { status, qrData, loading } = useTelegramCompanion();

  beforeEach(() => {
    // Reset state
    status.value = {
      configured: false,
      is_paired: false,
      bot_username: "",
      paired_user: null,
    };
    qrData.value = {
      token: "",
      deep_link: "",
      qr_svg: "",
      expires_in: 300,
    };
    loading.value = false;
  });

  it("1. initial reactive state has default values", () => {
    assert.equal(status.value.configured, false);
    assert.equal(status.value.is_paired, false);
    assert.equal(qrData.value.deep_link, "");
  });

  it("2. checkTelegramStatus updates reactive status ref", async () => {
    // Mock global fetch
    globalThis.fetch = async (url) => {
      if (url.endsWith("/telegram/status")) {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({
            configured: true,
            is_paired: true,
            bot_username: "Aegis_bot",
            paired_user: { user_id: 12345, username: "adit" },
          }),
        };
      }
      return { ok: false, status: 404, text: async () => "{}" };
    };

    const res = await checkTelegramStatus();
    assert.equal(res.configured, true);
    assert.equal(res.is_paired, true);
    assert.equal(status.value.is_paired, true);
    assert.equal(status.value.paired_user.username, "adit");
  });

  it("3. fetchTelegramPairingQr updates qrData ref", async () => {
    globalThis.fetch = async (url) => {
      if (url.endsWith("/telegram/pairing-qr")) {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({
            token: "tok_abc",
            deep_link: "https://t.me/Aegis_bot?start=pair_tok_abc",
            qr_svg: "<svg>test</svg>",
            expires_in: 300,
          }),
        };
      }
      return { ok: false, status: 404, text: async () => "{}" };
    };

    const res = await fetchTelegramPairingQr();
    assert.equal(res.token, "tok_abc");
    assert.equal(qrData.value.qr_svg, "<svg>test</svg>");
  });

  it("4. unlinkTelegramUser resets paired state", async () => {
    globalThis.fetch = async (url, options) => {
      if (url.endsWith("/telegram/unlink") && options?.method === "POST") {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ success: true }),
        };
      }
      if (url.endsWith("/telegram/status")) {
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({
            configured: true,
            is_paired: false,
            bot_username: "Aegis_bot",
            paired_user: null,
          }),
        };
      }
      return { ok: false, status: 404, text: async () => "{}" };
    };

    const success = await unlinkTelegramUser();
    assert.equal(success, true);
    assert.equal(status.value.is_paired, false);
  });
});
