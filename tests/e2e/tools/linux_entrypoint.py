"""Launch the production app with seeded data for Linux accessibility screenshots."""

from __future__ import annotations

import logging

from ocarina_gui.app import App

from .linux_command_channel import poll_command_file
from .linux_environment import load_automation_paths
from .linux_preview import prime_preview
from .linux_shortcuts import install_shortcuts
from .linux_status import write_status

logger = logging.getLogger(__name__)


def _bootstrap_app() -> App:
    logging.basicConfig(level=logging.INFO)
    app = App()
    paths = load_automation_paths()

    write_status(paths.status, preview="pending")

    app.after(200, lambda: install_shortcuts(app))
    poll_command_file(app, paths.command, paths.status)

    if paths.sample is not None:
        app.after(600, lambda: prime_preview(app, paths.sample, paths.status))

    return app


def main() -> None:
    app = _bootstrap_app()
    try:
        app.start_automatic_update_check()
    except Exception:  # pragma: no cover - background diagnostic only
        logger.exception("Automatic update check failed to start")
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover - CLI hook
    main()

