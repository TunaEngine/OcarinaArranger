from __future__ import annotations


def test_default_mode_renders_classic_controls(gui_app):
    gui_app.update_idletasks()
    assert gui_app.arranger_mode.get() == "classic"
    frames = getattr(gui_app, "_arranger_mode_frames", {})
    classic_entry = frames.get("classic", {})
    best_effort_entry = frames.get("best_effort", {})
    classic = classic_entry.get("left")
    best_effort = best_effort_entry.get("left")
    results_section = getattr(gui_app, "_arranger_results_section", None)
    assert classic is not None
    assert best_effort is not None
    assert results_section is not None
    gui_app.update()  # ensure grid bookkeeping is initialised
    assert classic.winfo_manager() == "grid"
    assert best_effort.winfo_manager() in {"", None}
    assert results_section.winfo_manager() in {"", None}


def test_switch_to_best_effort_updates_preferences(gui_app, monkeypatch):
    saved_modes: list[str] = []

    def _record(preferences):  # noqa: ANN001 - matches monkeypatch target signature
        saved_modes.append(preferences.arranger_mode)

    monkeypatch.setattr("ocarina_gui.preferences.save_preferences", _record)
    monkeypatch.setattr(
        "ui.main_window.initialisation.convert_controls.save_preferences", _record
    )

    gui_app.arranger_mode.set("best_effort")
    gui_app.update()

    assert gui_app.arranger_mode.get() == "best_effort"
    assert gui_app._viewmodel.state.arranger_mode == "best_effort"
    assert gui_app.preferences is not None
    assert gui_app.preferences.arranger_mode == "best_effort"
    frames = getattr(gui_app, "_arranger_mode_frames", {})
    classic_entry = frames.get("classic", {})
    best_effort_entry = frames.get("best_effort", {})
    classic = classic_entry.get("left")
    best_effort = best_effort_entry.get("left")
    results_section = getattr(gui_app, "_arranger_results_section", None)
    assert classic is not None
    assert best_effort is not None
    assert results_section is not None
    assert best_effort.winfo_manager() == "grid"
    assert classic.winfo_manager() in {"", None}
    assert results_section.winfo_manager() == "grid"
    assert saved_modes
    assert saved_modes[-1] == "best_effort"

    gui_app.arranger_mode.set("classic")
    gui_app.update()
    assert classic.winfo_manager() == "grid"
    assert best_effort.winfo_manager() in {"", None}
    assert results_section.winfo_manager() in {"", None}
