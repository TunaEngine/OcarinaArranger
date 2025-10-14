# Arranger v3 Genetic Programming Overview

This guide documents the architecture, configuration knobs, and migration path for the
arranger v3 genetic-programming (GP) pipeline. It supplements the existing arranger v2
(best-effort) documentation by highlighting how the new strategy composes with the
current desktop UI, services, and analytics.

## Architecture

The GP pipeline extends the arranger domain package with a dedicated strategy that
invokes an evolutionary loop before scoring instruments:

- **GP session orchestration** – `domain.arrangement.gp.session.run_gp_session`
  handles population seeding, evolutionary operators, and telemetry logging via
  `GPSessionLog`, returning the best individual alongside archive snapshots and
  termination metadata.【F:domain/arrangement/gp/session.py†L200-L337】【F:domain/arrangement/gp/session_logging.py†L37-L97】
- **Strategy wrapper** – `domain.arrangement.gp.strategy.arrange_v3_gp` runs a session
  for the requested instrument, re-scores starred instruments using the winning program,
  and surfaces comparisons, explanations, and an optional v2 fallback when GP halts
  early.【F:domain/arrangement/gp/strategy.py†L150-L317】 Each candidate span is clamped to
  the active instrument range via `range_guard.enforce_instrument_range`, ensuring no GP
  result emits pitches outside the playable window while adding a `range-clamp`
  explanation when adjustments are required. The ranking key now multiplies the
  fidelity penalty (3× for modified programs detected via program length) before
  comparing difficulty so melodic accuracy is favoured even when parsimony weights are
  disabled.【F:domain/arrangement/gp/strategy.py†L82-L104】
  Manual transpose offsets selected in the preview UI are applied before the GP session
  begins so the resulting programs, difficulty summaries, and explanations stay aligned
  with the user’s requested key.【F:services/arranger_preview.py†L94-L115】【F:services/arranger_preview_gp.py†L45-L78】
- **Program primitives** – Primitives such as `GlobalTranspose`, `LocalOctave`, and
  `SimplifyRhythm` encapsulate edits that the GP loop explores while the validation layer
  enforces span limits and constraint windows.【F:domain/arrangement/gp/ops.py†L11-L214】【F:domain/arrangement/gp/validation.py†L15-L156】
- **Fitness evaluation** – Candidates are evaluated with multi-objective fitness vectors
  covering playability, fidelity, tessitura, and program size, ensuring compatibility with
  the existing difficulty summary UI and analytics feeds. Fidelity now blends contour,
  longest-common-subsequence, and pitch-drift penalties so semitone deviations are
  explicitly discouraged even when the melodic outline matches.【F:domain/arrangement/gp/fitness.py†L11-L204】

The services layer adapts these results for the view-models: `services.arranger_preview_gp`
converts `GPInstrumentCandidate` data into the existing summary/explanation/telemetry
structures consumed by the Tkinter views.【F:services/arranger_preview_gp.py†L1-L152】

## Configuration Knobs

Two layers expose tunable parameters:

- **UI settings** – `ArrangerGPSettings` now bounds generations, population size, archive
  depth, random-program seeding, crossover/mutation rates, logging, random seed, and
  per-objective fitness weights (playability, fidelity, tessitura, parsimony, contour,
  LCS, and pitch) in addition to the optional time budget before forwarding values to the
  services layer.【F:viewmodels/arranger_models.py†L58-L136】 The Convert tab surfaces these
  knobs inside the GP preview panel so users can dial in session behaviour and fidelity
  weighting—including the new pitch-weight control—without leaving the desktop UI.【F:ocarina_gui/ui_builders/convert_tab_sections.py†L332-L420】
- **Session configuration** – `GPSessionConfig` still guards the evolutionary loop;
  `_gp_session_config` now threads the advanced UI values into crossover/mutation
  rates, archive sizing, random seeding, and a rebuilt `FitnessConfig` so melodic
  fidelity weighting can be tuned per project while retaining safe defaults (10
  generations, 16-program population, 8-member archive, 8 random programs, fidelity
  weighting 1.8× with contour/LCS/pitch split 0.3/0.4/0.3).【F:domain/arrangement/gp/session.py†L184-L258】【F:services/arranger_preview_gp.py†L11-L85】

Telemetry emitted for analytics/UI consumers remains stable:

- `ArrangerTelemetryHint` continues to surface `(category, message)` pairs; the GP
  service appends messages about session runtime, archive retention, optional time
  budgets, and fallback activation without changing existing categories.【F:viewmodels/arranger_models.py†L36-L57】【F:services/arranger_preview_gp.py†L116-L151】
- `GPSessionLog.to_dict()` still returns `{seed, config, generations, final_best?}`; the
  only addition is the optional `final_best` object when the engine captures a terminal
  elite, which remains additive and backwards-compatible for analytics readers that
  deserialize generation metrics.【F:domain/arrangement/gp/session_logging.py†L37-L97】

## Migration Path from v2

Follow these steps to adopt the GP strategy while preserving the v2 experience:

1. **Seed from salvage traces** – Convert existing v2 `ExplanationEvent` streams into GP
   primitives using `translate_salvage_trace`, letting current salvage insights bootstrap
   the evolutionary search.【F:domain/arrangement/gp/init.py†L15-L102】
2. **Mirror service wiring** – Invoke `arrange_v3_gp` from the preview service alongside
   the v2 arranger, mapping results into shared view-model DTOs (`ArrangerResultSummary`,
   `ArrangerExplanationRow`, `ArrangerTelemetryHint`) so the UI can toggle between
   strategies without layout changes.【F:domain/arrangement/gp/strategy.py†L150-L317】【F:services/arranger_preview_gp.py†L43-L151】
3. **Maintain analytics contracts** – Persist GP session logs using the existing
   `GPSessionLog.to_dict()` shape and extend downstream consumers to read the additive
   `final_best` block when present. UI telemetry tabs already display the new GP-specific
   hints thanks to shared `ArrangerTelemetryHint` models.【F:domain/arrangement/gp/session_logging.py†L37-L97】【F:services/arranger_preview_gp.py†L116-L151】
4. **Fallback for parity** – Keep the v2 arranger available via the `fallback` field on
   `GPArrangementStrategyResult`, allowing gradual rollout and parity checks until the GP
   strategy fully replaces the salvage cascade for all instruments.【F:domain/arrangement/gp/strategy.py†L150-L317】

With these steps, teams can experiment with GP-driven edits while retaining the mature
telemetry, UI bindings, and analytics pipelines established for arranger v2.
