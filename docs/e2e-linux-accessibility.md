# Ubuntu Accessibility E2E Tests (X11 + Dogtail)

This companion guide explains how to run the desktop end-to-end (E2E) suite on
Ubuntu (or other Linux distributions that expose [AT-SPI][at-spi]). The main
BDD scenarios now drive the production application through an Openbox-managed
X11 session using `xdotool`, while the bundled diagnostics continue to rely on
[Dogtail][dogtail] for deeper accessibility inspection.

The X11 flow exercises the behaviour-driven scenarios with deterministic
keyboard automation, while the Dogtail utilities remain available when you need
to confirm that Tk widgets are present on the AT-SPI bus. The suite is still
skipped automatically on CI by default; run it explicitly on a workstation or
dedicated VM.

## Summary

* Test entry point: `pytest -m "e2e and linux" tests/e2e/test_main_window_linux.py`
* Automation stack: `xdotool` + Openbox + `pytest-bdd`, with optional Dogtail
  helpers for additional accessibility inspection
* Artifacts: per-scenario PNG captures via `xwd`/ImageMagick stored under
  `tests/e2e/artifacts/linux` (configurable via `E2E_LINUX_SCREENSHOT_DIR`)
* Default captures: Main window (full desktop), Fingerings, Original, and
  Arranged previews rendered from a seeded MusicXML score that showcases the
  arranger adjustments, Instrument Layout Editor, Third-Party Licenses, plus
  dark-theme variants for each capture
* Upload helper: pass `--e2e-upload-screenshots` to `pytest` to publish captured
  PNGs via Litterbox and print file-to-URL mappings for the PR description
* Supported platforms: Ubuntu 22.04+ (GNOME session) and derivatives with AT-SPI
  enabled
* Automation channel: the entrypoint monitors a command file so tests can
  deterministically switch tabs, toggle themes, and open auxiliary windows
  without timing-sensitive keyboard choreography

## Screenshot artifacts

The Linux X11 suite records the UI state as part of each scenario. Window-
specific captures rely on `xwd` piping raw X11 framebuffer data to
ImageMagick's `convert`, which writes timestamped PNG files under
`tests/e2e/artifacts/linux` by default. Override the output directory by
setting `E2E_LINUX_SCREENSHOT_DIR` before launching pytest. If either binary is
unavailable the test session skips with `Missing X11 tooling required for
diagnostics` so the prerequisites can be installed first.

