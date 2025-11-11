"""
Keyboard event controller.
"""

from ..config import ViewerConfig
from ..managers import ColorManager, SelectionManager
from .view_controller import ViewController
from ..managers.log_manager import logger


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
        self.view_controller = ViewController(display.View)

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
            logger.info("\n*** FACE SELECTION MODE ***")
            logger.info("  - Left click: Select/deselect faces")
            logger.info("  - Right click: Pan")
            logger.info("  - Mouse wheel: Zoom")
            logger.info("  - 's': Exit selection mode")
            logger.info("  - 'l': Select largest external face per part")
            logger.info("  - 'c': Clear all selections")
            logger.info("  - '1': Cycle selection fill color")
            logger.info("  - '2': Cycle outline color")

            fill_rgb, fill_name = self.color_manager.get_current_fill_color()
            outline_rgb, outline_name = self.color_manager.get_current_outline_color()
            logger.info(f"\n  CURRENT COLORS:")
            logger.info(f"    Fill: {fill_name} RGB{fill_rgb}")
            logger.info(f"    Outline: {outline_name} RGB{outline_rgb}")
            logger.info(f"    Outline width: {self.config.SELECTION_OUTLINE_WIDTH}px\n")

            self.root.configure(bg=self.config.SELECTION_MODE_BG)
            if self.mode_label:
                self.mode_label.config(text="Mode: Selection", fg='#00ff00')
        else:
            logger.info("\n*** NAVIGATION MODE ***")
            logger.info("  - Left click: Rotate")
            logger.info("  - Right click: Pan")
            logger.info("  - Mouse wheel: Zoom")
            logger.info("  - 's': Enter selection mode")

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

    # View preset shortcuts (Shift + number keys)
    def on_key_shift_1(self, event):
        """Set front view."""
        self.view_controller.set_front_view()
        logger.info("View: Front")

    def on_key_shift_2(self, event):
        """Set back view."""
        self.view_controller.set_back_view()
        logger.info("View: Back")

    def on_key_shift_3(self, event):
        """Set right view."""
        self.view_controller.set_right_view()
        logger.info("View: Right")

    def on_key_shift_4(self, event):
        """Set left view."""
        self.view_controller.set_left_view()
        logger.info("View: Left")

    def on_key_shift_5(self, event):
        """Set top view."""
        self.view_controller.set_top_view()
        logger.info("View: Top")

    def on_key_shift_6(self, event):
        """Set bottom view."""
        self.view_controller.set_bottom_view()
        logger.info("View: Bottom")

    def on_key_shift_7(self, event):
        """Set isometric view."""
        self.view_controller.set_isometric_view()
        logger.info("View: Isometric")
