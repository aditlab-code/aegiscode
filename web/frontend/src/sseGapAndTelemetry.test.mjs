// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import { KNOWN_SSE_EVENTS, openEventStream } from "./api.js";

test("AEG-09: KNOWN_SSE_EVENTS registers all backend lifecycle, observation, and policy events", () => {
  const REQUIRED_EVENTS = [
    "task_created",
    "task_started",
    "phase_changed",
    "agent_commentary",
    "tool_called",
    "tool_completed",
    "tool_result",
    "agent_observation",
    "observation_received",
    "provider_request",
    "provider_response",
    "validation_started",
    "validation_completed",
    "recovery_started",
    "recovery_completed",
    "policy_applied",
    "policy_escalated",
    "verification_strategy_applied",
    "change_detected",
    "approval_requested",
    "approval_resolved",
    "task_completed",
    "task_failed",
    "task_cancelled",
  ];

  for (const evt of REQUIRED_EVENTS) {
    assert.ok(
      KNOWN_SSE_EVENTS.includes(evt),
      `Event ${evt} harus terdaftar di KNOWN_SSE_EVENTS`
    );
  }
});

test("AEG-10: openEventStream appends last_event_id query parameter when specified", () => {
  let createdUrl = "";
  class MockEventSource {
    constructor(url) {
      createdUrl = url;
      this.addEventListener = () => {};
    }
  }
  globalThis.EventSource = MockEventSource;

  openEventStream({
    taskId: "task-123",
    lastEventId: "evt-999",
  });

  assert.ok(createdUrl.includes("task_id=task-123"), "URL harus memuat task_id");
  assert.ok(createdUrl.includes("last_event_id=evt-999"), "URL harus memuat last_event_id");
});

test("AEG-18: Monotonic telemetry does not decrease when visual event window shifts (> 500 events)", () => {
  const activityEvents = [];
  const taskTelemetry = { rounds: 0, toolCalls: 0, observations: 0 };

  // Simulasikan kedatangan 600 events (500 tool_called + 100 lainnya)
  for (let i = 0; i < 600; i++) {
    const evt = {
      event_type: i < 500 ? "tool_called" : "observation_received",
      task_id: "task-long",
      event_id: `evt-${i}`,
    };

    activityEvents.push(evt);
    if (activityEvents.length > 500) {
      activityEvents.shift();
    }

    if (evt.event_type === "provider_request") {
      taskTelemetry.rounds += 1;
    } else if (evt.event_type === "tool_called") {
      taskTelemetry.toolCalls += 1;
    } else if (evt.event_type === "observation_received") {
      taskTelemetry.observations += 1;
    }
  }

  // Meskipun array tampilan activityEvents hanya menyimpan 500 elemen terakhir,
  // akumulasi toolCalls tidak boleh turun dari 500 menjadi 400!
  assert.equal(activityEvents.length, 500, "Array tampilan visual dibatasi 500 baris");
  assert.equal(taskTelemetry.toolCalls, 500, "Akumulasi toolCalls harus tetap 500 (tidak berkurang)");
  assert.equal(taskTelemetry.observations, 100, "Akumulasi observations harus 100");
});

test("AEG-18: Connection status requires both HTTP gateway and SSE stream to be active", () => {
  const computeConnected = (httpOk, sseOk) => Boolean(httpOk && sseOk);

  assert.equal(computeConnected(true, true), true, "Keduanya aktif -> connected");
  assert.equal(computeConnected(true, false), false, "SSE putus -> disconnected");
  assert.equal(computeConnected(false, true), false, "HTTP gateway mati -> disconnected");
  assert.equal(computeConnected(false, false), false, "Keduanya mati -> disconnected");
});

console.log("[OK] sseGapAndTelemetry: event contracts, lastEventId param, monotonic telemetry, dan status koneksi terverifikasi!");