When you want to share the captures on a pull request, run pytest with
`--e2e-upload-screenshots`. The plugin uploads every PNG produced during the
session to [Litterbox](https://litterbox.catbox.moe) (default expiry: one hour)
and prints mappings in the form `file -> url`. Copy each `file -> url` line into
the PR description instead of committing the binary assets.

```text
/workspace/OcarinaArranger/tests/e2e/artifacts/linux/20240101T120000Z-tab-original.png -> https://litter.catbox.moe/example.png
```

The PR description should reproduce the exact `file -> url` mapping lines from
the test output with no extra suffixes or formatting tweaks so reviewers can
open each capture directly.

## System prerequisites

1. Install the X11 automation utilities plus the desktop accessibility runtime
   and helpers. The `gi` introspection bindings that Dogtail imports are
   provided by the `python3-gi` family _and_ their companion `gir1.2-*`
   metadata packages, so make sure they are installed together:

   ```bash
   sudo apt-get update
   sudo apt-get install -y \
    openbox \
    xdotool \
    wmctrl \
    x11-apps \
    imagemagick \
    x11-utils \
     at-spi2-core \
     dbus-x11 \
     gir1.2-atspi-2.0 \
     gir1.2-gtk-3.0 \
     gnome-screenshot \
     libgirepository1.0-dev \
     python3-dogtail \
     python3-gi \
     python3-gi-cairo \
     python3-venv \
     python3-tk \
     xvfb
   ```

  * `openbox`, `xdotool`, `wmctrl`, `x11-apps` (for `xwd`), and `x11-utils`
    supply the lightweight X11 environment and capture tooling that powers the
    keyboard-driven scenarios.
  * `imagemagick` provides the `convert` CLI that turns raw XWD buffers into
    portable PNG screenshots.
   * `python3-dogtail` brings the Python bindings used by the diagnostic suite.
   * `gnome-screenshot` is required for high-quality captures via Dogtail.
   * `dbus-x11` ensures the AT-SPI bus is reachable when running under Xvfb or
     SSH.
   * `gir1.2-atspi-2.0`, `gir1.2-gtk-3.0`, and `libgirepository1.0-dev`
     provide the introspection data that satisfies `import gi` at runtime.

2. Ensure accessibility is enabled:

   ```bash
   gsettings set org.gnome.desktop.interface toolkit-accessibility true
   ```

   Log out and back in if accessibility was disabled previously. The setting is
   persistent across reboots.

## Python environment

Create a virtual environment with the same interpreter that ships with your
desktop session (Ubuntu 24.04+ provides Python **3.12** by default) and install
the shared dependencies:

```bash
# Optional on older releases: sudo apt-get install -y python3.12 python3.12-venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
# Expose the distribution-provided accessibility bindings to the virtualenv
export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH}"
python -c "import pyatspi, gi; print('AT-SPI bridge OK')"
```

The shared requirements file now installs `dogtail` so the accessibility suite
can run from an isolated virtual environment. Dogtail still relies on the
system libraries installed earlier (GTK, AT-SPI, and the GI introspection data)
as well as the distribution-provided `pyatspi` bindings. Install the AT-SPI
Python bridge via apt (`sudo apt-get install python3-pyatspi`) if it is not
already present on your workstation.

## Smoke-test the AT-SPI bus (optional)

When Dogtail imports succeed but the tests still skip with "Unable to locate
application" messages, double-check that the accessibility bus can enumerate
windows from your virtual environment. A lightweight check launches Openbox and
`gnome-calculator` under Xvfb, then queries the AT-SPI desktop via PyAT-SPI:

```bash
sudo apt-get install -y dbus-user-session at-spi2-core xvfb openbox gnome-calculator

xvfb-run -a dbus-run-session -- bash -lc '
  export GTK_MODULES=atk-bridge
  export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH}"
  source "$(pwd)/.venv/bin/activate"
  openbox &
  gnome-calculator & sleep 1
  python - <<"PY"
import time, pyatspi
print("python exe:", __import__("sys").executable)
time.sleep(2)
desktop = pyatspi.Registry.getDesktop(0)
print("children:", [node.name for node in desktop])
PY
'
```

You should see `gnome-calculator` listed among the reported desktop children.
Warnings about portals, PipeWire, or FUSE mounts are safe to ignore in headless
containers; the crucial signal is that `pyatspi` connects and discovers
Openbox-managed windows.

## Verify the Tk window is registered on the AT-SPI bus

After confirming the generic AT-SPI smoke test above, run the application under
the same headless session to ensure Tk is exposing an accessible top-level
window. The script below mirrors the calculator flow but launches Ocarina
Arranger via the project virtual environment and prints the desktop children
that PyAT-SPI can see:

```bash
xvfb-run -a dbus-run-session -- bash -lc '
  export GTK_MODULES=atk-bridge
  export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH}"
  source "$(pwd)/.venv/bin/activate"
  openbox &
  OPENBOX_PID=$!
  .venv/bin/python -m ocarina_gui.app &
  APP_PID=$!
  python - <<"PY"
import os
import sys
import time
import pyatspi

print("python exe:", sys.executable)
print("openbox pid:", os.environ.get("OPENBOX_PID"))
print("app pid:", os.environ.get("APP_PID"))
for attempt in range(20):
    time.sleep(0.5)
    desktop = pyatspi.Registry.getDesktop(0)
    names = [node.name for node in desktop]
    print(f"attempt {attempt}: {names}")
    if any(name and "Ocarina" in name for name in names):
        break
PY
  status=$?
  kill $APP_PID || true
  kill $OPENBOX_PID || true
  exit $status
'
```

Expected output includes the application name (for example, `"Ocarina Arranger
v1.5.0"`) among the reported desktop children within a few attempts. When every
attempt prints an empty list, the Tk build in use is not advertising itself on
the AT-SPI bus. In that situation:

* Re-run the calculator smoke test above to confirm the accessibility stack is
  otherwise functioning.
* Ensure you are launching the suite from a desktop session that ships a Tk
  build compiled with accessibility enabled (Ubuntu derivatives typically do so
  when running under GNOME Wayland or X11).
* If your distribution omits the Tk accessibility bridge, install a patched Tk
  build (for example, via a vendor package that bundles AT-SPI integration) or
  rebuild Tk with AT-SPI support enabled before retrying the suite.

The Linux E2E tests will skip with an "Unable to locate application" message as
long as the Tk window is missing from the AT-SPI desktop tree, so address this
gap before retrying pytest.

## Environment variables

Export the following environment variables before invoking pytest:

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `OCARINA_LINUX_APP_CMD` | ✅ | Launch command for the Linux build, e.g. `.venv/bin/python -m tests.e2e.tools.linux_entrypoint` (seeds a sample MusicXML file for the preview tabs). |
| `OCARINA_LINUX_APP_NAME` | ➖ | Substring of the accessible application name (default: `Ocarina Arranger`). |
| `OCARINA_LINUX_WINDOW_TITLE_PREFIX` | ➖ | Optional prefix used to match the main window title. |
| `OCARINA_FORCE_NATIVE_MENUBAR` | ➖ | Set to `1` to force the Tk native menubar so keyboard-driven automation can post the menus. |
| `E2E_LINUX_SCREENSHOT_DIR` | ➖ | Overrides the screenshot output directory used by the X11 automation. |
| `OCARINA_E2E_STATUS_FILE` | ➖ | Optional JSON file recording preview progress _and_ automation command acknowledgements. The pytest harness sets this automatically. |
| `OCARINA_E2E_COMMAND_FILE` | ➖ | Path polled by the entrypoint for newline-delimited automation commands (tab/theme selection, dialog launch). Set automatically during the suite. |
| `OCARINA_E2E_SHORTCUTS` | ➖ | Enable Linux E2E-only keyboard shortcuts (set to `1`). The harness exports this so `Ctrl+Alt+Shift` accelerators work. |

Example configuration for a development checkout:

```bash
export OCARINA_LINUX_APP_CMD="$(pwd)/.venv/bin/python -m tests.e2e.tools.linux_entrypoint"
export OCARINA_LINUX_APP_NAME="Ocarina Arranger"
export OCARINA_LINUX_WINDOW_TITLE_PREFIX="Ocarina Arranger v"
export OCARINA_FORCE_NATIVE_MENUBAR=1

The `tests.e2e.tools.linux_entrypoint` helper reads the
`OCARINA_E2E_SAMPLE_XML` path that pytest injects during the suite to seed a
simple MusicXML score. This ensures the Fingerings, Original, and Arranged tabs
render meaningful content in each screenshot without requiring manual setup.

The Linux automation harness now drives the UI through a lightweight command
file. When `OCARINA_E2E_COMMAND_FILE` is defined the entrypoint polls the file
for newline-delimited commands, executes each one on the Tk event loop, and
records an acknowledgement in `OCARINA_E2E_STATUS_FILE`. The pytest fixtures use
the following commands to keep screenshots deterministic:

* `select_tab:convert`, `select_tab:fingerings`, `select_tab:original`, and
  `select_tab:arranged` focus the relevant notebook page and trigger preview
  rendering when necessary.
* `set_theme:light` and `set_theme:dark` toggle the active ttk theme.
* `open_instrument_layout` launches the Instrument Layout Editor dialog.
* `open_licenses` opens the Third-Party Licenses window.

The corresponding keyboard accelerators remain registered for manual smoke
testing (`Ctrl+Alt+Shift+F` for Fingerings, `Ctrl+Alt+Shift+O` for Original,
`Ctrl+Alt+Shift+A` for Arranged, `Ctrl+Alt+Shift+D` for dark theme, etc.), so you
can still verify behaviour interactively without the command file when needed.

## Running the suite

1. Start a graphical session or launch a virtual framebuffer (recommended when
   running on headless machines):

   ```bash
   export DISPLAY=:99
   Xvfb :99 -screen 0 1920x1080x24 &
   ```

2. Activate the virtual environment (or invoke `pytest` via the absolute path
   inside `.venv`) so the interpreter retains access to the GTK and PyGObject
   bindings registered for Python 3.12, then run the tagged scenarios:

   ```bash
   source .venv/bin/activate
   pytest -m "e2e and linux" tests/e2e/test_main_window_linux.py -rs
   ```

   The test module verifies that `openbox` and `xdotool` are available. Pytest
   skips the scenarios automatically when the binaries or
   `OCARINA_LINUX_APP_CMD` are missing, so the command can be run safely on
   hosts that have not yet been configured. The harness also exports
   `OCARINA_FORCE_NATIVE_MENUBAR=1` so keyboard navigation can post the native
   Tk menus; keep that variable in your shell if you launch the app manually
   for debugging.

3. Captured screenshots land in `tests/e2e/artifacts/linux` (or the directory
   defined by `E2E_LINUX_SCREENSHOT_DIR`). Pass `--e2e-upload-screenshots` to
   `pytest` to upload those PNGs to Litterbox automatically and copy the printed
   URLs into your pull request description. On headless hosts it is safest to
   wrap the command with `xvfb-run` and `dbus-run-session` so the AT-SPI bus is
   available while the harness captures windows:

   ```bash
   xvfb-run -a dbus-run-session -- bash -lc '
     export GTK_MODULES=atk-bridge
     export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH}"
     source "$(pwd)/.venv/bin/activate"
     pytest -m "e2e and linux" --e2e-upload-screenshots tests/e2e/test_main_window_linux.py
   '
   ```

## Troubleshooting

| Symptom | Resolution |
| ------- | ---------- |
| `Skipped: Missing X11 tooling required for diagnostics: ...` | Install `openbox` and `xdotool` (plus the supporting utilities) via the apt command above, then retry from the activated virtualenv. |
| `Skipped: Install python3-dogtail ...` | Confirm the desktop packages above are installed and exposed to your Python interpreter. From the activated virtualenv run `python -c "import dogtail; print(dogtail.__version__)"`. If it fails, prepend `/usr/lib/python3/dist-packages` to `PYTHONPATH` (e.g. `export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH`) so the distribution's Dogtail build is visible, or install Dogtail directly inside the environment with `pip install dogtail`. |
| `ModuleNotFoundError: No module named 'gi'` | Install `python3-gi`, `python3-gi-cairo`, `gir1.2-atspi-2.0`, and `gir1.2-gtk-3.0`; verify with `python -c "import gi"`. |
| `ImportError: cannot import name 'enum_register_new_gtype_and_add' from 'gi._gi'` | The PyGObject binaries provided by your distribution are tied to its default Python (e.g., 3.12 on Ubuntu 24.04). Run the suite from that interpreter (`python3 -m venv .venv && source .venv/bin/activate`) or rebuild/install matching `gi` wheels for your custom Python. |
| `Could not locate a window for ...` skip | Verify the `OCARINA_LINUX_APP_NAME` and `OCARINA_LINUX_WINDOW_TITLE_PREFIX` values match the accessible title (use `dogtail-tree` or `accerciser` to inspect). Confirm the app is launching with `headless=False` in `~/.ocarina_arranger/logs/preview.log` and that the process inherits the `DISPLAY`/`PYTHONPATH` variables from the activated virtualenv (for headless hosts, run the suite via `dbus-run-session -- xvfb-run -a ...`). |
| No menus found | Confirm the application exposes accessibility names for menu entries. Enable the Tk `-use` option if using XWayland. |
| `gnome-screenshot` errors | Install the `gnome-screenshot` package or override `DOGTAIL_SCREENSHOT_CMD` with a custom tool. |

## Utilities

* `dogtail-tree` (installed alongside Dogtail) prints the current accessibility
  hierarchy and is invaluable for adjusting selector names.
* [Accerciser](https://wiki.gnome.org/Apps/Accerciser) offers a visual
  inspector. Install it with `sudo apt-get install accerciser`.

[at-spi]: https://wiki.linuxfoundation.org/accessibility/at-spi/overview
[dogtail]: https://fedorahosted.org/dogtail/
