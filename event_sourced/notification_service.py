"""
Notification service for the event-sourced approach.

This service subscribes to domain events and determines when and how to send
notifications to customers. It encapsulates all notification logic in one place.

Design decisions:
- Single service handles all notification logic (centralized)
- Subscribes to events, doesn't poll or get called directly
- Looks up customer data and preferences when handling events
- Uses templates to format messages
- Sends via configured channels (email, SMS)

Key insight for the demo:
- All "when to notify" logic is HERE, not in the publishing services
- Adding a new notification type = adding a new event handler here
- The ordering/pricing/etc services just publish events, they don't know
  that notifications will be sent

Tradeoffs demonstrated:
- PRO: Centralized logic, easy to understand and modify
- PRO: Publishing services are simple, just emit events
- CON: This service must understand all event types
- CON: Complex scenarios require event correlation (see event_correlator.py)
"""

import logging
from typing import Optional

from event_sourced.event_bus import Event, EventBus, get_event_bus
from event_sourced.events import EventTypes
from shared.channels import NotificationChannels
from shared.data_store import DataStore, get_data_store
from shared.templates import (
    NotificationType,
    render_notification,
    format_item_list,
)

logger = logging.getLogger("notification_service")


class NotificationService:
    """
    Event-driven notification service.
    
    Subscribes to domain events and sends appropriate notifications
    based on customer preferences.
    
    Example:
        # Create and start the service
        service = NotificationService()
        service.start()
        
        # Now when events are published, notifications are sent automatically
        bus = get_event_bus()
        bus.publish(order_status_changed(...))  # Triggers notification
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        data_store: Optional[DataStore] = None,
        channels: Optional[NotificationChannels] = None,
    ):
        """
        Initialize the notification service.
        
        Args:
            event_bus: Event bus to subscribe to (defaults to singleton)
            data_store: Data store for customer/order lookups (defaults to singleton)
            channels: Notification channels for sending (defaults to new instance)
        """
        self.event_bus = event_bus or get_event_bus()
        self.data_store = data_store or get_data_store()
        self.channels = channels or NotificationChannels()
        
        # Track if we've subscribed
        self._started = False
    
    def start(self) -> None:
        """
        Start the notification service by subscribing to events.
        
        This registers handlers for all event types we care about.
        """
        if self._started:
            logger.warning("NotificationService already started")
            return
        
        # Subscribe to order events
        self.event_bus.subscribe(
            EventTypes.ORDER_STATUS_CHANGED,
            self._handle_order_status_changed,
        )
        
        # Subscribe to payment events
        self.event_bus.subscribe(
            EventTypes.PAYMENT_FAILED,
            self._handle_payment_failed,
        )
        
        self._started = True
        logger.info("NotificationService started - subscribed to events")
    
    def stop(self) -> None:
        """Stop the service by unsubscribing from events."""
        if not self._started:
            return
        
        self.event_bus.unsubscribe(
            EventTypes.ORDER_STATUS_CHANGED,
            self._handle_order_status_changed,
        )
        self.event_bus.unsubscribe(
            EventTypes.PAYMENT_FAILED,
            self._handle_payment_failed,
        )
        
        self._started = False
        logger.info("NotificationService stopped")
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def _handle_order_status_changed(self, event: Event) -> None:
        """
        Handle OrderStatusChanged events.
        
        This implements the simple "Order Shipped" notification scenario.
        When an order status changes to SHIPPED, we notify the customer.
        """
        payload = event.payload
        order_id = payload["order_id"]
        customer_id = payload["customer_id"]
        new_status = payload["new_status"]
        
        logger.info(f"Handling OrderStatusChanged: order={order_id}, status={new_status}")
        
        # Only notify for certain status changes
        if new_status == "SHIPPED":
            self._send_order_shipped_notification(order_id, customer_id)
        elif new_status == "DELIVERED":
            self._send_order_delivered_notification(order_id, customer_id)
    
    def _handle_payment_failed(self, event: Event) -> None:
        """
        Handle PaymentFailed events.
        
        This implements the "Payment Failed" notification scenario.
        """
        payload = event.payload
        payment_id = payload["payment_id"]
        order_id = payload["order_id"]
        customer_id = payload["customer_id"]
        amount = payload["amount"]
        failure_reason = payload["failure_reason"]
        
        logger.info(f"Handling PaymentFailed: payment={payment_id}, order={order_id}")
        
        self._send_payment_failed_notification(
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            failure_reason=failure_reason,
        )
    
    # =========================================================================
    # Notification Sending Logic
    # =========================================================================
    
    def _send_order_shipped_notification(self, order_id: str, customer_id: str) -> None:
        """
        Send "Order Shipped" notification to customer.
        
        This demonstrates the full notification flow:
        1. Look up customer contact info
        2. Look up customer notification preferences
        3. Look up order details for the message
        4. Render the appropriate template
        5. Send via preferred channels
        """
        # Step 1 & 2: Get customer and preferences
        customer = self.data_store.get_customer(customer_id)
        prefs = self.data_store.get_notification_preferences(customer_id)
        
        if not customer:
            logger.error(f"Customer not found: {customer_id}")
            return
        
        # Step 3: Get order details for the message
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return
        
        # Build item list for the email
        item_list_data = []
        for item in order.line_items:
            product = self.data_store.get_product(item.product_id)
            if product:
                item_list_data.append({
                    "name": product.name,
                    "quantity": item.quantity,
                    "price": item.unit_price,
                })
        
        # Step 4: Determine which channels to use
        # Default to email if no preferences found
        channels_to_use = ["email"]
        if prefs:
            channels_to_use = prefs.get_channels_for_type("order_updates")
        
        if not channels_to_use:
            logger.info(f"Customer {customer_id} has disabled order_updates notifications")
            return
        
        # Step 5: Send via each enabled channel
        for channel in channels_to_use:
            try:
                subject, body = render_notification(
                    NotificationType.ORDER_SHIPPED,
                    channel=channel,
                    customer_name=customer.name,
                    order_id=order_id,
                    item_list=format_item_list(item_list_data),
                )
                
                if channel == "email":
                    self.channels.send_email(customer.email, subject, body)
                elif channel == "sms":
                    self.channels.send_sms(customer.phone, body)
                    
                logger.info(f"Sent ORDER_SHIPPED notification via {channel} to {customer_id}")
                
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")
    
    def _send_order_delivered_notification(self, order_id: str, customer_id: str) -> None:
        """Send "Order Delivered" notification to customer."""
        customer = self.data_store.get_customer(customer_id)
        prefs = self.data_store.get_notification_preferences(customer_id)
        
        if not customer:
            logger.error(f"Customer not found: {customer_id}")
            return
        
        channels_to_use = ["email"]
        if prefs:
            channels_to_use = prefs.get_channels_for_type("order_updates")
        
        if not channels_to_use:
            return
        
        for channel in channels_to_use:
            try:
                subject, body = render_notification(
                    NotificationType.ORDER_DELIVERED,
                    channel=channel,
                    customer_name=customer.name,
                    order_id=order_id,
                )
                
                if channel == "email":
                    self.channels.send_email(customer.email, subject, body)
                elif channel == "sms":
                    self.channels.send_sms(customer.phone, body)
                    
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")
    
    def _send_payment_failed_notification(
        self,
        order_id: str,
        customer_id: str,
        amount: float,
        failure_reason: str,
    ) -> None:
        """
        Send "Payment Failed" notification to customer.
        
        This demonstrates the medium-complexity scenario where we need to:
        - Look up customer info
        - Check notification preferences
        - Include contextual information (failure reason)
        """
        customer = self.data_store.get_customer(customer_id)
        prefs = self.data_store.get_notification_preferences(customer_id)
        
        if not customer:
            logger.error(f"Customer not found: {customer_id}")
            return
        
        # Payment alerts typically go through all enabled channels
        channels_to_use = ["email"]
        if prefs:
            channels_to_use = prefs.get_channels_for_type("payment_alerts")
        
        if not channels_to_use:
            logger.info(f"Customer {customer_id} has disabled payment_alerts notifications")
            return
        
        for channel in channels_to_use:
            try:
                subject, body = render_notification(
                    NotificationType.PAYMENT_FAILED,
                    channel=channel,
                    customer_name=customer.name,
                    order_id=order_id,
                    amount=amount,
                    failure_reason=failure_reason,
                )
                
                if channel == "email":
                    self.channels.send_email(customer.email, subject, body)
                elif channel == "sms":
                    self.channels.send_sms(customer.phone, body)
                    
                logger.info(f"Sent PAYMENT_FAILED notification via {channel} to {customer_id}")
                
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")
