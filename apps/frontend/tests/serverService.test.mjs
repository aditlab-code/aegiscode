import test from "node:test";
import assert from "node:assert/strict";
import {
  terminateServer,
  checkServerHealth,
  isTerminating,
  serverTerminated,
  isServerOnline,
  startServerHealthMonitor,
} from "../src/services/serverService.js";

test("serverService: terminateServer calls /api/server/terminate and updates reactive state", async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  let fetchUrl = "";
  let fetchOptions = null;

  globalThis.fetch = async (url, options) => {
    fetchCalled = true;
    fetchUrl = url;
    fetchOptions = options;
    const body = {
      status: "terminating",
      message: "Penghentian server AegisCode telah diinisiasi.",
      pid: 12345,
    };
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
      json: async () => body,
    };
  };

  try {
    serverTerminated.value = false;
    assert.equal(isTerminating.value, false);

    const result = await terminateServer(false);

    assert.equal(fetchCalled, true);
    assert.equal(fetchUrl, "/api/server/terminate");
    assert.equal(fetchOptions.method, "POST");

    assert.equal(result.success, true);
    assert.equal(result.data.status, "terminating");
    assert.equal(serverTerminated.value, true);
    assert.equal(isTerminating.value, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("serverService: terminateServer handles error responses gracefully", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    const body = {
      error: { code: "server_error", message: "Failed to trigger shutdown" },
    };
    return {
      ok: false,
      status: 500,
      text: async () => JSON.stringify(body),
      json: async () => body,
    };
  };

  try {
    serverTerminated.value = false;
    const result = await terminateServer(true);

    assert.equal(result.success, false);
    assert.ok(result.error.includes("Failed to trigger shutdown"));
    assert.equal(serverTerminated.value, false);
    assert.equal(isTerminating.value, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("serverService: checkServerHealth returns true on 200 and false on error", async () => {
  const originalFetch = globalThis.fetch;

  try {
    const okBody = { status: "ok" };
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(okBody),
      json: async () => okBody,
    });
    const healthy = await checkServerHealth();
    assert.equal(healthy, true);
    assert.equal(isServerOnline.value, true);

    globalThis.fetch = async () => {
      throw new Error("Network unreachable");
    };
    const unhealthy = await checkServerHealth();
    assert.equal(unhealthy, false);
    assert.equal(isServerOnline.value, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("serverService: startServerHealthMonitor executes immediate check and periodic poll", async () => {
  const originalFetch = globalThis.fetch;
  let pollCount = 0;

  const okBody = { status: "ok" };
  globalThis.fetch = async () => {
    pollCount += 1;
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify(okBody),
      json: async () => okBody,
    };
  };

  try {
    const statuses = [];
    const stop = startServerHealthMonitor((ok) => {
      statuses.push(ok);
    }, 20);

    assert.equal(pollCount >= 1, true, "Initial poll must execute immediately");
    await new Promise((r) => setTimeout(r, 60));
    assert.equal(pollCount >= 2, true, "Interval poll must execute");
    assert.equal(statuses.includes(true), true);

    stop();
    const countAfterStop = pollCount;
    await new Promise((r) => setTimeout(r, 40));
    assert.equal(pollCount, countAfterStop, "Monitor must not poll after stop");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
