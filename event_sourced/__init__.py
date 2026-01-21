"""
Event-sourced notification approach.

This package implements the event-sourced architecture for notifications:
- Services publish events when things happen in their domain
- Notification service subscribes to events and sends notifications
- Publishers and subscribers are decoupled via the event bus
"""

from event_sourced.event_bus import Event, EventBus, get_event_bus, reset_event_bus
from event_sourced.notification_service import NotificationService
from event_sourced.services.ordering import OrderingService

__all__ = [
    "Event",
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
    "NotificationService",
    "OrderingService",
]
