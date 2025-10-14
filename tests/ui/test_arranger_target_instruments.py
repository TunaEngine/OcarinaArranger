from __future__ import annotations

from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)


def _activate_best_effort(gui_app) -> None:
    gui_app.arranger_mode.set("best_effort")
    gui_app.update_idletasks()
    if hasattr(gui_app, "_update_arranger_mode_layout"):
        gui_app._update_arranger_mode_layout()
    gui_app.update_idletasks()


def test_best_effort_strategy_controls_visible(gui_app) -> None:
    _activate_best_effort(gui_app)

    buttons = getattr(gui_app, "_arranger_strategy_buttons", {})
    assert set(buttons) == {"current", "starred-best"}
    for button in buttons.values():
        assert button.winfo_manager()

    checkboxes = getattr(gui_app, "_starred_checkbox_widgets", {})
    assert len(checkboxes) >= 2
    texts = [widget.cget("text") for widget in checkboxes.values()]
    assert any("Test instrument" in text for text in texts)


def test_starred_selection_updates_viewmodel(gui_app) -> None:
    _activate_best_effort(gui_app)

    checkboxes = getattr(gui_app, "_starred_checkbox_widgets", {})
    instrument_id, widget = next(iter(checkboxes.items()))
    assert instrument_id not in gui_app._viewmodel.state.starred_instrument_ids

    widget.invoke()
    gui_app.update_idletasks()
    assert instrument_id in gui_app._viewmodel.state.starred_instrument_ids

    widget.invoke()
    gui_app.update_idletasks()
    assert instrument_id not in gui_app._viewmodel.state.starred_instrument_ids


def test_arranger_summary_renders_rows(gui_app) -> None:
    _activate_best_effort(gui_app)

    summaries = (
        ArrangerInstrumentSummary(
            instrument_id="test",
            instrument_name="Test instrument",
            easy=1.0,
            medium=0.5,
            hard=0.0,
            very_hard=0.0,
            tessitura=0.25,
            transposition=0,
            is_winner=True,
        ),
        ArrangerInstrumentSummary(
            instrument_id="test_alt",
            instrument_name="Secondary test instrument",
            easy=0.5,
            medium=0.75,
            hard=0.25,
            very_hard=0.1,
            tessitura=0.5,
            transposition=2,
            is_winner=False,
        ),
    )

    gui_app._render_arranger_summary(summaries)
    gui_app.update_idletasks()

    body = getattr(gui_app, "_arranger_summary_body", None)
    assert body is not None
    texts = [child.cget("text") for child in body.winfo_children()]
    assert "Test instrument" in texts
    assert "Secondary test instrument" in texts
    assert "⭐ Winner" in texts
    assert any(text.startswith("0.5") or text.startswith("0.50") for text in texts)
    assert any(text in {"+2", "2"} for text in texts)


def test_arranger_summary_placeholder_when_empty(gui_app) -> None:
    _activate_best_effort(gui_app)
    gui_app._render_arranger_summary(())
    gui_app.update_idletasks()
    body = getattr(gui_app, "_arranger_summary_body", None)
    assert body is not None
    messages = [child.cget("text") for child in body.winfo_children()]
    assert any("Arrange a score" in text for text in messages)


def test_results_panel_defaults(gui_app) -> None:
    _activate_best_effort(gui_app)

    results_section = getattr(gui_app, "_arranger_results_section", None)
    assert results_section is not None
    assert results_section.winfo_manager() == "grid"

    assert "Arrange a score" in gui_app.arranger_summary_status.get()
    tree = getattr(gui_app, "_arranger_explanations_tree", None)
    assert tree is not None
    assert tree.get_children() == ()
    assert "No explanation" in gui_app.arranger_explanation_detail.get()


def test_results_panel_updates_from_state(gui_app) -> None:
    _activate_best_effort(gui_app)

    summary = ArrangerResultSummary(
        instrument_id="test",
        instrument_name="Test instrument",
        transposition=-1,
        easy=1.0,
        medium=0.5,
        hard=0.2,
        very_hard=0.0,
        tessitura=0.25,
        starting_difficulty=0.9,
        final_difficulty=0.6,
        difficulty_threshold=0.65,
        met_threshold=True,
        difficulty_delta=0.3,
        applied_steps=("OCTAVE_DOWN_LOCAL", "rhythm-simplify"),
        edits=ArrangerEditBreakdown(total=2, octave=1, rhythm=1, substitution=0),
    )
    explanations = (
        ArrangerExplanationRow(
            bar=5,
            action="OCTAVE_DOWN_LOCAL",
            reason="RANGE_EDGE (G5..A5 > max G5)",
            reason_code="range-edge",
            difficulty_delta=0.2,
            before_note_count=8,
            after_note_count=8,
            span_id="span-1",
            span="beats 3-4",
            key_id=None,
        ),
        ArrangerExplanationRow(
            bar=8,
            action="rhythm-simplify",
            reason="Dropped ornament",
            reason_code="rhythm-simplify",
            difficulty_delta=0.1,
            before_note_count=10,
            after_note_count=8,
            span_id="span-2",
            key_id="key-1",
        ),
    )
    telemetry = (
        ArrangerTelemetryHint(
            category="Breath",
            message="Insert a breath at bar 4 after the held note.",
        ),
    )

    gui_app._viewmodel.update_arranger_results(
        summary=summary,
        explanations=explanations,
        telemetry=telemetry,
    )
    gui_app._refresh_arranger_results_from_state()
    gui_app.update_idletasks()

    status = gui_app.arranger_summary_status.get()
    assert "0.60" in status and "0.65" in status and "transposition -1" in status
    assert gui_app.arranger_edits_total.get() == "2"
    assert gui_app.arranger_applied_steps.get().startswith("OCTAVE_DOWN_LOCAL")

    tree = getattr(gui_app, "_arranger_explanations_tree", None)
    assert tree is not None
    children = tree.get_children()
    assert len(children) == 2
    tree.selection_set(children[0])
    gui_app._on_arranger_explanation_selected(None)
    detail = gui_app.arranger_explanation_detail.get()
    assert "Bar 5" in detail and "beats 3-4" in detail

    telemetry_container = getattr(gui_app, "_arranger_telemetry_container", None)
    assert telemetry_container is not None
    labels = []
    for child in telemetry_container.winfo_children():
        if child.winfo_children():
            labels.extend(c for c in child.winfo_children() if hasattr(c, "cget"))
        elif hasattr(child, "cget"):
            labels.append(child)
    assert any("Breath" in lbl.cget("text") or "Insert a breath" in lbl.cget("text") for lbl in labels)


