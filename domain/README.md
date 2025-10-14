# Domain Layer Glossary

This glossary explains the music-theory and arranger-specific terms that appear
throughout the `domain/` package. The definitions focus on how the best-effort
ocarina arranger uses each concept so new contributors can map terminology to
the code base quickly.

## Core Musical Vocabulary

| Term | Definition | Usage in the Domain Layer |
|------|------------|---------------------------|
| **Tessitura** | The range where a melody most comfortably sits relative to an instrument’s playable span. Unlike range limits, tessitura expresses how long a line stays high or low. | Difficulty scoring (`difficulty.py`) tracks tessitura drift and biases octave folding toward passages that keep the melody near the instrument’s preferred center. |
| **Ottava (8va / 8vb)** | A notational directive that the written notes should sound one octave higher (8va) or lower (8vb) than notated. | Importers (`importers.py`, `shared/ottava.py`) normalize ottava markings so the arranger reasons about absolute pitch while retaining provenance for explanations. |
| **Octave Folding** | Moving notes by an octave (±12 semitones) to fit a playable range without changing melodic contour. | The dynamic program in `folding.py` evaluates local ±12 shifts with finite penalties, enabling “best effort” salvages rather than hard failures. |
| **Subhole** | Half-covered holes on an ocarina used to produce chromatic pitches. Rapid subhole alternations are physically demanding. | `constraints.py` models per-pair subhole limits and substitutes grace notes or alternates fingerings when passages exceed the allowed change rate. |
| **Breath Planning** | Identifying natural pauses where a wind player can breathe without disrupting phrasing. | `constraints.py` inserts breath marks when the sustained airflow exceeds a tempo- and register-aware threshold. |
| **Salvage Cascade** | The ordered sequence of corrective edits (octave shifts, rhythm simplification, substitutions, etc.) applied when a span is too difficult. | `salvage.py` enforces per-span edit budgets and records structured `ExplanationEvent` payloads for each action. |
| **Micro Edit** | A localized transformation such as dropping an ornamental note or lengthening a pivotal tone to smooth difficulty. | `micro_edits.py` provides pure helper functions that the salvage cascade reuses. |
| **Soft Key Search** | Evaluating multiple transposition offsets to find the easiest key for an instrument. | `soft_key.py` scores transpositions within ±10 semitones before the cascade performs detailed salvaging. |
| **Difficulty Label** | Continuous score buckets (Easy, Medium, Hard, Very Hard) that summarize how playable a passage is. | `difficulty.py` aggregates finger-change rates, leaps, tessitura bias, subhole exposure, and breath load to derive the labels surfaced in explanations and UI summaries. |
| **Explanation Event** | A structured record that describes why the arranger performed an edit, including a schema version, action code, reason, and before/after metrics. | `explanations.py` emits payloads consumed by the UI and analytics to maintain transparency. |

## Instrument & Strategy Concepts

- **Instrument Range Registry** – `config.py` registers playable MIDI ranges so
  `arrange()` can clamp spans and compute tessitura metrics accurately.
- **Starred Instruments** – The arranger supports comparing the current
  instrument against a starred set. Strategy tie-breakers use Hard/VeryHard
  durations, then Medium durations, then tessitura distance to pick the winner.
- **Feature Flags** – `FeatureFlags` currently exposes `dp_slack` for staging the
  octave-folding DP rollout without affecting default behavior.

## Learning & Evaluation Terms

- **Approval Logging** – `learning.py` persists user-approved arrangements,
  enabling later tuning of difficulty weights and salvage ordering.
- **Arrangement Evaluator** – Compares fresh proposals to historical approvals to
  quantify improvement or regression trends.

Refer back to this glossary whenever the code references a musical concept—the
intent is to keep the domain layer approachable even for contributors who are
new to ocarina technique.
