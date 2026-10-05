# AETHER Developer Guide

This document is the onboarding and operational guide for developers building, extending, and maintaining the **AETHER** codebase.

---

## 1. Prerequisites & Environment Setup

### System Requirements
- **Python:** 3.10, 3.11, or 3.12
- **Node.js:** 18.x or 20.x LTS with npm
- **Operating System:** macOS, Linux, or Windows (WSL recommended for Windows)
- **Git:** 2.30+

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/adigayung/aether-agent.git
   cd aether-agent
   ```

2. **Configure Python Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Frontend Workbench:**
   ```bash
   cd web/frontend
   npm install
   cd ../..
   ```

4. **Environment Variables Configuration:**
   Copy `.env.example` to `.env` and configure your API keys:
   ```bash
   cp .env.example .env
   ```
   Key variables:
   ```ini
   # LLM Provider Configuration
   OPENROUTER_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   ANTHROPIC_API_KEY=your_key_here
   DEEPSEEK_API_KEY=your_key_here

   # Local Provider (Ollama)
   OLLAMA_BASE_URL=http://localhost:11434

   # Runtime Settings
   AETHER_MAX_TURNS=40
   AETHER_LOG_LEVEL=INFO
   ```

---

## 2. Running AETHER

### Full Stack (Backend + Workbench)
Using the built-in startup scripts:
```bash
# macOS / Linux
./run.sh

# Windows
run.bat
```
This boots:
- Django backend / API server on `http://localhost:8000`
- Vite frontend workbench on `http://localhost:5173`

### Headless CLI / Script Mode
To test or execute an autonomous task from the terminal:
```bash
python scripts/check_agent_runtime.py
```

---

## 3. Dual-Stack Testing Protocol

Quality verification in AETHER uses a **dual-stack testing framework**: `pytest` for the Python core engine/backend, and `vitest` for the frontend workbench.

### 3.1 Backend & Engine Testing (`pytest`)

Backend test suites live in `tests/` and validate runtime execution, tool sandboxing, context building, and provider integrations.

```bash
# Run all backend unit and integration tests
pytest

# Run tests with verbose output and console logging
pytest -v -s

# Run a specific test suite
pytest tests/test_agent_execution_mode.py
pytest tests/test_agent_settings.py

# Run only unit tests excluding live LLM calls
pytest tests/ -m "not integration"
```

#### Backend Test Conventions:
- Place unit tests in `tests/test_<module_name>.py`.
- Mock external LLM API calls using `unittest.mock` or pytest fixtures unless running explicit integration benchmarks.
- Clean up any temporary directories or scratch files generated during testing.

### 3.2 Frontend & Workbench Testing (Node Test Runner & Vite SSR)

Frontend tests live in `web/frontend/src/` and validate UI components, responsive layout behaviors, services, autocomplete triggers, and workbench integration.

```bash
# Run all frontend unit and integration tests from repo root
node --test web/frontend/src/*.test.mjs

# Or from web/frontend directory
cd web/frontend
node --test src/*.test.mjs

# Validate production build bundle
npm run build
```

#### Frontend Test Conventions:
- Use Node's native test runner (`node:test`, `node:assert/strict`) with Vite SSR loader (`createServer`).
- Verify that `App.vue` strictly adheres to line count budgets (< 450 LOC).
- Ensure view state retention (`v-show`) keeps long-running background tasks and streams alive across drawer collapses.
- Verify streaming event handlers and terminal command streams do not cause layout thrashing.

---

## 4. Coding Standards & Best Practices

1. **Lean Code Policy (YAGNI):**
   - Implement only the direct requirements needed.
   - Avoid speculative configuration options or premature abstraction layers.
2. **Type Annotations:**
   - All new Python functions must include Python type hints (`mypy` compatible).
   - Use TypeScript strict mode in `web/frontend/`.
3. **Docstrings & Comments:**
   - Write clear docstrings for public classes and methods.
   - Maintain documentation integrity: do not delete existing functional comments.
4. **Error Handling:**
   - Raise explicit, typed exceptions (e.g. `ToolExecutionError`, `ContextBudgetExceededError`).
   - Never use bare `except:` clauses that catch `KeyboardInterrupt` or `SystemExit`.
5. **Language Rule:**
   - All code, comments, docstrings, and commit messages must be in **English**.
