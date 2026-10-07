# AegisCode Architecture Overview

This document details the architectural design, core subsystems, and runtime lifecycles of **AegisCode** (AegisCode Studio & Aegis Agent).

---

## 1. System Philosophy
AegisCode decouples decision-making (LLM) from physical action execution (runtime engine) and enforces a **Hybrid Asymmetric Split-Brain** model:

```
┌────────────────────────────────────────────────────────┐
│                      LLM (Brain)                       │
│    • Cloud Orchestrator (Reasoning & Diff Synthesis)   │
│    • Tool Selection & Argument Construction            │
│    • Budgeted Context Window (< 4,000 tokens)          │
└───────────────────────────▲────────────────────────────┘
                            │ JSON-RPC / API
┌───────────────────────────▼────────────────────────────┐
│                   Aegis Agent (Hands)                  │
│    • Local Worker: AST parsing, fastembed, sqlite-vec  │
│    • Interactive PTY Terminal (zero-zombie lifecycle)  │
│    • FileWriteLock & HITL Diff Approval (Supervised)   │
│    • Context budgeting, RRF ranking, & rollback stash  │
└────────────────────────────────────────────────────────┘
```

The LLM remains the autonomous decision-maker. Aegis Agent provides a safe, reproducible, observable execution environment that allows the model to explore codebases, apply edits under strict deterministic guardrails, execute test suites, and self-correct over iterative cycles.

Backward-compatibility notice: For workspace state and intelligence discovery, AegisCode prioritizes `.aegis/` (`.aegis/vectors.db`, `.aegis/bible/`, `.aegis/map/`) and `data/aegis.db`, with automatic fallback to legacy `.aether/` and `data/aether.db`.

## 2. High-Level Subsystems

Aegis Agent is organized into clean, decoupled Python modules under `src/agent_ai/`:

```mermaid
graph TD
    Client["AegisCode Studio (Vue 3 + Vite IDE)"] --> Gateway["Django API Gateway / PTY Bridge"]
    Gateway --> Runtime["Aegis Agent Runtime<br/>(runtime/runtime.py)"]
    
    subgraph CoreEngine ["Aegis Agent Core Engine (src/agent_ai/)"]
        Runtime --> ContextBuilder["Context Builder & Budget<br/>(contextbuilder / contextbudget)"]
        Runtime --> Planner["Planning & Replanner<br/>(planning/)"]
        Runtime --> ProviderRegistry["Provider Layer<br/>(providers/)"]
        Runtime --> ToolRegistry["Tool Layer & FileWriteLock<br/>(tools/)"]
        Runtime --> RepoIntel["Repository Intelligence & Split-Brain<br/>(repointel / semantic / codeindex)"]
        Runtime --> PolicyGateway["Permission & HITL Supervised Gate<br/>(permission/)"]
        Runtime --> Validation["Validation & Checkpoint Recovery<br/>(validation / git/checkpoint.py)"]
    end

    ToolRegistry --> FS["Filesystem & Git Facade"]
    ToolRegistry --> Term["Interactive PTY Terminal (@xterm/xterm)"]
    ToolRegistry --> MCP["MCP Adapters (.aegis/mcp.json)"]
    ProviderRegistry --> LLMs["Google Antigravity / Anthropic / OpenAI / Ollama"]
```

### Module Directory Breakdown

| Subsystem Path | Description | Key Modules |
| :--- | :--- | :--- |
| `src/agent_ai/runtime/` | Core execution loop and turn controller | `runtime.py`, `working_state.py`, `policy.py` |
| `src/agent_ai/planning/` | Task decomposition, milestone tracking, replanning | `planner.py`, `replanner.py`, `models.py` |
| `src/agent_ai/contextbuilder/` | Compiles repository context, prompts, system states, and `@file` mentions | `builder.py`, `mention.py`, `models.py` |
| `src/agent_ai/contextbudget/` | Sliding window compaction, deduplication, tool pruning | `budget.py`, `tool_compaction.py`, `dedup.py` |
| `src/agent_ai/tools/` | Tool registry, filesystem, terminal, symbols, vision | `filesystem.py`, `terminal.py`, `source_symbols.py`, `project_map.py` |
| `src/agent_ai/providers/` | Unified LLM abstraction layer supporting multiple backends | `factory.py`, `base.py`, `deepseek.py`, `ollama.py`, `openrouter.py` |
| `src/agent_ai/repointel/` | AST parsing, symbol indexing, repository graph | `indexer.py`, `symbols.py` |
| `src/agent_ai/permission/` | Policy gateway, path whitelists, command safety | `gateway.py`, `policy.py` |
| `src/agent_ai/validation/` | Verification guards and sanity checks | `validator.py`, `syntax.py` |
| `src/agent_ai/recovery/` | Loop detection, backoff, and runtime self-healing | `loop_breaker.py`, `fallback.py` |

