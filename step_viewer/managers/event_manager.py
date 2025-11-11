"""
Event manager for managing mouse and keyboard event bindings.
"""

import tkinter as tk


class EventManager:
    """Manages event binding for mouse and keyboard interactions."""

    def __init__(
        self,
        root: tk.Tk,
        canvas,
        mouse_controller,
        keyboard_controller,
        exclusion_zone_controller=None,
        coordinate_converter=None,
    ):
        self.root = root
        self.canvas = canvas
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.exclusion_zone_controller = exclusion_zone_controller
        self.coordinate_converter = coordinate_converter

    def bind_events(
        self, toggle_duplicate_callback, toggle_planar_callback, select_largest_callback
    ):
        """
        Bind mouse and keyboard events.

        Args:
            toggle_duplicate_callback: Callback for toggling duplicate visibility
            toggle_planar_callback: Callback for toggling planar alignment
            select_largest_callback: Callback for selecting largest faces
        """
        # Unbind OCC's default handlers
        widgets_to_unbind = [self.canvas, self.root]
        for widget in widgets_to_unbind:
            for event in [
                "<Button-1>",
                "<Button-2>",
                "<Button-3>",
                "<B1-Motion>",
                "<B2-Motion>",
                "<B3-Motion>",
                "<ButtonRelease-1>",
                "<ButtonRelease-2>",
                "<ButtonRelease-3>",
            ]:
                try:
                    widget.unbind(event)
                except:
                    pass

        # Helper to stop event propagation (but allow tree widget events)
        def make_handler(func):
            def handler(event):
                # Don't intercept events from the parts tree
                if (
                    hasattr(event.widget, "winfo_class")
                    and event.widget.winfo_class() == "Treeview"
                ):
                    return
                func(event)
                return "break"

            return handler

        # Bind mouse events (with exclusion zone handling if available)
        self.root.bind_all("<Button-1>", make_handler(self._on_left_press_wrapper))
        self.root.bind_all("<B1-Motion>", make_handler(self._on_left_motion_wrapper))
        self.root.bind_all("<ButtonRelease-1>", make_handler(self._on_release_wrapper))
        self.root.bind_all(
            "<Button-3>", make_handler(self.mouse_controller.on_right_press)
        )
        self.root.bind_all(
            "<B3-Motion>", make_handler(self.mouse_controller.on_right_motion)
        )
        self.root.bind_all(
            "<ButtonRelease-3>", make_handler(self.mouse_controller.on_release)
        )
        self.root.bind_all("<MouseWheel>", make_handler(self.mouse_controller.on_wheel))
        self.root.bind_all("<Button-4>", make_handler(self.mouse_controller.on_wheel))
        self.root.bind_all("<Button-5>", make_handler(self.mouse_controller.on_wheel))

        # Bind keyboard events
        self.canvas.bind("<f>", self.keyboard_controller.on_key_f)
        self.canvas.bind("<F>", self.keyboard_controller.on_key_f)
        self.canvas.bind("<q>", self.keyboard_controller.on_key_q)
        self.canvas.bind("<Q>", self.keyboard_controller.on_key_q)
        self.canvas.bind("<Escape>", self.keyboard_controller.on_key_q)
        self.canvas.bind("<s>", self.keyboard_controller.on_key_s)
        self.canvas.bind("<S>", self.keyboard_controller.on_key_s)
        self.canvas.bind("<c>", self.keyboard_controller.on_key_c)
        self.canvas.bind("<C>", self.keyboard_controller.on_key_c)
        self.canvas.bind("<Key-1>", self.keyboard_controller.on_key_1)
        self.canvas.bind("<Key-2>", self.keyboard_controller.on_key_2)
        self.canvas.bind("<d>", lambda e: toggle_duplicate_callback())
        self.canvas.bind("<D>", lambda e: toggle_duplicate_callback())
        self.canvas.bind("<p>", lambda e: toggle_planar_callback())
        self.canvas.bind("<P>", lambda e: toggle_planar_callback())
        self.canvas.bind("<l>", lambda e: select_largest_callback())
        self.canvas.bind("<L>", lambda e: select_largest_callback())

        # Bind view preset keys (Shift + number keys)
        self.canvas.bind(
            "<exclam>", self.keyboard_controller.on_key_shift_1
        )  # Shift+1 = ! (Front)
        self.canvas.bind(
            "<at>", self.keyboard_controller.on_key_shift_2
        )  # Shift+2 = @ (Back)
        self.canvas.bind(
            "<numbersign>", self.keyboard_controller.on_key_shift_3
        )  # Shift+3 = # (Right)
        self.canvas.bind(
            "<dollar>", self.keyboard_controller.on_key_shift_4
        )  # Shift+4 = $ (Left)
        self.canvas.bind(
            "<percent>", self.keyboard_controller.on_key_shift_5
        )  # Shift+5 = % (Top)
        self.canvas.bind(
            "<asciicircum>", self.keyboard_controller.on_key_shift_6
        )  # Shift+6 = ^ (Bottom)
        self.canvas.bind(
            "<ampersand>", self.keyboard_controller.on_key_shift_7
        )  # Shift+7 = & (Isometric)

        self.canvas.focus_set()

    def _on_left_press_wrapper(self, event):
        """Wrapper for left mouse press that handles exclusion zone drawing."""
        if (
            self.exclusion_zone_controller
            and self.exclusion_zone_controller.exclusion_draw_mode
        ):
            if (
                self.exclusion_zone_controller.planar_alignment_manager.is_aligned
                and self.coordinate_converter
            ):
                world_x, world_y, _ = self.coordinate_converter(event.x, event.y)
                if self.exclusion_zone_controller.handle_click(world_x, world_y):
                    return  # Consumed by exclusion zone drawing

        # Otherwise, delegate to normal mouse controller
        self.mouse_controller.on_left_press(event)

    def _on_left_motion_wrapper(self, event):
        """Wrapper for left mouse motion that handles exclusion zone drawing."""
        if (
            self.exclusion_zone_controller
            and self.exclusion_zone_controller.exclusion_draw_mode
        ):
            if (
                self.exclusion_zone_controller.planar_alignment_manager.is_aligned
                and self.exclusion_zone_controller.exclusion_start_point
                and self.coordinate_converter
            ):
                world_x, world_y, _ = self.coordinate_converter(event.x, event.y)
                if self.exclusion_zone_controller.handle_drag(world_x, world_y):
                    return  # Consumed by exclusion zone drawing

        # Otherwise, delegate to normal mouse controller
        self.mouse_controller.on_left_motion(event)

    def _on_release_wrapper(self, event):
        """Wrapper for mouse release that handles exclusion zone drawing."""
        if (
            self.exclusion_zone_controller
            and self.exclusion_zone_controller.exclusion_draw_mode
        ):
            if (
                self.exclusion_zone_controller.planar_alignment_manager.is_aligned
                and self.exclusion_zone_controller.exclusion_start_point
                and self.coordinate_converter
            ):
                world_x, world_y, _ = self.coordinate_converter(event.x, event.y)
                if self.exclusion_zone_controller.handle_release(world_x, world_y):
                    return  # Consumed by exclusion zone drawing

        # Otherwise, delegate to normal mouse controller
        self.mouse_controller.on_release(event)
