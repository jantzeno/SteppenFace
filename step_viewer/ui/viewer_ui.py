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
        self.explode_slider = None
        self.explode_label = None

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

        # Explode slider section
        explode_separator = tk.Frame(parent, bg=self.config.SEPARATOR_BG, height=1)
        explode_separator.pack(fill=tk.X, pady=(10, 0))

        explode_frame = tk.Frame(parent, bg=self.config.PANEL_BG)
        explode_frame.pack(fill=tk.X, padx=10, pady=10)

        self.explode_label = tk.Label(
            explode_frame, text="Explode: 0.0", bg=self.config.PANEL_BG, fg='#ffaa00',
            font=('Arial', 9, 'bold'), anchor='w'
        )
        self.explode_label.pack(fill=tk.X)

        self.explode_slider = tk.Scale(
            explode_frame, from_=0.0, to=2.0, resolution=0.01,
            orient=tk.HORIZONTAL, bg=self.config.PANEL_BG, fg='#ffffff',
            highlightthickness=0, troughcolor='#3a3b3f', activebackground='#ffaa00',
            showvalue=False
        )
        self.explode_slider.set(0.0)
        self.explode_slider.pack(fill=tk.X, pady=(5, 0))

        # View preset buttons section
        self._create_view_buttons(parent)

    def _create_view_buttons(self, parent):
        """Create view preset buttons."""
        view_separator = tk.Frame(parent, bg=self.config.SEPARATOR_BG, height=1)
        view_separator.pack(fill=tk.X, pady=(10, 0))

        view_frame = tk.Frame(parent, bg=self.config.PANEL_BG)
        view_frame.pack(fill=tk.X, padx=10, pady=10)

        view_label = tk.Label(
            view_frame, text="View Presets", bg=self.config.PANEL_BG, fg='#ffffff',
            font=('Arial', 9, 'bold'), anchor='w'
        )
        view_label.pack(fill=tk.X, pady=(0, 5))

        # Create button grid (2 columns x 4 rows)
        button_style = {
            'bg': '#3a3b3f',
            'fg': '#ffffff',
            'activebackground': '#00e0ff',
            'activeforeground': '#000000',
            'relief': 'raised',
            'borderwidth': 1,
            'font': ('Arial', 8),
            'width': 8,
            'height': 1
        }

        # Store button commands (will be set later by viewer)
        self.view_buttons = {}

        # Row 1: Front and Back
        row1 = tk.Frame(view_frame, bg=self.config.PANEL_BG)
        row1.pack(fill=tk.X, pady=2)

        btn_front = tk.Button(row1, text="Front (!)", **button_style)
        btn_front.pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)
        self.view_buttons['front'] = btn_front

        btn_back = tk.Button(row1, text="Back (@)", **button_style)
        btn_back.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.view_buttons['back'] = btn_back

        # Row 2: Right and Left
        row2 = tk.Frame(view_frame, bg=self.config.PANEL_BG)
        row2.pack(fill=tk.X, pady=2)

        btn_right = tk.Button(row2, text="Right (#)", **button_style)
        btn_right.pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)
        self.view_buttons['right'] = btn_right

        btn_left = tk.Button(row2, text="Left ($)", **button_style)
        btn_left.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.view_buttons['left'] = btn_left

        # Row 3: Top and Bottom
        row3 = tk.Frame(view_frame, bg=self.config.PANEL_BG)
        row3.pack(fill=tk.X, pady=2)

        btn_top = tk.Button(row3, text="Top (%)", **button_style)
        btn_top.pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)
        self.view_buttons['top'] = btn_top

        btn_bottom = tk.Button(row3, text="Bottom (^)", **button_style)
        btn_bottom.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.view_buttons['bottom'] = btn_bottom

        # Row 4: Isometric (centered)
        row4 = tk.Frame(view_frame, bg=self.config.PANEL_BG)
        row4.pack(fill=tk.X, pady=2)

        btn_iso = tk.Button(row4, text="Isometric (&)", **button_style)
        btn_iso.pack(expand=True, fill=tk.X)
        self.view_buttons['isometric'] = btn_iso

    def populate_parts_tree(self, parts_list: List, deduplication_manager=None):
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

            # Check if this part is hidden as a duplicate
            is_hidden = deduplication_manager and deduplication_manager.is_part_hidden(i)

            if is_hidden:
                part_name = f'■ Part {i+1} (hidden - duplicate)'
                # Use a dimmed color for hidden parts
                hex_color = '#666666'
            else:
                part_name = f'■ Part {i+1}'

            self.parts_tree.insert(root_node, 'end', text=part_name, tags=(f'part_{i}',))
            self.parts_tree.tag_configure(f'part_{i}', foreground=hex_color)

    def update_parts_tree(self, parts_list: List, deduplication_manager=None):
        """Update the parts tree to reflect current visibility state."""
        if not self.parts_tree:
            return

        # Clear existing tree
        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        # Repopulate with updated information
        self.populate_parts_tree(parts_list, deduplication_manager)
