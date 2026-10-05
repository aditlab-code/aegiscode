# AegisCode Developer Documentation

Welcome to the developer documentation for **AegisCode** (AegisCode Studio & Aegis Agent). This directory contains comprehensive architectural specifications, developer onboarding instructions, Chain of Thought (CoT) execution guidelines, and agent framework details.

---

## Documentation Index

| Document | Description |
| :--- | :--- |
| **[Architecture Overview](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/architecture.md)** | Subsystem breakdowns, runtime lifecycle, Hybrid Asymmetric Split-Brain, and system component interactions. |
| **[Chain of Thought (CoT) Runtime](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/cot_reasoning_runtime.md)** | In-depth exploration of the reasoning loop, dynamic replanning, observation compaction, and cognitive stages within Aegis Agent. |
| **[Developer Guide](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/developer_guide.md)** | Environment setup, running the application, dual-stack testing (`pytest` & Node tests), zero-zombie process verification, and coding standards. |
| **[Tool & Provider Extensibility](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/tool_and_provider_extensibility.md)** | How to implement custom tools, connect MCP servers (`.aegis/mcp.json`), and register new LLM backends. |
| **[Oh My Company (OMC) Agent Framework](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/omc_agent_framework.md)** | Specification of the 13-agent OMC roster, star topology, 4-role delivery pipeline, and RTK protocol within AegisCode. |
| **[AegisCode Studio Workbench Features & Guardrails](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/workbench_features.md)** | Specifications for persistent drawer execution, prompt autocomplete, interactive PTY terminal streaming, and HITL DiffModal guardrails. |
| **[UI Modern IDE Roadmap](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/UI-IDE-Roadmap.md)** | Architecture, responsive knowledge rules, and implementation checklist for AegisCode Studio. |
| **[Local Hybrid RAG Roadmap](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/RAG-local-Roadmap.md)** | Architectural roadmap and verification checklist for AegisCode Split-Brain engine (`.aegis/vectors.db`, AST chunking, sqlite-vec, fastembed, RRF). |
| **[Google Antigravity Provider](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/Antigravity-Provider.md)** | Integration guide for Google Antigravity frontier reasoning models and authentication. |
| **[Community Open-Core Strategy](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/docs/community-fork.md)** | Transition strategy and commercial licensing matrix (Community Edition vs Pro / Commercial Edition). |

---

## Key Root References

- **[AGENTS.md](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/AGENTS.md)**: Repository-level autonomous agent instructions, 5-stage CoT protocol, and operational rules.
- **[README.md](file:///Users/aditwicaksono/Documents/Project-AI/Aether-Agent/README.md)**: Project overview, features, and quickstart guide.
