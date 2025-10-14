# Arranger Algorithm Overview

This document explains how the best-effort arranger processes MusicXML scores
into playable ocarina phrases. It complements the implementation plan by
mapping each stage to the code modules and surfacing the data that flows between
layers. Three Mermaid diagrams illustrate the system at different zoom levels.

## High-Level Pipeline

The top-level view shows how importer utilities, the arranger domain package,
and the desktop UI cooperate to generate feedback for the player.

```mermaid
flowchart LR
    subgraph Input
        A[MusicXML Score]
        B[Instrument Selection]
        C[User Preferences]
    end

    A --> D[Event Import & Ottava Normalization]
    D --> E[Phrase Extraction]
    E --> F[Arranger Domain API]
    B --> F
    C --> F

    F -->|Best-Effort (v2)| G[Difficulty Summary]
    F -->|Best-Effort (v2)| H[Edited Phrase Span]
    F -->|Best-Effort (v2)| I[Explanation Events]
    F -->|GP Strategy| GP[arrange_v3_gp]

    GP --> G2[GP Difficulty Summary]
    GP --> H2[GP Edited Phrase]
    GP --> I2[GP Explanations & Telemetry]

    subgraph Output
        G --> J[Convert Tab – Summary]
        H --> K[Arranged Preview]
        I --> L[Explanations & Telemetry Tabs]
        G2 --> J
        H2 --> K
        I2 --> L
    end
```

Key takeaways:

- Importers resolve notation (8va/8vb, tuplets, voices) into normalized events
  before the domain layer reasons about pitches.
- `domain.arrangement.api.arrange` is the orchestration point that applies key
  search, octave folding, constraints, and salvage budgets, while
  `domain.arrangement.gp.arrange_v3_gp` invokes the genetic-programming branch
  before mapping results back into the shared view-model DTOs.
- The UI consumes three products: edited phrases for playback/preview,
  difficulty summaries for ranking instruments, and explanation payloads for
  transparency.

## Mid-Level Component Interactions

The mid-level diagram highlights how the arranger domain package decomposes the
work. Each subgraph corresponds to a module family under `domain/arrangement/`.

```mermaid
flowchart TD
    subgraph Import & Modeling
        I1[importers.phrase_from_events]
        I2[phrase.PhraseSpan / PhraseNote]
        I3[melody.identify_melody_voice]
    end

    subgraph Key Search & Folding
        K1[soft_key.soft_key_search]
        K2[folding.fold_octaves_with_slack]
    end

    subgraph Constraints & Difficulty
        C1[constraints.enforce_subhole_and_speed]
        C2[constraints.plan_breaths]
        C3[difficulty.score_span]
    end

    subgraph Salvage & Explainability
        S1[salvage.SalvageCascade]
        S2[micro_edits.*]
        S3[explanations.ExplanationEvent]
    end

    subgraph GP Strategy
        G1[gp.session.run_gp_session]
        G2[gp.strategy.arrange_v3_gp]
        G3[services.arranger_preview_gp]
    end

    subgraph Strategy & Learning
        R1[api.arrange / arrange_span]
        R2[config.FeatureFlags]
        R3[learning.ApprovalLogger]
    end

    I1 --> I2 --> I3 --> R1
    R1 --> K1 --> K2 --> S1
    S1 --> C1
    S1 --> C2
    S1 --> S2
    C1 --> C3
    C2 --> C3
    S1 --> C3
    C3 --> R1
    S1 --> S3 --> R1
    R1 --> R3
    R2 --> R1
    R1 -. GP preview .-> G1
    G1 --> G2 --> G3 --> R1
```

Highlights:

- Melody isolation runs before key search so polyphonic MusicXML inputs reduce
  to a single melodic voice.
- When polyphonic passages include octave-duplicated chord tones, melody
  isolation now anchors the chosen voice to the lower register before continuity
  heuristics run, and emits a `register_anchor` explanation so UI/analytics flows
  record when we suppress upper-octave harmonies.
- Continuity heuristics relax the anchor toward newly selected, shorter melody
  notes so sustained upper harmonies can no longer drag the voice up an octave
  or mask downstream phrases (e.g., the “Shire” excerpt regression).
