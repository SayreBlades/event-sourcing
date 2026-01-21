"""
Domain service simulators for the API-driven approach.

These services represent the various bounded contexts in a BSS platform.
Unlike the event-sourced approach, these services:
- Call the notification API directly
- Must determine WHEN to send notifications
- Must gather context data for notifications
- Must query CROSS-DOMAIN data for eligibility checks

This demonstrates the key tradeoff:
- Notification service is simpler
- But domain services are more complex and coupled to notification concerns
"""

from api_driven.services.ordering import OrderingService
from api_driven.services.pricing import PricingService
from api_driven.services.billing import BillingService
from api_driven.services.promotions import PromotionsService

__all__ = [
    "OrderingService",
    "PricingService",
    "BillingService",
    "PromotionsService",
]
