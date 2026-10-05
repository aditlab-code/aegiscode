# AegisCode

### Autonomous AI Coding Agent & Studio Workbench

> **Fork Notice & Attribution:** AegisCode is developed as an independent product branching from the foundation created by **adigayung** in [adigayung/aether-agent](https://github.com/adigayung/aether-agent), licensed under the [MIT License](LICENSE). Core improvements are continuously contributed upstream, while AegisCode Studio and protective runtime features are maintained independently. Original upstream source remains available at `https://github.com/adigayung/aether-agent`.

**AegisCode gives an LLM the tools, project intelligence, and protective execution environment it needs to work on real software projects autonomously.**

```
AETHER = Hands
LLM    = Brain
```

The LLM remains the decision-maker. AETHER provides the hands: filesystem tools, terminal, project navigation, and a runtime that lets the model investigate, edit, run, and validate code over multiple rounds without human micromanagement.

---

## What is AETHER?

AETHER is a coding agent engine plus a workbench for running it. You describe a task in natural language; AETHER prepares context, streams the agent's reasoning, executes tools, and reports results.

Core idea:

```
User prompt
  → Task Preparation (context + advisory plan)
    → Agent Runtime (continuous loop)
      → LLM decides → Tool calls → Observations → LLM decides → ...
    → Validation / Result → Report
```

No heuristic "done" detector. The loop ends only when the LLM returns a final response without requesting a tool.

---

## How It Works

```
User
 │
 ├── Workbench (web UI — Modern AI-First IDE)
 │
 └── Consultant (read-only advisor)
       │
       ↓
     Task
       │
       ├── Queue      ─┐
       └── Parallel   ─┤
                       ↓
                 Agent Runtime
                       │
                ┌──────┼─────────┐
                ↓      ↓         ↓
              Tools  Project    LLM
                     Memory
```

Relationship of the memory layers:

```
Bible → WHAT   (knowledge about the project)
Map   → WHERE  (where code lives — navigation/lookup)
Skill → HOW    (how to do things — procedural guidance)
Tool  → ACTION (capability the LLM can invoke)
LLM   → DECISION
```

`Map` is a lookup mechanism (`atlas_query`, `rig_query`, `project_map_status`). It is not injected wholesale into the LLM context.

---

## Key Features

### Autonomous Agent

- Continuous Native Tool Calling loop — one conversation per task.
- LLM-driven tool selection (no hard-coded step order).
- Multi-round execution with retry, investigation, implementation, and validation.
- Plan (when present) is advisory only — the LLM decides actual tool order.
- Cooperative cancellation (`Stop` at a safe boundary).
- Activity phase telemetry (`planning` / `inspecting` / `editing` / `running` / `validating`) derived from real tool usage.

### Agent vs Consultant

```
Agent
→ execute / modify the project
→ read + write + run commands
→ can create / update / delete Skills

Consultant
→ inspect / investigate / analyze / propose
→ read-only against project source code
→ may read and update Project Bible via a curated tool
→ never gets write/edit/delete/move capabilities on source
```

Consultant reuses the same loop and tool infrastructure but with a curated read-only registry and a separate permission policy. It supports two workflow modes:

| Mode | Purpose | Retrieval bound (Map) |
|------|---------|-----------------------|
| `quick` | Fast Q&A, light investigation | lower (e.g. 3 Atlas + 3 RIG) |
| `investigate` | Deeper exploration | higher (e.g. 6 Atlas + 6 RIG) |

Mode controls which tools the LLM is offered and the prompt instructions — it is not just a prompt prefix. When the bound is reached, map tools are removed from the offer and the model is asked to answer from evidence already gathered.

Consultant can optionally include images (base64, bounded) — processed through the existing vision module — and can emit a Task Proposal:

````markdown
```task
Fix the login redirect bug by updating auth middleware...
```
````

The proposal can be sent to the Agent with one click via the existing task flow.

### Project Intelligence

Project-local, additive, and stored under `<project>/.aether/` — no new databases.

| Layer | Location | Purpose |
|-------|----------|---------| 
| **Bible** | `.aether/bible/` | Structured markdown knowledge (`architecture.md`, `conventions.md`, `facts.md`, `decisions.md`, `learnings.md`, `problems.md`, …) plus `index.md` manifest. Read as context; updated once per task (Agent) or explicitly via Consultant. |
| **Map** | `.aether/map/` | `atlas.json` (CODE ATLAS) + `rig.json` (MAP_CODE_RIG) + `*.meta.json` freshness metadata. Generated via vendored engines in `vendor/`. |
| **Environment** | `.aether/ENVIRONMENT.md` | OS / shell / runtime context — built once per session, injected on the first task. |
| **Log** | `.aether/log/<task_id>.log` | Append-only JSON Lines — source of truth for Task History, Activity, and Report. |

**Bible = WHAT, Map = WHERE, Skill = HOW, Tool = CAPABILITY.** Map provides navigation; the LLM looks up locations and then reads the actual files. Staleness is detected deterministically (SHA-256 over `.py` source), but regeneration is never automatic — the LLM/Agent decides when to call `refresh_project_map`.

Relevant tools: `project_map_status`, `atlas_query`, `rig_query`, `refresh_project_map` (Agent only; Consultant gets the first three).

### Skill System

Dynamic, progressive, and shared by Agent and Consultant.

```
skill_catalog
↓
LLM chooses 0 / 1 / N skill_ids
↓
load_skill(skill_id)  →  .aether/bible/skills/<skill_id>/skill.md
↓
load_skill_reference(skill_id, reference)  →  references/<reference> (on demand)
```

- **Dynamic IDs** — any `skill_id` matching `^[A-Za-z0-9._-]+$` (1–64 chars); directory names are not hard-coded.
- **Progressive loading** — catalog returns only lightweight metadata (`skill_id`, `name`, `description`, `scope`, `location`). Content is loaded only when the LLM asks for it.
- **References are optional** — loaded individually by path, never all at once.
- **Shared mechanism** — Agent and Consultant use the same `SkillStore` (`agent_ai.projects.skills` / `agent_ai.tools.skills`). No second storage, no duplicate loader.
- **Permissions differ**:
  - Read tools (`skill_catalog`, `load_skill`, `load_skill_reference`) — available to both.
  - Lifecycle tools (`create_skill`, `update_skill`, `delete_skill`) — **Agent only**, LLM-driven. Consultant remains read-only.
- **No automatic selector** — no keyword matcher, scoring, or heuristic. The LLM decides whether to create / update / delete a Skill.
- **Scope** — currently `project` (`project` is the only supported value today; the design is generic for future scopes).
- **Storage** — `SkillStore` with atomic writes, idempotent `ensure()`, and tolerant parsing (corrupt files are skipped, not crashed).

Skills are guidance/context, not a permission grant and not an auto-loaded context compressor.

### Provider & Model

Provider and model are configured independently.

- Provider types are registered in `agent_ai.providers.registry` (`ollama`, `deepseek`, `openrouter`, `openai`, `opencode`, `9router`, `custom` / OpenAI-compatible). Adding a provider means registering a class with a unique `name` — core never imports a concrete provider.
- **Configuration is stored in SQLite** (`data/aether.db`) via `agent_ai.llm_config.LLMConfigService`. The same database is used by the gateway launcher. Tables: `llm_provider_instances` and `llm_models`.
- Each **Provider Instance** points to an env-var name (`api_key_env`, e.g. `OPENROUTER_API_KEY`), not the secret value. The secret stays in `.env`; the DB stores only the variable name, base URL, and metadata.
- Each instance can have multiple **Models**. Selection is `Provider Instance → Model` (one instance, many models).
- **OpenAI-compatible / custom provider** is a first-class entry (`CustomOpenAIProvider`). Any base URL + API key + model string can be wired through it, including self-hosted OpenAI-compatible endpoints.
- **OpenCode Zen provider** (`OpenCodeProvider`) — built-in provider for [opencode.ai/zen](https://opencode.ai/docs/providers/#opencode-zen). Endpoint: `https://opencode.ai/zen/v1`. Supports Claude, GPT, Gemini, DeepSeek, and free model variants.
- Resolution at runtime uses `agent_ai.providers.factory.build_provider_from_config` — the same path for Agent and Consultant.
- No hard-coded "recommended" model list in the README; the architecture is provider-agnostic and the UI reads available providers/models from the service.

### Queue & Parallel Agent

AETHER executes tasks in two modes that coexist:

```
Execution
├── Queue      — serial / FIFO
└── Parallel   — immediate, concurrent
```

**Queue**

- Task joins the existing queue and waits for the global serial slot (1 execution slot).
- FIFO by `queue_order`; `Move Up / Down` reorders.
- `Disable` (`queue_state: disabled`) keeps a task from being scheduled without cancelling it.
- `Remove` is only for non-running tasks.

**Parallel**

- Task starts its own Agent immediately, without waiting for the queue slot.
- Multiple parallel tasks can run concurrently with each other and with the one queue task occupying the serial slot.
- Each task carries its own Provider + Model (no global override).
- There is no artificial limit on the number of parallel agents.

Queue and Parallel coexist — a parallel task never blocks the queue slot and a queue task never blocks parallel tasks.

**File Write Lock**

Parallel agents share an in-process lock on write tools to prevent simultaneous writes to the same file:

```
Agent A → write_file(example.py)
           ↓
         lock acquired
           ↓
         write
           ↓
        unlock

Agent B → write_file(example.py)
           ↓
        locked
           ↓
      tool error
           ↓
     LLM reads error → decides next step
```

- Applies to `write_file`, `edit_file`, `delete_file`, `move_file` (both paths for `move_file` are locked atomically).
- Read tools remain unrestricted.
- `run_command` is not part of the File Write Lock.
- The lock is temporary — held only for the duration of the write operation, not the whole task.
- Errors are returned through the existing tool error path; no new error channel. The LLM decides how to proceed (retry, pick another file, etc.).
- This is not absolute filesystem isolation — it is a cooperative in-process guard within the same runtime process.

### Modern IDE Workbench

Vue 3 + Vite frontend (`web/frontend`) and a thin Django gateway (`web/django_app`). No agent logic lives in the frontend. The UI follows a **VS Code-style AI-first IDE layout**:

```
┌────────────────────────────────────────────────────────────────────────┐
│  [⌘] AETHER WORKBENCH  ─ Workspace  [ ⌘K Command Palette ]            │
├──────┬─────────────────┬──────────────────────┬────────────────────────┤
│ ACT. │ LEFT SIDEBAR    │ CENTER CANVAS        │ RIGHT AI DRAWER        │
│ BAR  │ (200–450px)     │ Monaco Code Editor   │ (320–650px)            │
├──────┼─────────────────┼──────────────────────┼────────────────────────┤
│ 📁   │ File Explorer   │ [Tab] [Tab] [Tab]    │ Agent | Consultant     │
│ 🔀   │ Source Control  │ ─────────────────── │ Activity / Chat        │
│ ⏳   │ Task Queue      │ Code editor area     ├────────────────────────┤
│ ⚙️   │ Settings        ├──────────────────────┤                        │
│ 🌓   │ Theme Toggle    │ Bottom Dock (Ctrl+`) │                        │
│      │                 │ [Terminal][Logs]     │                        │
└──────┴─────────────────┴──────────────────────┴────────────────────────┘
│ STATUSBAR: Ln/Col | Language | Model | Provider | Theme | Version      │
└────────────────────────────────────────────────────────────────────────┘
```

**Layout components:**

| Component | Description |
|-----------|-------------|
| `AppActivityBar` | Left icon strip — switches between Explorer, Git, Queue, Settings, Theme |
| `AppLeftSidebar` | Draggable panel (200–450px) — File Explorer, Source Control, Task Queue |
| `WorkbenchView` | Center canvas — Monaco editor with multi-tab support |
| `AppRightDrawer` | Draggable AI panel (320–650px) — Agent Activity + Consultant Chat tabs |
| `AppBottomDock` | Collapsible bottom panel (`Ctrl+\``) — Interactive Terminal, Logs |
| `AppNavbar` | Top bar — workspace path, breadcrumbs, status chips |
| `AppFooter` | Statusbar — Ln/Col, language, provider/model, version |
| `AppCommandPalette` | Global command palette (`Ctrl+K`) — fuzzy search across commands |

