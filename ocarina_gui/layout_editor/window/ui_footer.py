"""Footer and preview helpers for the layout editor window."""

from __future__ import annotations

import logging

import tkinter as tk
from shared.ttk import ttk

from shared.tk_style import apply_round_scrollbar_style


LOGGER = logging.getLogger(__name__)


class _LayoutEditorFooterMixin:
    """Constructs and manages the footer, export menu, and preview widgets."""

    _preview_frame: ttk.Frame | None
    _preview_toggle: ttk.Button | None
    _json_text: tk.Text | None
    _preview_visible: bool
    _footer_menus: tuple[tk.Menu, ...] | None
    _footer_button_row: ttk.Frame | None
    _footer_export_row: ttk.Frame | None
    _footer_actions_row: ttk.Frame | None
    _footer_action_buttons: tuple[ttk.Button, ...] | None
    _footer_status_label: ttk.Label | None
    _footer_layout_stacked: bool
    _footer_layout_stack_forced: bool
    _footer_actions_vertical: bool
    _footer_layout_after_id: str | None
    _footer_layout_idle_id: str | None
    _footer_layout_defer_attempts: int
    _cancel_button: ttk.Button | None
    _done_button: ttk.Button | None

    def _build_export_panel(self) -> None:
        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        footer.columnconfigure(0, weight=1)
        footer.rowconfigure(1, weight=1)

        button_row = ttk.Frame(footer)
        button_row.grid(row=0, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=0)

        export_row = ttk.Frame(button_row)
        export_row.grid(row=0, column=0, sticky="w")

        config_button = ttk.Menubutton(export_row, text="Config", direction="below")
        config_button.pack(side="left", padx=4)

        config_menu = tk.Menu(config_button, tearoff=False)
        config_menu.add_command(label="Export Config...", command=self._save_json)
        config_menu.add_command(label="Import Config...", command=self._load_json)
        config_button["menu"] = config_menu

        instrument_button = ttk.Menubutton(export_row, text="Instrument", direction="below")
        instrument_button.pack(side="left", padx=4)

        instrument_menu = tk.Menu(instrument_button, tearoff=False)
        instrument_menu.add_command(label="Export Instrument...", command=self._export_instrument)
        instrument_menu.add_command(label="Import Instrument...", command=self._import_instrument)
        instrument_button["menu"] = instrument_menu

        self._footer_menus = (config_menu, instrument_menu)

        actions = ttk.Frame(button_row)
        actions.grid(row=0, column=1, sticky="e")

        toggle = ttk.Button(actions, text="Show Preview", command=self._toggle_preview)
        self._preview_toggle = toggle

        cancel_button = ttk.Button(actions, text="Cancel", command=self._cancel_edits)
        self._cancel_button = cancel_button

        done_button = ttk.Button(actions, text="Done", command=self._apply_and_close)
        self._done_button = done_button

        self._footer_button_row = button_row
        self._footer_export_row = export_row
        self._footer_actions_row = actions

        self._footer_action_buttons = (toggle, cancel_button, done_button)
        self._footer_actions_vertical = False
        self._set_footer_actions_orientation(vertical=False)

        status_label = ttk.Label(button_row, textvariable=self._status_var, style="Hint.TLabel")
        status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self._footer_status_label = status_label
        self._footer_layout_stacked = False
        self._footer_layout_stack_forced = False
        self._footer_layout_after_id = None
        self._footer_layout_idle_id = None
        self._footer_layout_defer_attempts = 0

        button_row.bind("<Configure>", lambda _e: self._refresh_footer_layout(), add="+")

        preview_frame = ttk.Frame(footer)
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self._json_text = tk.Text(preview_frame, height=10, wrap="word")
        self._json_text.grid(row=0, column=0, sticky="nsew")
        self._json_text.configure(state="disabled", font=("TkFixedFont", 9))

        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self._json_text.yview)
        apply_round_scrollbar_style(scrollbar)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._json_text.configure(yscrollcommand=scrollbar.set)

        self._preview_frame = preview_frame
        self._preview_visible = False
        self._hide_preview()

    def _toggle_preview(self) -> None:
        if self._preview_visible:
            self._hide_preview()
        else:
            self._show_preview()

    def _show_preview(self) -> None:
        frame = self._preview_frame
        if frame is None:
            return
        frame.grid()
        self._preview_visible = True
        toggle = self._preview_toggle
        if toggle is not None:
            toggle.configure(text="Hide Preview")
        self._refresh_footer_layout()

    def _hide_preview(self) -> None:
        frame = self._preview_frame
        if frame is None:
            return
        frame.grid_remove()
        self._preview_visible = False
        toggle = self._preview_toggle
        if toggle is not None:
            toggle.configure(text="Show Preview")
        self._refresh_footer_layout()

    def _set_footer_actions_orientation(self, *, vertical: bool) -> None:
        actions_row = getattr(self, "_footer_actions_row", None)
        buttons = getattr(self, "_footer_action_buttons", None)
        if not actions_row or not buttons:
            return

        if vertical:
            for index, button in enumerate(buttons):
                pady = (0, 4) if index < len(buttons) - 1 else (0, 0)
                button.grid(row=index, column=0, sticky="ew", padx=(0, 0), pady=pady)
            actions_row.grid_columnconfigure(0, weight=1)
            for column in range(1, len(buttons)):
                actions_row.grid_columnconfigure(column, weight=0)
        else:
            for column, button in enumerate(buttons):
                padx = (0, 4) if column < len(buttons) - 1 else (0, 0)
                button.grid(row=0, column=column, sticky="e", padx=padx, pady=0)
            for column in range(len(buttons)):
                actions_row.grid_columnconfigure(column, weight=0)

        self._footer_actions_vertical = vertical

    def _schedule_footer_layout_refresh(self, *, delay: int | None = 16, idle: bool = False) -> None:
        """Queue a footer layout refresh while avoiding duplicate callbacks."""

        try:
            exists = bool(self.winfo_exists())
        except tk.TclError:
            return
        if not exists:
            return

        if idle:
            if getattr(self, "_footer_layout_idle_id", None):
                return
            self._footer_layout_idle_id = self.after_idle(self._refresh_footer_layout)
            return

        existing_after = getattr(self, "_footer_layout_after_id", None)
        if existing_after:
            try:
                self.after_cancel(existing_after)
            except tk.TclError:
                pass
        delay_ms = 0 if delay is None else max(0, int(delay))
        self._footer_layout_after_id = self.after(delay_ms, self._refresh_footer_layout)

    def _cancel_footer_layout_callbacks(self) -> None:
        """Cancel any scheduled footer layout callbacks."""

        for attr in ("_footer_layout_after_id", "_footer_layout_idle_id"):
            handle = getattr(self, attr, None)
            if handle:
                try:
                    self.after_cancel(handle)
                except tk.TclError:
                    pass
                finally:
                    setattr(self, attr, None)

    def _refresh_footer_layout(self) -> None:
        self._footer_layout_after_id = None
        self._footer_layout_idle_id = None
        button_row = getattr(self, "_footer_button_row", None)
        export_row = getattr(self, "_footer_export_row", None)
        actions_row = getattr(self, "_footer_actions_row", None)
        status_label = getattr(self, "_footer_status_label", None)
        action_buttons = getattr(self, "_footer_action_buttons", None)

        if (
            not button_row
            or not export_row
            or not actions_row
            or not status_label
            or not action_buttons
        ):
            return

        raw_width = button_row.winfo_width()
        parent_mapped = bool(self.winfo_ismapped())
        button_row_mapped = bool(button_row.winfo_ismapped())
        parent_viewable = False
        try:
            parent_viewable = bool(self.winfo_viewable())
        except tk.TclError:
            parent_viewable = False

        master = getattr(self, "master", None)
        master_mapped = bool(master.winfo_ismapped()) if hasattr(master, "winfo_ismapped") else None
        master_state = None
        if hasattr(master, "state"):
            try:
                master_state = master.state()
            except tk.TclError:
                master_state = "<error>"

        requested_width = button_row.winfo_reqwidth()
        if not parent_mapped:
            try:
                state = self.state()
            except tk.TclError:
                state = "<destroyed>"
            defer_attempts = getattr(self, "_footer_layout_defer_attempts", 0)
            LOGGER.debug(
                "Footer parent not mapped (state=%s viewable=%s master_mapped=%s master_state=%s raw_width=%s req_width=%s attempts=%s)",
                state,
                parent_viewable,
                master_mapped,
                master_state,
                raw_width,
                requested_width,
                defer_attempts,
            )
            defer_attempts += 1
            self._footer_layout_defer_attempts = defer_attempts
            reschedule_delay = min(128, 16 * defer_attempts)
            self._schedule_footer_layout_refresh(delay=reschedule_delay)
        else:
            self._footer_layout_defer_attempts = 0

        if parent_mapped and not button_row_mapped:
            LOGGER.debug(
                "Footer button row not mapped yet; deferring layout (raw_width=%s req_width=%s)",
                raw_width,
                requested_width,
            )
            self._schedule_footer_layout_refresh()
            return

        available_width = raw_width
        if available_width <= 1:
            available_width = requested_width

        export_width = export_row.winfo_reqwidth()
        actions_width = actions_row.winfo_reqwidth()

        total_required = export_width + actions_width + 16
        measured_stack = bool(available_width) and total_required > available_width
        forced_stack = getattr(self, "_footer_layout_stack_forced", False)
        should_stack = measured_stack or forced_stack
        is_stacked = getattr(self, "_footer_layout_stacked", False)

        if should_stack and not is_stacked:
            self._force_footer_stack_layout(
                button_row,
                export_row,
                actions_row,
                status_label,
                force=forced_stack,
            )
        elif not should_stack and is_stacked:
            self._apply_horizontal_footer_layout(button_row, export_row, actions_row, status_label)
        elif not should_stack:
            button_row.grid_columnconfigure(0, weight=1)
            button_row.grid_columnconfigure(1, weight=0)

        available_actions_width_horizontal = (
            available_width - export_width - 8 if available_width else 0
        )
        available_actions_width_stacked = available_width - 8 if available_width else 0
        available_actions_width = (
            available_actions_width_stacked if should_stack else available_actions_width_horizontal
        )
        if available_actions_width < 0:
            available_actions_width = 0

        horizontal_required = sum(button.winfo_reqwidth() for button in action_buttons)
        if action_buttons:
            horizontal_required += 4 * (len(action_buttons) - 1)

        needs_vertical = horizontal_required > available_actions_width if action_buttons else False
        if not needs_vertical and available_actions_width == 0 and action_buttons:
            needs_vertical = True
        vertical_orientation = should_stack or needs_vertical
        self._set_footer_actions_orientation(vertical=vertical_orientation)

        mapped_state = [bool(button.winfo_ismapped()) for button in action_buttons]

        LOGGER.debug(
            "Layout editor footer metrics: width=%s (raw=%s) export=%s actions=%s total=%s measured_stack=%s forced_stack=%s stacked=%s vertical=%s mapped=%s parent_mapped=%s button_row_mapped=%s available_actions=%s required_horizontal=%s needs_vertical=%s",
            available_width,
            raw_width,
            export_width,
            actions_width,
            total_required,
            measured_stack,
            forced_stack,
            getattr(self, "_footer_layout_stacked", False),
            vertical_orientation,
            mapped_state,
            parent_mapped,
            button_row_mapped,
            available_actions_width,
            horizontal_required,
            needs_vertical,
        )

        if not all(mapped_state):
            if parent_mapped and not button_row_mapped:
                LOGGER.debug(
                    "Footer button row still unmapped; deferring forced stack until mapped"
                )
                if parent_mapped:
                    self._schedule_footer_layout_refresh()
                return

            LOGGER.debug(
                "Footer buttons unmapped after layout adjustment; forcing stacked layout"
            )
            self._force_footer_stack_layout(
                button_row,
                export_row,
                actions_row,
                status_label,
                force=True,
            )
            button_row.update_idletasks()
            mapped_state = [bool(button.winfo_ismapped()) for button in action_buttons]
            LOGGER.debug("Footer buttons remapped after forcing stack: %s", mapped_state)
            if not all(mapped_state):
                LOGGER.debug(
                    "Footer buttons still unmapped after idle flush; scheduling refresh"
                )
                if parent_mapped:
                    self._schedule_footer_layout_refresh(idle=True)
                else:
                    self._schedule_footer_layout_refresh()
                return

        if forced_stack and not measured_stack:
            actions_headroom = available_actions_width_horizontal - horizontal_required
            total_headroom = available_width - total_required if available_width else 0
            LOGGER.debug(
                "Footer forced stack headroom horizontal=%s total=%s", actions_headroom, total_headroom
            )
            if actions_headroom >= 12 and total_headroom >= 24:
                LOGGER.debug("Releasing forced footer stack after headroom increase")
                self._footer_layout_stack_forced = False
                if parent_mapped:
                    self._schedule_footer_layout_refresh(idle=True)

    def _apply_horizontal_footer_layout(
        self,
        button_row: ttk.Frame,
        export_row: ttk.Frame,
        actions_row: ttk.Frame,
        status_label: ttk.Label,
    ) -> None:
        LOGGER.debug("Restoring horizontal footer layout")
        export_row.grid_configure(row=0, column=0, columnspan=1, sticky="w")
        actions_row.grid_configure(row=0, column=1, columnspan=1, sticky="e", pady=0)
        status_label.grid_configure(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=0)
        self._footer_layout_stacked = False
        if not getattr(self, "_footer_layout_stack_forced", False):
            self._footer_layout_stack_forced = False

    def _force_footer_stack_layout(
        self,
        button_row: ttk.Frame,
        export_row: ttk.Frame,
        actions_row: ttk.Frame,
        status_label: ttk.Label,
        *,
        force: bool = False,
    ) -> None:
        """Ensure the footer rows stack vertically and remain mapped."""

        LOGGER.debug("Stacking footer layout (force=%s)", force)
        export_row.grid_configure(row=0, column=0, columnspan=1, sticky="w")
        actions_row.grid_configure(row=1, column=0, columnspan=1, sticky="ew", pady=(6, 0))
        status_label.grid_configure(row=2, column=0, columnspan=1, sticky="w", pady=(6, 0))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=0)
        self._footer_layout_stacked = True
        if force:
            self._footer_layout_stack_forced = True
        elif not getattr(self, "_footer_layout_stack_forced", False):
            self._footer_layout_stack_forced = False
        self._set_footer_actions_orientation(vertical=True)
