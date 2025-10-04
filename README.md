# Ocarina Arranger

**Disclaimer**: This is a vibe-coded project, it works for me and I find it useful. Use at your own risk, no warranties provided.

## Run

### Option 1: download the Release binary (Windows and Linux only). Linux is non-tested.

### Option 2:

```bash
python -m ocarina_gui.app
```

## Main features

1. Audio playback - both original and arranged tracks
2. Tempo change
3. Transposition
4. Metronome
5. Loop for faster learning

## Loop feature

![alt text](README-assets/loop.gif)

## Instrument editor

![alt text](README-assets/instrument-editor.png)

## Fingerings

![alt text](README-assets/fingerings.png)

## PDF export

![alt text](README-assets/pdf-pianoroll.png)
![alt text](README-assets/pdf-staff.png)
![alt text](README-assets/pdf-fingerings.png)

## Dark theme

![alt text](README-assets/dark.png)

## Community

Join our Discord community on [Discord](https://discord.gg/xVs5W6WR).

## Notes

- Conversion pipeline: transpose to C/Am -> collapse chords -> enforce A4-F6 -> (optional) favor lower register.

## Debug logs

When troubleshooting preview playback the app now records verbose diagnostics to
`~/.ocarina_arranger/logs/preview.log` (or to the directory specified via the
`OCARINA_LOG_DIR` / `OCARINA_LOG_FILE` environment variables). Share this file
when reporting audio issues so we can inspect the detailed playback timeline.

## Automatic updates (Windows)

On Windows, the application can automatically check GitHub releases on startup and
download the portable ZIP package when a newer version is available. Automatic
checks are disabled by default; enable them through **Tools → Enable Automatic
Updates** and the preference will be remembered between sessions. Manual checks are
available through
**Tools → Check for Updates...**, which surfaces the release notes (when
available) before downloading a newer release. To exercise the update flow
locally without publishing a release, point the application at a directory
containing a `release.json` manifest by setting the
`OCARINA_UPDATE_LOCAL_DIR` environment variable. The manifest should provide the
fields `version`, `installer` and either `sha256` or `sha256_file`, with
optional `release_notes` and `entry_point` strings, for example:

```json
{
  "version": "1.2.3",
  "installer": "OcarinaArranger-windows.zip",
  "sha256": "<sha256 hex digest>",
  "release_notes": "Bug fixes and improvements.",
  "entry_point": "OcarinaArranger/OcarinaArranger.exe"
}
```

When `sha256_file` is specified it must point to a sibling file containing the
digest (in the common `<hash>  <filename>` format). After verifying the hash,
the updater stages the portable bundle and replaces the existing
`OcarinaArranger/` directory (which also contains the `_internal` folder with
the bundled DLLs and Python runtime) before relaunching from the same
location.

## Package Layout

- GUI code now lives in the `ocarina_gui/` package, split into focused modules (`app.py`, `piano_roll.py`, `staff.py`, `fingering.py`, etc.).
- Core music logic remains in the `ocarina_tools/` package.
- `ocarina_gui/__init__.py` re-exports `App` and the exporter helpers so existing imports continue to work.
- Tests import through the package roots; see `tests/conftest.py` for the path helper.

## Running Tests

Install the test dependencies first:

```
python -m pip install pytest pytest-bdd
```

Then run the suite:

```
python -m pytest
```

For the roadmap that tracks behaviour-driven UI coverage, see
[`docs/e2e_test_plan.md`](docs/e2e_test_plan.md).

### Polyphonic MIDI regression

The automated regression that exercises a polyphonic MIDI import/export round-trip expects a local sample file that you
provide yourself. Point the test suite at a polyphonic MIDI file by exporting an environment variable before running pytest:

```
export OCARINA_TEST_POLYPHONIC_MIDI=/path/to/your/polyphonic.mid
python -m pytest tests/test_exporters.py::test_polyphonic_midi_roundtrip_preserves_events
```

for Windows:

```
set OCARINA_TEST_POLYPHONIC_MIDI=C:\path\to\your\polyphonic.mid
```

If the variable is unset the test is skipped, so regular `python -m pytest` runs still succeed without the optional asset.
