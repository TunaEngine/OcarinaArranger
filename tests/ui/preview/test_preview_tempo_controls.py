from __future__ import annotations

import pytest

from ocarina_gui.piano_roll.view.widget import (
    _TEMPO_MARKER_BARLINE_PADDING as ROLL_TEMPO_BARLINE_PADDING,
    _TEMPO_MARKER_LEFT_PADDING as ROLL_TEMPO_LEFT_PADDING,
)
from ocarina_gui.staff.view.base import (
    _TEMPO_MARKER_BARLINE_PADDING as STAFF_TEMPO_BARLINE_PADDING,
    _TEMPO_MARKER_LEFT_PADDING as STAFF_TEMPO_LEFT_PADDING,
)

from helpers import (
    make_linear_score,
    make_linear_score_with_tempo,
    make_score_with_tempo_changes,
)
from shared.tempo import scaled_tempo_marker_pairs

from tests.ui._preview_helpers import write_score


def _canvas_marker_texts(canvas) -> list[str]:
    markers = canvas.find_withtag("tempo_marker")
    return [canvas.itemcget(item, "text") for item in markers]


def test_preview_tempo_control_updates_viewmodel(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    cancel_button = gui_app._preview_cancel_buttons["original"]
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()

    tempo_var.set(150.0)
    gui_app.update_idletasks()
    assert "disabled" not in apply_button.state()

    apply_button.invoke()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert playback.state.tempo_bpm == pytest.approx(150.0)
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()


def test_preview_tempo_summary_updates_with_scaling(gui_app, tmp_path):
    tree, _ = make_score_with_tempo_changes()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["original"]
    tempo_changes = gui_app._preview_tempo_maps["original"]
    target = float(tempo_var.get())
    marker_pairs = gui_app._preview_tempo_marker_pairs["original"]
    expected_pairs = scaled_tempo_marker_pairs(tempo_changes, target)
    assert marker_pairs == expected_pairs

    tempo_var.set(90.0)
    gui_app._on_preview_tempo_changed("original")
    gui_app.update_idletasks()

    updated_target = float(tempo_var.get())
    updated_pairs = gui_app._preview_tempo_marker_pairs["original"]
    expected_updated = scaled_tempo_marker_pairs(tempo_changes, updated_target)
    assert updated_pairs == expected_updated


def test_preview_tempo_markers_follow_tempo_changes(gui_app, tmp_path):
    tree, _ = make_score_with_tempo_changes()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    roll = gui_app.roll_orig
    staff = gui_app.staff_orig
    assert roll is not None
    assert staff is not None

    tempo_var = gui_app._preview_tempo_vars["original"]
    tempo_changes = gui_app._preview_tempo_maps["original"]
    target = float(tempo_var.get())
    expected_pairs = scaled_tempo_marker_pairs(tempo_changes, target)
    markers = gui_app._preview_tempo_marker_pairs["original"]
    assert markers == expected_pairs

    expected_labels = {label for _tick, label in expected_pairs}
    roll_texts = _canvas_marker_texts(roll.canvas)
    staff_texts = _canvas_marker_texts(staff.canvas)
    assert set(roll_texts) == expected_labels
    assert set(staff_texts) == expected_labels

    if len(expected_pairs) > 1:
        roll_items = roll.canvas.find_withtag("tempo_marker")
        staff_items = staff.canvas.find_withtag("tempo_marker")
        for (tick, label), item in zip(expected_pairs, roll_items):
            coords = roll.canvas.coords(item)
            assert coords
            bbox = roll.canvas.bbox(item)
            assert bbox
            expected_left = (
                roll.LEFT_PAD
                + tick * roll.px_per_tick
                + ROLL_TEMPO_BARLINE_PADDING
            )
            if tick == 0:
                assert bbox[0] >= roll.LEFT_PAD + ROLL_TEMPO_LEFT_PADDING
            else:
                assert bbox[0] == pytest.approx(expected_left, abs=2.0)
            expected_y = max(
                24.0,
                roll._current_geometry().note_y(roll.max_midi)  # type: ignore[attr-defined]
                + min(roll.px_per_note * 0.4, 14.0)
                - 18.0,
            )
            assert coords[1] == pytest.approx(expected_y, abs=1.5)
            assert roll.canvas.itemcget(item, "text") == label
        for (tick, label), item in zip(expected_pairs, staff_items):
            coords = staff.canvas.coords(item)
            assert coords
            bbox = staff.canvas.bbox(item)
            assert bbox
            expected_left = (
                staff.LEFT_PAD
                + tick * staff.px_per_tick
                + STAFF_TEMPO_BARLINE_PADDING
            )
            if tick == 0:
                assert bbox[0] >= staff.LEFT_PAD + STAFF_TEMPO_LEFT_PADDING
            else:
                assert bbox[0] == pytest.approx(expected_left, abs=2.0)
            expected_y = max(24.0, staff._last_y_top - 18.0)  # type: ignore[attr-defined]
            assert coords[1] == pytest.approx(expected_y, abs=1.5)
            assert staff.canvas.itemcget(item, "text") == label


def test_preview_tempo_markers_survive_zoom(gui_app, tmp_path):
    tree, _ = make_score_with_tempo_changes()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    roll = gui_app.roll_orig
    staff = gui_app.staff_orig
    assert roll is not None
    assert staff is not None

    expected_labels = set(_canvas_marker_texts(roll.canvas))
    assert expected_labels

    roll.set_zoom(2)
    gui_app.update_idletasks()
    roll.set_time_zoom(1.5)
    gui_app.update_idletasks()
    staff.set_time_zoom(0.75)
    gui_app.update_idletasks()

    assert roll._tempo_marker_items  # type: ignore[attr-defined]
    assert staff._tempo_marker_items  # type: ignore[attr-defined]
    assert set(_canvas_marker_texts(roll.canvas)) == expected_labels
    assert set(_canvas_marker_texts(staff.canvas)) == expected_labels
    assert set(label for _tick, label in gui_app._preview_tempo_marker_pairs["original"]) == expected_labels


def test_preview_tempo_markers_survive_wrapped_zoom(gui_app, tmp_path):
    tree, _ = make_score_with_tempo_changes()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    roll = gui_app.roll_orig
    assert roll is not None

    roll.set_time_scroll_orientation("vertical")
    gui_app.update_idletasks()

    roll.set_zoom(2)
    gui_app.update_idletasks()

    expected_labels = set(_canvas_marker_texts(roll.canvas))
    assert expected_labels

    roll.set_time_zoom(1.5)
    gui_app.update_idletasks()

    assert set(_canvas_marker_texts(roll.canvas)) == expected_labels


def test_preview_metronome_toggle_updates_viewmodel(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    metronome_var = gui_app._preview_metronome_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    metronome_var.set(True)
    gui_app.update_idletasks()
    apply_button.invoke()
    gui_app.update_idletasks()

    playback = gui_app._preview_playback["original"]
    assert playback.state.metronome_enabled


def test_preview_cancel_restores_previous_values(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["original"]
    metronome_var = gui_app._preview_metronome_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    cancel_button = gui_app._preview_cancel_buttons["original"]
    original_tempo = tempo_var.get()
    original_metronome = metronome_var.get()

    tempo_var.set(original_tempo + 12.0)
    metronome_var.set(not original_metronome)
    gui_app.update_idletasks()
    assert "disabled" not in cancel_button.state()

    cancel_button.invoke()
    gui_app.update_idletasks()

    assert tempo_var.get() == pytest.approx(original_tempo)
    assert metronome_var.get() == original_metronome
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()


def test_importing_new_file_resets_preview_adjustments(gui_app, tmp_path):
    tree_one, _ = make_linear_score()
    tree_two, _ = make_linear_score()
    first = write_score(tmp_path, tree_one, name="first.musicxml")
    second = write_score(tmp_path, tree_two, name="second.musicxml")

    gui_app.input_path.set(str(first))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["arranged"]
    loop_start_var = gui_app._preview_loop_start_vars["arranged"]
    loop_end_var = gui_app._preview_loop_end_vars["arranged"]
    loop_enabled_var = gui_app._preview_loop_enabled_vars["arranged"]
    apply_button = gui_app._preview_apply_buttons["arranged"]
    assert apply_button is not None

    tempo_var.set(180.0)
    loop_start_var.set(1.0)
    loop_end_var.set(2.0)
    loop_enabled_var.set(True)
    gui_app.update_idletasks()
    apply_button.invoke()
    gui_app.update_idletasks()

    arranged_playback = gui_app._preview_playback["arranged"]
    arranged_playback.state.position_tick = 240
    gui_app._update_playback_visuals("arranged")
    assert arranged_playback.state.tempo_bpm != pytest.approx(120.0)
    assert arranged_playback.state.loop.enabled

    gui_app.input_path.set(str(second))
    gui_app.update_idletasks()

    arranged_playback = gui_app._preview_playback["arranged"]
    assert arranged_playback.state.position_tick == 0
    assert arranged_playback.state.tempo_bpm == pytest.approx(120.0)
    assert not arranged_playback.state.loop.enabled
    assert not arranged_playback.state.metronome_enabled
    assert not bool(gui_app._preview_loop_enabled_vars["arranged"].get())

    preview_settings = gui_app._viewmodel.state.preview_settings
    arranged_snapshot = preview_settings.get("arranged")
    assert arranged_snapshot is not None
    assert arranged_snapshot.tempo_bpm == pytest.approx(120.0)
    assert not arranged_snapshot.metronome_enabled
    assert not arranged_snapshot.loop_enabled
    assert arranged_snapshot.loop_start_beat == pytest.approx(0.0)
    assert arranged_snapshot.loop_end_beat >= arranged_snapshot.loop_start_beat


def test_arranged_tempo_matches_original_tempo(gui_app, tmp_path):
    tree, _ = make_linear_score_with_tempo(tempo=84)
    path = write_score(tmp_path, tree)

    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    original_applied = gui_app._preview_applied_settings["original"]
    arranged_applied = gui_app._preview_applied_settings["arranged"]

    assert original_applied["tempo"] == pytest.approx(84.0)
    assert arranged_applied["tempo"] == pytest.approx(84.0)

    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    assert gui_app._preview_playback["original"].state.tempo_bpm == pytest.approx(84.0)
    assert gui_app._preview_playback["arranged"].state.tempo_bpm == pytest.approx(84.0)
    assert gui_app._preview_applied_settings["arranged"]["tempo"] == pytest.approx(84.0)
