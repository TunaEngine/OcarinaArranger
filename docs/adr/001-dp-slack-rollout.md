# ADR 001: Stage the Octave-Folding DP Behind a Feature Flag

## Context

The arranger roadmap lists the octave-folding dynamic program (DP with slack)
as a later-phase milestone, yet the implementation already exists inside
`domain.arrangement.folding`. Without a guardrail the DP would be active for
all spans, making it hard to compare behaviour against the pre-DP baseline or
disable the feature quickly if regressions appear.

## Decision

- Introduce `domain.arrangement.config.FeatureFlags` with a `dp_slack` boolean
  defaulting to `False`.
- Route all entry points through `domain.arrangement.api.arrange_span`, which
  only invokes `fold_octaves_with_slack` when the flag is enabled.
- Document the rollout path so QA can verify parity with the baseline before
  flipping the flag in production.

## Consequences

- We can run targeted A/B tests by toggling `dp_slack` without touching the DP
  implementation.
- The default configuration remains equivalent to the previous behaviour,
  reducing the risk of surprises while parity tests (see `tests/unit/arrangement/test_arrangement_api.py`)
  execute.
- Callers must opt in to the DP explicitly, which provides a clear hand-off for
  future telemetry and gradual rollout.
