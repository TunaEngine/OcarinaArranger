from __future__ import annotations

import logging
import time
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from tests.e2e.support.linux_command_channel import (
    invoke_automation_command,
    wait_for_status,
)
from tests.e2e.support.linux_screenshots import normalise_slug, timestamped_filename
from tests.e2e.support.x11_window import X11WindowSession

logger = logging.getLogger(__name__)


@given("the Ocarina Arranger app is launched with Linux X11 automation")
def ensure_linux_app_launched(linux_main_window_session: X11WindowSession) -> None:
    linux_main_window_session.activate_window()


@then(parsers.parse('xdotool should detect a window titled "{title}"'))
def linux_xdotool_detects_window(
    linux_main_window_session: X11WindowSession,
    title: str,
) -> None:
    linux_main_window_session.require_window(title=title)


@then(parsers.parse('the Linux Ocarina Arranger window title should start with "{prefix}"'))
def linux_window_title_prefix(
    linux_main_window_session: X11WindowSession,
    prefix: str,
) -> None:
    actual = linux_main_window_session.window_name()
    assert actual.startswith(prefix), f"Expected title to start with '{prefix}', got '{actual}'"


@when(parsers.parse('on Linux I focus the window titled "{title}"'))
def linux_focus_window(
    linux_main_window_session: X11WindowSession,
    title: str,
) -> None:
    linux_main_window_session.focus_window(title=title)


@when(parsers.parse('on Linux I send the keys "{key_sequence}" to the Ocarina Arranger window'))
def linux_send_keys(
    linux_main_window_session: X11WindowSession,
    key_sequence: str,
) -> None:
    linux_send_keys_to_window(linux_main_window_session, key_sequence, "Ocarina Arranger")


@when(parsers.parse('on Linux I send the keys "{key_sequence}" to the window titled "{title}"'))
def linux_send_keys_to_window(
    linux_main_window_session: X11WindowSession,
    key_sequence: str,
    title: str,
) -> None:
    linux_main_window_session.focus_window(title=title)
    keys = [token for token in key_sequence.split() if token]
    if not keys:
        return
    linux_main_window_session.send_keys(*keys)
    time.sleep(0.3)


@when(parsers.parse('on Linux I select the "{theme}" theme via the menu'))
def linux_select_theme(linux_main_window_session: X11WindowSession, theme: str) -> None:
    normalized = theme.strip().lower()
    if normalized not in {"light", "dark"}:
        raise AssertionError(f"Unsupported theme request: {theme}")
    linux_main_window_session.activate_window()
    linux_main_window_session.send_keys("alt+V")
    time.sleep(0.4)
    linux_main_window_session.send_keys("Home")
    time.sleep(0.2)
    if normalized == "dark":
        linux_main_window_session.send_keys("Down")
        time.sleep(0.2)
    linux_main_window_session.send_keys("Return")
    time.sleep(0.6)


@when(parsers.parse("on Linux I wait {seconds:f} seconds"))
@then(parsers.parse("on Linux I wait {seconds:f} seconds"))
def linux_wait(seconds: float) -> None:
    time.sleep(seconds)


@when("on Linux I open the Instrument Layout Editor via the menu")
def linux_open_instrument_editor(
    linux_command_file: Path,
    linux_preview_status_file: Path,
) -> None:
    invoke_automation_command(
        linux_command_file, linux_preview_status_file, "open_instrument_layout"
    )


@when("on Linux I open the Third-Party Licenses via the menu")
def linux_open_licenses_menu(
    linux_command_file: Path, linux_preview_status_file: Path
) -> None:
    invoke_automation_command(
        linux_command_file, linux_preview_status_file, "open_licenses"
    )


@when("on Linux I wait for the seeded preview data to render")
@then("on Linux I wait for the seeded preview data to render")
def linux_wait_for_preview(linux_preview_status_file: Path) -> None:
    wait_for_status(linux_preview_status_file, "preview", "ready")


@when(parsers.parse('on Linux I select the "{tab}" tab via automation'))
def linux_select_tab_via_automation(
    linux_command_file: Path, linux_preview_status_file: Path, tab: str
) -> None:
    normalized = tab.strip().lower()
    if normalized not in {"convert", "fingerings", "original", "arranged"}:
        raise AssertionError(f"Unsupported tab request: {tab}")
    invoke_automation_command(
        linux_command_file, linux_preview_status_file, f"select_tab:{normalized}"
    )
    time.sleep(0.2)


@when(parsers.parse('on Linux I activate the "{theme}" theme via automation'))
def linux_activate_theme_via_automation(
    linux_command_file: Path, linux_preview_status_file: Path, theme: str
) -> None:
    normalized = theme.strip().lower()
    if normalized not in {"light", "dark"}:
        raise AssertionError(f"Unsupported theme request: {theme}")
    invoke_automation_command(
        linux_command_file, linux_preview_status_file, f"set_theme:{normalized}"
    )
    time.sleep(0.4)


@when(parsers.parse('on Linux I capture a screenshot of the active window named "{slug}"'))
@then(parsers.parse('on Linux I capture a screenshot of the active window named "{slug}"'))
def linux_capture_window_screenshot(
    linux_main_window_session: X11WindowSession,
    linux_screenshot_directory: Path,
    record_e2e_screenshot,
    slug: str,
) -> Path:
    normalised = normalise_slug(slug)
    destination = linux_screenshot_directory / timestamped_filename(normalised)
    linux_main_window_session.capture_window_screenshot(destination)
    record_e2e_screenshot(destination)
    return destination


@when(parsers.parse('on Linux I capture a full screen screenshot named "{slug}"'))
@then(parsers.parse('on Linux I capture a full screen screenshot named "{slug}"'))
def linux_capture_full_screen(
    linux_main_window_session: X11WindowSession,
    linux_screenshot_directory: Path,
    record_e2e_screenshot,
    slug: str,
) -> Path:
    normalised = normalise_slug(slug)
    destination = linux_screenshot_directory / timestamped_filename(f"full-{normalised}")
    linux_main_window_session.capture_fullscreen_screenshot(destination)
    record_e2e_screenshot(destination)
    return destination


@when("the Linux Ocarina Arranger process should still be running")
@then("the Linux Ocarina Arranger process should still be running")
def linux_process_running(linux_main_window_session: X11WindowSession) -> None:
    linux_main_window_session.assert_running()


__all__ = []

