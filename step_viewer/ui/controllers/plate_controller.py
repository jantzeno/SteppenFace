"""
Plate controller for managing plates and part arrangement.
"""

import tkinter as tk
from tkinter import simpledialog, messagebox

from ...managers.log_manager import logger


class PlateController:
    """Manages plate operations (add, delete, rename, arrange)."""

    def __init__(self, root: tk.Tk, canvas, display, ui, plate_manager, planar_alignment_manager):
        self.root = root
        self.canvas = canvas
        self.display = display
        self.ui = ui
        self.plate_manager = plate_manager
        self.planar_alignment_manager = planar_alignment_manager

    def setup_controls(self):
        """Setup plate management button callbacks."""
        self.ui.plate_widgets['add'].config(command=self.add_plate)
        self.ui.plate_widgets['delete'].config(command=self.delete_plate)
        self.ui.plate_widgets['rename'].config(command=self.rename_plate)
        self.ui.plate_widgets['arrange'].config(command=self.arrange_parts_on_plates)

        # Initialize plate list display
        self.ui.update_plate_list(self.plate_manager)

    def add_plate(self):
        """Add a new plate."""
        # Ask for plate name
        name = simpledialog.askstring(
            "Add Plate",
            "Enter name for new plate:",
            initialvalue=f"Plate {self.plate_manager.next_plate_id}",
            parent=self.root
        )

        if name:
            plate = self.plate_manager.add_plate(name)
            logger.info(f"Added new plate: {plate.name}")

            # Update UI
            self.ui.update_plate_list(self.plate_manager)

            # If planar alignment is active, update the display
            if self.planar_alignment_manager.is_aligned:
                self.plate_manager.update_all_plates(self.display)
                self.display.Repaint()

        self.canvas.focus_set()

    def delete_plate(self):
        """Delete the selected plate."""
        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a plate to delete.", parent=self.root)
            self.canvas.focus_set()
            return

        plate_idx = selection[0]
        if plate_idx >= len(self.plate_manager.plates):
            self.canvas.focus_set()
            return

        plate = self.plate_manager.plates[plate_idx]

        # Confirm deletion
        if messagebox.askyesno(
            "Delete Plate",
            f"Delete '{plate.name}'?\nParts will not be deleted, only disassociated.",
            parent=self.root
        ):
            if self.plate_manager.remove_plate(plate.id):
                logger.info(f"Deleted plate: {plate.name}")

                # Update UI
                self.ui.update_plate_list(self.plate_manager)

                # If planar alignment is active, update the display
                if self.planar_alignment_manager.is_aligned:
                    self.plate_manager.update_all_plates(self.display)
                    self.display.Repaint()
            else:
                messagebox.showwarning(
                    "Cannot Delete",
                    "Cannot delete the last plate.",
                    parent=self.root
                )

        self.canvas.focus_set()

    def rename_plate(self):
        """Rename the selected plate."""
        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a plate to rename.", parent=self.root)
            self.canvas.focus_set()
            return

        plate_idx = selection[0]
        if plate_idx >= len(self.plate_manager.plates):
            self.canvas.focus_set()
            return

        plate = self.plate_manager.plates[plate_idx]

        # Ask for new name
        new_name = simpledialog.askstring(
            "Rename Plate",
            "Enter new name for plate:",
            initialvalue=plate.name,
            parent=self.root
        )

        if new_name and new_name != plate.name:
            if self.plate_manager.rename_plate(plate.id, new_name):
                logger.info(f"Renamed plate '{plate.name}' to '{new_name}'")

                # Update UI
                self.ui.update_plate_list(self.plate_manager)

        self.canvas.focus_set()

    def arrange_parts_on_plates(self):
        """Arrange parts on plates (placeholder for future logic)."""
        messagebox.showinfo(
            "Arrange Parts",
            "Part arrangement logic is not yet implemented.\n\n"
            "In the future, this will automatically arrange parts on the selected plate "
            "to optimize space usage.",
            parent=self.root
        )

        self.canvas.focus_set()
