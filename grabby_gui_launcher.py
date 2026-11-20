"""Windowed entry point for the portable user app."""

import grabby
from grabby_gui import GrabbyApp


if __name__ == "__main__":
    grabby.enable_dpi_awareness()
    GrabbyApp().run()