---

## 3. End-to-End Execution Lifecycle
The lifecycle of an AegisCode task progresses through four primary phases:
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Workbench as AegisCode Studio (UI)
    participant Runtime as Aegis Agent Runtime
    participant Context as Context Builder
    participant LLM as LLM Provider
    participant Tools as Tool Execution

    User->>Workbench: Submit Task Prompt
    Workbench->>Runtime: Initialize Session & Task State
    Runtime->>Context: Build Initial Context (Repo Map, Symbols, Prompt)
    Context-->>Runtime: Initial Context Packet
    
    loop Continuous Reasoning Loop (Until Final Response)
        Runtime->>LLM: Send Context + History + Tool Definitions
        LLM-->>Runtime: Chain-of-Thought + Tool Call Request
        Runtime->>Tools: Dispatch Tool (e.g. read_file, run_command)
        Tools-->>Runtime: Tool Observation Result
        Runtime->>Context: Compact Observation & Update Working State
    end

    Runtime->>Workbench: Stream Final Result & Validation Report
    Workbench->>User: Display Completion Status
```

### 1. Task Preparation
- Incoming user prompt is sanitized.
- `repointel` queries symbol maps and relevant directory trees to build an initial repository summary.
- Permissions and sandbox parameters are initialized for the target workspace.

### 2. Context Construction & Budget Allocation
- System prompt, user goals, and active file contexts are assembled by `contextbuilder`.
- Token consumption is measured against provider constraints by `contextbudget`. If history overflows, tool compaction and token deduplication are applied.

### 3. Continuous Agent Execution Loop
The loop runs without heuristic "done" detectors:
- The LLM streams internal reasoning (Chain of Thought).
- The LLM emits structured tool calls (JSON-RPC or provider-native schema).
- Tools execute deterministically in the workspace.
- Outputs (observations) are formatted, sanitized, and fed back into context.
- If an observation indicates error or plan diversion, `replanner.py` updates the execution plan.

### 4. Termination & Validation
- The loop terminates strictly when the model returns a final text response without requesting any further tool calls.
- Validation checks run automated unit tests and lint verifications before reporting completion.

---

## 4. AegisCode Studio Workbench & System Integration

AegisCode features a developer-first IDE workbench (**AegisCode Studio**):
- **Backend Gateway:** Django application (`web/django_app/`) serving WebSocket/SSE and REST APIs for session lifecycle, PTY interactive terminal bridge, token metrics, and real-time streaming.
- **Frontend:** Modern Vue 3 + Vite single-page application (`web/frontend/`) featuring a VS Code-style 3-column layout (Monaco Editor, Monaco Diff Editor, interactive PTY terminal via `@xterm/xterm`, HITL DiffModal, and Git Source Control drawer).

---

## 5. Local Semantic Index & Vector Database (Phase 2.1)

Phase 2.1 establishes an independent, entirely on-device semantic search and vector database pipeline located in `src/agent_ai/repointel/semantic/`.

### 5.1 Architecture Diagram
```mermaid
flowchart TD
    subgraph ClientAndTools ["Clients & Tools Layer"]
        A_TOOL["semantic_search (Agent)"] --> SVC["SemanticIndexService"]
        R_TOOL["refresh_semantic_index (Agent)"] --> SVC
        C_TOOL["semantic_search (Consultant read-only)"] --> SVC
    end

    subgraph CoreSemanticEngine ["Semantic Engine (src/agent_ai/repointel/semantic/)"]
        SVC --> IDX["SemanticIndexer (Incremental)"]
        IDX --> CHK["chunker.py (AST + Brace-Matching + Splitter)"]
        IDX --> FP["FingerprintTable (SHA-256)"]
        CHK --> EMB["FastEmbedEmbeddings (BAAI/bge-small-en-v1.5)"]
        EMB --> STORE{"Dual-Engine Selector"}
        STORE -->|"sqlean.py + sqlite-vec"| VEC["AegisSQLiteVec"]
        STORE -->|"stdlib sqlite3 fallback"| BF["BruteForceVectorStore (Cosine Similarity)"]
    end

    subgraph LocalStorage ["Persistent Local Storage"]
        VEC --> DB[(".aegis/vectors.db / fallback .aether/vectors.db")]
        BF --> DB
    end