**Responsive breakpoints:**

- `> 1280px` — Full 3-column layout (sidebar + editor + drawer)
- `900–1280px` — Compact: right drawer auto-collapses to floating overlay
- `< 900px` — Mobile: both sidebar and drawer become slide-out overlays

**Other workbench features:**

- **Task input** — Task Composer modal (task text + Provider Instance + Model + Execution mode + retrieval profile).
- **Multi-tab editor** — `EditorTabsService`: open multiple files simultaneously, tab lifecycle (open/close/activate/dirty state).
- **Editor settings** — `EditorSettingsPanel`: Monaco live code preview, auto-save, per-project settings with VS Code-style gear menu.
- **Light / Dark theme** — `ThemeService`: full light theme (`theme-light.css`) + wallpaper support (`Aether-dark.jpeg`, `Aether-light.jpeg`).
- **Agent Workbench** — Latest Task card, lifecycle progress (Planning → Completed), duration ticker, and unified Agent Activity timeline (tool calls, observations, phase changes) with compact vertical layout.
- **Consultant** — chat modal with quick/investigate mode, image attachments, and Task Proposal → Run with the same Provider/Model selectors.
- **Task History & Queue** — History reads from `.aether/log/` (persistent); Queue reflects `GET /api/tasks/queue` (pending/running/disabled). Both are the same global queue the backend uses.
- **Changes & Explorer** — live filesystem changes (diff, additions/deletions) and a file tree bound to the active project root. Editor is Monaco.
- **Task status** — `prepared` / `running` / `queued` / `validating` / `completed` / `failed` / `cancelled`.
- **Stop confirmation** — cooperative cancellation via confirmation dialog.

