from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Iterable

import pytest

from tests.e2e.harness import E2EHarness, create_e2e_harness


_LITTERBOX_UPLOAD_URL = "https://litterbox.catbox.moe/resources/internals/api.php"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("e2e")
    group.addoption(
        "--e2e-upload-screenshots",
        action="store_true",
        default=False,
        help="Upload captured E2E screenshots to Litterbox and print file-to-URL mappings.",
    )
    group.addoption(
        "--e2e-upload-expiry",
        action="store",
        default="1h",
        help="When uploading screenshots, request this Litterbox expiration window (e.g. 1h, 12h, 1d).",
    )


def _get_screenshot_registry(config: pytest.Config) -> list[Path]:
    registry = getattr(config, "_e2e_screenshots", None)
    if registry is None:
        registry = []
        setattr(config, "_e2e_screenshots", registry)
    return registry


@pytest.fixture
def record_e2e_screenshot(pytestconfig: pytest.Config) -> Callable[[Path], None]:
    registry = _get_screenshot_registry(pytestconfig)

    def _record(path: Path) -> None:
        registry.append(Path(path))

    return _record


def _upload_to_litterbox(path: Path, expiry: str) -> str:
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-F",
            "reqtype=fileupload",
            "-F",
            f"time={expiry}",
            "-F",
            f"fileToUpload=@{path}",
            _LITTERBOX_UPLOAD_URL,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _iter_unique_existing(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        yield path


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # pragma: no cover - CLI utility
    config = session.config
    if not config.getoption("--e2e-upload-screenshots"):
        return

    reporter = config.pluginmanager.get_plugin("terminalreporter")
    screenshots = list(_iter_unique_existing(_get_screenshot_registry(config)))
    if not screenshots:
        if reporter is not None:
            reporter.write_line("No E2E screenshots captured; skipping Litterbox upload.")
        return

    expiry = config.getoption("--e2e-upload-expiry")
    if reporter is not None:
        reporter.section("Uploading E2E screenshots to Litterbox", sep="=")

    for path in screenshots:
        try:
            url = _upload_to_litterbox(path, expiry)
        except FileNotFoundError:
            if reporter is not None:
                reporter.write_line("curl is not available on PATH; unable to upload E2E screenshots.")
            break
        except subprocess.CalledProcessError as exc:
            message = exc.stderr or exc.stdout or str(exc)
            if reporter is not None:
                reporter.write_line(f"Failed to upload {path}: {message}")
        else:
            if reporter is not None:
                reporter.write_line(f"{path} -> {url}")


@pytest.fixture
def e2e_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> E2EHarness:
    harness = create_e2e_harness(monkeypatch, tmp_path)
    yield harness
    harness.destroy()
