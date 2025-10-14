# Test Execution Guide

This guide consolidates the commands and troubleshooting tips for exercising the
Ocarina Arranger automated test suite.

## Prerequisites

Create and activate the project virtual environment before installing
dependencies or invoking any tooling:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows the activation command is:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The GUI tests depend on `ttkbootstrap`, which is only available once the
virtual environment is active. If you forget to activate it, `pytest` will
report missing imports when collecting the UI suite.

## Running the suite

Run all tests from the same activated environment so Python resolves modules
and native libraries from the virtualenv:

```bash
xvfb-run -a .venv/bin/pytest
```

On Windows invoke the virtualenv binary directly:

```powershell
.venv\Scripts\pytest.exe
```

### File length guard

We enforce a 500-line ceiling on Python source files via
`tests/test_source_file_lengths.py`. Run the guard with `--maxfail=1` so the
first oversized file is reported immediately:

```bash
pytest tests/test_source_file_lengths.py --maxfail=1
```

Audio renderer tests now live under `tests/unit/audio_renderer/` after splitting
the legacy monolithic module, so each test file complies with this limit.

### Headless GUI tests

Tkinter-based GUI tests require a display server. On Linux CI we rely on
`xvfb-run` as shown above. Locally on Windows and macOS, run the suite from a
regular desktop session so the tests can create and destroy Tk windows.

## Troubleshooting

### Layout editor footer tests never see mapped widgets on Windows

The `tests/ui/test_gui_layout_editor.py` suite used to fail on Windows because
we launched the instrument layout editor while the hidden root window was still
transitioning from `withdrawn` to `deiconify`. The footer hierarchy stays
unmapped until several idle cycles complete, which meant our tight polling loop
never observed the mapping and the assertions failed.

The fix deiconifies the root window before opening the layout editor, so the
footer widgets can map immediately. If you reintroduce a similar failure on
Windows (for example by modifying the layout editor launcher), make sure the
root window is viewable before triggering the editor.

### Tkinter display unavailable

Many GUI tests call `pytest.skip` when Tk cannot create a display (for example
when running in a pure SSH session without `xvfb-run`). Activate the virtualenv
and rerun the suite with `xvfb-run -a` or from a desktop session to satisfy the
Tk requirement.

### Missing fixtures or assets

If tests complain about missing fixture assets (for example MIDI or MusicXML
fixtures), rerun `git submodule update --init --recursive` and ensure you are in
the project root when executing the suite.
