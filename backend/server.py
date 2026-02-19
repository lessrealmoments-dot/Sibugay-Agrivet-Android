"""
AgriPOS Server Entry Point
==========================
This file serves as the entry point for uvicorn (server:app).
The actual application is defined in main.py with modular routes.

This allows the supervisor config to remain unchanged while using
the new modular architecture.
"""

# Re-export app from main module
from main import app

# The `app` is now available for uvicorn: `uvicorn server:app`
