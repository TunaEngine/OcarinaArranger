"""Helpers for working with :mod:`ttkbootstrap` styles."""

from __future__ import annotations

import logging
import tkinter as tk
from types import MethodType
from typing import Optional

try:
    from ttkbootstrap import Style as BootstrapStyle
except ModuleNotFoundError as exc:  # pragma: no cover - triggered when dependency missing
    BootstrapStyle = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from shared.ttk import ttk, is_bootstrap_enabled, use_native_ttk

logger = logging.getLogger(__name__)

_DEFAULT_THEME = "litera"
_STYLE: ttk.Style | None = None
_STYLE_THEME: str | None = None
_STYLE_ROOT: tk.Misc | None = None


def _reset_bootstrap_instance() -> None:
    """Clear ttkbootstrap's global ``Style.instance`` cache."""

    if BootstrapStyle is None:
        return

    try:
        if getattr(BootstrapStyle, "instance", None) is not None:
            logger.debug("Resetting ttkbootstrap Style.instance cache")
            BootstrapStyle.instance = None  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive safety net
        logger.debug("Failed to reset ttkbootstrap Style.instance", exc_info=True)


def _canonicalize(widget: Optional[tk.Misc]) -> Optional[tk.Misc]:
    if widget is None:
        return None
    try:
        return widget.winfo_toplevel()
    except tk.TclError:
        return widget


def _default_root_exists(widget: Optional[tk.Misc]) -> bool:
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _reset_cached_style(event: Optional[tk.Event] = None) -> None:
    global _STYLE, _STYLE_THEME, _STYLE_ROOT
    if event is not None and _STYLE_ROOT is not None:
        widget = getattr(event, "widget", None)
        if widget is not _STYLE_ROOT:
            return

    logger.debug("Resetting cached ttk style (event=%s)", event)
    _STYLE = None
    _STYLE_THEME = None
    _STYLE_ROOT = None
    _reset_bootstrap_instance()
    if BootstrapStyle is not None:
        try:
            from ttkbootstrap import publisher

            publisher.Publisher.clear_subscribers()
        except Exception:
            logger.debug("Failed to clear ttkbootstrap publisher subscribers", exc_info=True)


def _ensure_default_root(master: Optional[tk.Misc]) -> tk.Misc:
    global _STYLE_ROOT

    candidates = (
        _canonicalize(master),
        _canonicalize(getattr(tk, "_default_root", None)),
        _canonicalize(_STYLE_ROOT),
    )

    for candidate in candidates:
        if _default_root_exists(candidate):
            _STYLE_ROOT = candidate
            return candidate  # type: ignore[return-value]

    root = tk.Tk()
    try:
        root.withdraw()
    except tk.TclError:
        pass

    setattr(root, "_tk_style_managed", True)
    _STYLE_ROOT = root

    try:
        root.bind("<Destroy>", _reset_cached_style, add="+")
    except tk.TclError:
        pass

    return root


def _instantiate_bootstrap_style(
    root: tk.Misc, theme: str
) -> ttk.Style:
    """Create a ttkbootstrap ``Style`` bound to ``root``.

    ttkbootstrap has evolved its ``Style`` signature over time. Prefer the
    modern ``master=`` keyword but gracefully fall back to the positional
    invocation used by older releases.
    """

    last_type_error: TypeError | None = None

    for constructor in (
        lambda: BootstrapStyle(master=root, theme=theme),
        lambda: BootstrapStyle(master=root),
        lambda: BootstrapStyle(theme=theme),
        lambda: BootstrapStyle(theme),
        lambda: BootstrapStyle(),
    ):
        try:
            style = constructor()
        except TypeError as exc:
            last_type_error = exc
            continue
        else:
            return style

    if last_type_error is not None:
        raise last_type_error

    # Should be unreachable, but keep mypy satisfied.
    raise TypeError("Unable to construct ttkbootstrap Style")


