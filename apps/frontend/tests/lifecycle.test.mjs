import assert from "node:assert/strict";
import {
  VALIDATING_STEP,
  VERIFYING_STEP,
  OLYMPUS_PHASES,
  activityPhaseIndex,
  addMilestone,
  buildLifecycleStates,
  isActivityPhase,
  lifecycleFromEvents,
} from "../src/lifecycle.js";

const STEPS = OLYMPUS_PHASES;
const P = "";
const D = "done";
const A = "active";

// --- activityPhaseIndex / isActivityPhase -----------------------------------
assert.equal(activityPhaseIndex("define"), 0);
assert.equal(activityPhaseIndex("DEFINE"), 0);
assert.equal(activityPhaseIndex("plan"), 1);
assert.equal(activityPhaseIndex("PLAN"), 1);
assert.equal(activityPhaseIndex("build"), 2);
assert.equal(activityPhaseIndex("BUILD"), 2);
assert.equal(activityPhaseIndex("verify"), 3);
assert.equal(activityPhaseIndex("VERIFY"), 3);
assert.equal(activityPhaseIndex("review"), 4);
assert.equal(activityPhaseIndex("REVIEW"), 4);
assert.equal(activityPhaseIndex("ship"), 5);
assert.equal(activityPhaseIndex("SHIP"), 5);

// Aliases
assert.equal(activityPhaseIndex("planning"), 1);
assert.equal(activityPhaseIndex("inspecting"), 2);
assert.equal(activityPhaseIndex("editing"), 2);
assert.equal(activityPhaseIndex("validating"), 3);
assert.equal(activityPhaseIndex("completed"), 5);

// Internal non-phases
assert.equal(activityPhaseIndex("replan"), -1);
assert.equal(activityPhaseIndex("provider_fallback"), -1);
assert.equal(activityPhaseIndex(""), -1);
assert.equal(activityPhaseIndex(null), -1);
assert.equal(isActivityPhase("build"), true);
assert.equal(isActivityPhase("replan"), false);
assert.equal(VALIDATING_STEP, 3);
assert.equal(VERIFYING_STEP, 3);

// --- addMilestone (immutable, unik, terurut) --------------------------------
assert.deepEqual(addMilestone([], 2), [2]);
assert.deepEqual(addMilestone([2], 2), [2], "tidak duplikat");
assert.deepEqual(addMilestone([3, 1], 2), [1, 2, 3], "terurut");
assert.deepEqual(addMilestone([], 9), [], "index di luar rentang diabaikan");

function lifecycle(status = "running") {
  let milestones = [];
  let currentPhase = "";
  const step = (p) => {
    const idx = activityPhaseIndex(p);
    if (idx >= 0) {
      milestones = addMilestone(milestones, idx);
      currentPhase = String(p).trim().toLowerCase();
    }
  };
  const render = () =>
    buildLifecycleStates({
      hasTask: true,
      status,
      currentPhase,
      milestones,
      count: STEPS.length,
    });
  return {
    step,
    setStatus: (s) => (status = s),
    render,
    get milestones() {
      return milestones;
    },
  };
}

const expectStates = (steps, expected) => {
  assert.equal(steps.length, STEPS.length);
  assert.deepEqual(steps, expected);
  return steps;
};

// --- Acceptance 1..6: Olympus Progression -----------------------------------
// task_started -> DEFINE
{
  const lc = lifecycle();
  lc.step("define");
  expectStates(lc.render(), [A, P, P, P, P, P]);
}

// phase_changed plan -> PLAN, DEFINE jadi milestone done.
{
  const lc = lifecycle();
  lc.step("define");
  lc.step("plan");
  expectStates(lc.render(), [D, A, P, P, P, P]);
}

// phase_changed build -> BUILD.
{
  const lc = lifecycle();
  ["define", "plan", "build"].forEach(lc.step);
  expectStates(lc.render(), [D, D, A, P, P, P]);
}

