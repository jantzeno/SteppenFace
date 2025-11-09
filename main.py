#!/usr/bin/env python3
"""
STEP File Viewer - Main entry point
Displays STEP files using OpenCASCADE's native BREP representation with face selection capabilities.
"""

import sys

try:
    from OCC.Core.STEPControl import STEPControl_Reader
except ImportError:
    print("Error: pythonocc-core is not installed.")
    print("Install it using: conda install -c conda-forge pythonocc-core")
    sys.exit(1)

from step_viewer.viewer import StepViewer


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <step_file>")
        print("\nExample:")
        print("  python main.py model.step")
        print("  python main.py model.stp")
        sys.exit(1)

    step_file = sys.argv[1]
    viewer = StepViewer(step_file)
    viewer.run()


if __name__ == "__main__":
    main()