### Interactive Terminal

The Bottom Dock hosts a fully interactive terminal (`TerminalView`):

```
Features:
├── Shell input with prompt (run commands from workspace root)
├── Command history (↑/↓ navigation, last 50 entries)
├── Ctrl+C → abort running command (SSE abort signal)
├── Ctrl+Shift+C → copy selected output
├── Ctrl+Shift+V → paste into input
├── ANSI output rendering (ok / err / warn / input line classes)
└── Read-only mode for passive agent output viewing
```

Backend streams command output via SSE. The LLM's `run_command` output and user-initiated commands share the same output channel.

### Telemetry

Available on the task card and via Activity / SSE events. All values are derived from existing lifecycle events, not estimates:

```
Provider      — from provider_request / provider_response
Model         — from the same events
Execution     — Queue / Parallel (from TaskRecord)
Round         — LLM invocation count (provider_request count)
LLM Rounds    — same as Round
Tool Calls    — tool_called count
Tokens        — provider-reported usage (total / prompt+completion / prompt_eval+eval); "—" if not reported
Duration      — from task_started → task_completed/failed/cancelled timestamps
Status        — completed / failed / cancelled / running / queued
```

No local tokenizer estimate is used for Tokens.

### Planning Module

Deterministic, provider-agnostic task planner (`agent_ai.planning`):

