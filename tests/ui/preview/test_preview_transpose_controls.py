from __future__ import annotations

from helpers import make_linear_score

from tests.ui._preview_helpers import write_score


def test_arranged_preview_transpose_requires_apply(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    calls: list[bool] = []
    original = gui_app.render_previews

    def _tracked_render() -> None:
        calls.append(True)
        return original()

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    gui_app.transpose_offset.set(gui_app.transpose_offset.get() + 1)
    gui_app.update_idletasks()

    apply_button = gui_app._transpose_apply_button
    cancel_button = gui_app._transpose_cancel_button
    assert apply_button is not None
    assert cancel_button is not None
    assert "disabled" not in apply_button.state()
    assert "disabled" not in cancel_button.state()
    assert not calls

    apply_button.invoke()
    gui_app.update_idletasks()

    assert calls
    assert "disabled" in apply_button.state()
    assert "disabled" in cancel_button.state()


def test_transpose_cancel_restores_previous_value(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    original = int(gui_app.transpose_offset.get())
    calls: list[bool] = []

    def _tracked_render() -> None:
        calls.append(True)

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    gui_app.transpose_offset.set(original + 2)
    gui_app.update_idletasks()

    cancel_button = gui_app._transpose_cancel_button
    apply_button = gui_app._transpose_apply_button
    assert cancel_button is not None
    assert apply_button is not None
    assert "disabled" not in cancel_button.state()

    cancel_button.invoke()
    gui_app.update_idletasks()

    assert gui_app.transpose_offset.get() == original
    assert not calls
    assert "disabled" in cancel_button.state()
    assert "disabled" in apply_button.state()
