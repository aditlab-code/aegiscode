# Independent Frontend Regression Report — AegisCode v0.2.05

**Repository:** `aditlab-code/aegiscode`  
**Commit tested:** `587dd480015d5876ee36c6e0bf9a713fde6d76a2`  
**Commit title:** `chore: rilis sinkronisasi edisi komunitas v0.2.05`  
**Test date:** 9 October 2026 (WIB)  
**Method:** Clean shallow clone; tests and build run outside the repository's pre-existing workspace state.

## Verdict

**Functional regression gate: PASS, with one release-blocking reproducibility defect.**

All executable frontend tests and the production build passed. However, a clean, lockfile-respecting installation (`npm ci`) cannot currently be reproduced.

| Gate | Result | Evidence |
|---|---|---|
| Exact source snapshot | PASS | Clone HEAD equals `587dd480015d5876ee36c6e0bf9a713fde6d76a2` |
| Clean dependency installation | FAIL | `npm ci` reports missing `@popperjs/core@2.11.8` in `package-lock.json` |
| Frontend test suite | PASS | 27 passed, 0 failed, 0 skipped; duration 54.3 s |
| Production build | PASS | Vite built 1,194 modules successfully in 46.72 s |
| HTTP smoke test | PASS | Vite dev server returned the AegisCode Studio HTML shell with HTTP success |
| Repository mutation during test | PASS | No tracked-file changes after testing |

## Executed checks

### 1. Dependency reproducibility

Command:

```bash
npm ci
```

Result: **FAIL**. npm refuses the clean installation because the package lock is out of sync with `package.json`:

```text
Missing: @popperjs/core@2.11.8 from lock file
```

For the remaining functional tests only, dependencies were installed with:

```bash
npm install --package-lock=false --no-audit --no-fund
```

This avoided editing the tested lockfile. It must not be treated as a release fix.

### 2. Node frontend regression suite

Command:

```bash
npm test
```

Result: **PASS — 27/27 tests**. Coverage included activity copy, async-audit remediation, authentication service, diagnostics, editor lifecycle, Git flows, lifecycle contracts, task/queue state, SSE telemetry, Telegram service, themes, token usage, unified sessions, workspace context and isolation.

### 3. Production build

Command:

```bash
npm run build
```

Result: **PASS**. Generated `dist/` contains 105 files and occupies approximately 16 MB.

Warnings observed (non-fatal):

- `src/api.js` is both statically and dynamically imported, so the intended lazy import will not become a separate chunk.
- Large generated bundles remain: `monacoSetup` is ~3.34 MB minified (858.94 kB gzip) and the main `index` bundle is ~763 kB minified (218.75 kB gzip). Vite emits the standard >500 kB warning.

### 4. Runtime smoke test

The Vite development server started successfully on `127.0.0.1:5173`. A local HTTP request returned the expected document shell with title **AegisCode Studio**, app mount point `#app`, Vite client, and `/src/main.js` entrypoint.

Browser automation could not reach the isolated local server from its separate browser environment, so full visual interaction and backend-integrated UI paths were not asserted in this run.

## Defects and follow-up

| ID | Severity | Finding | Recommendation |
|---|---|---|---|
| FR-001 | P1 — release reproducibility | `npm ci` fails because `@popperjs/core@2.11.8` is absent from `package-lock.json`. Fresh CI or contributors cannot perform the canonical install. | Regenerate and commit `apps/frontend/package-lock.json` using the supported npm version; then require `npm ci && npm test && npm run build` in CI. |
| FR-002 | P2 — performance | Monaco/editor-related chunks exceed Vite's 500 kB warning threshold. | Measure route-level loading, then split Monaco/language workers or configure deliberate chunk boundaries. |
| FR-003 | P3 — bundle hygiene | `api.js` is imported both eagerly and lazily, defeating the lazy boundary. | Keep one loading strategy: either eagerly import it or move all consumers behind the lazy boundary. |

## Confidence and scope

The tested commit passes its present automated frontend functional suite and compiles for production. The outcome does **not** prove end-to-end correctness for Django/SSE/WebSocket integrations, real agent queues, or browser interactions because those require a running backend and a browser network path to the local server. The dependency-lock defect should be fixed before calling v0.2.05 reproducibly releasable.