```
TaskPlanner.create_plan(prompt, context)
  → classify task type (fix / add / refactor / test / doc)
  → generate ordered PlanSteps (objective, dependencies, prerequisites, expected_outcome)
  → TaskPlan (advisory — not executed directly)

Replanner.replan(plan, observation)
  → triggered when step execution deviates from expectation
  → adapts remaining steps without losing completed progress
```

The plan is advisory only — the LLM Agent decides the actual execution order.

### Reliability & Recovery

`agent_ai.reliability` — observes runtime events and decides recovery actions:

```
ReliabilityManager
├── observe(event)         → record failures / tool errors / provider errors
├── record_progress(snap)  → snapshot current execution state
├── should_retry(…)        → bool: retry eligible?
├── should_recover(…)      → bool: recovery needed?
├── should_stop(…)         → bool: must abort?
└── decide(…)              → ReliabilityDecision (retry / recover / stop / fail)
```

`RetryController` implements bounded exponential backoff. `Detector` classifies error types (rate limit, network, provider, tool).

### Task Resume

`agent_ai.resume` — safe task continuation mechanism:

- Reconstructs execution state from `TaskState` snapshot + `ExecutionEvent` list + `ChangeTracker` + `GitRepositoryFacade` (optional).
- Prevents double-resume (idempotent).
- Detects workspace divergence via file fingerprint comparison.
- Persistence-ready: all inputs are serializable (no in-memory-only state).
- No agent logic — purely a state analysis layer.

