from __future__ import annotations

import contextlib
import logging
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Optional, Sequence

import pytest

logger = logging.getLogger(__name__)


class LinuxAccessibilityApp:
    """Wrapper around Dogtail APIs for interacting with a Tk window."""

    def __init__(
        self,
        process: subprocess.Popen[str],
        application: object,
        window: object,
        tree_module: ModuleType,
        rawinput_module: ModuleType,
    ) -> None:
        self._process = process
        self._application = application
        self._window = window
        self._tree = tree_module
        self._rawinput = rawinput_module

    def refresh_window(self) -> None:
        """Refresh the window reference in case Dogtail returns a proxy copy."""

        try:
            self._window = self._application.child(roleName="frame")
        except self._tree.SearchError:  # pragma: no cover - defensive guard
            self._window = self._application.child(roleName="window")

    def ensure_title_prefix(self, prefix: str) -> None:
        self.refresh_window()
        title = getattr(self._window, "name", "") or ""
        assert title.startswith(prefix), f"Expected title to start with '{prefix}', got '{title}'"

    def open_menu(self, menu_name: str) -> None:
        self.refresh_window()
        node = self._find_first_by_role(menu_name, ("menu", "menu item", "push button"))
        node.click()
        time.sleep(0.2)

    def require_menu_item(self, item_label: str) -> None:
        self.refresh_window()
        self._find_first_by_role(item_label, ("menu item", "push button", "menu"))

    def require_accessible_name(self, name: str, roles: Optional[tuple[str, ...]] = None) -> object:
        """Ensure a node with the provided accessible name is discoverable."""

        self.refresh_window()
        role_candidates = roles or (
            "label",
            "push button",
            "static",
            "text",
            "menu item",
        )
        return self._find_first_by_role(name, role_candidates)

    def dismiss_menus(self) -> None:
        self.refresh_window()
        self._rawinput.keyCombo("<Escape>")
        time.sleep(0.2)

    def assert_focused(self) -> None:
        self.refresh_window()
        state = getattr(self._window, "state", None)
        if state is None:  # pragma: no cover - defensive guard
            pytest.fail("Unable to query window focus state")
        is_focused = any(state.contains(flag) for flag in ("focused", "active"))
        assert is_focused, f"Expected the window to be focused, states: {list(state)}"

    def capture_screenshot(self, destination: Path) -> Path:
        self.refresh_window()
        try:
            self._window.screenshot(str(destination))
        except Exception as exc:  # pragma: no cover - depends on desktop tooling
            pytest.fail(f"Unable to capture screenshot via Dogtail: {exc}")
        return destination

    def close(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                self._process.wait(timeout=5)
            if self._process.poll() is None:
                self._process.kill()

    def _find_first_by_role(self, name: str, roles: tuple[str, ...]):
        last_error: Optional[Exception] = None
        for role in roles:
            try:
                return self._window.child(name=name, roleName=role)
            except self._tree.SearchError as exc:
                last_error = exc
                continue
        raise AssertionError(f"Could not locate accessible element '{name}' with roles {roles}") from last_error


def is_linux_host() -> bool:
    return sys.platform.startswith("linux")


@pytest.fixture(scope="session")
def skip_unless_linux() -> None:
    if not is_linux_host():
        pytest.skip("Linux-only accessibility tests", allow_module_level=True)
    if os.environ.get("CI"):
        pytest.skip("Skipped on CI by request", allow_module_level=True)
    logger.debug("Linux accessibility suite enabled. Python executable: %s", sys.executable)


@pytest.fixture(scope="session")
def dogtail_modules(skip_unless_linux: None) -> tuple[ModuleType, ModuleType]:
    tree_module = pytest.importorskip(
        "dogtail.tree",
        reason="Install python3-dogtail to run Linux accessibility tests (see docs/e2e-linux-accessibility.md)",
    )
    rawinput_module = pytest.importorskip(
        "dogtail.rawinput",
        reason="Install python3-dogtail to run Linux accessibility tests (see docs/e2e-linux-accessibility.md)",
    )
    pytest.importorskip(
        "dogtail.utils",
        reason="Install python3-dogtail to run Linux accessibility tests (see docs/e2e-linux-accessibility.md)",
    )
    return tree_module, rawinput_module


def linux_environment(base_environment: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = dict(base_environment or os.environ)
    env.setdefault("GTK_MODULES", "gail:atk-bridge")
    env.setdefault("QT_ACCESSIBILITY", "1")
    env.setdefault("OCARINA_FORCE_NATIVE_MENUBAR", "1")
    logger.debug(
        "Linux accessibility environment prepared. GTK_MODULES=%s, PYTHONPATH=%s",
        env.get("GTK_MODULES"),
        env.get("PYTHONPATH", "<unset>"),
    )
    return env


def launch_accessible_app(
    command: Sequence[str] | str,
    tree_module: ModuleType,
    rawinput_module: ModuleType,
    *,
    expected_app_names: Sequence[str] | None,
    title_prefix: Optional[str],
    env: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> LinuxAccessibilityApp:
    command_list = _normalise_command(command)
    process = subprocess.Popen(command_list, env=linux_environment(env))
    logger.info("Launched Linux app via command: %s (pid=%s)", " ".join(command_list), process.pid)
    try:
        application, window = wait_for_application(
            tree_module,
            expected_app_names or (),
            title_prefix,
            timeout=timeout,
        )
    except TimeoutError as exc:
        logger.error("Dogtail could not attach: %s", exc)
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
        raise

    return LinuxAccessibilityApp(process, application, window, tree_module, rawinput_module)


def wait_for_application(
    tree_module: ModuleType,
    expected_names: Sequence[str],
    title_prefix: Optional[str],
    timeout: float = 30.0,
):
    deadline = time.monotonic() + timeout
    last_error: Optional[Exception] = None
    normalised_names = tuple(name.lower() for name in expected_names if name)
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        discovered: list[str] = []
        for application in tree_module.root.applications():
            app_name = (getattr(application, "name", "") or "").strip()
            if app_name:
                discovered.append(app_name)
            matches_expected = not normalised_names or any(
                candidate in app_name.lower() for candidate in normalised_names
            )
            try:
                window = resolve_window(application, tree_module, title_prefix)
            except Exception as exc:  # pragma: no cover - diagnostic path
                last_error = exc
                continue
            window_title = (getattr(window, "name", "") or "").strip()
            title_matches = not title_prefix or window_title.startswith(title_prefix)
            if matches_expected or title_matches:
                return application, window
        logger.debug(
            "AT-SPI poll #%s did not locate names=%s title_prefix=%s. Discovered applications: %s",
            attempt,
            list(normalised_names) or "<any>",
            title_prefix or "<unset>",
            discovered or "<none>",
        )
        time.sleep(0.5)
    snapshot = describe_accessible_desktop()
    expected_description = ", ".join(normalised_names) or "<any>"
    message = f"Unable to locate application names={expected_description}"
    if title_prefix:
        message += f" window_title startswith '{title_prefix}'"
    if snapshot:
        message = (
            f"{message}; {snapshot}. "
            "See docs/e2e-linux-accessibility.md#verify-the-tk-window-is-registered-on-the-at-spi-bus"
        )
    logger.error("%s", message)
    raise TimeoutError(message) from last_error


def describe_accessible_desktop() -> Optional[str]:
    try:
        import pyatspi
    except Exception:  # pragma: no cover - optional dependency
        return None
    try:
        desktop = pyatspi.Registry.getDesktop(0)
    except Exception as exc:  # pragma: no cover - depends on desktop stack
        return f"pyatspi registry unavailable ({exc})"
    names = []
    for index in range(desktop.childCount):
        child = desktop.getChildAtIndex(index)
        role = child.getRoleName()
        name = (getattr(child, "name", "") or "").strip()
        names.append(f"{role}:{name or '<unnamed>'}")
    if not names:
        return "AT-SPI desktop has no registered applications"
    return "AT-SPI desktop children -> " + ", ".join(names)


def resolve_window(application: object, tree_module: ModuleType, title_prefix: Optional[str]):
    if title_prefix:
        try:
            for child in application.children:  # type: ignore[attr-defined]
                name = getattr(child, "name", "") or ""
                if child.roleName == "frame" and name.startswith(title_prefix):
                    return child
        except AttributeError:  # pragma: no cover - tree implementations may vary
            pass
    try:
        return application.child(roleName="frame")
    except tree_module.SearchError:
        return application.child(roleName="window")


def parse_expected_names(raw_value: Optional[str], *fallbacks: str) -> list[str]:
    names: list[str] = []
    if raw_value:
        for candidate in raw_value.replace(";", ",").split(","):
            stripped = candidate.strip()
            if stripped:
                names.append(stripped)
    for fallback in fallbacks:
        if fallback and fallback not in names:
            names.append(fallback)
    return names


def _normalise_command(command: Sequence[str] | str) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return list(command)
