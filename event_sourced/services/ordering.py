"""
Ordering service simulator for the event-sourced approach.

This service manages orders and publishes events when order state changes.
It represents what a real order management system (like TMF622) would do.

Key insight for the demo:
- This service ONLY publishes events
- It does NOT call the notification service
- It doesn't even know the notification service exists
- This is the decoupling that event-sourcing provides
"""

import logging
from typing import Optional

from event_sourced.event_bus import Event, EventBus, get_event_bus
from event_sourced.events import (
    order_status_changed,
    line_item_status_changed,
    order_created,
)
from shared.data_store import DataStore, get_data_store
from shared.models import OrderStatus, LineItemStatus

logger = logging.getLogger("ordering_service")


class OrderingService:
    """
    Simulated ordering service that publishes events.
    
    In a real system, this would be a separate microservice with its own
    database. Here we simulate it by updating the shared data store and
    publishing events.
    
    Example:
        service = OrderingService()
        
        # Ship an order - this publishes an event
        service.ship_order("ord-001")
        
        # The notification service (if subscribed) will receive the event
        # and send a notification - but this service doesn't know about that!
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        data_store: Optional[DataStore] = None,
    ):
        """
        Initialize the ordering service.
        
        Args:
            event_bus: Event bus for publishing events
            data_store: Data store for order data
        """
        self.event_bus = event_bus or get_event_bus()
        self.data_store = data_store or get_data_store()
    
    def ship_order(self, order_id: str) -> bool:
        """
        Mark an order as shipped and publish an event.
        
        This is the simple scenario: one action, one event, one notification.
        
        Args:
            order_id: The order to ship
        
        Returns:
            True if successful, False if order not found or already shipped
        """
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return False
        
        if order.status == OrderStatus.SHIPPED:
            logger.warning(f"Order already shipped: {order_id}")
            return False
        
        previous_status = order.status
        
        # Update the order status
        updated_order = self.data_store.update_order_status(order_id, OrderStatus.SHIPPED)
        if not updated_order:
            return False
        
        logger.info(f"Order {order_id} shipped: {previous_status} -> SHIPPED")
        
        # Publish the event - this is the key action!
        # The notification service will receive this and send a notification
        event = order_status_changed(
            order_id=order_id,
            customer_id=order.customer_id,
            previous_status=previous_status,
            new_status=OrderStatus.SHIPPED,
        )
        self.event_bus.publish(event)
        
        return True
    
    def deliver_order(self, order_id: str) -> bool:
        """
        Mark an order as delivered and publish an event.
        
        Args:
            order_id: The order to mark as delivered
        
        Returns:
            True if successful, False otherwise
        """
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return False
        
        previous_status = order.status
        
        updated_order = self.data_store.update_order_status(order_id, OrderStatus.DELIVERED)
        if not updated_order:
            return False
        
        logger.info(f"Order {order_id} delivered: {previous_status} -> DELIVERED")
        
        event = order_status_changed(
            order_id=order_id,
            customer_id=order.customer_id,
            previous_status=previous_status,
            new_status=OrderStatus.DELIVERED,
        )
        self.event_bus.publish(event)
        
        return True
    
    def ship_line_item(self, order_id: str, product_id: str) -> bool:
        """
        Ship a specific line item within an order.
        
        This is for the "Order Complete" scenario where items ship separately.
        We publish a LineItemStatusChanged event, which includes how many
        items are still pending. When items_remaining hits 0, the notification
        service knows to send the "all items shipped" notification.
        
        Args:
            order_id: The order containing the item
            product_id: The product/line item to ship
        
        Returns:
            True if successful, False otherwise
        """
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return False
        
        # Find the line item
        line_item = None
        for item in order.line_items:
            if item.product_id == product_id:
                line_item = item
                break
        
        if not line_item:
            logger.error(f"Line item not found: {product_id} in order {order_id}")
            return False
        
        previous_status = line_item.status
        
        # Update the line item status
        updated_order = self.data_store.update_line_item_status(
            order_id, product_id, LineItemStatus.SHIPPED
        )
        if not updated_order:
            return False
        
        # Calculate how many items are still not shipped
        items_remaining = updated_order.get_pending_items_count()
        
        logger.info(
            f"Line item {product_id} in order {order_id} shipped. "
            f"Items remaining: {items_remaining}"
        )
        
        # Publish the event
        event = line_item_status_changed(
            order_id=order_id,
            customer_id=order.customer_id,
            product_id=product_id,
            previous_status=previous_status,
            new_status=LineItemStatus.SHIPPED,
            items_remaining=items_remaining,
        )
        self.event_bus.publish(event)
        
        return True