### Model Routing

`agent_ai.routing` — deterministic provider/model selection **before** task execution:

```
RoutingRequest
  → TaskClassifier (complexity: simple / moderate / complex / critical)
  → RoutingRegistry (capability candidates from ModelCapabilityRegistry)
  → elimination: required capabilities, context window, availability
  → deterministic scoring
  → RoutingDecision (selected candidate + rationale / failure reason)
```

Does not use an LLM to choose a model. Same input → same decision. No provider-specific branching.

### MCP — Model Context Protocol

`agent_ai.mcp` — standard MCP adapter layer:

```
MCPClient (abstract interface)
  → connect() / list_tools() / call_tool(name, args) / close()

MCPAdapter
  → bridges MCP tools into AETHER's ToolRegistry
  → dynamic tool discovery on session init

Transport layer
  → stdio (local subprocess) / HTTP / SSE
```

- Fully optional — Agent Core runs without MCP; module is not imported by default.
- Config: `.aether/mcp.json` (compatible with Claude Desktop / Cursor format).
- `InMemoryMCPClient` provided for testing/verification.

---

## Security & Permissions

- **Workspace boundary** — every filesystem and terminal tool resolves paths with `_resolve_within_root` and `cwd = project root`. Traversal and symlink escape are denied. `shell=False` for commands.
- **Permission layer** (`agent_ai.permission`) — `PermissionPolicy` classifies actions (`READ_ONLY`, `WORKSPACE_WRITE`, `DELETE_MOVE`, `COMMAND_EXECUTION`, …) and decides `ALLOW / DENY / REQUIRE_APPROVAL`. Default is `ALLOW` when disabled (backward-compatible).
- **Agent vs Consultant boundary** — Consultant gets `read_only: ALLOW`, `workspace_write: DENY`, `delete_move: DENY`, `external_network: DENY`. Its registry is also curated (no write/move/delete tools), so the boundary is layered: policy + registry + retrieval bound.
- **Skill read tools are not a bypass** — loading a skill does not grant write capability. Lifecycle tools are only registered on the Agent registry.
- **Secrets** — API keys stay in `.env`. SQLite holds only `api_key_env` names. Responses mask secrets (`sk-o***…`).
- **No absolute claims** — these are project-bound, best-effort guards within the workspace root. They are not a sandbox or cross-process isolation boundary.

---

## Architecture

```mermaid
flowchart TD
  U[User] --> W[Workbench - Modern IDE]
  U --> C[Consultant]
  C --> T[Task]
  T --> Q[Queue - serial FIFO]
  T --> P[Parallel - concurrent]
  Q --> R[Agent Runtime]
  P --> R
  R --> TL[Tools]
  R --> PM[Project Memory\nBible / Map / Skills]
  R --> LLM[LLM Provider]
  R --> PL[Planning Module]
  R --> RL[Reliability Manager]
  R --> MCP[MCP Adapter]
```

Runtime per task:

```
PreparedTask → AgentRuntime → AgentOrchestrator.run_continuous_loop
               → Provider.generate → LLMResponse (tool_calls / final)
               → ToolExecutor → ToolRegistry
               → observation (role: tool) → Provider.generate → ...
               → DONE / FAILED / CANCELLED
```

---

## Project Structure