def _create_style(theme: str, master: Optional[tk.Misc]) -> ttk.Style:
    if BootstrapStyle is None:
        raise _IMPORT_ERROR  # type: ignore[misc]

    attempts = 0
    last_error: tk.TclError | None = None

    while attempts < 2:
        attempts += 1
        root = _ensure_default_root(master)
        managed_root = bool(getattr(root, "_tk_style_managed", False))
        _ = root  # pragma: no cover - keep reference alive to prevent Tk GC
        try:
            try:
                root.tk.call("package", "require", "Ttk")
            except tk.TclError as exc:
                logger.warning(
                    "Tk interpreter does not provide ttk widgets (%s); falling back to native ttk",
                    exc,
                )
                use_native_ttk()
                return ttk.Style(master=root)
            style = _instantiate_bootstrap_style(root, theme)
        except tk.TclError as exc:
            last_error = exc
            logger.debug(
                "ttkbootstrap Style creation failed on attempt %s: %s", attempts, exc, exc_info=True
            )
            if "ttk::style" in str(exc) and is_bootstrap_enabled():
                logger.warning(
                    "Bootstrap style commands unavailable; falling back to native ttk"
                )
                use_native_ttk()
                return ttk.Style(master=root)
            try:
                if managed_root:
                    root.destroy()
            except tk.TclError:
                pass
            _reset_cached_style()
            master = None
            continue
        except TypeError as exc:
            raise exc
        else:
            break
    else:
        assert last_error is not None
        raise last_error

    try:
        if theme:
            style.theme_use(theme)
            # Log success/failure for debugging
            current_theme = style.theme_use()
            if current_theme == theme:
                logger.debug("Successfully activated ttk theme '%s'", theme)
            else:
                logger.warning(
                    "Theme activation mismatch: requested '%s', got '%s'", theme, current_theme
                )
    except tk.TclError as e:
        logger.warning("Failed to activate ttk theme '%s' on initialisation: %s", theme, e)
    try:
        root.bind("<Destroy>", _reset_cached_style, add="+")
    except tk.TclError:
        pass
    return style


def get_ttk_style(master: Optional[tk.Misc] = None, *, theme: Optional[str] = None) -> ttk.Style:
    """Return a shared ttkbootstrap :class:`Style` instance.

    The helper recreates the global style when the requested theme changes or if
    the underlying Tk interpreter has been destroyed.
    """

    if BootstrapStyle is None:
        raise _IMPORT_ERROR  # type: ignore[misc]

    global _STYLE, _STYLE_THEME

    bootstrap_instance = getattr(BootstrapStyle, "instance", None)
    if bootstrap_instance is not None:
        master = getattr(bootstrap_instance, "master", None)
        if not _default_root_exists(master):
            logger.debug("Bootstrap Style.instance root is gone; resetting cache")
            _reset_cached_style()

    # If no theme is explicitly requested, try to preserve current theme
    # Only use default theme for initial creation
    desired_theme = theme
    if desired_theme is None and _STYLE is not None:
        try:
            # Preserve the current theme instead of defaulting to _DEFAULT_THEME
            desired_theme = str(_STYLE.theme_use())
        except tk.TclError:
            desired_theme = _DEFAULT_THEME
    elif desired_theme is None:
        desired_theme = _DEFAULT_THEME
    
    requested_root = _canonicalize(master)

    if _STYLE is None:
        logger.debug("Creating ttkbootstrap Style (theme=%s)", desired_theme)
        _STYLE = _create_style(desired_theme, master)
    else:
        if (
            requested_root is not None
            and _STYLE_ROOT is not None
            and _default_root_exists(_STYLE_ROOT)
            and requested_root is not _STYLE_ROOT
        ):
            logger.debug(
                "Requested root %s differs from cached ttk style root %s; recreating",
                requested_root,
                _STYLE_ROOT,
            )
            _STYLE = _create_style(desired_theme, requested_root)
        try:
            current_theme = str(_STYLE.theme_use())
        except tk.TclError:
            logger.debug(
                "Cached ttkbootstrap Style is unusable; recreating", exc_info=True
            )
            _STYLE = _create_style(desired_theme, master)
        else:
            if desired_theme and current_theme != desired_theme:
                try:
                    _STYLE.theme_use(desired_theme)
                    # Verify theme switch was successful
                    actual_theme = _STYLE.theme_use()
                    if actual_theme != desired_theme:
                        logger.warning(
                            "Theme switch verification failed: requested '%s', current is '%s'; recreating style",
                            desired_theme, actual_theme
                        )
                        _STYLE = _create_style(desired_theme, master)
                except tk.TclError as e:
                    logger.warning(
                        "Switching ttk theme to '%s' failed: %s; recreating style", desired_theme, e
                    )
                    _STYLE = _create_style(desired_theme, master)

    try:
        _STYLE_THEME = str(_STYLE.theme_use())
    except tk.TclError:
        _STYLE_THEME = desired_theme

    return _STYLE


