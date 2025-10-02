from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from services.update import (
    API_RELEASES_URL,
    API_URL,
    GitHubReleaseProvider,
    LocalFolderReleaseProvider,
    UPDATE_CHANNEL_BETA,
    UPDATE_CHANNEL_STABLE,
)
from tests.unit.update_service_test_utils import build_update_archive


def test_local_release_provider_reads_metadata(tmp_path: Path) -> None:
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    metadata = {
        "version": "3.1.4",
        "installer": archive_path.name,
        "sha256": digest,
        "release_notes": "  Lots of improvements.  ",
        "entry_point": "OcarinaArranger/OcarinaArranger.exe",
    }
    (tmp_path / "release.json").write_text(json.dumps(metadata), encoding="utf-8")

    provider = LocalFolderReleaseProvider(tmp_path)
    info = provider.fetch_latest()

    assert info is not None
    assert info.version == "3.1.4"
    assert info.asset_name == archive_path.name
    assert info.source_path == archive_path
    assert info.hash_value == digest
    assert info.release_notes == "Lots of improvements."
    assert info.entry_point == "OcarinaArranger/OcarinaArranger.exe"


def test_github_provider_prefers_windows_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    latest_payload = {
        "url": "https://api.github.com/repos/TunaEngine/OcarinaArranger/releases/251525990",
        "tag_name": "v1.2.1",
        "body": "1.2.1 Fixed GH release action\n\n- 1.2.1 Fixed GH release action\n- Added support links\n- Added auto-update feature (Windows-only)\n- Add windway editing support for multi-chamber instruments\n- Expand fingering note range support\n- Adjust preview hover behaviour for playback and cursor drag",
        "assets": [
            {
                "name": "OcarinaArranger-linux.zip",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v1.2.1/OcarinaArranger-linux.zip",
            },
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v1.2.1/OcarinaArranger-windows.zip",
            },
        ],
    }

    detail_payload = {
        **latest_payload,
        "assets": [
            {
                "name": "OcarinaArranger-linux.zip",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v1.2.1/OcarinaArranger-linux.zip",
                "digest": "sha256:23312fa9e67350e7809e58ffd9a8c2e220fe857180d087407145ec3cf29612a0",
            },
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v1.2.1/OcarinaArranger-windows.zip",
                "digest": "sha256:1a90f7d53827d01d76a5292a24f4a4ca0a3a561e0e889eb157c1c046e5780ff6",
            },
        ],
    }

    responses = {
        "https://example.invalid/api": json.dumps(latest_payload).encode("utf-8"),
        latest_payload["url"]: json.dumps(detail_payload).encode("utf-8"),
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    requested_urls: list[str] = []

    def fake_urlopen(url: str):  # type: ignore[override]
        requested_urls.append(url)
        payload = responses.get(url)
        if payload is None:
            raise AssertionError(f"Unexpected URL requested: {url}")
        return FakeResponse(payload)

    monkeypatch.setattr("services.update.providers.urlopen", fake_urlopen)

    provider = GitHubReleaseProvider(api_url="https://example.invalid/api")
    info = provider.fetch_latest()

    assert info is not None
    assert info.version == "1.2.1"
    assert info.asset_name == "OcarinaArranger-windows.zip"
    assert (
        info.download_url
        == "https://github.com/TunaEngine/OcarinaArranger/releases/download/v1.2.1/OcarinaArranger-windows.zip"
    )
    assert info.hash_value == "1a90f7d53827d01d76a5292a24f4a4ca0a3a561e0e889eb157c1c046e5780ff6"
    assert info.hash_url is None
    assert info.release_notes is not None
    assert info.release_notes.startswith("1.2.1 Fixed GH release action")
    assert requested_urls == ["https://example.invalid/api", latest_payload["url"]]


def test_github_provider_falls_back_to_companion_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    latest_payload = {
        "url": "https://api.github.com/repos/TunaEngine/OcarinaArranger/releases/2718281828",
        "tag_name": "v2.0.0",
        "body": "v2.0.0 release notes",
        "assets": [
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v2.0.0/OcarinaArranger-windows.zip",
            },
        ],
    }

    detail_payload = {
        **latest_payload,
        "assets": [
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v2.0.0/OcarinaArranger-windows.zip",
            },
            {
                "name": "OcarinaArranger-windows.zip.sha256",
                "browser_download_url": "https://github.com/TunaEngine/OcarinaArranger/releases/download/v2.0.0/OcarinaArranger-windows.zip.sha256",
            },
        ],
    }

    responses = {
        "https://example.invalid/api": json.dumps(latest_payload).encode("utf-8"),
        latest_payload["url"]: json.dumps(detail_payload).encode("utf-8"),
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    def fake_urlopen(url: str):  # type: ignore[override]
        payload = responses.get(url)
        if payload is None:
            raise AssertionError(f"Unexpected URL requested: {url}")
        return FakeResponse(payload)

    monkeypatch.setattr("services.update.providers.urlopen", fake_urlopen)

    provider = GitHubReleaseProvider(api_url="https://example.invalid/api")
    info = provider.fetch_latest()

    assert info is not None
    assert info.version == "2.0.0"
    assert info.asset_name == "OcarinaArranger-windows.zip"
    assert (
        info.download_url
        == "https://github.com/TunaEngine/OcarinaArranger/releases/download/v2.0.0/OcarinaArranger-windows.zip"
    )
    assert info.hash_value is None
    assert (
        info.hash_url
        == "https://github.com/TunaEngine/OcarinaArranger/releases/download/v2.0.0/OcarinaArranger-windows.zip.sha256"
    )


def test_github_provider_prefers_beta_releases_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    listing_payload = [
        {
            "url": "https://api.github.com/repos/TunaEngine/OcarinaArranger/releases/2",
            "tag_name": "v1.2.4.dev",
            "prerelease": True,
        },
        {
            "url": "https://api.github.com/repos/TunaEngine/OcarinaArranger/releases/1",
            "tag_name": "v1.2.3",
            "prerelease": False,
        },
    ]

    dev_detail = {
        "tag_name": "v1.2.4.dev",
        "prerelease": True,
        "assets": [
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://example.invalid/dev.zip",
                "digest": "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            }
        ],
    }
    stable_detail = {
        "tag_name": "v1.2.3",
        "prerelease": False,
        "assets": [
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://example.invalid/stable.zip",
                "digest": "sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            }
        ],
    }

    responses = {
        "https://example.invalid/releases": json.dumps(listing_payload).encode("utf-8"),
        listing_payload[0]["url"]: json.dumps(dev_detail).encode("utf-8"),
        listing_payload[1]["url"]: json.dumps(stable_detail).encode("utf-8"),
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.close()

    requested_urls: list[str] = []

    def fake_urlopen(url: str):  # type: ignore[override]
        requested_urls.append(url)
        payload = responses.get(url)
        if payload is None:
            raise AssertionError(f"Unexpected URL requested: {url}")
        return FakeResponse(payload)

    monkeypatch.setattr("services.update.providers.urlopen", fake_urlopen)

    provider = GitHubReleaseProvider(
        api_url=API_URL,
        releases_url="https://example.invalid/releases",
        channel=UPDATE_CHANNEL_BETA,
    )

    info = provider.fetch_latest()

    assert info is not None
    assert info.version == "1.2.4.dev"
    assert info.download_url == "https://example.invalid/dev.zip"
    assert info.hash_value == "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    assert requested_urls == ["https://example.invalid/releases", listing_payload[0]["url"]]


def test_github_provider_falls_back_to_listing_when_latest_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    stable_detail = {
        "tag_name": "v1.2.1",
        "prerelease": False,
        "assets": [
            {
                "name": "OcarinaArranger-windows.zip",
                "browser_download_url": "https://example.invalid/stable.zip",
                "digest": "sha256:" + "ab" * 32,
            }
        ],
    }

    provider = GitHubReleaseProvider(channel=UPDATE_CHANNEL_STABLE)

    def fake_request(self: GitHubReleaseProvider, url: str) -> dict | list[dict] | None:
        calls.append(url)
        if url == API_URL:
            return None
        if url == API_RELEASES_URL:
            return [stable_detail]
        raise AssertionError(f"Unexpected URL requested: {url}")

    monkeypatch.setattr(GitHubReleaseProvider, "_request_json", fake_request)
    monkeypatch.setattr(
        GitHubReleaseProvider,
        "_resolve_release_details",
        lambda self, payload: payload,
    )

    release = provider.fetch_latest()

    assert release is not None
    assert release.version == "1.2.1"
    assert calls == [API_URL, API_RELEASES_URL]
