"""
Plate controller for managing plates and part arrangement.
"""

import tkinter as tk
from tkinter import simpledialog, messagebox
from ..managers.log_manager import logger
from ..managers.plate_arrangement_manager import PlateArrangementManager
from ..managers.units_manager import UnitSystem


class PlateController:
    """Manages plate operations (add, delete, rename, arrange)."""

    def __init__(
        self,
        root: tk.Tk,
        canvas,
        display,
        ui,
        plate_manager,
        planar_alignment_manager,
        selection_manager=None,
        units_manager=None,
    ):
        self.root = root
        self.canvas = canvas
        self.display = display
        self.ui = ui
        self.plate_manager = plate_manager
        self.planar_alignment_manager = planar_alignment_manager
        self.selection_manager = selection_manager
        self.units_manager = units_manager
        self.arrangement_manager = PlateArrangementManager(plate_manager)
        self.parts_list = None  # Will be set from outside

    def setup_controls(self):
        """Setup plate management button callbacks."""
        self.ui.plate_widgets["add"].config(command=self.add_plate)
        self.ui.plate_widgets["delete"].config(command=self.delete_plate)
        self.ui.plate_widgets["rename"].config(command=self.rename_plate)
        self.ui.plate_widgets["arrange"].config(command=self.arrange_parts_on_plates)
        self.ui.plate_widgets["edit_dimensions"].config(
            command=self.edit_plate_dimensions
        )

        # Setup unit system change callback
        if self.units_manager:
            self.ui.unit_var.trace_add("write", self._on_unit_change)
            # Initialize unit selection to match units manager
            self.ui.unit_var.set(self.units_manager.get_unit_label())

        # Initialize plate list display
        self.ui.update_plate_list(self.plate_manager)

    def _on_unit_change(self, *args):
        """Handle unit system change."""
        if not self.units_manager:
            return

        unit_str = self.ui.unit_var.get()
        new_unit = UnitSystem.METRIC if unit_str == "mm" else UnitSystem.IMPERIAL
        self.units_manager.preferred_unit = new_unit
        logger.info(f"Unit system changed to: {self.units_manager.get_unit_label()}")

    def add_plate(self):
        """Add a new plate."""
        # Ask for plate name
        name = simpledialog.askstring(
            "Add Plate",
            "Enter name for new plate:",
            initialvalue=f"Plate {self.plate_manager.next_plate_id}",
            parent=self.root,
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
            messagebox.showwarning(
                "No Selection", "Please select a plate to delete.", parent=self.root
            )
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
            parent=self.root,
        ):
            # Erase exclusion zones from display BEFORE removing the plate
            if self.planar_alignment_manager.is_aligned:
                for zone in plate.exclusion_zones:
                    if zone.ais_shape is not None:
                        self.display.Context.Erase(zone.ais_shape, False)

                # Erase the plate itself from display
                if plate.ais_shape is not None:
                    self.display.Context.Erase(plate.ais_shape, False)

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
                    "Cannot Delete", "Cannot delete the last plate.", parent=self.root
                )

        self.canvas.focus_set()

    def rename_plate(self):
        """Rename the selected plate."""
        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a plate to rename.", parent=self.root
            )
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
            parent=self.root,
        )

        if new_name and new_name != plate.name:
            if self.plate_manager.rename_plate(plate.id, new_name):
                logger.info(f"Renamed plate '{plate.name}' to '{new_name}'")

                # Update UI
                self.ui.update_plate_list(self.plate_manager)

        self.canvas.focus_set()

    def set_parts_list(self, parts_list):
        """
        Set the parts list for arrangement.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
        """
        self.parts_list = parts_list

    def edit_plate_dimensions(self):
        """Edit dimensions of the selected plate."""
        if not self.units_manager:
            logger.error("Cannot edit plate dimensions: units_manager not set")
            messagebox.showerror(
                "Error",
                "Units manager not available. Cannot edit plate dimensions.",
                parent=self.root,
            )
            self.canvas.focus_set()
            return

        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection",
                "Please select a plate to edit dimensions.",
                parent=self.root,
            )
            self.canvas.focus_set()
            return

        plate_idx = selection[0]
        if plate_idx >= len(self.plate_manager.plates):
            self.canvas.focus_set()
            return

        plate = self.plate_manager.plates[plate_idx]

        # Show edit dimensions dialog
        dialog = PlateDimensionsDialog(self.root, plate, self.units_manager)
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            # Update plate dimensions
            old_width = plate.width_mm
            old_height = plate.height_mm
            plate.width_mm = dialog.width_mm
            plate.height_mm = dialog.height_mm

            logger.info(
                f"Updated plate '{plate.name}' dimensions from "
                f"{old_width:.1f}x{old_height:.1f}mm to "
                f"{plate.width_mm:.1f}x{plate.height_mm:.1f}mm"
            )

            # Update display if in planar view
            if self.planar_alignment_manager.is_aligned:
                self.plate_manager.update_single_plate(plate, self.display)
                self.display.Repaint()

            # Update UI
            self.ui.update_plate_list(self.plate_manager)

        self.canvas.focus_set()

    def arrange_parts_on_plates(self):
        """Arrange parts on plates using automatic packing algorithm."""
        # Check if planar alignment is active
        if not self.planar_alignment_manager.is_aligned:
            messagebox.showwarning(
                "Planar Alignment Required",
                "Please enable planar alignment (press 'P') before arranging parts.",
                parent=self.root,
            )
            self.canvas.focus_set()
            return

        # Check if we have parts to arrange
        if not self.parts_list:
            messagebox.showwarning(
                "No Parts", "No parts available to arrange.", parent=self.root
            )
            self.canvas.focus_set()
            return

        # Show arrangement options dialog
        dialog = ArrangementSettingsDialog(self.root, self.arrangement_manager)
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            # Apply settings
            self.arrangement_manager.set_spacing(dialog.spacing)
            self.arrangement_manager.set_margin(dialog.margin)
            self.arrangement_manager.set_rotation_enabled(dialog.allow_rotation)
            self.arrangement_manager.set_packing_mode(dialog.packing_mode)
            self.arrangement_manager.set_nfp_quality(dialog.nfp_quality)
            # self.arrangement_manager.set_packing_strategy(dialog.strategy)  # Commented out - using best_fit only

            # Perform arrangement
            try:
                logger.info("Starting automatic part arrangement...")
                packing_results = self.arrangement_manager.arrange_parts_on_plates(
                    self.parts_list, self.display
                )

                if packing_results:
                    # Apply the arrangement by transforming parts
                    self.arrangement_manager.apply_arrangement(
                        self.parts_list, packing_results, self.display
                    )

                    # Update selected faces to move with their parts
                    if self.selection_manager:
                        self.selection_manager.update_face_transformations()

                    # Update plate display
                    self.plate_manager.update_all_plates(self.display)
                    self.display.FitAll()
                    self.display.Repaint()

                    # Update UI
                    self.ui.update_plate_list(self.plate_manager)

                    messagebox.showinfo(
                        "Arrangement Complete",
                        f"Successfully arranged {len(packing_results)} parts on "
                        f"{len(self.plate_manager.plates)} plate(s).",
                        parent=self.root,
                    )
                else:
                    messagebox.showwarning(
                        "Arrangement Failed",
                        "Could not arrange parts. Check part sizes and plate dimensions.",
                        parent=self.root,
                    )

            except Exception as e:
                logger.error(f"Arrangement failed: {e}")
                messagebox.showerror(
                    "Arrangement Error",
                    f"An error occurred during arrangement:\n{str(e)}",
                    parent=self.root,
                )

        self.canvas.focus_set()


