from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from services.update.models import ReleaseInfo


@dataclass(slots=True)
class FakeUpdateService:
    """Record update interactions and return queued outcomes."""

    name: str
    _check_results: Deque[ReleaseInfo | None | Exception] = field(default_factory=deque)
    _install_outcomes: Deque[Exception | None] = field(default_factory=deque)
    get_available_release_calls: int = 0
    download_calls: list[ReleaseInfo] = field(default_factory=list)

    def queue_available_release(self, release: ReleaseInfo | None) -> None:
        self._check_results.append(release)

    def queue_check_error(self, error: Exception) -> None:
        self._check_results.append(error)

    def queue_install_error(self, error: Exception) -> None:
        self._install_outcomes.append(error)

    def queue_install_success(self) -> None:
        self._install_outcomes.append(None)

    def get_available_release(self) -> ReleaseInfo | None:
        self.get_available_release_calls += 1
        if self._check_results:
            outcome = self._check_results.popleft()
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return None

    def download_and_install(self, release: ReleaseInfo) -> None:
        self.download_calls.append(release)
        if self._install_outcomes:
            outcome = self._install_outcomes.popleft()
            if isinstance(outcome, Exception):
                raise outcome
        return None


@dataclass(slots=True)
class FakeUpdateBuilder:
    """Factory that returns pre-registered fake update services."""

    default_service: FakeUpdateService | None
    services: dict[str, FakeUpdateService] = field(default_factory=dict)

    def register(self, channel: str, service: FakeUpdateService) -> None:
        self.services[channel] = service

    def build(self, channel: str) -> FakeUpdateService | None:
        if channel in self.services:
            return self.services[channel]
        return self.default_service
