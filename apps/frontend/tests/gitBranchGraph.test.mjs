import test from "node:test";
import assert from "node:assert/strict";
import { parseGitRefs, computeGitGraph, GRAPH_PALETTE } from "../src/services/gitGraphLayout.js";

test("1. parseGitRefs: extracts HEAD, branch, remote, and tag badges correctly", () => {
  const rawRefs = ["HEAD -> main", "origin/main", "origin/feature-1", "tag: v1.0.0"];
  const badges = parseGitRefs(rawRefs);

  assert.equal(badges.length, 5);
  assert.deepEqual(badges[0], { type: "head", name: "HEAD", label: "HEAD" });
  assert.deepEqual(badges[1], { type: "branch", name: "main", label: "main" });
  assert.deepEqual(badges[2], { type: "remote", name: "origin/main", label: "origin/main" });
  assert.deepEqual(badges[3], { type: "remote", name: "origin/feature-1", label: "origin/feature-1" });
  assert.deepEqual(badges[4], { type: "tag", name: "v1.0.0", label: "v1.0.0" });
});

test("2. parseGitRefs: handles comma-separated string format", () => {
  const rawStr = "HEAD -> master, origin/master, tag: beta-1";
  const badges = parseGitRefs(rawStr);

  assert.equal(badges.length, 4);
  assert.equal(badges[0].type, "head");
  assert.equal(badges[1].name, "master");
  assert.equal(badges[2].type, "remote");
  assert.equal(badges[3].type, "tag");
});

test("3. computeGitGraph: assigns linear commits to lane 0 with vertical track continuity", () => {
  const commits = [
    { hash: "c3", parents: ["c2"], subject: "Third commit", refs: ["HEAD -> main"] },
    { hash: "c2", parents: ["c1"], subject: "Second commit" },
    { hash: "c1", parents: [], subject: "Initial commit" },
  ];

  const graph = computeGitGraph(commits, { laneWidth: 16, rowHeight: 40 });

  assert.equal(graph.length, 3);
  assert.equal(graph[0].lane, 0);
  assert.equal(graph[1].lane, 0);
  assert.equal(graph[2].lane, 0);

  // Colors match palette
  assert.equal(graph[0].color, GRAPH_PALETTE[0]);
  assert.equal(graph[0].cx, 12);
  assert.equal(graph[0].cy, 20);

  // Check ref badges
  assert.equal(graph[0].parsedRefs.length, 2);
  assert.equal(graph[0].parsedRefs[0].name, "HEAD");
  assert.equal(graph[0].parsedRefs[1].name, "main");
});

test("4. computeGitGraph: handles branching and merging with multiple lanes", () => {
  const commits = [
    // Merge commit
    { hash: "c4", parents: ["c3", "c2"], subject: "Merge feature" },
    // Main branch commit
    { hash: "c3", parents: ["c1"], subject: "Main work" },
    // Feature branch commit
    { hash: "c2", parents: ["c1"], subject: "Feature work" },
    // Root commit
    { hash: "c1", parents: [], subject: "Root" },
  ];

  const graph = computeGitGraph(commits, { laneWidth: 16, rowHeight: 40 });
  assert.equal(graph.length, 4);

  // Check that secondary parent occupies lane 1
  assert.equal(graph[0].lane, 0);
  // Merge track is generated
  const mergeTracks = graph[0].tracks.filter((t) => t.type === "merge");
  assert.equal(mergeTracks.length, 1);
  assert.ok(mergeTracks[0].d.includes("C "));
});

test("5. computeGitGraph: handles empty or invalid commits safely", () => {
  assert.deepEqual(computeGitGraph([]), []);
  assert.deepEqual(computeGitGraph(null), []);
  assert.deepEqual(computeGitGraph(undefined), []);
});
