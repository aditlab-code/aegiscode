// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  KNOWN_SSE_EVENTS,
  getOperationalMode,
  setOperationalMode,
  listApprovals,
  resolveApproval,
} from "../src/api.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const readSrc = (relPath) => fs.readFileSync(path.join(__dirname, "..", "src", relPath), "utf8");

test("API: KNOWN_SSE_EVENTS includes mode_updated, approval_requested, and approval_resolved", () => {
  assert.ok(KNOWN_SSE_EVENTS.includes("mode_updated"), "mode_updated harus terdaftar di KNOWN_SSE_EVENTS");
  assert.ok(KNOWN_SSE_EVENTS.includes("approval_requested"), "approval_requested harus terdaftar di KNOWN_SSE_EVENTS");
  assert.ok(KNOWN_SSE_EVENTS.includes("approval_resolved"), "approval_resolved harus terdaftar di KNOWN_SSE_EVENTS");
});

test("API: getOperationalMode dispatches GET /api/mode", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  let requestOptions = null;

  globalThis.fetch = async (url, opts) => {
    requestedUrl = String(url);
    requestOptions = opts;
    return {
      status: 200,
      ok: true,
      text: async () => JSON.stringify({ status: "ok", mode: "ask" }),
    };
  };

  try {
    const res = await getOperationalMode();
    assert.equal(requestedUrl, "/api/mode");
    assert.deepEqual(res, { status: "ok", mode: "ask" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("API: setOperationalMode dispatches POST /api/mode with mode payload", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  let requestOptions = null;

  globalThis.fetch = async (url, opts) => {
    requestedUrl = String(url);
    requestOptions = opts;
    return {
      status: 200,
      ok: true,
      text: async () => JSON.stringify({ status: "ok", mode: "agents" }),
    };
  };

  try {
    const res = await setOperationalMode("agents");
    assert.equal(requestedUrl, "/api/mode");
    assert.equal(requestOptions.method, "POST");
    assert.deepEqual(JSON.parse(requestOptions.body), { mode: "agents" });
    assert.deepEqual(res, { status: "ok", mode: "agents" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("API: listApprovals and resolveApproval contract verification", async () => {
  const originalFetch = globalThis.fetch;
  let calls = [];

  globalThis.fetch = async (url, opts) => {
    calls.push({ url: String(url), opts });
    if (String(url).includes("/tasks/approvals/resolve")) {
      return {
        status: 200,
        ok: true,
        text: async () => JSON.stringify({ status: "ok", resolved: true }),
      };
    }
    return {
      status: 200,
      ok: true,
      text: async () => JSON.stringify({ approvals: [{ id: "app-1", tool: "run_command" }] }),
    };
  };

  try {
    const list = await listApprovals("task-123");
    assert.equal(calls[0].url, "/api/tasks/approvals?task_id=task-123");
    assert.equal(list.approvals.length, 1);

    const resolved = await resolveApproval("app-1", true);
    assert.equal(calls[1].url, "/api/tasks/approvals/resolve");
    assert.equal(calls[1].opts.method, "POST");
    assert.deepEqual(JSON.parse(calls[1].opts.body), { request_id: "app-1", allow: true });
    assert.equal(resolved.status, "ok");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("M3-APPROVAL: ApprovalModal.vue renders dialog header, tool badge, target, reason, and action buttons", () => {
  const modalCode = readSrc("components/ui/ApprovalModal.vue");

  assert.ok(modalCode.includes("Human Approval Required"), "ApprovalModal harus memiliki judul 'Human Approval Required'");
  assert.ok(modalCode.includes("Tool:"), "ApprovalModal harus menampilkan badge tool");
  assert.ok(modalCode.includes("Target / Command"), "ApprovalModal harus menampilkan target/command");
  assert.ok(modalCode.includes("Reason"), "ApprovalModal harus menampilkan reason");
  assert.ok(modalCode.includes("Request ID:"), "ApprovalModal harus menampilkan Request ID");
  assert.ok(modalCode.includes("Session ID:"), "ApprovalModal harus menampilkan Session ID");
  assert.ok(modalCode.includes("resolveApproval"), "ApprovalModal harus memanggil resolveApproval()");
  assert.ok(modalCode.includes("handleResolve(true)"), "ApprovalModal harus memiliki aksi Approve");
  assert.ok(modalCode.includes("handleResolve(false)"), "ApprovalModal harus memiliki aksi Reject");
  assert.ok(modalCode.includes("listApprovals"), "ApprovalModal harus mendukung fetching pending approvals via listApprovals");
  assert.ok(modalCode.includes("aegis:approval_requested"), "ApprovalModal harus mendukung event approval_requested");
  assert.ok(modalCode.includes("aegis:approval_resolved"), "ApprovalModal harus mendukung event approval_resolved");
});

test("M3-STATUSBAR: AppStatusBar.vue renders operational mode badge with click toggle", () => {
  const statusBarCode = readSrc("components/layout/AppStatusBar.vue");

  assert.ok(statusBarCode.includes("badge-operational-mode"), "AppStatusBar harus memiliki badge badge-operational-mode");
  assert.ok(statusBarCode.includes("getOperationalMode"), "AppStatusBar harus mengimpor getOperationalMode");
  assert.ok(statusBarCode.includes("setOperationalMode"), "AppStatusBar harus mengimpor setOperationalMode");
  assert.ok(statusBarCode.includes("toggleMode"), "AppStatusBar harus mendukung fungsi toggleMode");
  assert.ok(statusBarCode.includes("operationalMode"), "AppStatusBar harus memiliki state/prop operationalMode");
  assert.ok(statusBarCode.includes("mode-changed"), "AppStatusBar harus memancarkan emit mode-changed");
  assert.ok(statusBarCode.includes("Agents ⚡"), "AppStatusBar harus menampilkan label Agents ⚡");
  assert.ok(statusBarCode.includes("Ask ⏸️"), "AppStatusBar harus menampilkan label Ask ⏸️");
  assert.ok(statusBarCode.includes("aegis:mode_updated"), "AppStatusBar harus mendengarkan event mode_updated");
});

test("M3-APP: App.vue mounts ApprovalModal and coordinates operational mode & SSE approval events", () => {
  const appCode = readSrc("App.vue");

  assert.ok(appCode.includes("import ApprovalModal from \"./components/ui/ApprovalModal.vue\""), "App.vue harus mengimpor ApprovalModal");
  assert.ok(appCode.includes("<ApprovalModal"), "App.vue harus menyematkan <ApprovalModal");
  assert.ok(appCode.includes("approvalModalOpen"), "App.vue harus memiliki state ref approvalModalOpen");
  assert.ok(appCode.includes("pendingApproval"), "App.vue harus memiliki state ref pendingApproval");
  assert.ok(appCode.includes("operationalMode"), "App.vue harus memiliki state ref operationalMode");
  assert.ok(appCode.includes("getOperationalMode"), "App.vue harus mengimpor getOperationalMode");
  assert.ok(appCode.includes("approval_requested"), "App.vue harus merespons SSE approval_requested");
  assert.ok(appCode.includes("approval_resolved"), "App.vue harus merespons SSE approval_resolved");
  assert.ok(appCode.includes("mode_updated"), "App.vue harus merespons SSE mode_updated");
  assert.ok(appCode.includes(":operational-mode=\"operationalMode\""), "App.vue harus meneruskan operationalMode ke AppStatusBar");
  assert.ok(appCode.includes("@mode-changed="), "App.vue harus menyelaraskan perubahan mode dari AppStatusBar");
});
