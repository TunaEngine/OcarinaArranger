"""Compatibility wrapper exposing :class:`ui.main_window.MainWindow` as ``App``."""

from __future__ import annotations

from ui.main_window import MainWindow


class App(MainWindow):
    """Legacy alias retaining the public ``ocarina_gui.app.App`` entry point."""


def _main() -> None:
    app = App()
    app.start_automatic_update_check()
    app.mainloop()


if __name__ == "__main__":
    _main()
