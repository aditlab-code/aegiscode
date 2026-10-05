import assert from "node:assert/strict";
import test from "node:test";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createSSRApp } from "vue";
import { renderToString } from "@vue/server-renderer";

import {
  PROMPT_TEMPLATES,
  filterTemplates,
  parseAutocompleteTrigger,
  applySuggestion,
  createHistoryManager,
  usePromptAutocomplete,
} from "./services/promptSuggestionService.js";

import {
  getCachedFiles,
  setCachedFiles,
  invalidateFileCache,
} from "./services/fileCacheService.js";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

// Start headless Vite server for SSR loading of Vue SFCs
const vite = await createServer({
  root: frontendRoot,
  server: { middlewareMode: true },
  appType: "custom",
});

async function loadComponent(relPath) {
  const mod = await vite.ssrLoadModule(relPath);
  return mod.default;
}

// -----------------------------------------------------------------------------
// Test 1: parseAutocompleteTrigger detects @mentions and /templates
// -----------------------------------------------------------------------------
test("1. parseAutocompleteTrigger: detects @mentions and /templates with boundary validation", () => {
  // @ at start of input
  let t = parseAutocompleteTrigger("@", 1);
  assert.equal(t.active, true);
  assert.equal(t.type, "mention");
  assert.equal(t.query, "");
  assert.equal(t.start, 0);
  assert.equal(t.end, 1);

  // @with path query
  t = parseAutocompleteTrigger("Inspect @src/components/Task", 28);
  assert.equal(t.active, true);
  assert.equal(t.type, "mention");
  assert.equal(t.query, "src/components/Task");
  assert.equal(t.start, 8);

  // @preceded by bracket or paren
  t = parseAutocompleteTrigger("check (@FileExplorer", 20);
  assert.equal(t.active, true);
  assert.equal(t.type, "mention");
  assert.equal(t.query, "FileExplorer");

  // Email address should NOT trigger mention
  t = parseAutocompleteTrigger("user@example.com", 16);
  assert.equal(t.active, false);

  // Mention with whitespace in query should NOT trigger
  t = parseAutocompleteTrigger("@some file here", 15);
  assert.equal(t.active, false);

  // /template at start of input
  t = parseAutocompleteTrigger("/fix", 4);
  assert.equal(t.active, true);
  assert.equal(t.type, "template");
  assert.equal(t.query, "fix");
  assert.equal(t.start, 0);

  // /template after newline
  t = parseAutocompleteTrigger("hello world\n/refactor", 21);
  assert.equal(t.active, true);
  assert.equal(t.type, "template");
  assert.equal(t.query, "refactor");

  // File path with slash should NOT trigger template if preceded by alphanumeric
  t = parseAutocompleteTrigger("path/to/file", 7);
  assert.equal(t.active, false);

  // Invalid input handling
  assert.equal(parseAutocompleteTrigger(null, 0).active, false);
  assert.equal(parseAutocompleteTrigger("", 0).active, false);
});

// -----------------------------------------------------------------------------
// Test 2: filterTemplates filters prompt templates by id, command, and description
// -----------------------------------------------------------------------------
test("2. filterTemplates: filters templates by query", () => {
  assert.equal(PROMPT_TEMPLATES.length, 4);

  // Empty query returns all templates
  assert.equal(filterTemplates("").length, 4);
  assert.equal(filterTemplates("/").length, 4);

  // Specific query
  const fix = filterTemplates("fix");
  assert.equal(fix.length, 1);
  assert.equal(fix[0].command, "/fix");

  const testT = filterTemplates("/test");
  assert.equal(testT.length, 1);
  assert.equal(testT[0].id, "test");

  const audit = filterTemplates("audit");
  assert.equal(audit.length, 1);
  assert.equal(audit[0].command, "/audit");

  const refactor = filterTemplates("simplify");
  assert.equal(refactor.length, 1);
  assert.equal(refactor[0].id, "refactor");

  // Unknown query returns empty
  assert.equal(filterTemplates("unknown_cmd").length, 0);
});

// -----------------------------------------------------------------------------
// Test 3: applySuggestion replaces triggers and calculates new cursor position
// -----------------------------------------------------------------------------
test("3. applySuggestion: replaces triggers and computes cursor position", () => {
  // Replace mention
  const triggerMention = {
    start: 7,
    end: 12,
    type: "mention",
  };
  const res1 = applySuggestion("Please @Task and check", triggerMention, "src/components/TaskComposer.vue");
  assert.equal(res1.newText, "Please @src/components/TaskComposer.vue and check");
  assert.equal(res1.newCursorPos, 7 + "@src/components/TaskComposer.vue ".length);

  // Replace template
  const triggerTemplate = {
    start: 0,
    end: 4,
    type: "template",
  };
  const res2 = applySuggestion("/fix", triggerTemplate, PROMPT_TEMPLATES[0]);
  assert.equal(res2.newText, PROMPT_TEMPLATES[0].template);
  assert.equal(res2.newCursorPos, PROMPT_TEMPLATES[0].template.length);
});

