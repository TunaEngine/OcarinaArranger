from __future__ import annotations

from viewmodels.arranger_models import (
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerResultSummary,
)


def test_arranger_layouts_and_explanations_flow(gui_app) -> None:
    """Exercise the arranger UI across v1/v2 layouts and populated results."""

    gui_app.update_idletasks()

    frames = getattr(gui_app, "_arranger_mode_frames", {})
    classic_frame = frames.get("classic", {}).get("left")
    best_effort_frame = frames.get("best_effort", {}).get("left")
    gp_frame = frames.get("gp", {}).get("left")
    assert classic_frame is not None
    assert best_effort_frame is not None
    assert gp_frame is not None
    assert gp_frame.winfo_manager() == "grid"
    assert classic_frame.winfo_manager() in {"", None}
    assert best_effort_frame.winfo_manager() in {"", None}

    summary = ArrangerResultSummary(
        instrument_id="test",
        instrument_name="Test instrument",
        transposition=2,
        easy=0.75,
        medium=0.40,
        hard=0.10,
        very_hard=0.00,
        tessitura=0.30,
        starting_difficulty=0.85,
        final_difficulty=0.55,
        difficulty_threshold=0.65,
        met_threshold=True,
        difficulty_delta=0.30,
        applied_steps=("OCTAVE_DOWN_LOCAL", "rhythm-simplify"),
        edits=ArrangerEditBreakdown(total=2, octave=1, rhythm=1, substitution=0),
    )
    explanations = (
        ArrangerExplanationRow(
            bar=4,
            action="OCTAVE_DOWN_LOCAL",
            reason="RANGE_EDGE (G5..A5 > max G5)",
            reason_code="range-edge",
            difficulty_delta=0.18,
            before_note_count=12,
            after_note_count=12,
            span_id="span-001",
            span="beats 3-4",
            key_id="key-c",
        ),
        ArrangerExplanationRow(
            bar=9,
            action="rhythm-simplify",
            reason="Dropped ornament",
            reason_code="rhythm-simplify",
            difficulty_delta=0.12,
            before_note_count=10,
            after_note_count=8,
            span_id="span-002",
            key_id=None,
        ),
    )

    gui_app._viewmodel.update_settings(arranger_mode="best_effort")
    gui_app._viewmodel.update_arranger_results(
        summary=summary,
        explanations=explanations,
        telemetry=(),
    )

    gui_app._sync_controls_from_state()
    if hasattr(gui_app, "_update_arranger_mode_layout"):
        gui_app._update_arranger_mode_layout()
    gui_app.update_idletasks()

    assert best_effort_frame.winfo_manager() == "grid"
    assert classic_frame.winfo_manager() in {"", None}
    assert gp_frame.winfo_manager() in {"", None}

    status = gui_app.arranger_summary_status.get()
    assert "0.55" in status and "0.65" in status and "transposition +2" in status

    tree = getattr(gui_app, "_arranger_explanations_tree", None)
    assert tree is not None
    rows = tree.get_children()
    assert len(rows) == len(explanations)
    tree.selection_set(rows[0])
    gui_app._on_arranger_explanation_selected(None)
    detail_first = gui_app.arranger_explanation_detail.get()
    assert "beats 3-4" in detail_first
    tree.selection_set(rows[-1])
    gui_app._on_arranger_explanation_selected(None)
    detail = gui_app.arranger_explanation_detail.get()
    assert "Bar 9" in detail

    gui_app._viewmodel.update_settings(arranger_mode="gp")
    gui_app._sync_controls_from_state()
    if hasattr(gui_app, "_update_arranger_mode_layout"):
        gui_app._update_arranger_mode_layout()
    gui_app.update_idletasks()

    assert gp_frame.winfo_manager() == "grid"
    assert best_effort_frame.winfo_manager() in {"", None}
