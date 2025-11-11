#!/usr/bin/env python3
import sys

try:
    from OCC.Core.STEPControl import STEPControl_Reader
except ImportError:
    import logging

    logging.basicConfig(level=logging.ERROR, format="[%(levelname)s] %(message)s")
    logging.error("pythonocc-core is not installed.")
    logging.error("Install it using: conda install -c conda-forge pythonocc-core")
    sys.exit(1)

from step_viewer.managers.application_manager import ApplicationManager
from step_viewer.managers.log_manager import logger


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        logger.error("Usage: python main.py <step_file>")
        logger.info("\nExample:")
        logger.info("  python main.py model.step")
        logger.info("  python main.py model.stp")
        sys.exit(1)

    """Print viewer controls to console."""
    logger.info("\n" + "=" * 60)
    logger.info("\nViewer Controls:")
    logger.info("  - Left mouse button: Rotate")
    logger.info("  - Right mouse button: Pan")
    logger.info("  - Mouse wheel: Zoom")
    logger.info("  - 'f': Fit all")
    logger.info("  - 's': Toggle face selection mode")
    logger.info("  - 'l': Select largest external face per part")
    logger.info("  - 'c': Clear all selections")
    logger.info("  - 'd': Toggle duplicate parts visibility")
    logger.info("  - 'p': Toggle planar alignment (lay parts flat)")
    logger.info("  - '1': Cycle selection fill color (in selection mode)")
    logger.info("  - '2': Cycle outline color (in selection mode)")
    logger.info("\nView Presets (Shift + number keys):")
    logger.info("  - Shift+1 (!): Front view")
    logger.info("  - Shift+2 (@): Back view")
    logger.info("  - Shift+3 (#): Right view")
    logger.info("  - Shift+4 ($): Left view")
    logger.info("  - Shift+5 (%): Top view")
    logger.info("  - Shift+6 (^): Bottom view")
    logger.info("  - Shift+7 (&): Isometric view")
    logger.info("\nQuit:")
    logger.info("  - 'q' or ESC")

    step_file = sys.argv[1]
    viewer = ApplicationManager(step_file)
    viewer.run()


if __name__ == "__main__":
    main()
