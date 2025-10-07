"""UI test for preview controls dark theme styling."""

import tkinter as tk
from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

from shared.ttk import ttk
from shared.tk_style import get_ttk_style
from ocarina_gui.themes import set_active_theme, get_current_theme, apply_theme_to_toplevel
from ocarina_gui.ui_builders.preview_controls import build_preview_controls, build_arranged_preview_controls

if TYPE_CHECKING:
    pass


@pytest.fixture
def reset_theme():
    """Reset theme to default after test."""
    original_theme = get_current_theme().theme_id
    yield
    set_active_theme(original_theme)


class MockApp:
    """Mock App class for testing preview controls."""
    
    def __init__(self):
        self._preview_play_vars = {"test": tk.StringVar(value="Play"), "arranged": tk.StringVar(value="Play")}
        self._preview_tempo_vars = {"test": tk.IntVar(value=120), "arranged": tk.IntVar(value=120)}
        self._preview_metronome_vars = {"test": tk.BooleanVar(value=False), "arranged": tk.BooleanVar(value=False)}
        self._preview_loop_enabled_vars = {"test": tk.BooleanVar(value=False), "arranged": tk.BooleanVar(value=False)}
        self._preview_loop_start_vars = {"test": tk.DoubleVar(value=0.0), "arranged": tk.DoubleVar(value=0.0)}
        self._preview_loop_end_vars = {"test": tk.DoubleVar(value=4.0), "arranged": tk.DoubleVar(value=4.0)}
        self.transpose_offset = tk.IntVar(value=0)
    
    def _on_preview_play_toggle(self, side): pass
    def _zoom_all(self, delta): pass
    def _hzoom_all(self, factor): pass
    def _register_preview_adjust_widgets(self, side, *widgets): pass
    def _begin_loop_range_selection(self, side): pass
    def _register_preview_loop_range_button(self, side, button): pass
    def _register_preview_loop_widgets(self, side, *widgets): pass
    def _apply_preview_settings(self, side): pass
    def _cancel_preview_settings(self, side): pass
    def _register_preview_control_buttons(self, side, *buttons, **kwargs): pass
    def _apply_transpose_offset(self): pass
    def _cancel_transpose_offset(self): pass
    def _register_transpose_spinbox(self, spinbox, **kwargs): pass


@pytest.mark.gui
def test_preview_controls_apply_dark_theme_styles(reset_theme):
    """Test that preview controls properly apply dark theme styles."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")
    
    root.withdraw()
    
    try:
        # Switch to dark theme
        set_active_theme("dark")
        theme = get_current_theme()
        
        # Create window with proper theme setup
        window = tk.Toplevel(root)
        palette = apply_theme_to_toplevel(window)
        
        # Get the TTK style and apply dark theme
        style = get_ttk_style(window, theme=theme.ttk_theme)

        # Apply theme styles manually (this is what the main window does)
        window_bg = palette.window_background
        text_fg = palette.text_primary

        # Apply Panel styles using the utility function 
        from shared.tk_style import apply_theme_to_panel_widgets
        apply_theme_to_panel_widgets(window)

        # Create main frame
        main_frame = ttk.Frame(window, style="Panel.TFrame")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create mock app and build controls
        mock_app = MockApp()

        # Build preview controls
        build_preview_controls(mock_app, main_frame, "test")

        # Add separator
        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

        # Build arranged preview controls
        build_arranged_preview_controls(mock_app, main_frame, "arranged")

        # Update display
        window.update_idletasks()
        
        # Re-apply Panel styles after update_idletasks (ttkbootstrap may have reset them)
        apply_theme_to_panel_widgets(window)
        
        # Test that Panel.TFrame style has dark background
        panel_frame_bg = style.lookup("Panel.TFrame", "background")
        assert panel_frame_bg == window_bg, \
            f"Panel.TFrame background should be {window_bg}, got {panel_frame_bg}"
        
        # Test that Panel.TLabelframe has dark theme colors
        panel_label_bg = style.lookup("Panel.TLabelframe", "background")
        panel_label_fg = style.lookup("Panel.TLabelframe", "foreground")
        assert panel_label_bg == window_bg, \
            f"Panel.TLabelframe background should be {window_bg}, got {panel_label_bg}"
        assert panel_label_fg == text_fg, \
            f"Panel.TLabelframe foreground should be {text_fg}, got {panel_label_fg}"
        
        # Verify dark theme colors
        assert window_bg == "#1c1f23", f"Expected dark background, got {window_bg}"
        assert text_fg == "#f8f9fa", f"Expected light text, got {text_fg}"
        
    finally:
        with suppress(Exception):
            window.destroy()
        with suppress(Exception):
            root.destroy()


@pytest.mark.gui
def test_preview_controls_switch_themes_properly(reset_theme):
    """Test that preview controls properly switch between light and dark themes."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")
    
    root.withdraw()
    
    try:
        # Start with light theme
        set_active_theme("light")
        
        window = tk.Toplevel(root)
        palette = apply_theme_to_toplevel(window)
        style = get_ttk_style(window, theme=get_current_theme().ttk_theme)
        
        # Configure Panel styles for light theme
        window_bg = palette.window_background
        text_fg = palette.text_primary
        from shared.tk_style import apply_theme_to_panel_widgets
        apply_theme_to_panel_widgets(window)
        
        main_frame = ttk.Frame(window, style="Panel.TFrame")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        mock_app = MockApp()
        build_preview_controls(mock_app, main_frame, "test")
        
        window.update_idletasks()
        
        # Verify light theme colors
        light_bg = "#f8f9fa"
        light_fg = "#212529"
        assert window_bg == light_bg, f"Expected light background, got {window_bg}"
        assert text_fg == light_fg, f"Expected dark text, got {text_fg}"
        
        # Switch to dark theme
        set_active_theme("dark")
        theme = get_current_theme()
        palette = apply_theme_to_toplevel(window)
        
        # Re-configure styles for dark theme
        style = get_ttk_style(window, theme=theme.ttk_theme)
        window_bg = palette.window_background
        text_fg = palette.text_primary
        apply_theme_to_panel_widgets(window)
        
        window.update_idletasks()
        
        # Re-apply Panel styles after update_idletasks (ttkbootstrap may have reset them)
        apply_theme_to_panel_widgets(window)

        # Verify dark theme colors
        dark_bg = "#1c1f23"
        dark_fg = "#f8f9fa"
        assert window_bg == dark_bg, f"Expected dark background, got {window_bg}"
        assert text_fg == dark_fg, f"Expected light text, got {text_fg}"

        # Check that Panel styles are properly configured
        panel_frame_bg = style.lookup("Panel.TFrame", "background")
        assert panel_frame_bg == dark_bg, f"Panel.TFrame background should be {dark_bg}, got {panel_frame_bg}"
        
    finally:
        with suppress(Exception):
            window.destroy()
        with suppress(Exception):
            root.destroy()


if __name__ == "__main__":
    # Run the test manually for visual inspection
    import sys
    sys.exit(pytest.main([__file__, "-v"]))