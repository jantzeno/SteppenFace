"""
Configuration settings for the STEP viewer.
"""


class ViewerConfig:
    """Configuration settings for the STEP viewer."""

    # Display settings
    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 768
    BACKGROUND_COLOR = (17/255.0, 18/255.0, 22/255.0)
    MSAA_SAMPLES = 4  # Anti-aliasing quality

    # Color scheme
    DARK_BG = '#111216'
    PANEL_BG = '#1a1b1f'
    SEPARATOR_BG = '#2a2b2f'
    SELECTION_MODE_BG = '#2a2520'

    # Selection settings
    SELECTION_COLOR = (1.0, 0.5, 0.0)
    SELECTION_OUTLINE_COLOR = (0.07, 0.07, 0.09)
    SELECTION_OUTLINE_WIDTH = 2.0
    SELECTION_TRANSPARENCY = 0.1

    # Material thickness for external face detection (mm)
    # This controls the raycast threshold - intersections within this distance
    # are considered self-intersections and ignored
    # The threshold will be: max(2.5 × thickness, 5.0mm) to handle thin parts
    MATERIAL_THICKNESS_MM = 3.0  # Default: 3mm (adjust based on your material)

    # Sheet/platter size for planar view (mm)
    # Common laser cutter bed sizes:
    # - 600x400mm (small)
    # - 900x600mm (medium)
    # - 1300x900mm (large)
    SHEET_WIDTH_MM = 600.0  # Default: 600mm
    SHEET_HEIGHT_MM = 400.0  # Default: 400mm

    # Color presets
    SELECTION_COLOR_PRESETS = [
        ((1.0, 0.5, 0.0), "Orange"),
        ((1.0, 0.0, 0.0), "Red"),
        ((0.0, 1.0, 0.0), "Green"),
        ((0.0, 0.0, 1.0), "Blue"),
        ((1.0, 0.0, 1.0), "Magenta"),
        ((0.0, 1.0, 1.0), "Cyan"),
        ((1.0, 1.0, 0.0), "Yellow"),
    ]

    OUTLINE_COLOR_PRESETS = [
        ((0.07, 0.07, 0.09), "Dark Gray"),
        ((0.0, 0.0, 0.0), "Black"),
        ((1.0, 1.0, 1.0), "White"),
        ((1.0, 1.0, 0.0), "Yellow"),
        ((0.0, 1.0, 1.0), "Cyan"),
    ]

    # Part colors (colorblind-friendly palette)
    PART_PALETTE = [
        (0.90, 0.40, 0.60),  # Rose/Pink
        (0.40, 0.50, 0.90),  # Bright blue
        (1.00, 0.60, 0.20),  # Orange
        (0.45, 0.85, 0.45),  # Green
        (0.95, 0.90, 0.25),  # Yellow
        (0.65, 0.35, 0.85),  # Purple
        (0.30, 0.75, 0.90),  # Cyan
        (0.95, 0.35, 0.35),  # Red
        (0.50, 0.70, 0.50),  # Gray-green
        (0.80, 0.60, 0.90),  # Lavender
        (0.60, 0.90, 0.70),  # Mint
        (0.90, 0.75, 0.45),  # Tan/Beige
    ]
