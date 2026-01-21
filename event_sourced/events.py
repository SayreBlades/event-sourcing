"""
Event definitions for the event-sourced approach.

This module defines all the domain events that services can publish.
Events represent facts about things that have happened in the system.

Design decisions:
- Events are named in past tense (OrderShipped, not ShipOrder)
- Events contain all data needed by subscribers (no need to query back)
- Events are versioned implicitly by their structure
- Helper functions create properly structured Event objects

Key insight for the demo:
- These events are defined by the publishing service (domain ownership)
- The notification service must understand these events to react to them
- Adding new fields is backward compatible; removing/changing is not

TMF-inspired event naming:
- OrderStatusChanged (TMF622 - Order Management)
- PaymentStatusChanged (TMF676 - Payment Management)  
- PriceChanged (TMF620 - Product Catalog)
- PromotionActivated (TMF671 - Promotion)
"""

from datetime import datetime
from typing import Any, Optional

from event_sourced.event_bus import Event


# =============================================================================
# Event Type Constants
# =============================================================================

class EventTypes:
    """
    Constants for event type names.
    
    Using constants prevents typos and makes it easy to see all event types.
    """
    # Order events
    ORDER_CREATED = "OrderCreated"
    ORDER_STATUS_CHANGED = "OrderStatusChanged"
    LINE_ITEM_STATUS_CHANGED = "LineItemStatusChanged"
    
    # Payment events
    PAYMENT_ATTEMPTED = "PaymentAttempted"
    PAYMENT_SUCCEEDED = "PaymentSucceeded"
    PAYMENT_FAILED = "PaymentFailed"
    
    # Pricing events
    PRICE_CHANGED = "PriceChanged"
    
    # Promotion events
    PROMOTION_ACTIVATED = "PromotionActivated"
    PROMOTION_DEACTIVATED = "PromotionDeactivated"


# =============================================================================
# Order Events
# =============================================================================

def order_created(
    order_id: str,
    customer_id: str,
    line_items: list[dict],
    total_amount: float,
    source: str = "ordering-service",
) -> Event:
    """
    Create an OrderCreated event.
    
    Published when a new order is placed.
    """
    return Event(
        event_type=EventTypes.ORDER_CREATED,
        source=source,
        payload={
            "order_id": order_id,
            "customer_id": customer_id,
            "line_items": line_items,
            "total_amount": total_amount,
        },
    )


def order_status_changed(
    order_id: str,
    customer_id: str,
    previous_status: str,
    new_status: str,
    source: str = "ordering-service",
) -> Event:
    """
    Create an OrderStatusChanged event.
    
    Published when an order's overall status changes (e.g., PROCESSING -> SHIPPED).
    This is the key event for the "Order Shipped" notification scenario.
    
    Note: We include customer_id in the event so subscribers don't need to
    look it up. This is a key design decision in event-sourced systems.
    """
    return Event(
        event_type=EventTypes.ORDER_STATUS_CHANGED,
        source=source,
        payload={
            "order_id": order_id,
            "customer_id": customer_id,
            "previous_status": previous_status,
            "new_status": new_status,
        },
    )


def line_item_status_changed(
    order_id: str,
    customer_id: str,
    product_id: str,
    previous_status: str,
    new_status: str,
    items_remaining: int,
    source: str = "ordering-service",
) -> Event:
    """
    Create a LineItemStatusChanged event.
    
    Published when an individual line item's status changes.
    This is key for the "Order Complete" scenario where items ship separately.
    
    Args:
        order_id: The order containing this line item
        customer_id: The customer who placed the order
        product_id: Which product/line item changed
        previous_status: Status before the change
        new_status: Status after the change
        items_remaining: Number of items in the order still not shipped/delivered
    """
    return Event(
        event_type=EventTypes.LINE_ITEM_STATUS_CHANGED,
        source=source,
        payload={
            "order_id": order_id,
            "customer_id": customer_id,
            "product_id": product_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "items_remaining": items_remaining,
        },
    )


# =============================================================================
# Payment Events
# =============================================================================

def payment_attempted(
    payment_id: str,
    order_id: str,
    customer_id: str,
    amount: float,
    attempt_number: int,
    source: str = "payment-service",
) -> Event:
    """Create a PaymentAttempted event."""
    return Event(
        event_type=EventTypes.PAYMENT_ATTEMPTED,
        source=source,
        payload={
            "payment_id": payment_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": amount,
            "attempt_number": attempt_number,
        },
    )


def payment_succeeded(
    payment_id: str,
    order_id: str,
    customer_id: str,
    amount: float,
    source: str = "payment-service",
) -> Event:
    """Create a PaymentSucceeded event."""
    return Event(
        event_type=EventTypes.PAYMENT_SUCCEEDED,
        source=source,
        payload={
            "payment_id": payment_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": amount,
        },
    )


def payment_failed(
    payment_id: str,
    order_id: str,
    customer_id: str,
    amount: float,
    failure_reason: str,
    attempt_number: int,
    source: str = "payment-service",
) -> Event:
    """
    Create a PaymentFailed event.
    
    This is the key event for the "Payment Failed" notification scenario.
    """
    return Event(
        event_type=EventTypes.PAYMENT_FAILED,
        source=source,
        payload={
            "payment_id": payment_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": amount,
            "failure_reason": failure_reason,
            "attempt_number": attempt_number,
        },
    )


# =============================================================================
# Pricing Events
# =============================================================================

def price_changed(
    product_id: str,
    product_name: str,
    previous_price: float,
    new_price: float,
    source: str = "pricing-service",
) -> Event:
    """
    Create a PriceChanged event.
    
    This is the key event for the "Price Drop Alert" scenario.
    
    Note: We include product_name so notification service doesn't need
    to look it up. We also include both prices so subscribers can
    determine if this is a price increase or decrease.
    """
    return Event(
        event_type=EventTypes.PRICE_CHANGED,
        source=source,
        payload={
            "product_id": product_id,
            "product_name": product_name,
            "previous_price": previous_price,
            "new_price": new_price,
            "price_difference": new_price - previous_price,
            "is_decrease": new_price < previous_price,
        },
    )


# =============================================================================
# Promotion Events
# =============================================================================

def promotion_activated(
    promotion_id: str,
    promotion_name: str,
    description: str,
    promo_code: Optional[str],
    eligible_segments: list[str],
    end_date: str,
    source: str = "promotions-service",
) -> Event:
    """
    Create a PromotionActivated event.
    
    Published when a new promotion becomes active.
    """
    return Event(
        event_type=EventTypes.PROMOTION_ACTIVATED,
        source=source,
        payload={
            "promotion_id": promotion_id,
            "promotion_name": promotion_name,
            "description": description,
            "promo_code": promo_code,
            "eligible_segments": eligible_segments,
            "end_date": end_date,
        },
    )
