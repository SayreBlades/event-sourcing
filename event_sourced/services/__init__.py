"""
Domain service simulators for the event-sourced approach.

These services represent the various bounded contexts in a BSS platform:
- Ordering: Manages customer orders and fulfillment
- Pricing: Manages product prices
- Promotions: Manages promotional offers
- Billing: Manages invoicing and billing

Each service publishes events when things happen in their domain.
They do NOT know about the notification service - they just publish events.
"""

from event_sourced.services.ordering import OrderingService
from event_sourced.services.pricing import PricingService
from event_sourced.services.billing import BillingService
from event_sourced.services.promotions import PromotionsService

__all__ = [
    "OrderingService",
    "PricingService",
    "BillingService",
    "PromotionsService",
]
