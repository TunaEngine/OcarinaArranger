from __future__ import annotations

import logging
import os
import shlex
import textwrap
from pathlib import Path
from typing import Generator

import pytest

from tests.e2e.support.linux_accessibility import skip_unless_linux
from tests.e2e.support.x11_window import X11WindowSession, ensure_x11_cli_dependencies

logger = logging.getLogger(__name__)

_SAMPLE_MUSICXML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
    <score-partwise version="3.1">
      <part-list>
        <score-part id="P1">
          <part-name>Ocarina</part-name>
        </score-part>
      </part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
            <key>
              <fifths>0</fifths>
            </key>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
            <clef>
              <sign>G</sign>
              <line>2</line>
            </clef>
          </attributes>
          <note>
            <pitch>
              <step>C</step>
              <octave>5</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
          </note>
          <note>
            <pitch>
              <step>G</step>
              <alter>1</alter>
              <octave>7</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
          </note>
        </measure>
      </part>
    </score-partwise>
    """
).strip()


@pytest.fixture(scope="session")
def linux_screenshot_directory(pytestconfig: pytest.Config) -> Path:
    configured = os.environ.get("E2E_LINUX_SCREENSHOT_DIR")
    if configured:
        directory = Path(configured)
    else:
        directory = (
            Path(pytestconfig.rootpath)
            / "tests"
            / "e2e"
            / "artifacts"
            / "linux"
        )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture(scope="session")
def linux_sample_musicxml(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("linux-musicxml")
    path = directory / "sample-e2e.musicxml"
    path.write_text(_SAMPLE_MUSICXML, encoding="utf-8")
    return path


@pytest.fixture(scope="session")
def linux_preview_status_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("linux-status")
    path = directory / "preview-status.json"
    if path.exists():
        path.unlink()
    return path


@pytest.fixture(scope="session")
def linux_command_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("linux-command")
    path = directory / "command.txt"
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture(scope="session")
def linux_main_window_session(
    skip_unless_linux: None,
    linux_sample_musicxml: Path,
    linux_preview_status_file: Path,
    linux_command_file: Path,
) -> Generator[X11WindowSession, None, None]:
    try:
        ensure_x11_cli_dependencies()
    except RuntimeError as exc:
        pytest.skip(str(exc), allow_module_level=True)

    command = os.environ.get("OCARINA_LINUX_APP_CMD")
    if not command:
        pytest.skip(
            "Set OCARINA_LINUX_APP_CMD to launch the application (see docs/e2e-linux-accessibility.md)",
            allow_module_level=True,
        )

    title_prefix = os.environ.get("OCARINA_LINUX_WINDOW_TITLE_PREFIX", "Ocarina Arranger")
    command_tokens = shlex.split(command)

    logger.info(
        "Launching Linux X11 session. command=%s title_prefix=%s",
        " ".join(command_tokens),
        title_prefix,
    )

    launch_env = dict(os.environ)
    launch_env["OCARINA_E2E_SAMPLE_XML"] = str(linux_sample_musicxml)
    launch_env["OCARINA_E2E_STATUS_FILE"] = str(linux_preview_status_file)
    launch_env["OCARINA_E2E_SHORTCUTS"] = "1"
    launch_env["OCARINA_E2E_COMMAND_FILE"] = str(linux_command_file)

    session = X11WindowSession.launch(
        command_tokens,
        title_prefix,
        env=launch_env,
        warmup_delay=1.0,
    )

    try:
        session.require_window(title=title_prefix)
    except AssertionError as exc:
        session.close()
        pytest.skip(
            f"xdotool could not locate the Ocarina Arranger window: {exc}",
            allow_module_level=True,
        )

    try:
        yield session
    finally:
        session.close()


__all__ = [
    "linux_command_file",
    "linux_main_window_session",
    "linux_preview_status_file",
    "linux_sample_musicxml",
    "linux_screenshot_directory",
]

