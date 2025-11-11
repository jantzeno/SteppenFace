"""
Tree controller for managing part selection and highlighting in the UI tree.
"""

from typing import List, Tuple, Dict, Any
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from ..managers.log_manager import logger


class TreeController:
    """Manages tree-based part selection and highlighting."""

    def __init__(
        self, ui, canvas, display, parts_list: List[Tuple], deduplication_manager=None
    ):
        self.ui = ui
        self.canvas = canvas
        self.display = display
        self.parts_list = parts_list
        self.deduplication_manager = deduplication_manager
        self.highlighted_parts: Dict[int, Tuple[Any, Quantity_Color]] = {}

    def setup_tree_selection(self):
        """Setup tree selection to highlight parts with multi-select and toggle."""

        def on_tree_click(event):
            # Get the item that was clicked
            item = self.ui.parts_tree.identify_row(event.y)
            if not item:
                return

            # Get the tag to extract part index
            tags = self.ui.parts_tree.item(item, "tags")
            if not tags or not tags[0].startswith("part_"):
                return

            part_idx = int(tags[0].split("_")[1])

            # Toggle highlight for this part
            if part_idx in self.highlighted_parts:
                self.unhighlight_part(part_idx)
                # Deselect in tree
                self.ui.parts_tree.selection_remove(item)
            else:
                self.highlight_part(part_idx)
                # Select in tree
                self.ui.parts_tree.selection_add(item)

            # Return focus to canvas so keyboard shortcuts work
            self.canvas.focus_set()

            return "break"  # Prevent default selection behavior

        # Bind to ButtonRelease to handle clicks
        self.ui.parts_tree.bind("<ButtonRelease-1>", on_tree_click)

    def highlight_part(self, part_idx: int):
        """
        Highlight a part in the 3D view.

        Args:
            part_idx: Index of the part to highlight
        """
        if part_idx < 0 or part_idx >= len(self.parts_list):
            return

        # Already highlighted
        if part_idx in self.highlighted_parts:
            return

        _, color, ais_shape = self.parts_list[part_idx]

        # Store original color
        original_color = Quantity_Color(color[0], color[1], color[2], Quantity_TOC_RGB)

        # Create bright highlight color (yellow)
        highlight_color = Quantity_Color(1.0, 1.0, 0.0, Quantity_TOC_RGB)

        # Apply highlight
        self.display.Context.SetColor(ais_shape, highlight_color, False)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

        # Store for later restoration
        self.highlighted_parts[part_idx] = (ais_shape, original_color)

        # Update tree item to show highlighted state
        self.update_tree_highlight_indicator(part_idx, True)

        logger.info(
            f"Highlighted Part {part_idx + 1} ({len(self.highlighted_parts)} selected)"
        )

    def unhighlight_part(self, part_idx: int):
        """
        Remove highlight from a specific part.

        Args:
            part_idx: Index of the part to unhighlight
        """
        if part_idx not in self.highlighted_parts:
            return

        ais_shape, original_color = self.highlighted_parts[part_idx]

        # Restore original color
        self.display.Context.SetColor(ais_shape, original_color, False)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

        # Remove from tracked highlights
        del self.highlighted_parts[part_idx]

        # Update tree item to remove highlighted state
        self.update_tree_highlight_indicator(part_idx, False)

        logger.info(
            f"Unhighlighted Part {part_idx + 1} ({len(self.highlighted_parts)} selected)"
        )

    def clear_all_part_highlights(self):
        """Clear all part highlights."""
        for part_idx in list(self.highlighted_parts.keys()):
            self.unhighlight_part(part_idx)

        # Clear tree selection
        self.ui.parts_tree.selection_remove(self.ui.parts_tree.selection())

    def update_tree_highlight_indicator(self, part_idx: int, is_highlighted: bool):
        """
        Update tree item visual indicator for highlighted parts.

        Args:
            part_idx: Index of the part
            is_highlighted: Whether the part is highlighted
        """
        # Find the tree item for this part
        root_items = self.ui.parts_tree.get_children()
        if not root_items:
            return

        # Get all part items under the root
        root_item = root_items[0]
        part_items = self.ui.parts_tree.get_children(root_item)

        # Find the item with matching part tag
        for item in part_items:
            tags = self.ui.parts_tree.item(item, "tags")
            if tags and tags[0] == f"part_{part_idx}":
                # Get current item text
                current_text = self.ui.parts_tree.item(item, "text")

                if is_highlighted:
                    # Add visual indicator (star) if not already present
                    if not current_text.startswith("★ "):
                        new_text = "★ " + current_text
                        self.ui.parts_tree.item(item, text=new_text)
                        # Make text bold and bright yellow
                        self.ui.parts_tree.tag_configure(
                            f"part_{part_idx}",
                            foreground="#ffff00",
                            font=("Arial", 9, "bold"),
                        )
                else:
                    # Remove visual indicator
                    if current_text.startswith("★ "):
                        new_text = current_text[2:]  # Remove "★ "
                        self.ui.parts_tree.item(item, text=new_text)
                        # Restore original color (need to recalculate from parts_list)
                        if part_idx < len(self.parts_list):
                            _, color, _ = self.parts_list[part_idx]
                            r, g, b = color
                            hex_color = (
                                f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                            )
                            # Check if this part is hidden as duplicate
                            is_hidden = (
                                self.deduplication_manager
                                and self.deduplication_manager.is_part_hidden(part_idx)
                            )
                            if is_hidden:
                                hex_color = "#666666"
                            self.ui.parts_tree.tag_configure(
                                f"part_{part_idx}",
                                foreground=hex_color,
                                font=("Arial", 9),
                            )
                break

    def restore_tree_highlight_indicators(self):
        """Restore highlight indicators in tree after tree refresh."""
        for part_idx in self.highlighted_parts.keys():
            self.update_tree_highlight_indicator(part_idx, True)
