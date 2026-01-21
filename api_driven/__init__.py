"""
API-driven notification approach.

This package implements the API-driven architecture for notifications:
- Services call the notification API directly when they want to notify
- The calling service must determine WHEN to notify and provide context
- The notification API handles lookup, templating, and sending
"""

from api_driven.notification_api import NotificationAPI, app
from api_driven.models import NotificationRequest, NotificationResponse, NotificationType
from api_driven.services.ordering import OrderingService

__all__ = [
    "NotificationAPI",
    "app",
    "NotificationRequest",
    "NotificationResponse", 
    "NotificationType",
    "OrderingService",
]
