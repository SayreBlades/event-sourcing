"""
Shared infrastructure for the notification architecture demo.

This package contains code used by both the event-sourced and API-driven approaches:
- Domain models (Customer, Order, Product, etc.)
- Data store for JSON-backed persistence
- Mock notification channels (Email, SMS)
- Notification templates
"""

from shared.models import (
    Customer,
    Product,
    Order,
    LineItem,
    Cart,
    CartItem,
    NotificationPreference,
    ChannelPreferences,
)
from shared.data_store import DataStore
from shared.channels import EmailChannel, SMSChannel, NotificationResult

__all__ = [
    "Customer",
    "Product", 
    "Order",
    "LineItem",
    "Cart",
    "CartItem",
    "NotificationPreference",
    "ChannelPreferences",
    "DataStore",
    "EmailChannel",
    "SMSChannel",
    "NotificationResult",
]
