"""Support and feedback menu integration for :class:`MenuActionsMixin`."""

from __future__ import annotations

import platform
import urllib.parse
import webbrowser

from app.version import get_app_version

from ._logger import logger

_SUPPORT_FORM_ID = "1FAIpQLSf_RKAOaQ2dyCPRR931x55_k34HlNPagsp6xDBodngHF0v5Wg"
_ROUTER_QUESTION_ID = "1276457049"
_APP_VERSION_QUESTION_ID = "1926758933"
_OS_QUESTION_ID = "1600824233"
_DISCORD_INVITE_URL = "https://discord.gg/xVs5W6WR"


class SupportMenuMixin:
    """Provide menu commands that route to Google Forms for user support."""

    def _send_feedback_command(self) -> None:
        self._open_support_form("General feedback")

    def _report_problem_command(self) -> None:
        self._open_support_form("Bug report")

    def _suggest_feature_command(self) -> None:
        self._open_support_form("Feature request")

    def _open_support_form(self, router_value: str) -> None:
        url = self._build_support_form_url(router_value)
        self._open_url(
            url,
            context="support form",
            failure_message="Support form URL did not open",
        )

    def _open_discord_command(self) -> None:
        self._open_url(
            _DISCORD_INVITE_URL,
            context="Discord community",
            failure_message="Discord community URL did not open",
        )

    def _build_support_form_url(self, router_value: str) -> str:
        query_params = {
            f"entry.{_ROUTER_QUESTION_ID}": router_value,
            f"entry.{_APP_VERSION_QUESTION_ID}": get_app_version(),
            f"entry.{_OS_QUESTION_ID}": self._detect_platform_label(),
        }
        encoded_params = urllib.parse.urlencode(query_params)
        return (
            f"https://docs.google.com/forms/d/e/{_SUPPORT_FORM_ID}/viewform?usp=pp_url&"
            f"{encoded_params}"
        )

    def _open_url(self, url: str, *, context: str, failure_message: str) -> None:
        try:
            opened = webbrowser.open(url, new=1, autoraise=True)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Unable to open %s", context, extra={"url": url})
            return
        if not opened:
            logger.warning(failure_message, extra={"url": url})

    def _detect_platform_label(self) -> str:
        system = (platform.system() or "").strip()
        release = (platform.release() or "").strip()
        if system and release:
            return f"{system} {release}"
        if system:
            return system
        if release:
            return release
        return platform.platform()


__all__ = ["SupportMenuMixin"]