```
.
├── src/agent_ai/            # Core library
│   ├── browser/             # Browser automation
│   ├── capabilities/        # Capability declarations
│   ├── codeindex/           # Code indexer
│   ├── config/              # Settings (python-dotenv)
│   ├── consultant/          # Consultant service, guard, policy, prompt
│   ├── context/             # Context builder
│   ├── core/                # Orchestrator, executor, cancel, observability
│   ├── extensions/          # Extension system (loader, manager, installer)
│   ├── git/                 # GitRepositoryFacade (status, diff, commits)
│   ├── llm_config/          # Provider Instance / Model service (SQLite)
│   ├── mcp/                 # MCP client adapter (stdio / SSE transport)
│   ├── permission/          # Permission policy & classifier
│   ├── planning/            # TaskPlanner + Replanner (deterministic)
│   ├── projects/            # AetherProjectStore, Bible, Map, Skills, discovery
│   ├── providers/           # BaseProvider + ollama / openai_compatible / opencode / custom / …
│   ├── reliability/         # ReliabilityManager, RetryController, Detector
│   ├── resume/              # TaskResumer (safe task continuation)
│   ├── routing/             # ModelRouter, TaskClassifier (deterministic selection)
│   ├── runtime/             # AgentRuntime, activity, models
│   ├── task/                # Task preparation
│   ├── tools/               # Filesystem, workspace, terminal, project_map, skills
│   └── validation/          # Validation runner
├── web/
│   ├── django_app/          # Thin HTTP gateway (api/services.py, api/views.py)
│   │   ├── api/             # Execution bridge, streaming (SSE), project_store
│   │   └── config/          # Django settings
│   └── frontend/            # Vue 3 + Vite workbench
│       └── src/
│           ├── components/  # UI components (AgentActivity, TerminalView, …)
│           │   ├── layout/  # AppActivityBar, AppLeftSidebar, AppRightDrawer, …
│           │   └── ui/      # AppCommandPalette, AppModal, AppToggle, …
│           ├── pages/       # WorkbenchView, SettingsOverlay
│           ├── services/    # commandPaletteService, editorTabsService, themeService, …
│           └── styles/      # Modular CSS (base, components, layout, themes)
├── scripts/                 # install_aether.py, check_*.py verifiers
├── tests/                   # Project tests
├── vendor/                  # Vendored engines: CODE_ATLAS, MAP_CODE_RIG
├── data/                    # SQLite DB (data/aether.db), version.json
├── projects/                # Example / registered project roots
├── run.bat                  # Self-bootstrapping launcher (Windows)
└── run.sh                   # Self-bootstrapping launcher (macOS/Linux)
```

`.aether` layout (created inside the active project root):

```
.aether/
├── bible/
│   ├── index.md
│   ├── architecture.md
│   ├── conventions.md
│   ├── decisions.md
│   ├── facts.md
│   ├── learnings.md
│   ├── problems.md
│   └── skills/
│       └── <skill_id>/
│           ├── skill.md
│           └── references/     # optional
├── map/
│   ├── atlas.json
│   ├── rig.json
│   ├── atlas.meta.json
│   └── rig.meta.json
├── log/
│   └── <task_id>.log
├── mcp.json                    # optional — MCP server config
├── github/                     # optional — GitHub backup config (DPAPI on Windows)
└── ENVIRONMENT.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- Node.js (for frontend build — installed automatically by `run.bat` / `scripts/install_aether.py`; manual install only needed for frontend dev)

### 1. Get the code

```bash
git clone https://github.com/aditlab-code/aether.git
cd aether
```

Original upstream (read-only reference): `https://github.com/adigayung/aether-agent`.

Or just download and double-click `run.bat` (Windows) / `run.sh` (macOS/Linux) — it will clone to `aether-agent/` next to the launcher if no installation is found.

### 2. Configure providers

Copy the template and fill in what you need:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

`LLMConfigService` is the source of truth for Provider Instance → Model. You can configure providers two ways:

- **Via the Workbench** — open Settings after first launch: add a Provider Instance (type + base URL + `api_key_env` name), add Models, and set API keys (written to `.env` masked in responses).
- **Via `.env` directly** — set `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENCODE_API_KEY`, `OLLAMA_HOST`, etc. These are used as fallbacks and for the env-var names that instances point to.

Context budgets are optional:

```ini
CONTEXT_KNOWLEDGE_MAX_TOKENS=8000
CONTEXT_MAX_TOKENS=16000
```