class ArrangementSettingsDialog:
    """Dialog for configuring arrangement settings."""

    def __init__(self, parent, arrangement_manager):
        self.result = False
        self.spacing = arrangement_manager.spacing_mm
        self.margin = arrangement_manager.margin_mm
        self.allow_rotation = arrangement_manager.allow_rotation
        self.packing_mode = arrangement_manager.packing_mode
        self.nfp_quality = arrangement_manager.nfp_quality

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Arrangement Settings")
        self.dialog.geometry("350x400")  # Increased height for new options
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#1a1b1f")

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.update_idletasks()
        x = (
            parent.winfo_x()
            + (parent.winfo_width() // 2)
            - (self.dialog.winfo_width() // 2)
        )
        y = (
            parent.winfo_y()
            + (parent.winfo_height() // 2)
            - (self.dialog.winfo_height() // 2)
        )
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        """Create dialog widgets."""
        # Spacing setting
        spacing_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        spacing_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(
            spacing_frame,
            text="Part Spacing (mm):",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10),
        ).pack(side="left")

        self.spacing_var = tk.DoubleVar(value=self.spacing)
        spacing_spinbox = tk.Spinbox(
            spacing_frame,
            from_=0,
            to=50,
            increment=1,
            textvariable=self.spacing_var,
            width=10,
            bg="#2a2b2f",
            fg="white",
            buttonbackground="#3a3b3f",
            insertbackground="white",
        )
        spacing_spinbox.pack(side="right")

        # Margin setting
        margin_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        margin_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(
            margin_frame,
            text="Plate/Exclusion Margin (mm):",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10),
        ).pack(side="left")

        self.margin_var = tk.DoubleVar(value=self.margin)
        margin_spinbox = tk.Spinbox(
            margin_frame,
            from_=0,
            to=50,
            increment=1,
            textvariable=self.margin_var,
            width=10,
            bg="#2a2b2f",
            fg="white",
            buttonbackground="#3a3b3f",
            insertbackground="white",
        )
        margin_spinbox.pack(side="right")

        # Rotation setting
        rotation_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        rotation_frame.pack(pady=10, padx=20, fill="x")

        self.rotation_var = tk.BooleanVar(value=self.allow_rotation)
        tk.Checkbutton(
            rotation_frame,
            text="Allow 90° rotation",
            variable=self.rotation_var,
            bg="#1a1b1f",
            fg="white",
            selectcolor="#3a3b3f",
            activebackground="#1a1b1f",
            activeforeground="white",
            font=("Arial", 10),
        ).pack(side="left")

        # Packing mode setting
        self.mode_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        self.mode_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(
            self.mode_frame,
            text="Packing Mode:",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10),
        ).pack(side="left")

        self.mode_var = tk.StringVar(value=self.packing_mode)

        mode_rect = tk.Radiobutton(
            self.mode_frame,
            text="Rectangle",
            variable=self.mode_var,
            value="rectangle",
            bg="#1a1b1f",
            fg="white",
            selectcolor="#3a3b3f",
            activebackground="#1a1b1f",
            activeforeground="white",
            font=("Arial", 9),
            command=self._on_mode_change,
        )
        mode_rect.pack(side="left", padx=5)

        mode_nfp = tk.Radiobutton(
            self.mode_frame,
            text="NFP (Smart)",
            variable=self.mode_var,
            value="nfp",
            bg="#1a1b1f",
            fg="white",
            selectcolor="#3a3b3f",
            activebackground="#1a1b1f",
            activeforeground="white",
            font=("Arial", 9),
            command=self._on_mode_change,
        )
        mode_nfp.pack(side="left", padx=5)

        # NFP quality setting (only shown when NFP mode is active)
        self.quality_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        self.quality_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(
            self.quality_frame,
            text="NFP Quality:",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10),
        ).pack(side="left")

        self.quality_var = tk.StringVar(value=self.nfp_quality)

        for quality in ["fast", "medium", "high"]:
            tk.Radiobutton(
                self.quality_frame,
                text=quality.capitalize(),
                variable=self.quality_var,
                value=quality,
                bg="#1a1b1f",
                fg="white",
                selectcolor="#3a3b3f",
                activebackground="#1a1b1f",
                activeforeground="white",
                font=("Arial", 9),
            ).pack(side="left", padx=5)

        # Initially hide quality frame if rectangle mode
        if self.packing_mode != "nfp":
            self.quality_frame.pack_forget()

        # Strategy setting (commented out - only best_fit currently available)
        # strategy_frame = tk.Frame(self.dialog, bg='#1a1b1f')
        # strategy_frame.pack(pady=10, padx=20, fill='x')
        #
        # tk.Label(
        #     strategy_frame,
        #     text="Packing Strategy:",
        #     bg='#1a1b1f',
        #     fg='white',
        #     font=('Arial', 10)
        # ).pack(side='left')
        #
        # self.strategy_var = tk.StringVar(value="best_fit")
        # strategy_combo = tk.OptionMenu(
        #     strategy_frame,
        #     self.strategy_var,
        #     "best_fit",
        #     "first_fit",
        #     "bottom_left"
        # )
        # strategy_combo.config(
        #     bg='#2a2b2f',
        #     fg='white',
        #     activebackground='#3a3b3f',
        #     activeforeground='white',
        #     highlightthickness=0,
        #     width=12
        # )
        # strategy_combo['menu'].config(bg='#2a2b2f', fg='white')
        # strategy_combo.pack(side='right')

        # Info label
        info_label = tk.Label(
            self.dialog,
            text="This will arrange all parts on plates\nusing automatic bin packing.",
            bg="#1a1b1f",
            fg="#888888",
            font=("Arial", 9),
            justify="center",
        )
        info_label.pack(pady=15)

        # Buttons
        button_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="Arrange",
            command=self._on_ok,
            bg="#3a7bff",
            fg="white",
            activebackground="#5090ff",
            activeforeground="white",
            font=("Arial", 10, "bold"),
            width=12,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=5)

        tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bg="#3a3b3f",
            fg="white",
            activebackground="#4a4b4f",
            activeforeground="white",
            font=("Arial", 10),
            width=12,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=5)

    def _on_mode_change(self):
        """Handle packing mode change."""
        mode = self.mode_var.get()

        # Show/hide quality options based on mode
        if mode == "nfp":
            # Repack the quality frame in the correct position
            self.quality_frame.pack(pady=10, padx=20, fill="x", after=self.mode_frame)
        else:
            self.quality_frame.pack_forget()

    def _on_ok(self):
        """Handle OK button click."""
        self.spacing = self.spacing_var.get()
        self.margin = self.margin_var.get()
        self.allow_rotation = self.rotation_var.get()
        self.packing_mode = self.mode_var.get()
        self.nfp_quality = self.quality_var.get()
        # self.strategy = self.strategy_var.get()  # Commented out - using best_fit only
        self.result = True
        self.dialog.destroy()

    def _on_cancel(self):
        """Handle Cancel button click."""
        self.result = False
        self.dialog.destroy()


