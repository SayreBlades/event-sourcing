"""
Domain service simulators for the API-driven approach.

These services represent the various bounded contexts in a BSS platform.
Unlike the event-sourced approach, these services:
- Call the notification API directly
- Must determine WHEN to send notifications
- Must gather context data for notifications

This demonstrates the key tradeoff:
- Notification service is simpler
- But domain services are more complex and coupled to notification concerns
"""

from api_driven.services.ordering import OrderingService

__all__ = ["OrderingService"]