### 3. Run AETHER

Double-click `run.bat` (Windows) / `run.sh` (macOS/Linux), or from a terminal:

```bash
python scripts/install_aether.py
```

What it does (idempotent — safe to run repeatedly):

1. Verifies Python and Git
2. Creates `venv/` and installs `requirements.txt`
3. Ensures `.env` exists
4. Builds `web/frontend/dist` if missing (`vite build`)
5. Starts the gateway on the port from `data/settings.json` (`port`) and opens a browser

The **server port is read from `data/settings.json`** (`port`, e.g. `"port": 8478`);
`8000` is only the fallback when the file does not set `port`. If the configured
port is already in use, the launcher automatically falls back to the next free
port, and the printed/opened URL uses the port actually used. Set `AETHER_PORT`
to override explicitly.

Useful flags:

```bash
python scripts/install_aether.py --check          # verify prerequisites only
python scripts/install_aether.py --no-launch      # setup without starting server
python scripts/install_aether.py --simulate       # dry-run (no downloads / writes)
python scripts/install_aether.py --port 8478      # explicit port (overrides settings)
```

Manual alternative (after `venv` is ready):

```bash
# Windows
venv\Scripts\activate
python web\django_app\manage.py runserver 127.0.0.1:8478

# macOS / Linux
source venv/bin/activate
python web/django_app/manage.py runserver 127.0.0.1:8478
```

Deployment template: see `deployment.template` (checked in without secrets) for the environment variables consumed in a deployment. The verifier `scripts/check_packaging.py` ensures it contains no real API keys.

### 4. Create a task

1. Open the URL printed by the launcher (e.g. `http://127.0.0.1:8478/`).
2. Pick or create a Project in the launcher.
3. Add a Provider Instance + Model in Settings if none exists.
4. Click the input bar → Task Composer → write the task, pick **Provider**, **Model**, and **Execution** (`Queue` or `Parallel`), then Send.

### 5. Queue vs Parallel

- **Queue** — task waits for the serial slot (FIFO). Use for edits to the same area.
- **Parallel** — task starts immediately and can run alongside others. Use for independent areas.

Both appear in the global Task Queue; History is the persistent `.aether/log/` archive.

---

## Example Workflows

Single task:

```
User:
  "Fix authentication bug — login redirect drops session after OAuth callback"

AETHER:
  → reads Project Bible / Map
  → searches and inspects auth code
  → edits the relevant file(s)
  → runs validation / tests
  → reports the result with a diff summary
```

Parallel:

```
Task A → "Add calculator module (src/calc/*)\"   → Parallel
Task B → "Restyle login page (web/login.html)"  → Parallel

— Both start immediately.
— Each uses its own Provider + Model.
— File Write Lock prevents them from clobbering the same file;
  independent files proceed without contention.
```

Consultant → Agent:

```
Consultant (investigate):
  "Where is session handled and what could cause the drop?"

Consultant → Task Proposal (```task fence)