```

### 5.2 Storage & Schema Specifications
The vector database is housed inside `<project_root>/.aegis/vectors.db` (with transparent fallback to `.aether/vectors.db`):
- **`aegis_chunks`**: Stores code chunk text, structured metadata JSON (file path, symbol name, symbol kind, line span), and raw float32 embedding BLOBs.
- **`file_fingerprints`**: Tracks `path`, `sha256`, `chunk_count`, and `indexed_at` timestamps for sub-second incremental indexing bypassing unchanged files.
- **`index_meta`**: Tracks `schema_version` (2.1), active `model_name`, and active `backend` engine. Changing model configuration triggers an automatic full index rebuild.

### 5.3 Deterministic AST Chunking
Code chunking operates on semantic unit boundaries:
- **Python:** Standard library `ast.parse` isolates top-level functions and class methods with decorators, signatures, docstrings, and bodies preserved. Classes generate dedicated header chunks (signatures + docstrings + class attributes).
- **JavaScript & TypeScript:** Regex symbol boundary detection paired with lexical brace-matching (`_match_braces`) ignoring string literals, template strings, and comments.
- **Size Bounds:** Chunks exceeding ~450 tokens (~1,800 characters) are partitioned using LangChain's `RecursiveCharacterTextSplitter.from_language` while preserving line number mapping.
- **Context Header:** Every chunk prepends a structured symbol header (`# path: <path> | symbol: <symbol> | kind: <kind>\n<code>`) to maximize embedding retrieval precision.

---

## 6. Quality Assurance & Independent Testing Subsystem

To ensure deterministic stability and independent verification across development and production releases, AegisCode implements a dedicated multi-tiered QA architecture:

```mermaid
graph TD
    subgraph TestPyramid ["Testing Architecture Pyramid"]
        E2E["E2E Smoke Tests (Playwright)<br/>Critical IDE User Journeys"]
        Comp["Component Tests (Vue Test Utils & Vitest)<br/>Reactive UI, Monaco & Panel States"]
        Contract["Contract Validation Layer<br/>JSON Schema for Django Gateway SSE & REST"]
        Unit["Unit Tests (Python pytest & Node:test)<br/>Isolated Pure Reducers, Parsers, & Logic"]
        E2E --> Comp
        Comp --> Contract
        Contract --> Unit
    end

    subgraph Governance ["Independent Stop-Gate Governance (Asgard / OMA)"]
        Brokkr["brokkr-coder (Implementation)"] --> Thor["thor-tester (Independent Stop-Gate)"]
        Thor -->|"Failure Log"| QALog[("docs/QA/logs/ Registry")]
        Thor -->|"Pass (Exit Code 0)"| Forseti["forseti-auditor (Bash & Security Audit)"]
        Forseti --> Odin["odin-orchestrator (Merge Approval)"]
    end
```

### 6.1 Testing Architecture Principles
1. **Zero-Flakiness Polling**: Elimination of static `time.sleep` calls across subprocesses and PTY tests in favor of deadline-driven polling assertions.
2. **Complete State Isolation**: Dynamic filesystem isolation via `tmp_path` fixtures for `.aegis/`, workspace directories, and SQLite databases to prevent cross-test contamination.
3. **Contract-First Synchronization**: Canonical JSON Schemas governing Server-Sent Events (SSE) and REST payloads to prevent breaking changes between Django Gateway and the Vue frontend.
4. **Audit Log Persistence**: Mandatory test run tracking recorded in `docs/QA/logs/` adhering to [docs/QA/QA_LOGS_RULES.md](file:///Users/aditwicaksono/Documents/Project-AI/AegisCode/docs/QA/QA_LOGS_RULES.md).

