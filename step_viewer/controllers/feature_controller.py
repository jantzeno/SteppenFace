"""
Feature controller for managing viewer features like duplicate visibility and planar alignment.
"""

import tkinter as tk
from typing import List, Tuple, Dict
from ..managers.log_manager import logger
from ..managers.canvas_view_helper import Canvas_View_Helper


class FeatureController:
    """Manages feature toggles like duplicate visibility, planar alignment, and face selection."""

    def __init__(
        self,
        root: tk.Tk,
        display,
        ui,
        parts_list: List[Tuple],
        deduplication_manager,
        explode_manager,
        planar_alignment_manager,
        plate_manager,
        selection_manager,
        tree_controller,
    ):
        self.root = root
        self.display = display
        self.ui = ui
        self.parts_list = parts_list
        self.deduplication_manager = deduplication_manager
        self.explode_manager = explode_manager
        self.planar_alignment_manager = planar_alignment_manager
        self.plate_manager = plate_manager
        self.selection_manager = selection_manager
        self.tree_controller = tree_controller
        self.hidden_selections: Dict = {}
        self.view_helper = Canvas_View_Helper(display.View)

    def toggle_duplicate_visibility(self):
        """Toggle visibility of duplicate parts."""
        show_duplicates = self.deduplication_manager.toggle_duplicates()

        if show_duplicates:
            # Clear hidden indices when showing all parts
            self.deduplication_manager.hidden_indices.clear()

            # Show all parts
            for solid, color, ais_shape in self.parts_list:
                self.display.Context.Display(ais_shape, False)
            logger.info("Showing all parts (including duplicates)")

            # Restore hidden selections
            if self.hidden_selections:
                self.selection_manager.restore_hidden_selections(
                    self.hidden_selections, self.root
                )
                self.hidden_selections = {}

            # Update parts tree to remove hidden indicators
            self.ui.update_parts_tree(self.parts_list, self.deduplication_manager)

            # Restore highlight indicators in the refreshed tree
            self.tree_controller.restore_tree_highlight_indicators()
        else:
            # Hide duplicate parts
            unique_parts, duplicate_groups = (
                self.deduplication_manager.get_unique_parts(self.parts_list)
            )

            # Collect AIS shapes that will be hidden
            hidden_indices = self.deduplication_manager.hidden_indices
            ais_shapes_to_hide = [self.parts_list[i].ais_colored_shape for i in hidden_indices]

            # Hide selections for parts that are about to be hidden
            self.hidden_selections = self.selection_manager.hide_selections_for_parts(
                ais_shapes_to_hide, self.root
            )

            # Hide all parts first
            for part in self.parts_list:
                self.display.Context.Erase(part.ais_colored_shape, False)

            # Show only unique parts
            for part in unique_parts:
                self.display.Context.Display(part.ais_colored_shape, False)

            logger.info("Showing only unique parts (duplicates hidden)")

            # Update parts tree to show hidden status
            self.ui.update_parts_tree(self.parts_list, self.deduplication_manager)

            # Restore highlight indicators in the refreshed tree
            self.tree_controller.restore_tree_highlight_indicators()

        # Re-apply explosion if active
        if self.explode_manager.get_explosion_factor() > 0:
            # Get visible parts for explosion
            if show_duplicates:
                visible_parts = self.parts_list
            else:
                visible_parts, _ = self.deduplication_manager.get_unique_parts(
                    self.parts_list
                )

            self.explode_manager.initialize_parts(visible_parts)
            self.explode_manager.set_explosion_factor(
                self.explode_manager.get_explosion_factor(), self.display, self.root
            )

        # Update display
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        self.root.update_idletasks()

    def toggle_planar_alignment(self):
        """Toggle planar alignment to lay parts flat."""
        # Reset explosion first if we're enabling planar alignment
        if not self.planar_alignment_manager.is_aligned:
            if self.explode_manager.get_explosion_factor() > 0:
                # Fully reset explosion and ensure display is updated
                self.explode_manager.set_explosion_factor(0.0, self.display, self.root)
                self.ui.explode_slider.set(0.0)
                self.ui.explode_label.config(text="Explode: 0.00")
                # Force display update before applying planar alignment
                self.display.Context.UpdateCurrentViewer()
                self.display.Repaint()
                self.root.update_idletasks()
            # Disable explode slider when planar alignment is active
            self.ui.explode_slider.config(state="disabled")
        else:
            # Re-enable explode slider when disabling planar alignment
            self.ui.explode_slider.config(state="normal")

        is_aligned = self.planar_alignment_manager.toggle_planar_alignment(
            self.display, self.root
        )

        if is_aligned:
            # Associate parts with plates based on their positions
            self.plate_manager.associate_parts_by_position(
                self.parts_list, self.display
            )

            # Update plate list UI
            self.ui.update_plate_list(self.plate_manager)
            self.view_helper.set_top_view()

            logger.info("Planar alignment enabled - parts laid flat")
            logger.info(
                f"Parts automatically associated with {self.plate_manager.get_plate_count()} plate(s)"
            )
        else:
            self.view_helper.set_isometric_view()
            logger.info("Planar alignment disabled - parts restored")

    def select_largest_faces(self):
        """Select the largest external face of each part."""
        # Get the visible parts list (respecting duplicate hiding)
        if not self.deduplication_manager.show_duplicates:
            visible_parts, _ = self.deduplication_manager.get_unique_parts(
                self.parts_list
            )
        else:
            visible_parts = self.parts_list

        self.selection_manager.select_largest_external_faces(visible_parts, self.root)