User clicks Run Task → task is created via the normal Queue/Parallel path.
```

These are conceptual examples, not benchmarks.

---

## Design Principles

- LLM remains the decision maker — no heuristic auto-selector or forced completion.
- Provider / tool agnostic — core never imports a concrete provider; tools are registered generically.
- Project-first — all writes are project-local (`.aether/` inside the target root).
- Modular — gateway, runtime, tools, and project intelligence are thin facades over existing components.
- Progressive disclosure — catalog before content; references on demand; no bulk injection.
- Avoid unnecessary reads / tool calls — duplicate reads return `already_available` / `already_read` / `already_searched` and the agent is expected to use what it already has.
- No heuristic stop — the loop ends on the LLM's final response.
- No unnecessary context compression — `compression.enabled` stays `false`; no automatic truncation.
- Agent and Consultant separation — different registries, different permission policies, same loop infrastructure.
- YAGNI — implement the simplest solution for the stated requirement; no premature abstractions.

---

## Extension System

**Extension = capability package for AETHER**

AETHER can be extended by installing *extensions* – self‑contained Python packages that provide additional capabilities such as new tools, UI components, services, or storage back‑ends. The system consists of:

* **Directory layout** – extensions live under `<AETHER_ROOT>/Extension/`. Each extension is a normal Python package containing a `manifest.json` and `extension.py` which defines a subclass of `agent_ai.extensions.Extension`.
* **Manifest** – JSON file with required fields: `id`, `name`, `version`, `description`, `api_version`. Validated on load.
* **Discovery & loading** – at startup `ExtensionLoader` scans the extensions directory, validates manifests, imports the module, and creates an `Extension` instance.
* **Registration** – `extension.register(context)` is called. `ExtensionContext` exposes ten facades: `tools`, `skills`, `knowledge`, `config`, `services`, `providers`, `resources`, `hooks`, `commands`, `ui`, `storage`.
* **Lifecycle** – `ExtensionManager.enable(id)` / `disable(id)` flip the flag, invoke `on_enable` / `on_disable` hooks, and activate/deactivate all capabilities including `ToolRegistry` removal.
* **Install** – `ExtensionManager.install(repository_url)` clones, validates, and registers the extension.
* **Update** – `ExtensionManager.update(id, url)` validates the new version, backs up the old one, swaps atomically, and restores on failure.
* **Uninstall** – `ExtensionManager.uninstall(id)` disables, runs hooks, removes capabilities, and deletes the source folder.

```python
from agent_ai.extensions.manager import create_installer

installer = create_installer()
status = installer.install('https://github.com/example/myextension.git')
installer.disable('myorg.myextension')
installer.enable('myorg.myextension')
installer.update('myorg.myextension', 'https://github.com/example/myextension.git')
installer.uninstall('myorg.myextension')
```

All operations are safe: failures during install or update roll back any partially registered capabilities.

---

## Roadmap

### Implemented

```
Implemented
├── Autonomous Agent (continuous Native Tool Calling loop)
├── Consultant (quick / investigate, read-only, Task Proposals)
├── Project Intelligence (Bible / Atlas / RIG / Maps with freshness)
├── Skill System (catalog → load_skill → load_skill_reference, Agent lifecycle)
├── Provider & Model architecture (instances + models in SQLite)
│   └── OpenCode Zen provider (opencode.ai/zen, OpenAI-compatible)
├── Queue (serial FIFO) + Parallel Agent (concurrent, File Write Lock)
├── Modern IDE Workbench (VS Code-style layout, Activity Bar, Left Sidebar,
│   Right AI Drawer, Bottom Dock, Command Palette, Editor Tabs)
├── Interactive Terminal (shell input, command history, SSE streaming, Ctrl+C abort)
├── Light / Dark Theme + Wallpaper system
├── Telemetry (provider/model/round/tool calls/tokens/duration/status)
├── Permission & workspace boundary
├── Extension System (full lifecycle: install, enable, disable, update, uninstall)
├── Planning Module (deterministic TaskPlanner + Replanner)
├── Reliability Manager (error observation + retry/recovery/stop decisions)
├── Task Resume (safe idempotent continuation with workspace divergence detection)
├── Model Routing (deterministic provider/model selection before execution)
└── MCP — Model Context Protocol (client interface + adapter + transport layer)
```

### Future

```
Future
├── God Mode / Multi-Agent
├── Git UI Panel (REST endpoints + badge explorer + Monaco Diff Editor)
│   (backend GitRepositoryFacade already implemented)
├── Skill & Knowledge UI Editor (CRUD panel for .aether/skills/ and Bible)
├── Live Server Tab (dev server supervisor + iframe preview)
├── Human-in-the-Loop Guardrails & Snapshot Rollback
├── Local-First Semantic Code Search & RAG (sqlite-vec / fastembed)
└── Desktop App (Tauri v2 + Rust + Python sidecar)
```

---

## License

MIT — see [LICENSE](LICENSE).

- Original source: [adigayung/aether-agent](https://github.com/adigayung/aether-agent) — Copyright (c) 2026 adigayung
- Modifications: Copyright (c) 2026 aditlab-code
- AegisCode Studio & Aegis Agent: Copyright (c) 2026 AegisCode Authors