- GP comparison now weights melodic fidelity ahead of difficulty (tripling the
  penalty for modified programs and incorporating pitch-drift penalties) so
  octave-raising programs no longer outrank register-faithful spans when their
  difficulty scores tie.【F:domain/arrangement/gp/strategy.py†L82-L104】【F:domain/arrangement/gp/fitness.py†L11-L204】
- The Convert tab’s GP panel now exposes archive sizing, random-program counts,
  crossover/mutation rates, logging controls, random seeding, and fitness-weight
  sliders (including the new pitch-weight control) so advanced users can tune the
  session without editing config files.【F:ocarina_gui/ui_builders/convert_tab_sections.py†L332-L420】【F:viewmodels/arranger_models.py†L58-L136】
- Soft key search ranks transpositions; the winning candidates enter the octave
  folding DP before the salvage cascade applies micro edits.
- Constraint helpers (subhole speed, breath planning) and the difficulty model
  feed both the salvage decisions and the returned summary metrics.

## Low-Level Salvage Flow

The low-level diagram zooms into `SalvageCascade.run`, showing how edit budgets
and explanation events cooperate to keep each span deterministic.

```mermaid
flowchart LR
    Start[Span Difficulty > Threshold?]
    Start -->|No| ReturnOriginal
    Start -->|Yes| Init[Reset Budgets]
    Init --> Step1[Try Local Octave Shift]
    Step1 --> Check1{Difficulty <= Cap?}
    Check1 -->|Yes| Log1[Record OCTAVE_DOWN_LOCAL]
    Check1 -->|No| Budget1{Octave Budget Remaining?}
    Budget1 -->|No| Step2
    Budget1 -->|Yes| Repeat1[Apply Best Octave Edit]
    Repeat1 --> Step2[Try Rhythm Simplification]

    Step2 --> Check2{Difficulty <= Cap?}
    Check2 -->|Yes| Log2[Record RHYTHM_SIMPLIFY]
    Check2 -->|No| Budget2{Rhythm Budget Remaining?}
    Budget2 -->|No| Step3
    Budget2 -->|Yes| Repeat2[Apply Rhythm Edit]
    Repeat2 --> Step3[Try Passing-Note Removal]

    Step3 --> Check3{Difficulty <= Cap?}
    Check3 -->|Yes| Log3[Record DROP_PASSING_NOTE]
    Check3 -->|No| Budget3{Substitution Budget Remaining?}
    Budget3 -->|No| Fallback[Mark Span Not Recommended]
    Budget3 -->|Yes| Step4[Try Diatonic Substitution]

    Step4 --> Check4{Difficulty <= Cap?}
    Check4 -->|Yes| Log4[Record SUBSTITUTE_DIATONIC]
    Check4 -->|No| Fallback

    Log1 --> Aggregate[Update edits_used & difficulty delta]
    Log2 --> Aggregate
    Log3 --> Aggregate
    Log4 --> Aggregate
    Fallback --> Aggregate
    Aggregate --> ReturnResult
```

Implementation notes:

- Each ladder stage is bounded by `SalvageBudgets` so a span can consume at most
  one octave move, one rhythm simplification, one substitution, and a finite
  number of total steps before the cascade stops.
- After each edit, `ExplanationEvent` captures the action, reason code, span ID,
  and difficulty delta. The cascade persists these payloads so the UI can
  display them verbatim.
- When the cascade exhausts budgets without bringing the span below the target
  difficulty, it marks the specific span as “not recommended” rather than
  rejecting the full arrangement.

## Further Reading

- [Arranger Implementation Plan](arranger_best_effort_plan.md) – milestone
  breakdown, ROI ordering, and testing strategy.
- `tests/integration/test_arranger_polyphonic.py` – regression suite covering
  melody isolation, octave folding, subhole enforcement, breath planning, and
  range clamping.
- `services/arranger_preview.py` – service that adapts domain results into the
  desktop UI’s arranged preview, including diagnostic logging and monophonic
  sanitization.
