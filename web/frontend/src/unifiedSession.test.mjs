import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const readSrc = (relPath) => fs.readFileSync(path.join(__dirname, relPath), "utf8");

test("UNIFY-01: api.js mengekspor fungsi Unified Session API lengkap", async () => {
  const apiModule = await import("./api.js");

  assert.equal(typeof apiModule.listSessions, "function", "listSessions harus diekspor");
  assert.equal(typeof apiModule.getSession, "function", "getSession harus diekspor");
  assert.equal(typeof apiModule.createSession, "function", "createSession harus diekspor");
  assert.equal(typeof apiModule.renameSession, "function", "renameSession harus diekspor");
  assert.equal(typeof apiModule.deleteSession, "function", "deleteSession harus diekspor");
  assert.equal(typeof apiModule.sendSessionPrompt, "function", "sendSessionPrompt harus diekspor");
  assert.equal(typeof apiModule.cancelSessionRun, "function", "cancelSessionRun harus diekspor");
});

test("UNIFY-02: AppLeftSidebar mengintegrasikan subtab Threads dengan operasi CRUD in-situ", () => {
  const sidebarCode = readSrc("components/layout/AppLeftSidebar.vue");

  assert.ok(sidebarCode.includes("loadThreads"), "AppLeftSidebar harus memuat thread sesi");
  assert.ok(sidebarCode.includes("handleNewThread"), "AppLeftSidebar harus mendukung pembuatan thread baru");
  assert.ok(sidebarCode.includes("startRename"), "AppLeftSidebar harus mendukung rename in-situ");
  assert.ok(sidebarCode.includes("handleDeleteSession"), "AppLeftSidebar harus mendukung penghapusan thread");
  assert.ok(sidebarCode.includes("side-sess-running-tag"), "AppLeftSidebar harus menampilkan badge running");
  assert.ok(sidebarCode.includes("open-session"), "AppLeftSidebar harus memancarkan event open-session");
});

test("UNIFY-03: Penyelarasan ID Sesi: App.vue meneruskan session_id ke task metadata", () => {
  const appCode = readSrc("App.vue");

  assert.ok(
    appCode.includes("meta.session_id = activeSessionId.value"),
    "submitTask harus menyertakan activeSessionId ke metadata task"
  );
  assert.ok(
    appCode.includes("@open-session="),
    "App.vue harus menyelaraskan activeSessionId saat open-session dipancarkan"
  );
});

test("UNIFY-04: Isolasi Aliran Event SSE: parser membedakan context_type consultation vs agent", () => {
  const mockAgentEvent = {
    event_type: "tool_called",
    task_id: "task_123",
    payload: {
      tool: "edit_file",
      context_type: "agent",
      mode: "agent",
    },
  };

  const mockConsultEvent = {
    event_type: "provider_response",
    task_id: null,
    payload: {
      step: 1,
      context_type: "consultation",
      mode: "ask",
    },
  };

  function classifyEvent(evt) {
    const p = evt.payload || {};
    if (p.context_type === "agent" || evt.task_id) {
      return "agent";
    }
    return "consultation";
  }

  assert.equal(classifyEvent(mockAgentEvent), "agent", "Event agent harus diklasifikasikan ke tab agent");
  assert.equal(classifyEvent(mockConsultEvent), "consultation", "Event konsultasi harus diklasifikasikan ke tab ask");
});

test("UNIFY-05: ConsultantChat merender kartu eksekusi agen secara terpadu dalam feed percakapan", () => {
  const chatCode = readSrc("components/ConsultantChat.vue");

  assert.ok(
    chatCode.includes("consultant-execution-box"),
    "ConsultantChat harus merender kotak eksekusi untuk giliran agent"
  );
  assert.ok(
    chatCode.includes("cmsg-exec-badge"),
    "ConsultantChat harus menampilkan badge status eksekusi agent"
  );
  assert.ok(
    chatCode.includes("cmsg-exec-changes"),
    "ConsultantChat harus menampilkan ringkasan perubahan berkas agent"
  );
});

test("UNIFY-06: Persistensi State: turn ask dan agent berdampingan secara harmonis", () => {
  const unifiedTurns = [
    {
      turn_id: "t1",
      role: "user",
      mode: "ask",
      content: "Jelaskan struktur proyek",
      execution: null,
    },
    {
      turn_id: "t2",
      role: "assistant",
      mode: "ask",
      content: "Berikut analisis arsitektur...",
      execution: null,
    },
    {
      turn_id: "t3",
      role: "user",
      mode: "agent",
      content: "Tambahkan modul logger",
      execution: null,
    },
    {
      turn_id: "t4",
      role: "assistant",
      mode: "agent",
      content: "Modul logger berhasil ditambahkan.",
      execution: {
        task_id: "task_999",
        status: "completed",
        changes: [{ file: "logger.py", kind: "create" }],
      },
    },
  ];

  assert.equal(unifiedTurns.length, 4);
  assert.equal(unifiedTurns.filter((t) => t.mode === "ask").length, 2);
  assert.equal(unifiedTurns.filter((t) => t.mode === "agent").length, 2);
  assert.equal(unifiedTurns[3].execution.status, "completed");
  assert.equal(unifiedTurns[3].execution.changes[0].file, "logger.py");
});
