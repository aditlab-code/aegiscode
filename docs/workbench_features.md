# AETHER Workbench IDE Features & Runtime Guardrails

This document describes the modern AI-first IDE capabilities, interactive subsystems, and execution guardrails implemented across the **AETHER Engineering Workbench** (`web/frontend` and `web/django_app`).

---

## 1. Background Execution & Assistant Guardrail Architecture

To ensure uninterrupted autonomous task execution and long-running consultant reasoning, the workbench employs a **Decoupled Execution & Persistent View Retention** model:

```mermaid
graph TD
    subgraph UI ["Workbench Layout (WorkbenchView.vue)"]
        Navbar["AppNavbar (Top Header)"]
        Drawer["AppRightDrawer (v-show Persistent Retention)"]
        Chat["ConsultantChat / AgentActivity"]
        Toast["Floating Completion Toast (wb-bg-toast)"]
    end

    subgraph Backend ["AETHER Runtime & Gateway"]
        TaskQueue["Task Queue & Execution Loop"]
        ConsultantService["Consultant Reasoning Service"]
        SSE["SSE / HTTP Streaming Connection"]
    end

    Drawer --> Chat
    Chat <--> SSE
    SSE <--> TaskQueue
    SSE <--> ConsultantService

    Drawer -. "Drawer Collapsed (v-show=false)" .-> Navbar
    Navbar -->|"Shows 'AI Working…' Pulsing Pill"| User["Developer / User"]
    TaskQueue -->|"Task Complete / Failed"| Toast
    Toast -->|"Click 'Open' Action"| Drawer
```

### 1.1 Persistent View Retention (`v-show`)
- The AI Assistant column in [`WorkbenchView.vue`](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/web/frontend/src/pages/WorkbenchView.vue) is preserved in the DOM via `v-show="assistantVisible"`.
- Closing or toggling the assistant drawer (via `✕`, `Cmd+J`, `Ctrl+B`, or responsive breakpoint collapse) hides the container with `display: none;` without destroying the component instance.
- **Invariants Preserved**:
  - In-flight `consult(...)` promises and agent polling loops continue unaffected.
  - Active chat history, tool calls, and scroll positions remain intact in memory.
  - Re-opening the assistant immediately surfaces current progress without reloading.

### 1.2 Top Navigation Background Indicator
- When an AI process (Agent task or Consultant query) is executing while the assistant drawer is hidden:
  - [`AppNavbar.vue`](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/web/frontend/src/components/layout/AppNavbar.vue) displays a dedicated `.nav-assistant-pill` with a pulsating amber dot and `"AI Working…"` label.
  - The Assistant toggle button receives `.is-running` styling with a continuous subtle glow pulse.
  - Clicking either the pill or toggle button immediately re-opens the assistant.

### 1.3 Non-Intrusive Completion Toast Notification
- If an agent task or consultant response completes while the assistant sidebar is closed:
  - A notification toast (`.wb-bg-toast`) appears at the bottom-right of the workbench.
  - Displays status color (Green for Success, Amber for Warning/Failed), prompt preview, and an **"Open"** action button.
  - Clicking "Open" opens the assistant drawer and switches directly to the relevant tab (`agents` or `consultant`).
  - Auto-dismisses after 6 seconds or can be manually dismissed via `✕`.

---

## 2. Prompt Autocomplete & Context Mention Engine (`@file` and `/template`)

AETHER features an integrated suggestion and context-resolution pipeline:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Composer as TaskComposer / ConsultantChat
    participant Service as promptSuggestionService.js
    participant Cache as fileCacheService.js
    participant Backend as Gateway API & ContextBuilder

    User->>Composer: Types '@' or '/'
    Composer->>Service: parseAutocompleteTrigger(input, cursorPos)
    Service->>Cache: getCachedFiles(projectId)
    Service-->>Composer: Suggestions List (Files or Templates)
    Composer->>User: Renders PromptAutocompletePopover.vue
    User->>Composer: Selects item (Click / Enter / Tab)
    Composer->>User: Injects formatted '@path/to/file' or template
    User->>Backend: Submits task prompt with '@filename'
    Backend->>Backend: mention.py resolves & injects file contents (up to 64KB)
```

### 2.1 File Mentions (`@file`)
- **Trigger**: Typing `@` immediately queries cached workspace files.
- **Backend Resolution (`src/agent_ai/contextbuilder/mention.py`)**:
  - Validates relative paths against project root with strict path traversal prevention (`..` escaping is blocked).
  - Enforces a safety limit (default 64KB per file) to prevent context window dilution.
  - Injects file content directly into the prompt before sending to the model, ensuring tools-free modes (such as Quick Mode) still retain context.

### 2.2 Template Shortcuts (`/template`)
- **Trigger**: Typing `/` suggests pre-configured engineering prompts (e.g., `/refactor`, `/test`, `/audit`, `/explain`, `/fix-bugs`).
- Includes shortcut descriptions and instant template replacement.

### 2.3 Keyboard Ergonomics
- Full keyboard control inside [`PromptAutocompletePopover.vue`](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/web/frontend/src/components/ui/PromptAutocompletePopover.vue):
  - `ArrowDown` / `ArrowUp`: Traverse items.
  - `Enter` / `Tab`: Apply suggestion.
  - `Escape`: Dismiss popover.

---

## 3. Interactive Terminal & Process Streaming Subsystem

Located inside the collapsible [`AppBottomDock.vue`](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/web/frontend/src/components/layout/AppBottomDock.vue):

- **Backend Streaming (`web/django_app/api/views.py`)**:
  - Endpoint `/api/terminal/stream/`: Streams sub-process output over HTTP/SSE chunk-by-chunk.
  - Endpoint `/api/terminal/input/`: Writes user input into the running process's `stdin`.
  - Endpoint `/api/terminal/cancel/`: Terminates active processes cleanly (`SIGTERM` / `SIGKILL`).
- **Frontend Console (`TerminalView.vue`)**:
  - Real-time ANSI escape code color rendering.
  - Interactive command prompt with history recall.
  - Clear and auto-scroll controls.

---

## 4. Diagnostics & Problems Engine

The workbench incorporates client-side static analysis and Monaco marker synchronization:

- **Service (`web/frontend/src/services/diagnosticService.js`)**:
  - Validates code syntax on the fly for bracket imbalances, JSON errors, duplicate keys, and Python colon syntax.
  - Converts Monaco Editor markers into categorized diagnostic objects (`error`, `warning`, `info`).
- **Problems Dock**:
  - Displays total error and warning count badges in `AppFooter.vue` and `AppBottomDock.vue`.
  - Clicking a problem navigates directly to the offending line in the editor canvas.

---

## 5. Welcome Canvas & Project Onboarding

- [`WelcomeView.vue`](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/web/frontend/src/components/WelcomeView.vue):
  - Renders when no editor tabs are open.
  - Displays recent workspaces, quick clone Git repository modal, folder opener, and quick command shortcuts (`⌘K`, `⌘P`, `Ctrl+\``).