def test_results_explanation_filter(gui_app) -> None:
    _activate_best_effort(gui_app)

    explanations = (
        ArrangerExplanationRow(
            bar=1,
            action="OCTAVE_DOWN_LOCAL",
            reason="RANGE_EDGE (G5..A5 > max G5)",
            reason_code="range-edge",
            difficulty_delta=0.2,
            before_note_count=6,
            after_note_count=6,
            span_id="span-a",
            span="beat 1",
            key_id=None,
        ),
        ArrangerExplanationRow(
            bar=3,
            action="rhythm-simplify",
            reason="Drop",
            reason_code="rhythm-simplify",
            difficulty_delta=0.1,
            before_note_count=7,
            after_note_count=5,
            span_id="span-b",
            key_id=None,
        ),
    )
    gui_app._viewmodel.update_arranger_results(
        explanations=explanations,
    )
    gui_app._refresh_arranger_results_from_state()
    gui_app.update_idletasks()

    tree = getattr(gui_app, "_arranger_explanations_tree", None)
    assert tree is not None
    assert len(tree.get_children()) == 2

    gui_app.arranger_explanation_filter.set("range-edge")
    gui_app.update_idletasks()
    filtered = tree.get_children()
    assert len(filtered) == 1
    item_values = tree.item(filtered[0], "values")
    assert item_values[1] == "OCTAVE_DOWN_LOCAL"


def test_advanced_controls_toggle_visibility(gui_app) -> None:
    _activate_best_effort(gui_app)
    frames = getattr(gui_app, "_arranger_advanced_frames", {})
    frame = frames.get("best_effort")
    gp_frame = frames.get("gp")
    assert frame is not None
    assert gp_frame is not None
    gui_app.update_idletasks()
    assert frame.winfo_manager() in {"", None}

    gui_app.arranger_show_advanced.set(True)
    gui_app.update_idletasks()
    assert frame.winfo_manager() == "grid"

    gui_app.arranger_mode.set("classic")
    gui_app.update_idletasks()
    assert frame.winfo_manager() in {"", None}

    gui_app.arranger_mode.set("gp")
    gui_app.update_idletasks()
    assert gp_frame.winfo_manager() == "grid"

    gui_app.arranger_show_advanced.set(False)
    gui_app.update_idletasks()
    assert gp_frame.winfo_manager() in {"", None}

    gui_app.arranger_show_advanced.set(True)
    gui_app.update_idletasks()
    assert gp_frame.winfo_manager() == "grid"


def test_dp_slack_toggle_updates_viewmodel(gui_app) -> None:
    _activate_best_effort(gui_app)
    gui_app.arranger_show_advanced.set(True)
    gui_app.update_idletasks()

    assert gui_app._viewmodel.state.arranger_dp_slack_enabled is True
    gui_app.arranger_dp_slack.set(False)
    gui_app.update_idletasks()
    assert gui_app._viewmodel.state.arranger_dp_slack_enabled is False


def test_budget_spinboxes_update_viewmodel(gui_app) -> None:
    _activate_best_effort(gui_app)
    gui_app.arranger_show_advanced.set(True)
    gui_app.update_idletasks()

    gui_app.arranger_budget_octave.set(2)
    gui_app.arranger_budget_rhythm.set(2)
    gui_app.arranger_budget_substitution.set(3)
    gui_app.arranger_budget_total.set(4)
    gui_app.update_idletasks()

    budgets = gui_app._viewmodel.state.arranger_budgets
    assert budgets.max_octave_edits == 2
    assert budgets.max_rhythm_edits == 2
    assert budgets.max_substitutions == 3
    assert budgets.max_steps_per_span == 4


def test_reset_budgets_restores_defaults(gui_app) -> None:
    _activate_best_effort(gui_app)
    gui_app.arranger_show_advanced.set(True)
    gui_app.update_idletasks()

    gui_app.arranger_budget_octave.set(4)
    gui_app.arranger_budget_total.set(5)
    gui_app.update_idletasks()

    gui_app.reset_arranger_budgets()
    gui_app.update_idletasks()

    defaults = ArrangerBudgetSettings()
    budgets = gui_app._viewmodel.state.arranger_budgets
    assert budgets == defaults
    assert gui_app.arranger_budget_octave.get() == defaults.max_octave_edits
    assert gui_app.arranger_budget_total.get() == defaults.max_steps_per_span
