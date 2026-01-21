"""
Unified API for the notification architecture demo.

This package provides a single FastAPI application that exposes:
- Demo endpoints for both event-sourced and API-driven approaches
- Comparison endpoints to run scenarios side-by-side
- Direct access to the notification API
- Data exploration endpoints
"""

from api.main import app

__all__ = ["app"]
