#!/usr/bin/env python3
"""
STEP File Viewer - Main entry point
Displays STEP files using OpenCASCADE's native BREP representation with face selection capabilities.
"""

import sys

try:
    from OCC.Core.STEPControl import STEPControl_Reader
except ImportError:
    import logging
    logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] %(message)s')
    logging.error("pythonocc-core is not installed.")
    logging.error("Install it using: conda install -c conda-forge pythonocc-core")
    sys.exit(1)

from step_viewer.viewer import StepViewer
from step_viewer.logger import logger


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        logger.error("Usage: python main.py <step_file>")
        logger.info("\nExample:")
        logger.info("  python main.py model.step")
        logger.info("  python main.py model.stp")
        sys.exit(1)

    step_file = sys.argv[1]
    viewer = StepViewer(step_file)
    viewer.run()


if __name__ == "__main__":
    main()
