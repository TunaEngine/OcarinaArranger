from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .linux_accessibility import linux_environment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowGeometry:
    width: int
    height: int
    x: int
    y: int


@dataclass
class X11WindowSession:
    """Manage an Openbox-backed X11 session for window diagnostics."""

    command: Sequence[str]
    window_title: str
    env: dict[str, str]
    _wm_process: subprocess.Popen[str] | None = None
    _app_process: subprocess.Popen[str] | None = None
    _window_id: str | None = None

    @classmethod
    def launch(
        cls,
        command: Sequence[str],
        window_title: str,
        *,
        env: dict[str, str] | None = None,
        warmup_delay: float = 0.5,
    ) -> "X11WindowSession":
        session_env = linux_environment(env)
        logger.info(
            "Starting Openbox-managed X11 session for command=%s title=%s",
            " ".join(command),
            window_title,
        )
        wm_process = subprocess.Popen(["openbox"], env=session_env)
        time.sleep(max(warmup_delay, 0.1))
        app_process = subprocess.Popen(list(command), env=session_env)
        return cls(
            command=list(command),
            window_title=window_title,
            env=session_env,
            _wm_process=wm_process,
            _app_process=app_process,
        )

    @property
    def app_pid(self) -> int | None:
        process = self._app_process
        return process.pid if process else None

    def require_window(self, *, timeout: float = 10.0, title: str | None = None) -> str:
        search_title = title or self.window_title
        logger.info("Waiting for X11 window titled '%s'", search_title)
        try:
            result = subprocess.run(
                ["xdotool", "search", "--sync", "--limit", "1", "--name", search_title],
                env=self.env,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - diagnostic
            stderr = exc.stderr.strip() if exc.stderr else "<no stderr>"
            stdout = exc.stdout.strip() if exc.stdout else "<no stdout>"
            raise AssertionError(
                f"xdotool could not find window '{search_title}'. stdout={stdout} stderr={stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - diagnostic
            raise AssertionError(f"Timed out waiting for window '{search_title}' via xdotool") from exc
        output = (result.stdout or "").strip().splitlines()
        if not output:
            raise AssertionError(f"xdotool did not return a window id for '{search_title}'")
        self._window_id = output[-1].strip()
        logger.info("xdotool located window id %s for title '%s'", self._window_id, search_title)
        return self._window_id

    def activate_window(self) -> None:
        window_id = self._window_id
        if not window_id:
            raise AssertionError("Call require_window() before activating the window")
        logger.info("Activating window id %s", window_id)
        subprocess.run(["xdotool", "windowactivate", "--sync", window_id], env=self.env, check=True)

    def focus_window(self, title: str | None = None) -> None:
        window_id = self.require_window(title=title)
        logger.info("Focusing window id %s (title hint=%s)", window_id, title or self.window_title)
        self.activate_window()

    def send_keys(self, *keys: str) -> None:
        if not keys:
            return
        logger.info("Sending keys to window id %s: %s", self._window_id, keys)
        subprocess.run(["xdotool", "key", *keys], env=self.env, check=True)

    def wait_for_exit(self, timeout: float = 5.0) -> None:
        process = self._app_process
        if not process:
            return
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(
                f"Application process did not exit within {timeout}s after automation keystrokes"
            ) from exc
        logger.info("Application process exited with code %s", process.returncode)

    def assert_running(self) -> None:
        process = self._app_process
        if process is None:
            raise AssertionError("Application process was not started")
        if process.poll() is not None:
            raise AssertionError(
                f"Application process exited unexpectedly with code {process.returncode}"
            )

    def window_name(self) -> str:
        window_id = self._window_id or self.require_window()
        result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        name = (result.stdout or "").strip()
        logger.info("Window id %s currently titled '%s'", window_id, name)
        return name

    def window_geometry(self) -> WindowGeometry:
        window_id = self._window_id or self.require_window()
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        width = height = x = y = None
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("WIDTH="):
                width = int(line.split("=", 1)[1])
            elif line.startswith("HEIGHT="):
                height = int(line.split("=", 1)[1])
            elif line.startswith("X="):
                x = int(line.split("=", 1)[1])
            elif line.startswith("Y="):
                y = int(line.split("=", 1)[1])
        if None in {width, height, x, y}:
            raise AssertionError(
                f"Unable to parse window geometry from xdotool output: {result.stdout!r}"
            )
        return WindowGeometry(width=width, height=height, x=x, y=y)

    def click_relative(self, x_ratio: float, y_ratio: float, button: int = 1) -> None:
        geometry = self.window_geometry()
        if geometry.width <= 0 or geometry.height <= 0:
            raise AssertionError("Window geometry must be positive to perform clicks")
        x = max(0, min(int(geometry.width * x_ratio), geometry.width - 1))
        y = max(0, min(int(geometry.height * y_ratio), geometry.height - 1))
        window_id = self._window_id or self.require_window()
        logger.info(
            "Clicking window id %s at relative coordinates (%s, %s) -> (%s, %s)",
            window_id,
            x_ratio,
            y_ratio,
            x,
            y,
        )
        subprocess.run(
            ["xdotool", "mousemove", "--window", window_id, str(x), str(y)],
            env=self.env,
            check=True,
        )
        subprocess.run(
            ["xdotool", "click", "--window", window_id, str(button)],
            env=self.env,
            check=True,
        )
        time.sleep(0.3)

    def type_text(self, text: str, *, delay_ms: int = 0) -> None:
        window_id = self._window_id or self.require_window()
        logger.info("Typing text into window id %s: %s", window_id, text)
        command = ["xdotool", "type"]
        if delay_ms > 0:
            command.extend(["--delay", str(delay_ms)])
        command.extend(["--window", window_id, text])
        subprocess.run(command, env=self.env, check=True)
        time.sleep(0.2)

    def capture_window_screenshot(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        window_id = self._window_id or self.require_window()
        logger.info("Capturing X11 window screenshot to %s", destination)
        with subprocess.Popen(
            ["xwd", "-silent", "-id", window_id],
            env=self.env,
            stdout=subprocess.PIPE,
        ) as xwd_proc:
            try:
                subprocess.run(
                    ["convert", "xwd:-", str(destination)],
                    env=self.env,
                    check=True,
                    stdin=xwd_proc.stdout,
                )
            finally:
                if xwd_proc.stdout:
                    xwd_proc.stdout.close()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    xwd_proc.wait(timeout=5)
        return destination

    def capture_fullscreen_screenshot(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Capturing full-screen X11 screenshot to %s", destination)
        with subprocess.Popen(
            ["xwd", "-silent", "-root"],
            env=self.env,
            stdout=subprocess.PIPE,
        ) as xwd_proc:
            try:
                subprocess.run(
                    ["convert", "xwd:-", str(destination)],
                    env=self.env,
                    check=True,
                    stdin=xwd_proc.stdout,
                )
            finally:
                if xwd_proc.stdout:
                    xwd_proc.stdout.close()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    xwd_proc.wait(timeout=5)
        return destination

    def close(self) -> None:
        for proc in (self._app_process, self._wm_process):
            if not proc:
                continue
            if proc.poll() is None:
                proc.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=5)
                if proc.poll() is None:
                    proc.kill()
        self._app_process = None
        self._wm_process = None


def ensure_x11_cli_dependencies() -> None:
    required = ("openbox", "xdotool", "xwd", "convert")
    missing: list[str] = [binary for binary in required if shutil.which(binary) is None]
    if missing:
        raise RuntimeError(
            "Missing X11 tooling required for diagnostics: " + ", ".join(sorted(missing))
        )