def apply_round_scrollbar_style(scrollbar: ttk.Scrollbar) -> None:
    """Give ``scrollbar`` the ttkbootstrap rounded appearance."""

    if scrollbar is None:
        return

    # Check if ttkbootstrap style is available without potentially changing theme
    try:
        # Try to get existing style from the scrollbar's root first to preserve theme
        root = scrollbar.winfo_toplevel()
        if hasattr(root, '_style') and root._style is not None:
            # Style exists, we can use ttkbootstrap features
            pass
        else:
            # Fall back to getting style
            get_ttk_style(scrollbar)
    except (tk.TclError, AttributeError):
        return

    def _install_bootstyle_accessor(value: object) -> None:
        try:
            setattr(scrollbar, "_bootstrap_bootstyle", value)
            original = getattr(scrollbar, "_bootstrap_original_cget", None)
            if original is None:
                original = scrollbar.cget
                setattr(scrollbar, "_bootstrap_original_cget", original)

                def _cget(self: ttk.Scrollbar, key: str, _orig=original):
                    if key == "bootstyle":
                        return getattr(self, "_bootstrap_bootstyle", "")
                    result = _orig(key)
                    if key != "bootstyle" and not isinstance(result, str):
                        try:
                            return str(result)
                        except Exception:
                            return result
                    return result

                scrollbar.cget = MethodType(_cget, scrollbar)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to install bootstyle accessor", exc_info=True)

    for token in ("info-round", ("info", "round"), "round"):
        try:
            scrollbar.configure(bootstyle=token)
        except (tk.TclError, TypeError):
            ttkstyle = None
            if BootstrapStyle is not None:
                try:
                    from ttkbootstrap.style import Bootstyle

                    ttkstyle = Bootstyle.update_ttk_widget_style(scrollbar, token)
                except Exception:
                    logger.debug(
                        "Failed to update scrollbar bootstyle using ttkbootstrap", exc_info=True
                    )
            if not ttkstyle:
                continue
            try:
                scrollbar.configure(style=ttkstyle)
            except tk.TclError:
                continue
            _install_bootstyle_accessor(token)
            return
        else:
            _install_bootstyle_accessor(token)
            return


def configure_style(style: ttk.Style, style_name: str, /, **options: object) -> bool:
    """Configure ``style_name`` via ttkbootstrap."""

    try:
        style.configure(style_name, **options)
    except tk.TclError:
        logger.debug(
            "Failed to configure style '%s' with %s", style_name, options, exc_info=True
        )
        return False
    return True


def map_style(style: ttk.Style, style_name: str, /, **option_map: object) -> bool:
    """Map state-specific options for ``style_name`` via ttkbootstrap."""

    try:
        style.map(style_name, **option_map)
    except tk.TclError:
        logger.debug(
            "Failed to map style '%s' with %s", style_name, option_map, exc_info=True
        )
        return False
    return True


def configure_panel_styles(style: ttk.Style, window_bg: str, text_fg: str) -> None:
    """Configure Panel.TFrame and Panel.TLabelframe styles for themed containers.
    
    This ensures that Panel-styled widgets use the correct theme colors when
    created in standalone windows or dialogs outside the main window.
    """
    configure_style(style, "Panel.TFrame", background=window_bg)
    configure_style(style, "Panel.TLabelframe", background=window_bg, foreground=text_fg)
    configure_style(style, "Panel.TLabelframe.Label", background=window_bg, foreground=text_fg)


def apply_theme_to_panel_widgets(window: tk.Misc) -> None:
    """Apply current theme's Panel styles to a standalone window.
    
    This function should be called after creating Panel-styled widgets in standalone
    windows or after calling update_idletasks(), as ttkbootstrap may reset custom
    Panel styles during widget hierarchy updates.
    
    This is primarily needed for standalone dialogs and windows that contain
    Panel.TFrame or Panel.TLabelframe widgets outside the main application window.
    """
    from ocarina_gui.themes import get_current_theme
    
    try:
        theme = get_current_theme()
        palette = theme.palette
        style = get_ttk_style(window, theme=theme.ttk_theme)
        configure_panel_styles(style, palette.window_background, palette.text_primary)
    except Exception:
        logger.debug("Failed to apply Panel styles to window", exc_info=True)


__all__ = [
    "apply_round_scrollbar_style",
    "apply_theme_to_panel_widgets",
    "configure_panel_styles",
    "configure_style",
    "get_ttk_style",
    "map_style",
]