class PlateDimensionsDialog:
    """Dialog for editing plate dimensions with unit selection."""

    def __init__(self, parent, plate, units_manager):
        if not units_manager:
            logger.error("PlateDimensionsDialog requires units_manager to be set")
            raise ValueError("units_manager is required for PlateDimensionsDialog")

        self.result = False
        self.plate = plate
        self.units_manager = units_manager
        self.width_mm = plate.width_mm
        self.height_mm = plate.height_mm

        # Determine initial unit and values
        self.current_unit = units_manager.preferred_unit
        width_display = units_manager.from_internal(plate.width_mm)
        height_display = units_manager.from_internal(plate.height_mm)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Plate Dimensions - {plate.name}")
        self.dialog.geometry("400x280")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg="#1a1b1f")

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.update_idletasks()
        x = (
            parent.winfo_x()
            + (parent.winfo_width() // 2)
            - (self.dialog.winfo_width() // 2)
        )
        y = (
            parent.winfo_y()
            + (parent.winfo_height() // 2)
            - (self.dialog.winfo_height() // 2)
        )
        self.dialog.geometry(f"+{x}+{y}")

        # Store initial display values
        self.width_display = width_display
        self.height_display = height_display

        self._create_widgets()

    def _create_widgets(self):
        """Create dialog widgets."""
        # Unit selection frame
        unit_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        unit_frame.pack(pady=15, padx=20, fill="x")

        tk.Label(
            unit_frame,
            text="Units:",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side="left")

        self.unit_var = tk.StringVar(
            value="mm" if self.current_unit == UnitSystem.METRIC else "in"
        )

        unit_mm = tk.Radiobutton(
            unit_frame,
            text="mm",
            variable=self.unit_var,
            value="mm",
            command=self._on_unit_change,
            bg="#1a1b1f",
            fg="white",
            selectcolor="#3a3b3f",
            activebackground="#1a1b1f",
            activeforeground="white",
            font=("Arial", 10),
        )
        unit_mm.pack(side="left", padx=10)

        unit_in = tk.Radiobutton(
            unit_frame,
            text="inches",
            variable=self.unit_var,
            value="in",
            command=self._on_unit_change,
            bg="#1a1b1f",
            fg="white",
            selectcolor="#3a3b3f",
            activebackground="#1a1b1f",
            activeforeground="white",
            font=("Arial", 10),
        )
        unit_in.pack(side="left", padx=10)

        # Width setting
        width_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        width_frame.pack(pady=10, padx=20, fill="x")

        self.width_label = tk.Label(
            width_frame,
            text=f"Width ({self.unit_var.get()}):",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10),
        )
        self.width_label.pack(side="left")

        self.width_var = tk.DoubleVar(value=self.width_display)
        width_spinbox = tk.Spinbox(
            width_frame,
            from_=1,
            to=10000,
            increment=1,
            textvariable=self.width_var,
            width=12,
            bg="#2a2b2f",
            fg="white",
            buttonbackground="#3a3b3f",
            insertbackground="white",
        )
        width_spinbox.pack(side="right")

        # Height setting
        height_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        height_frame.pack(pady=10, padx=20, fill="x")

        self.height_label = tk.Label(
            height_frame,
            text=f"Height ({self.unit_var.get()}):",
            bg="#1a1b1f",
            fg="white",
            font=("Arial", 10),
        )
        self.height_label.pack(side="left")

        self.height_var = tk.DoubleVar(value=self.height_display)
        height_spinbox = tk.Spinbox(
            height_frame,
            from_=1,
            to=10000,
            increment=1,
            textvariable=self.height_var,
            width=12,
            bg="#2a2b2f",
            fg="white",
            buttonbackground="#3a3b3f",
            insertbackground="white",
        )
        height_spinbox.pack(side="right")

        # Info label
        info_label = tk.Label(
            self.dialog,
            text="Enter the new dimensions for this plate.",
            bg="#1a1b1f",
            fg="#888888",
            font=("Arial", 9),
            justify="center",
        )
        info_label.pack(pady=15)

        # Buttons
        button_frame = tk.Frame(self.dialog, bg="#1a1b1f")
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="Apply",
            command=self._on_ok,
            bg="#3a7bff",
            fg="white",
            activebackground="#5090ff",
            activeforeground="white",
            font=("Arial", 10, "bold"),
            width=12,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=5)

        tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bg="#3a3b3f",
            fg="white",
            activebackground="#4a4b4f",
            activeforeground="white",
            font=("Arial", 10),
            width=12,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=5)

    def _on_unit_change(self):
        """Handle unit system change - convert displayed values."""
        new_unit_str = self.unit_var.get()
        new_unit = UnitSystem.METRIC if new_unit_str == "mm" else UnitSystem.IMPERIAL

        # Get current values in mm
        width_mm = self.units_manager.to_internal(
            self.width_var.get(), self.current_unit
        )
        height_mm = self.units_manager.to_internal(
            self.height_var.get(), self.current_unit
        )

        # Convert to new unit
        new_width = self.units_manager.from_internal(width_mm, new_unit)
        new_height = self.units_manager.from_internal(height_mm, new_unit)

        # Update variables and labels
        self.width_var.set(round(new_width, 2))
        self.height_var.set(round(new_height, 2))
        self.width_label.config(text=f"Width ({new_unit_str}):")
        self.height_label.config(text=f"Height ({new_unit_str}):")
        self.current_unit = new_unit

    def _on_ok(self):
        """Handle OK button click."""
        try:
            width = self.width_var.get()
            height = self.height_var.get()

            if width <= 0 or height <= 0:
                messagebox.showerror(
                    "Invalid Dimensions",
                    "Width and height must be positive values.",
                    parent=self.dialog,
                )
                return

            # Convert to mm (internal units)
            self.width_mm = self.units_manager.to_internal(width, self.current_unit)
            self.height_mm = self.units_manager.to_internal(height, self.current_unit)

            self.result = True
            self.dialog.destroy()

        except tk.TclError:
            messagebox.showerror(
                "Invalid Input",
                "Please enter valid numeric values.",
                parent=self.dialog,
            )

    def _on_cancel(self):
        """Handle Cancel button click."""
        self.result = False
        self.dialog.destroy()
