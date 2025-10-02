from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.update import (
    LOCAL_RELEASE_ENV,
    UPDATE_CHANNEL_STABLE,
    UpdateService,
    build_update_service,
    schedule_startup_update_check,
)
from services.update.models import InstallationPlan
from tests.unit.update_service_test_utils import RecordingInstaller, StaticReleaseProvider


def test_schedule_startup_update_check_noop_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked: list[None] = []

    class FakeInstaller:
        def install(self, plan: InstallationPlan, version: str) -> None:  # pragma: no cover - defensive
            invoked.append(None)

    monkeypatch.setenv("OCARINA_APP_VERSION", "0.0.1")
    monkeypatch.setattr("sys.platform", "linux", raising=False)

    schedule_startup_update_check(installer=FakeInstaller())

    assert invoked == []


def test_schedule_startup_update_check_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCARINA_APP_VERSION", "0.0.1")
    monkeypatch.setattr("sys.platform", "win32", raising=False)

    started: list[str] = []

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - behaviour stub
            started.append("created")

        def start(self) -> None:  # pragma: no cover - behaviour stub
            started.append("started")

    monkeypatch.setattr("services.update.builder.threading.Thread", lambda *a, **k: FakeThread())

    schedule_startup_update_check(enabled=False)

    assert started == []


def test_build_update_service_returns_none_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux", raising=False)

    service = build_update_service(channel=UPDATE_CHANNEL_STABLE)

    assert service is None


def test_build_update_service_creates_service_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32", raising=False)
    monkeypatch.setattr(
        "services.update.builder._build_provider_from_env",
        lambda channel: StaticReleaseProvider(None),
    )
    monkeypatch.setattr("services.update.builder.get_app_version", lambda: "1.0.0")

    service = build_update_service(installer=RecordingInstaller(), channel=UPDATE_CHANNEL_STABLE)

    assert isinstance(service, UpdateService)


def test_build_update_service_includes_github_fallback_for_local_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32", raising=False)
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    metadata = {
        "version": "1.2.2.dev",
        "installer": "OcarinaArranger.zip",
        "sha256": "deadbeef" * 8,
    }
    (local_dir / "release.json").write_text(json.dumps(metadata), encoding="utf-8")
    (local_dir / "OcarinaArranger.zip").write_bytes(b"payload")

    monkeypatch.setenv(LOCAL_RELEASE_ENV, str(local_dir))
    monkeypatch.setattr("services.update.builder.get_app_version", lambda: "1.2.2.dev")

    service = build_update_service(installer=RecordingInstaller(), channel=UPDATE_CHANNEL_STABLE)

    assert isinstance(service, UpdateService)
    fallback_names = [type(provider).__name__ for provider in service._fallback_providers]  # type: ignore[attr-defined]
    assert "GitHubReleaseProvider" in fallback_names
