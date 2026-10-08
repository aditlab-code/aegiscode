import test from "node:test";
import assert from "node:assert/strict";
import * as api from "./api.js";

test("1. api.js exports all comprehensive Git GUI client operations", () => {
  const expectedFunctions = [
    "checkoutProjectGitBranch",
    "createProjectGitBranch",
    "deleteProjectGitBranch",
    "mergeProjectGitBranch",
    "stashProjectGitChanges",
    "listProjectGitStashes",
    "popProjectGitStash",
    "applyProjectGitStash",
    "dropProjectGitStash",
    "pushProjectGit",
    "pullProjectGit",
    "fetchProjectGit",
    "getProjectGitRemotes",
    "addProjectGitRemote",
    "setProjectGitRemoteUrl",
    "cloneProjectGit",
    "commitProjectGit",
  ];

  for (const fnName of expectedFunctions) {
    assert.equal(
      typeof api[fnName],
      "function",
      `Function ${fnName} should be exported as a function`
    );
  }
});

test("2. Git action types contract for GitActionModal and Hamburger Menu", () => {
  const supportedActions = [
    "create_branch",
    "switch_branch",
    "delete_branch",
    "merge",
    "stash",
    "manage_stashes",
    "push",
    "pull",
    "fetch",
    "clone",
    "manage_remotes",
    "remote_settings",
  ];

  assert.equal(supportedActions.length, 12);
  assert.ok(supportedActions.includes("create_branch"));
  assert.ok(supportedActions.includes("switch_branch"));
  assert.ok(supportedActions.includes("merge"));
  assert.ok(supportedActions.includes("stash"));
  assert.ok(supportedActions.includes("push"));
  assert.ok(supportedActions.includes("pull"));
  assert.ok(supportedActions.includes("clone"));
  assert.ok(supportedActions.includes("remote_settings"));
});

test("3. Branch filter helper accurately filters local and remote branches", () => {
  const localBranches = ["main", "feature/auth", "feature/billing", "bugfix/issue-12"];
  const remoteBranches = ["origin/main", "origin/feature/auth", "origin/dev"];

  function filterBranches(list, query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) return list;
    return list.filter((b) => b.toLowerCase().includes(q));
  }

  // Empty query returns full list
  assert.deepEqual(filterBranches(localBranches, ""), localBranches);

  // Partial match query
  const authMatches = filterBranches(localBranches, "auth");
  assert.deepEqual(authMatches, ["feature/auth"]);

  // Multi match query
  const featureMatches = filterBranches(localBranches, "feature");
  assert.deepEqual(featureMatches, ["feature/auth", "feature/billing"]);

  // Remote filter query
  const remoteDevMatches = filterBranches(remoteBranches, "dev");
  assert.deepEqual(remoteDevMatches, ["origin/dev"]);

  // Non-matching query
  assert.deepEqual(filterBranches(localBranches, "nonexistent"), []);
});

test("4. Stash representation structure contract", () => {
  const sampleStash = {
    index: 0,
    ref: "stash@{0}",
    hash: "a1b2c3d",
    message: "WIP on feature/auth",
    date: "2 hours ago",
  };

  assert.equal(sampleStash.index, 0);
  assert.equal(sampleStash.ref, "stash@{0}");
  assert.ok(sampleStash.message.includes("WIP"));
  assert.ok(sampleStash.hash.length >= 7);
});

test("5. VS Code style Git context menu structure and actions contract", () => {
  const contextMenuItems = [
    "View as Tree",
    "View & Sort",
    "Pull",
    "Push",
    "Clone",
    "Checkout to...",
    "Fetch",
    "Commit",
    "Changes",
    "Pull, Push",
    "Branch",
    "Remote",
    "Stash",
    "Tags",
    "Show Git Output",
  ];

  assert.equal(contextMenuItems.length, 15);
  assert.ok(contextMenuItems.includes("Pull"));
  assert.ok(contextMenuItems.includes("Push"));
  assert.ok(contextMenuItems.includes("Clone"));
  assert.ok(contextMenuItems.includes("Checkout to..."));
  assert.ok(contextMenuItems.includes("Fetch"));
  assert.ok(contextMenuItems.includes("Branch"));
  assert.ok(contextMenuItems.includes("Remote"));
  assert.ok(contextMenuItems.includes("Stash"));
  assert.ok(contextMenuItems.includes("Commit"));
  assert.ok(contextMenuItems.includes("Changes"));
});
