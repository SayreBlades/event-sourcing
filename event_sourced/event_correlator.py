"""
Event correlator for complex multi-event scenarios.

This module handles scenarios that require tracking state across multiple events:
- Order Complete: Track shipments until all items in an order have shipped
- Other potential uses: Fraud detection, SLA monitoring, etc.

Design decisions:
- In-memory state tracking (would be Redis/database in production)
- Time-based expiration for stale correlation state
- Supports multiple correlation strategies

Key insight for the demo:
- Simple events (Order Shipped) are 1:1 with notifications
- Complex events require maintaining state and correlating multiple events
- This adds complexity to the notification service, but keeps it centralized
- The alternative (API-driven) would push this complexity to the calling services
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional
from collections import defaultdict

from event_sourced.event_bus import Event

logger = logging.getLogger("event_correlator")


@dataclass
class OrderShipmentState:
    """
    Tracks the shipment state of a multi-item order.
    
    Used for the "Order Complete" scenario where we only want to send
    a notification when ALL items have shipped, not for each individual item.
    """
    order_id: str
    customer_id: str
    total_items: int
    shipped_items: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def items_remaining(self) -> int:
        """Number of items still waiting to ship."""
        return self.total_items - len(self.shipped_items)
    
    @property
    def is_complete(self) -> bool:
        """True if all items have shipped."""
        return len(self.shipped_items) >= self.total_items
    
    def mark_shipped(self, product_id: str) -> bool:
        """
        Mark a product as shipped.
        
        Returns True if this was the last item (order is now complete).
        """
        self.shipped_items.add(product_id)
        self.last_updated = datetime.utcnow()
        return self.is_complete


class EventCorrelator:
    """
    Correlates multiple events to detect complex conditions.
    
    Currently supports:
    - Order Complete: Detects when all items in an order have shipped
    
    Example usage:
        correlator = EventCorrelator()
        
        # Register callback for when order is complete
        correlator.on_order_complete(lambda order_id, customer_id: 
            send_order_complete_notification(order_id, customer_id)
        )
        
        # Process line item shipment events
        correlator.process_line_item_shipped(event)
    """
    
    def __init__(self, state_ttl_hours: int = 72):
        """
        Initialize the correlator.
        
        Args:
            state_ttl_hours: How long to keep correlation state before expiring
        """
        self.state_ttl = timedelta(hours=state_ttl_hours)
        
        # Track order shipment state: order_id -> OrderShipmentState
        self._order_states: dict[str, OrderShipmentState] = {}
        
        # Callbacks for when conditions are met
        self._order_complete_callbacks: list[Callable[[str, str], None]] = []
    
    def on_order_complete(self, callback: Callable[[str, str], None]) -> None:
        """
        Register a callback for when an order is fully shipped.
        
        The callback receives (order_id, customer_id).
        """
        self._order_complete_callbacks.append(callback)
    
    def process_line_item_shipped(
        self,
        order_id: str,
        customer_id: str,
        product_id: str,
        total_items: int,
    ) -> bool:
        """
        Process a line item shipment event.
        
        Tracks the shipment and triggers callbacks if the order is now complete.
        
        Args:
            order_id: The order containing the item
            customer_id: The customer who placed the order
            product_id: The product that shipped
            total_items: Total number of items in the order
        
        Returns:
            True if this completed the order, False otherwise
        """
        # Get or create order state
        if order_id not in self._order_states:
            self._order_states[order_id] = OrderShipmentState(
                order_id=order_id,
                customer_id=customer_id,
                total_items=total_items,
            )
        
        state = self._order_states[order_id]
        
        # Mark this item as shipped
        is_complete = state.mark_shipped(product_id)
        
        logger.info(
            f"Order {order_id}: item {product_id} shipped. "
            f"{len(state.shipped_items)}/{state.total_items} items shipped."
        )
        
        if is_complete:
            logger.info(f"Order {order_id} is now COMPLETE - all items shipped!")
            
            # Trigger callbacks
            for callback in self._order_complete_callbacks:
                try:
                    callback(order_id, customer_id)
                except Exception as e:
                    logger.error(f"Order complete callback failed: {e}")
            
            # Clean up state
            del self._order_states[order_id]
        
        return is_complete
    
    def get_order_state(self, order_id: str) -> Optional[OrderShipmentState]:
        """Get the current shipment state for an order."""
        return self._order_states.get(order_id)
    
    def cleanup_expired_state(self) -> int:
        """
        Remove stale correlation state.
        
        Returns the number of states removed.
        """
        now = datetime.utcnow()
        expired = []
        
        for order_id, state in self._order_states.items():
            if now - state.created_at > self.state_ttl:
                expired.append(order_id)
        
        for order_id in expired:
            logger.warning(f"Expiring stale order state: {order_id}")
            del self._order_states[order_id]
        
        return len(expired)
    
    def clear_state(self) -> None:
        """Clear all correlation state (useful for testing)."""
        self._order_states.clear()


# Singleton instance
_correlator: Optional[EventCorrelator] = None


def get_event_correlator() -> EventCorrelator:
    """Get the default event correlator singleton."""
    global _correlator
    if _correlator is None:
        _correlator = EventCorrelator()
    return _correlator


def reset_event_correlator() -> EventCorrelator:
    """Reset the event correlator (useful for testing)."""
    global _correlator
    _correlator = EventCorrelator()
    return _correlator
