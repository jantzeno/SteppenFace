"""
Main viewer UI components.
"""

from typing import List
import tkinter as tk
from tkinter import ttk

from ..config import ViewerConfig


class ViewerUI:
    """Manages the viewer UI components."""

    def __init__(self, root: tk.Tk, config: ViewerConfig):
        self.root = root
        self.config = config
        self.parts_tree = None
        self.mode_label = None
        self.selection_label = None

    def setup_window(self):
        """Setup the main window."""
        self.root.title("STEP File Viewer")
        self.root.geometry(f"{self.config.WINDOW_WIDTH}x{self.config.WINDOW_HEIGHT}")
        self.root.configure(borderwidth=0, highlightthickness=0, bg=self.config.DARK_BG)

    def create_layout(self):
        """Create the main layout with panels. Returns (paned_window, left_panel, right_panel)."""
        paned_window = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg=self.config.DARK_BG,
            sashwidth=5, sashrelief=tk.RAISED, borderwidth=0
        )
        paned_window.pack(fill=tk.BOTH, expand=True)

        # Left panel for parts list
        left_panel = self._create_left_panel(paned_window)

        # Right panel for 3D viewer
        right_panel = tk.Frame(paned_window, bg=self.config.DARK_BG, borderwidth=0, highlightthickness=0)
        right_panel.pack_propagate(True)

        paned_window.add(left_panel, minsize=200, width=250, stretch="never")
        paned_window.add(right_panel, minsize=400, stretch="always")

        return paned_window, left_panel, right_panel

    def _create_left_panel(self, parent):
        """Create the left navigation panel."""
        left_panel = tk.Frame(parent, bg=self.config.PANEL_BG, width=250, borderwidth=0, highlightthickness=0)

        # Header
        header = tk.Label(
            left_panel, text="Parts", bg=self.config.PANEL_BG, fg='#ffffff',
            font=('Arial', 10, 'bold'), anchor='w', padx=10, pady=5
        )
        header.pack(fill=tk.X)

        separator = tk.Frame(left_panel, bg=self.config.SEPARATOR_BG, height=1)
        separator.pack(fill=tk.X)

        # Tree view
        tree_frame = tk.Frame(left_panel, bg=self.config.PANEL_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._configure_tree_style()

        self.parts_tree = ttk.Treeview(tree_frame, style="Dark.Treeview", show='tree')
        self.parts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.parts_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.parts_tree.configure(yscrollcommand=scrollbar.set)

        # Status panel
        self._create_status_panel(left_panel)

        return left_panel

    def _configure_tree_style(self):
        """Configure dark theme for tree view."""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Dark.Treeview",
                       background=self.config.PANEL_BG,
                       foreground='#ffffff',
                       fieldbackground=self.config.PANEL_BG,
                       borderwidth=0,
                       relief='flat')
        style.configure("Dark.Treeview.Heading",
                       background=self.config.SEPARATOR_BG,
                       foreground='#ffffff',
                       borderwidth=0,
                       relief='flat')
        style.map("Dark.Treeview",
                 background=[('selected', '#3a3b3f')],
                 foreground=[('selected', '#ffffff')])

    def _create_status_panel(self, parent):
        """Create status panel with mode and selection info."""
        status_separator = tk.Frame(parent, bg=self.config.SEPARATOR_BG, height=1)
        status_separator.pack(fill=tk.X)

        status_frame = tk.Frame(parent, bg=self.config.PANEL_BG)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        self.mode_label = tk.Label(
            status_frame, text="Mode: Navigation", bg=self.config.PANEL_BG, fg='#00e0ff',
            font=('Arial', 9, 'bold'), anchor='w'
        )
        self.mode_label.pack(fill=tk.X)

        self.selection_label = tk.Label(
            status_frame, text="Selected: 0 faces", bg=self.config.PANEL_BG, fg='#00ff00',
            font=('Arial', 9, 'bold'), anchor='w'
        )
        self.selection_label.pack(fill=tk.X, pady=(5, 0))

    def populate_parts_tree(self, parts_list: List):
        """Populate the parts tree with parts."""
        if not self.parts_tree:
            return

        root_node = self.parts_tree.insert(
            '', 'end',
            text=f'Model ({len(parts_list)} part{"s" if len(parts_list) != 1 else ""})',
            open=True
        )

        for i, (solid, color, ais_shape) in enumerate(parts_list):
            r, g, b = color
            hex_color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
            part_name = f'■ Part {i+1}'
            self.parts_tree.insert(root_node, 'end', text=part_name, tags=(f'part_{i}',))
            self.parts_tree.tag_configure(f'part_{i}', foreground=hex_color)
