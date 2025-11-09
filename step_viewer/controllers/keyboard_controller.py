"""
Keyboard event controller.
"""

from ..config import ViewerConfig
from ..managers import ColorManager, SelectionManager


class KeyboardController:
    """Handles all keyboard shortcuts."""

    def __init__(self, display, selection_manager: SelectionManager, color_manager: ColorManager,
                 root, config: ViewerConfig):
        self.display = display
        self.selection_manager = selection_manager
        self.color_manager = color_manager
        self.root = root
        self.config = config
        self.mode_label = None
        self.selection_label = None

    def set_ui_labels(self, mode_label, selection_label):
        """Set references to UI labels for updates."""
        self.mode_label = mode_label
        self.selection_label = selection_label

    def on_key_f(self, event):
        """Fit all objects in view."""
        self.display.FitAll()

    def on_key_q(self, event):
        """Quit application."""
        self.root.quit()

    def on_key_s(self, event):
        """Toggle selection mode."""
        is_selection = self.selection_manager.toggle_mode()

        if is_selection:
            print("\n*** FACE SELECTION MODE ***")
            print("  - Left click: Select/deselect faces")
            print("  - Right click: Pan")
            print("  - Mouse wheel: Zoom")
            print("  - 's': Exit selection mode")
            print("  - 'c': Clear all selections")
            print("  - '1': Cycle selection fill color")
            print("  - '2': Cycle outline color")

            fill_rgb, fill_name = self.color_manager.get_current_fill_color()
            outline_rgb, outline_name = self.color_manager.get_current_outline_color()
            print(f"\n  CURRENT COLORS:")
            print(f"    Fill: {fill_name} RGB{fill_rgb}")
            print(f"    Outline: {outline_name} RGB{outline_rgb}")
            print(f"    Outline width: {self.config.SELECTION_OUTLINE_WIDTH}px\n")

            self.root.configure(bg=self.config.SELECTION_MODE_BG)
            if self.mode_label:
                self.mode_label.config(text="Mode: Selection", fg='#00ff00')
        else:
            print("\n*** NAVIGATION MODE ***")
            print("  - Left click: Rotate")
            print("  - Right click: Pan")
            print("  - Mouse wheel: Zoom")
            print("  - 's': Enter selection mode")

            self.root.configure(bg=self.config.DARK_BG)
            if self.mode_label:
                self.mode_label.config(text="Mode: Navigation", fg='#00e0ff')

    def on_key_c(self, event):
        """Clear all selections."""
        self.selection_manager.clear_all(self.root)

    def on_key_1(self, event):
        """Cycle selection fill color."""
        self.color_manager.cycle_fill_color()
        self.selection_manager.update_all_colors(self.root)

    def on_key_2(self, event):
        """Cycle outline color."""
        self.color_manager.cycle_outline_color()
        self.selection_manager.update_all_colors(self.root)
