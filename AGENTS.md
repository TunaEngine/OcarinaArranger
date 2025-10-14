# AGENTS.md

A concise, enforceable playbook for how we (humans + tools) build and maintain this Python/Tkinter desktop app using **pytest**, **TDD**, and disciplined **refactoring** guided by the **Single Responsibility Principle (SRP)**.

---

## 1) Goals & Operating Principles

- **User-first quality**: fast, crash-free UI; predictable behavior; clear error paths.
- **TDD as default**: write a failing test, make it pass, then refactor.
- **SRP everywhere**: each module/class/function does one thing well.
- **Small, reversible changes**: short-lived branches; frequent merges.
- **Automate checks**: tests, lint, format, type hints; block regressions early.
- **Observable code**: meaningful logs, assertions, and diagnostics.

---

## 2) Roles (“Agents”) & Responsibilities

> One person may play multiple roles; the point is separation of concerns.

- **Planning Agent**
  - Clarifies scope; writes acceptance criteria (Given/When/Then).
  - Splits work into minimal testable stories.
- **Design Agent**
  - Chooses interaction patterns and module boundaries; keeps SRP.
  - Records decisions briefly (ADRs) when trade-offs matter.
- **Coding Agent**
  - Follows TDD loop; keeps functions short; prefers composition over inheritance.
  - Avoids UI logic in widgets; pushes logic to services/view-models.
- **Testing Agent**
  - Owns test strategy; adds/maintains fixtures; enforces coverage and speed.
  - Ensures tests are deterministic, hermetic, and named by behavior.
- **Refactoring Agent**
  - Continuously eliminates duplication; extracts modules/classes; simplifies APIs.
  - No behavior change; tests unchanged and green at each step.
- **Release Agent**
  - Verifies smoke tests; tags versions; updates changelog; ensures reproducible builds.
  - Bumps the project version following **SemVer**, matching the scope of the PR changes.

---

## 3) Anatomy of the Codebase (SRP-friendly)

```
project/
  app/                 # entrypoints, application wiring
    __init__.py
    main.py
  ui/                  # Tkinter widgets/views (no business logic)
    __init__.py
    windows.py
    widgets/
  viewmodels/          # UI state & commands; binds UI <-> services
    __init__.py
    main_vm.py
  domain/              # pure domain entities, value objects, rules
    __init__.py
    models.py
  services/            # use-cases/application services (I/O orchestrated here)
    __init__.py
    file_service.py
  adapters/            # infrastructure adapters (fs, network, settings)
    __init__.py
    fs_adapter.py
  shared/              # cross-cutting: result types, errors, utils (small, SRP)
    __init__.py
    result.py
  tests/
    unit/              # fast, isolated tests (domain, services, viewmodels)
    ui/                # slow/contained widget tests (kept minimal)
    integration/       # service+adapter boundaries
```

**Rules**

- UI layer knows only **viewmodels**; no direct calls into services/adapters.
- **Domain** is pure Python (no Tkinter/imports); 100% unit-tested.
- **Services** orchestrate adapters; side effects live here, not in UI or domain.
- Adapters implement I/O behind narrow interfaces; easily faked in tests.

---

## 4) The TDD Loop (enforced)

1. **Red** – write a failing test (name states intent).
2. **Green** – implement the minimal change to pass.
3. **Refactor** – remove duplication; extract functions/classes; improve names.
4. **Repeat** – keep tests fast; push complex logic out of UI.

**Definition of Done**

- Tests pass locally: `xvfb-run -a pytest` (always run this command for verification).
- Coverage ≥ **85%** overall; new/changed lines covered.
- No lints/formatting errors; types clean on changed files.
- UI behavior verified for changed screens (manual or scripted smoke).

---

## 5) Testing Strategy (pytest)

- **Unit (majority)**
  - Domain & services: pure, fast (< 50ms/test), no filesystem/network.
  - Use **fakes** for adapters; avoid mocking internals.
- **View-model tests**
  - Assert command enable/disable, state transitions, validation.
- **UI widget tests (limited)**
  - Instantiate widgets with a temporary `Tk()` root; drive events with `event_generate`; assert widget state and bindings. Keep few and targeted.
- **Headless follow-up**
  - After the xvfb-backed GUI suite is green, immediately rerun the matching headless UI tests (e.g. the `_Headless*` helpers under `tests/ui/test_gui_fingerings_interactions/`) to confirm we didn't regress the stubbed code paths.