// phase_changed verify -> VERIFY.
{
  const lc = lifecycle();
  ["define", "plan", "build", "verify"].forEach(lc.step);
  expectStates(lc.render(), [D, D, D, A, P, P]);
}

// phase_changed review -> REVIEW.
{
  const lc = lifecycle();
  ["define", "plan", "build", "verify", "review"].forEach(lc.step);
  expectStates(lc.render(), [D, D, D, D, A, P]);
}

// task_completed -> SHIP (terminal), seluruh step done.
{
  const lc = lifecycle();
  ["define", "plan", "build", "verify", "review"].forEach(lc.step);
  lc.setStatus("completed");
  expectStates(lc.render(), [D, D, D, D, D, A]);
}

// --- Acceptance 7/8: Current phase boleh mundur, milestone tetap done --------
{
  const lc = lifecycle();
  ["define", "plan", "build", "plan"].forEach(lc.step);
  const steps = lc.render();
  expectStates(steps, [D, A, D, P, P, P]);
  assert.equal(steps[2], D, `BUILD (${STEPS[2]}) tetap milestone done saat kembali ke PLAN`);
}

{
  const lc = lifecycle();
  ["define", "plan", "build", "verify", "build"].forEach(lc.step);
  expectStates(lc.render(), [D, D, A, D, P, P]);
}

// --- Acceptance 9/10: Failed & cancelled BUKAN Completed / SHIP --------------
{
  const lc = lifecycle();
  ["define", "plan", "build"].forEach(lc.step);
  lc.setStatus("failed");
  const steps = lc.render();
  expectStates(steps, [D, D, A, P, P, P]);
  assert.notEqual(steps[5], A, "Failed TIDAK menampilkan SHIP");
}
{
  const lc = lifecycle();
  ["define", "plan", "build", "verify"].forEach(lc.step);
  lc.setStatus("cancelled");
  const steps = lc.render();
  expectStates(steps, [D, D, D, A, P, P]);
  assert.notEqual(steps[5], A, "Cancelled TIDAK menampilkan SHIP");
}

// --- Acceptance 11: runtime.phase internal tidak menggerakkan lifecycle ------
{
  const lc = lifecycle();
  ["define", "build"].forEach(lc.step);
  lc.step("replan");
  lc.step("provider_fallback");
  expectStates(lc.render(), [D, P, A, P, P, P]);
}

// --- Task belum mulai / idle ------------------------------------------------
expectStates(
  buildLifecycleStates({ hasTask: false, status: "idle", currentPhase: "", milestones: [] }),
  [P, P, P, P, P, P]
);
// Task running tanpa phase -> DEFINE (fallback aman).
expectStates(
  buildLifecycleStates({ hasTask: true, status: "running", currentPhase: "", milestones: [] }),
  [A, P, P, P, P, P]
);

// --- lifecycleFromEvents (history task lama) --------------------------------
{
  const events = [
    { event: "task_started", data: {} },
    { event: "phase_changed", data: { phase: "plan" } },
    { event: "phase_changed", data: { phase: "build" } },
    { event: "phase_changed", data: { phase: "verify" } },
    { event: "task_failed", data: {} },
  ];
  const { milestones, currentPhase } = lifecycleFromEvents(events);
  assert.deepEqual(milestones, [0, 1, 2, 3]);
  assert.equal(currentPhase, "verify");
  const steps = buildLifecycleStates({
    hasTask: true,
    status: "failed",
    currentPhase,
    milestones,
    count: STEPS.length,
  });
  expectStates(steps, [D, D, D, A, P, P]);
  assert.notEqual(steps[5], A);
}

// Validation started -> verify
{
  const { milestones, currentPhase } = lifecycleFromEvents([
    { event: "task_started", data: {} },
    { event: "validation_started", data: {} },
  ]);
  assert.deepEqual(milestones, [0, 3]);
  assert.equal(currentPhase, "verify");
}

console.log("[OK] lifecycle: Olympus autonomous workflow (DEFINE..SHIP) tests passed!");
