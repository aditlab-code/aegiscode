# Tasks: Refine AI Aegis (Olympus Framework Autonomous Architecture)

- [x] Task 1: Relax provider runner rules and eliminate circuit breaker in `src/agent_ai/providers/antigravity.py`
  - Acceptance: Tool repetition does not trigger proc.kill() or fatal exception; redundant read/scan restrictions removed from prompt; no artificial guardrail warnings injected into output; transparent retry on connection failure.
  - Verify: `PYTHONPATH=src rtk pytest tests/test_native_skills_and_olympus.py`
  - Files: `src/agent_ai/providers/antigravity.py`

- [x] Task 2: Eliminate policy escalation tool and execution mode throttling in `src/agent_ai/`
  - Acceptance: RequestPolicyEscalationTool decommissioned cleanly; runtime and config policy simplified to full autonomous depth without fast/balanced/deep restrictions; no dead code or broken imports.
  - Verify: `PYTHONPATH=src rtk pytest`
  - Files: `src/agent_ai/tools/policy.py`, `src/agent_ai/tools/registry.py`, `src/agent_ai/runtime/policy.py`, `src/agent_ai/config/settings.py`

- [x] Task 3: Consolidate Telegram Companion and operational mode auto-approval in `src/agent_ai/`
  - Acceptance: Telegram views permanently set to Agents mode without Ask mode toggle buttons; callback handlers cleaned up; approval gate defaults to autonomous auto-approval; operational_mode defaults to 'agents'.
  - Verify: `PYTHONPATH=src rtk pytest tests/test_telegram_companion.py`
  - Files: `src/agent_ai/runtime/telegram/views.py`, `src/agent_ai/runtime/telegram/handler.py`, `src/agent_ai/permission/approval.py`, `apps/django_app/api/project_store.py`

- [x] Task 4: Remove Ask tab & mode selector and add 1-click active project root spec links in frontend
  - Acceptance: AppRightDrawer is a single-mode Agent panel without Ask tab; mode select (fast/bal/deep) removed from AgentDrawerPanel and AgentSettingsPanel; 1-click quick action buttons to open specs/SPEC.md and specs/TODO.md in active project root via Monaco Editor.
  - Verify: `rtk npm --prefix apps/frontend run build` and `rtk grep -rn "#[0-9a-fA-F]\{3,8\}" apps/frontend/src/ | grep "\.vue"`
  - Files: `apps/frontend/src/components/layout/AppRightDrawer.vue`, `apps/frontend/src/components/drawer/AgentDrawerPanel.vue`, `apps/frontend/src/components/settings/AgentSettingsPanel.vue`

- [x] Task 5: Decouple frontend lifecycle stepper to Olympus autonomous workflow in `apps/frontend/`
  - Acceptance: Stepper decoupled from rigid linear 6-step timeline; reflects dynamic Olympus framework phases (DEFINE, PLAN, BUILD, VERIFY, REVIEW, SHIP); AgentActivity supports interactive questioning dialog; frontend unit tests updated and passing 100%.
  - Verify: `rtk node --test apps/frontend/tests/*.test.mjs`
  - Files: `apps/frontend/src/lifecycle.js`, `apps/frontend/src/composables/useTaskLifecycle.js`, `apps/frontend/src/components/drawer/AgentActivity.vue`, `apps/frontend/tests/lifecycle.test.mjs`, `apps/frontend/tests/lifecycleContract.test.mjs`

- [x] Task 6: Full verification gates and zero-orphan audit
  - Acceptance: 100% test pass on frontend and backend; 0 build errors; 0 orphaned imports; 0 CSS hex token violations.
  - Verify: `rtk node --test apps/frontend/tests/*.test.mjs && rtk npm --prefix apps/frontend run build && PYTHONPATH=src rtk pytest`
  - Files: All touched files