- **Integration**
  - Exercise a service with a real adapter (e.g., real file IO under `tmp_path`).
- **Fixtures & marks**
  - `@pytest.mark.gui` for Tkinter-dependent tests; can be skipped in headless CI if needed.
- **Performance guardrails**
  - Add regression tests for operations that must stay under a threshold.

---

## 6) Tkinter-Specific Guidance

- **Main thread only** updates UI. Background work uses threads or executors; communicate via `queue.Queue` + `root.after(...)` to apply results.
- **No business logic in widget callbacks**; delegate to view-model commands.
- **Bind with StringVar/IntVar** in view-models; keep widgets “dumb”.
- **Centralize navigation** (window/dialog creation) in a small coordinator.

---

## 7) Refactoring Playbook (SRP)

- Extract a function/class when:
  - Name becomes “and/or”; parameters > 4; branching > 2 levels; or > ~50 LOC.
- Move code toward its data:
  - Domain rules → domain; orchestration → services; UI state/commands → view-models.
- Introduce narrow interfaces for adapters; prefer composition over inheritance.
- Replace booleans with small value objects/enums when meaning is unclear.
- Keep files cohesive; if a file crosses two themes, split it.

**Safe steps**

- Inline variable → Extract function → Move function → Extract class → Move class.
- After each step: tests green; commit.

---

## 8) Code Quality Gates

- **Coverage**: ≥ 85% overall; critical paths ≥ 90%.
- **Complexity**: functions cyclomatic ≤ 10; cognitive ≤ 15.
- **Size**: functions ≤ ~50 LOC, classes ≤ ~300 LOC, modules ≤ ~500 LOC (soft limits; justify exceptions).
- **File length**: keep every source and test file below **350 lines**; split cohesive sections into separate modules when approaching the limit.
- **Style**: format (Black), import order (isort), lint (Ruff), type hints on public APIs (mypy strict on changed files).

---

## 9) Workflows

### Feature Workflow

1. Planning Agent writes acceptance criteria.
2. Design Agent sketches module changes; update directory map if needed.
3. Coding Agent: TDD loop until criteria satisfied.
4. Testing Agent: adds missing edge cases; ensures speed & determinism.
5. Refactoring Agent: structural cleanup with green tests.
6. PR: small, focused; linked to criteria; checklist below.

### Refactor-Only Workflow

- No behavior change allowed; tests must be unchanged and green.
- If behavior must change, split into a separate feature PR.

---

## 10) Pull Request Checklist

- [ ] Title states behavior change, not implementation.
- [ ] Tests: new failing test added first; now green.
- [ ] Coverage: each feature or bug fix includes appropriate unit, integration, UI, or E2E tests.
- [ ] Coverage & quality gates met.
- [ ] SRP respected; no UI logic leaks.
- [ ] Public APIs typed; names are intention-revealing.
- [ ] Changelog entry (if user-visible).

---

## 11) Issue Templates (quick)

- **feat:** _As a user… I need… so that…_ **Acceptance:** Given/When/Then.
- **refactor:** _Improve structure of … without changing behavior._ **Risk:** low/med/high.
- **test gap:** _Add coverage for … scenario(s)._ **Why:** bug/regression risk.

---

## 12) ADR (lightweight)

- When a decision affects architecture or trade-offs, add `docs/adr/NNN-title.md`:
  - Context → Decision → Consequences → Alternatives (1–2 bullets each).

---

## 13) Tooling (suggested defaults)

- **Formatting/Linting**: Black, isort, Ruff.
- **Types**: mypy (strict on changed files).
- **Tests**: pytest + coverage; `pytest -q --maxfail=1 --disable-warnings`.
- **Pre-commit**: run format/lint/tests for changed files before push.
- **CI**: run unit + view-model tests; optionally mark `gui` tests to run in nightly.

---

## 14) Metrics We Watch

- Test runtime (keep under a few seconds locally).
- Flaky tests (target: zero; quarantine immediately).
- Crash rate / top exceptions (from logs).
- PR size (LOC changed) and cycle time.

---

### Quick Start (TL;DR)

1. Write acceptance criteria.
2. **TDD**: fail → pass → refactor.
3. Keep UI dumb; push logic to view-models/services; **SRP**.
4. Tests fast & deterministic; coverage ≥ 85%.
5. Small PR, passing gates, clear intent.

---

_This document is intentionally concise. If something feels ambiguous, open an ADR or a small doc and link it here._
