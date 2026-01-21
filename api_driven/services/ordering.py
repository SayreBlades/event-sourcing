"""
Ordering service simulator for the API-driven approach.

This service manages orders AND calls the notification API when
events occur that require customer notification.

Key insight for the demo:
- This service must KNOW when notifications should be sent
- This service must GATHER context data for notifications
- This service is MORE COMPLEX than the event-sourced version

Compare to event_sourced/services/ordering.py:
- Event-sourced: Just publishes events, doesn't know about notifications
- API-driven: Must call notification API with full context

Tradeoffs demonstrated:
- CON: Ordering service has notification logic mixed in
- CON: Ordering service depends on notification API
- CON: If notification rules change, ordering service must change
- PRO: Explicit control over when notifications are sent
- PRO: Can see notification logic in the same place as business logic
"""

import logging
from typing import Optional

from api_driven.notification_api import NotificationAPI
from api_driven.models import NotificationRequest, NotificationType
from shared.data_store import DataStore, get_data_store
from shared.models import OrderStatus, LineItemStatus

logger = logging.getLogger("ordering_service_api")


class OrderingService:
    """
    Simulated ordering service that calls notification API.
    
    Unlike the event-sourced version, this service:
    1. Updates order state
    2. Determines if notification is needed
    3. Gathers context for the notification
    4. Calls the notification API
    
    Example:
        service = OrderingService(notification_api, data_store)
        
        # Ship an order - this calls the notification API
        service.ship_order("ord-001")
    """
    
    def __init__(
        self,
        notification_api: Optional[NotificationAPI] = None,
        data_store: Optional[DataStore] = None,
    ):
        """
        Initialize the ordering service.
        
        Note: This service DEPENDS on NotificationAPI.
        In event-sourced, OrderingService has no such dependency.
        """
        self.notification_api = notification_api or NotificationAPI()
        self.data_store = data_store or get_data_store()
        
        # For Order Complete tracking - this service must track state!
        # In event-sourced, the notification service handles this.
        self._order_shipment_state: dict[str, set[str]] = {}
    
    def ship_order(self, order_id: str) -> bool:
        """
        Mark an order as shipped and notify the customer.
        
        This demonstrates the API-driven pattern:
        1. Update business state
        2. Decide to send notification (business logic HERE)
        3. Gather context data
        4. Call notification API
        """
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return False
        
        if order.status == OrderStatus.SHIPPED:
            logger.warning(f"Order already shipped: {order_id}")
            return False
        
        # Step 1: Update business state
        updated_order = self.data_store.update_order_status(order_id, OrderStatus.SHIPPED)
        if not updated_order:
            return False
        
        logger.info(f"Order {order_id} shipped")
        
        # Step 2 & 3: Decide to notify and gather context
        # THIS IS THE KEY DIFFERENCE: We must know notification rules here
        
        # Build item list for the notification
        item_list = self._build_item_list(order)
        
        # Step 4: Call notification API
        request = NotificationRequest(
            notification_type=NotificationType.ORDER_SHIPPED,
            customer_id=order.customer_id,
            context={
                "order_id": order_id,
                "item_list": item_list,
            },
        )
        
        try:
            response = self.notification_api.send_notification(request)
            logger.info(f"Notification sent: {response.channels_sent} channels")
        except Exception as e:
            # Note: In API-driven, we must decide how to handle notification failures
            # Should we retry? Roll back the shipment? Just log?
            logger.error(f"Failed to send notification: {e}")
        
        return True
    
    def deliver_order(self, order_id: str) -> bool:
        """Mark an order as delivered and notify the customer."""
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return False
        
        updated_order = self.data_store.update_order_status(order_id, OrderStatus.DELIVERED)
        if not updated_order:
            return False
        
        logger.info(f"Order {order_id} delivered")
        
        request = NotificationRequest(
            notification_type=NotificationType.ORDER_DELIVERED,
            customer_id=order.customer_id,
            context={"order_id": order_id},
        )
        
        try:
            self.notification_api.send_notification(request)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
        
        return True
    
    def ship_line_item(self, order_id: str, product_id: str) -> bool:
        """
        Ship a specific line item within an order.
        
        For Order Complete scenario: Track shipments and send notification
        only when ALL items have shipped.
        
        KEY INSIGHT: In API-driven approach, THIS SERVICE must track
        shipment state and decide when to send "Order Complete" notification.
        In event-sourced, the notification service handles this via EventCorrelator.
        
        This adds significant complexity to the ordering service!
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
        
        # Update the line item status
        updated_order = self.data_store.update_line_item_status(
            order_id, product_id, LineItemStatus.SHIPPED
        )
        if not updated_order:
            return False
        
        logger.info(f"Line item {product_id} in order {order_id} shipped")
        
        # Track shipment state (THIS SERVICE must do this!)
        if order_id not in self._order_shipment_state:
            self._order_shipment_state[order_id] = set()
        
        self._order_shipment_state[order_id].add(product_id)
        
        # Check if all items shipped
        total_items = len(order.line_items)
        shipped_items = len(self._order_shipment_state[order_id])
        
        logger.info(f"Order {order_id}: {shipped_items}/{total_items} items shipped")
        
        if shipped_items >= total_items:
            # All items shipped! Send Order Complete notification
            logger.info(f"Order {order_id} complete - all items shipped!")
            
            item_list = self._build_item_list(order)
            
            request = NotificationRequest(
                notification_type=NotificationType.ORDER_COMPLETE,
                customer_id=order.customer_id,
                context={
                    "order_id": order_id,
                    "item_list": item_list,
                    "item_count": total_items,
                },
            )
            
            try:
                self.notification_api.send_notification(request)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
            
            # Clean up state
            del self._order_shipment_state[order_id]
        
        return True
    
    def _build_item_list(self, order) -> str:
        """Build formatted item list for notifications."""
        from shared.templates import format_item_list
        
        items = []
        for item in order.line_items:
            product = self.data_store.get_product(item.product_id)
            if product:
                items.append({
                    "name": product.name,
                    "quantity": item.quantity,
                    "price": item.unit_price,
                })
        
        return format_item_list(items)
