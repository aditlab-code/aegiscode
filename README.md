# AegisCode

### Autonomous AI Coding Agent & Studio Workbench

> **Fork Notice & Attribution:** AegisCode is developed as an independent product branching from the foundation created by **adigayung** in [adigayung/aether-agent](https://github.com/adigayung/aether-agent), licensed under the [MIT License](LICENSE).

**AegisCode gives an LLM the tools, project intelligence, and protective execution environment it needs to work on real software projects autonomously.**

```
Aegis Agent = Hands      LLM = Brain
```

## What is AegisCode?

A local-first autonomous coding agent runtime (**Aegis Agent**) paired with a developer-first IDE workbench (**AegisCode Studio**). Describe a task in natural language; AegisCode prepares context, streams the agent's reasoning, runs tools under deterministic guardrails, and reports results. Bring your own key (BYOK) or run local models.

```
Prompt -> Task Preparation -> Agent Loop (LLM -> tool calls -> observations) -> Validation -> Report
```

The loop ends only when the LLM returns a final answer without requesting a tool.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Django, Channels, Daphne |
| Frontend | Vue 3, Vite, Monaco Editor, xterm |
| Storage | SQLite (`data/aegis.db`), Standard library SQLite CodeGraph (`.aegis/codegraph.db`) |
| Providers | Google Antigravity, OpenAI-compatible, OpenRouter, Ollama, custom |
| Protocols | SSE (live events), PTY terminal bridge, MCP |
| Desktop | Tauri v2 (planned) |

## Key Features

- **Autonomous Agent and Consultant**: full tool-using agent plus a read-only Ask mode.
- **Project Intelligence**: project map, code index, and local hybrid RAG (lexical + vector with RRF).
- **Multi-Provider**: provider instances and models managed from Settings or `.env`; deterministic model routing.
- **Queue and Parallel**: serial FIFO tasks or parallel tasks, with persistent history and task resume.
- **IDE Workbench**: Monaco editor and diff, file explorer, Git changes, interactive PTY terminal, responsive layout, dark and light themes.
- **Security and Permissions**: permission policy, approval flow, workspace path validation, no secrets in logs.
- **Reliability**: retry and recovery, cancellation, zero-zombie process cleanup.
- **Extensions and MCP**: extension system and MCP client (stdio / SSE).

## Quick Start

Requirements: Python 3.10+, Git (Node.js is installed automatically by the launcher).

```bash
git clone https://github.com/aditlab-code/aegiscode.git
cd aegiscode
cp .env.example .env            # Windows: copy .env.example .env
python scripts/install_aegis.py # creates venv, installs deps, builds frontend, starts the gateway
```

Or double-click `run.bat` (Windows) / `run.sh` (macOS/Linux). The port is read from `data/settings.json` (fallback 8000, auto-picks a free port; override with `AEGIS_PORT`). Useful flags: `--check`, `--no-launch`, `--simulate`, `--port <n>`.

Then: open the printed URL, pick a Project, add a Provider Instance and Model in Settings (or set keys in `.env`), write a task in the Task Composer, and choose `Queue` or `Parallel`.

## Project Structure

```
.
├── src/agent_ai/     # Core: runtime, providers, tools, project intelligence, permission
├── web/django_app/   # Thin HTTP/SSE gateway
├── web/frontend/     # Vue 3 + Vite workbench (AegisCode Studio)
├── scripts/          # Installer and verification scripts
├── tests/            # Pytest suite
└── data/             # Local settings and SQLite state
```

State directory is canonical `.aegis/` with transparent one-time legacy migration.

## Roadmap

```
Legacy (Phase 0-2.2)  Done: Antigravity provider, UI and Git facade, local hybrid RAG
Phase 0-1             Baseline, task lifecycle, sequence-aware event contract  (Done)
Phase 2               Orchestrator and runtime modularization                  (Done)
Phase 3               Provider boundary normalization                          (Done)
Phase 4               Reliability gate and strict QA                           (Done)
Phase 5               HITL guardrails, Studio UI, Tauri v2 desktop             (Active)
```

Stability first: no new features on the core execution path until Phases 1-2 are done. Details: `Roadmap.md` (development branch).

## Contributing

Open an issue first, then submit a Pull Request; all changes are reviewed before merge.

## License

MIT, see [LICENSE](LICENSE).

- Original source: [adigayung/aether-agent](https://github.com/adigayung/aether-agent), Copyright (c) 2026 adigayung
- Modifications: Copyright (c) 2026 aditlab-code
- AegisCode Studio & Aegis Agent: Copyright (c) 2026 AegisCode Authors