// -----------------------------------------------------------------------------
// Test 4: createHistoryManager handles prompt history & draft preservation
// -----------------------------------------------------------------------------
test("4. createHistoryManager: push, navigate up/down, draft restoration, and dedup", () => {
  const hm = createHistoryManager({ storageKey: "test_history", maxEntries: 5 });

  hm.push("first task");
  hm.push("second task");
  hm.push("third task");

  // Deduplicate consecutive
  hm.push("third task");
  assert.equal(hm.getHistory().length, 3);
  assert.deepEqual(hm.getHistory(), ["third task", "second task", "first task"]);

  // Navigate Up from unsaved draft "my draft"
  const up1 = hm.navigate("up", "my draft");
  assert.equal(up1, "third task");

  const up2 = hm.navigate("up");
  assert.equal(up2, "second task");

  const up3 = hm.navigate("up");
  assert.equal(up3, "first task");

  // Reached oldest: stays at first task
  const up4 = hm.navigate("up");
  assert.equal(up4, "first task");

  // Navigate Down
  const down1 = hm.navigate("down");
  assert.equal(down1, "second task");

  const down2 = hm.navigate("down");
  assert.equal(down2, "third task");

  // Reached bottom: restores unsaved draft
  const down3 = hm.navigate("down");
  assert.equal(down3, "my draft");

  // Navigate Down past bottom returns null
  const down4 = hm.navigate("down");
  assert.equal(down4, null);

  // Test seedHistory with past task objects, strings, and duplicate rejection
  hm.seedHistory([
    { task: "seeded task from past" },
    "another seeded prompt",
    "third task", // duplicate should be ignored
  ]);
  assert.equal(hm.getHistory().length, 5);
  assert.deepEqual(hm.getHistory(), [
    "third task",
    "second task",
    "first task",
    "seeded task from past",
    "another seeded prompt",
  ]);
});

// -----------------------------------------------------------------------------
// Test 5: fileCacheService stores and invalidates workspace files
// -----------------------------------------------------------------------------
test("5. fileCacheService: setCachedFiles, getCachedFiles, invalidateFileCache", () => {
  invalidateFileCache();
  assert.deepEqual(getCachedFiles(), []);

  setCachedFiles(["src/App.vue", "src/main.js", "package.json"]);
  assert.equal(getCachedFiles().length, 3);
  assert.ok(getCachedFiles().includes("src/App.vue"));

  invalidateFileCache();
  assert.deepEqual(getCachedFiles(), []);
});

// -----------------------------------------------------------------------------
// Test 6: usePromptAutocomplete composable methods and keydown handling
// -----------------------------------------------------------------------------
test("6. usePromptAutocomplete: trigger updates, popover state, and keyboard actions", async () => {
  setCachedFiles(["web/frontend/src/App.vue", "web/frontend/src/components/TaskComposer.vue"]);

  let updatedText = "";
  const auto = usePromptAutocomplete({
    storageKey: "test_auto",
    onUpdateText: (t) => {
      updatedText = t;
    },
  });

  // Initial state
  assert.equal(auto.popoverVisible.value, false);

  // Update suggestions on mention query "@Task"
  await auto.updateSuggestions("Please inspect @Task", 20);
  assert.equal(auto.popoverVisible.value, true);
  assert.equal(auto.popoverType.value, "mention");
  assert.equal(auto.popoverItems.value.length, 1);
  assert.equal(auto.popoverItems.value[0], "web/frontend/src/components/TaskComposer.vue");

  // Down arrow moves selection
  const downRes = auto.handleKeydown({ key: "ArrowDown", preventDefault: () => {} }, "Please inspect @Task", null);
  assert.equal(downRes.handled, true);

  // Escape closes popover
  const escRes = auto.handleKeydown({ key: "Escape", preventDefault: () => {} }, "Please inspect @Task", null);
  assert.equal(escRes.handled, true);
  assert.equal(auto.popoverVisible.value, false);

  // Template suggestions on "/fix"
  await auto.updateSuggestions("/fix", 4);
  assert.equal(auto.popoverVisible.value, true);
  assert.equal(auto.popoverType.value, "template");
  assert.equal(auto.popoverItems.value.length, 1);

  // Enter inserts template
  const enterRes = auto.handleKeydown({ key: "Enter", preventDefault: () => {} }, "/fix", null);
  assert.equal(enterRes.handled, true);
  assert.equal(auto.popoverVisible.value, false);
  assert.ok(updatedText.startsWith("Fix the following issue: "));
});

// -----------------------------------------------------------------------------
// Test 7: PromptAutocompletePopover SSR compilation and rendering
// -----------------------------------------------------------------------------
test("7. PromptAutocompletePopover: SSR compilation and rendering", async () => {
  const PopoverComp = await loadComponent("/src/components/ui/PromptAutocompletePopover.vue");
  assert.ok(PopoverComp, "PromptAutocompletePopover component exports default");

  // Render mention variant
  const appMention = createSSRApp(PopoverComp, {
    visible: true,
    type: "mention",
    items: ["src/components/TaskComposer.vue", "src/App.vue"],
    selectedIndex: 0,
  });
  const htmlMention = await renderToString(appMention);
  assert.ok(htmlMention.includes("Mention File"), "Displays Mention File title");
  assert.ok(htmlMention.includes("TaskComposer.vue"), "Displays file name");
  assert.ok(htmlMention.includes("src/components"), "Displays directory path");

  // Render template variant with placement="bottom"
  const appTemplate = createSSRApp(PopoverComp, {
    visible: true,
    type: "template",
    items: PROMPT_TEMPLATES,
    selectedIndex: 1,
    placement: "bottom",
  });
  const htmlTemplate = await renderToString(appTemplate);
  assert.ok(htmlTemplate.includes("placement-bottom"), "Has placement-bottom class");
  assert.ok(htmlTemplate.includes("Prompt Templates"), "Displays Prompt Templates title");
  assert.ok(htmlTemplate.includes("/fix"), "Displays /fix command");
  assert.ok(htmlTemplate.includes("/test"), "Displays /test command");
  assert.ok(htmlTemplate.includes("/audit"), "Displays /audit command");
  assert.ok(htmlTemplate.includes("/refactor"), "Displays /refactor command");

  // Render default placement (top)
  assert.ok(htmlMention.includes("placement-top"), "Has placement-top class by default");
});

test.after(async () => {
  await vite.close();
  console.log("[OK] promptAutocomplete: All 7 test cases passed cleanly.");
});
