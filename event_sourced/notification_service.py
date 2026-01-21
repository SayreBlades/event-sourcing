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
from event_sourced.event_correlator import EventCorrelator, get_event_correlator
from shared.channels import NotificationChannels
from shared.data_store import DataStore, get_data_store
from shared.templates import (
    NotificationType,
    render_notification,
    format_item_list,
)

logger = logging.getLogger("notification_service")


# Segments eligible for price drop alerts (business rule)
PRICE_ALERT_ELIGIBLE_SEGMENTS = {"gold", "platinum"}


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
        correlator: Optional[EventCorrelator] = None,
    ):
        """
        Initialize the notification service.
        
        Args:
            event_bus: Event bus to subscribe to (defaults to singleton)
            data_store: Data store for customer/order lookups (defaults to singleton)
            channels: Notification channels for sending (defaults to new instance)
            correlator: Event correlator for complex scenarios (defaults to singleton)
        """
        self.event_bus = event_bus or get_event_bus()
        self.data_store = data_store or get_data_store()
        self.channels = channels or NotificationChannels()
        self.correlator = correlator or get_event_correlator()
        
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
        
        # Subscribe to line item events (for Order Complete scenario)
        self.event_bus.subscribe(
            EventTypes.LINE_ITEM_STATUS_CHANGED,
            self._handle_line_item_status_changed,
        )
        
        # Subscribe to payment events
        self.event_bus.subscribe(
            EventTypes.PAYMENT_FAILED,
            self._handle_payment_failed,
        )
        
        # Subscribe to price events (for Price Drop Alert scenario)
        self.event_bus.subscribe(
            EventTypes.PRICE_CHANGED,
            self._handle_price_changed,
        )
        
        # Register callback for order complete (from correlator)
        self.correlator.on_order_complete(self._send_order_complete_notification)
        
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
            EventTypes.LINE_ITEM_STATUS_CHANGED,
            self._handle_line_item_status_changed,
        )
        self.event_bus.unsubscribe(
            EventTypes.PAYMENT_FAILED,
            self._handle_payment_failed,
        )
        self.event_bus.unsubscribe(
            EventTypes.PRICE_CHANGED,
            self._handle_price_changed,
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
    
    def _handle_line_item_status_changed(self, event: Event) -> None:
        """
        Handle LineItemStatusChanged events.
        
        This is part of the "Order Complete" scenario. We use the event
        correlator to track shipments across multiple items. When all
        items have shipped, the correlator triggers the notification.
        """
        payload = event.payload
        order_id = payload["order_id"]
        customer_id = payload["customer_id"]
        product_id = payload["product_id"]
        new_status = payload["new_status"]
        
        # Only track SHIPPED status
        if new_status not in ("SHIPPED", "LineItemStatus.SHIPPED"):
            return
        
        logger.info(f"Handling LineItemStatusChanged: order={order_id}, product={product_id}")
        
        # Get the order to know total item count
        order = self.data_store.get_order(order_id)
        if not order:
            logger.error(f"Order not found: {order_id}")
            return
        
        # Let the correlator track this shipment
        # It will call _send_order_complete_notification when all items ship
        self.correlator.process_line_item_shipped(
            order_id=order_id,
            customer_id=customer_id,
            product_id=product_id,
            total_items=len(order.line_items),
        )
    
    def _handle_price_changed(self, event: Event) -> None:
        """
        Handle PriceChanged events.
        
        This implements the complex "Price Drop Alert" scenario:
        1. Check if this is a price DECREASE (not increase)
        2. Find all customers who have this product in their cart
        3. Filter to customers who have opted into price alerts
        4. Filter to customers in eligible segments
        5. Send notifications to remaining customers
        
        This demonstrates the power of centralized notification logic:
        - The pricing service just publishes "price changed"
        - All the complex eligibility logic is HERE
        """
        payload = event.payload
        product_id = payload["product_id"]
        product_name = payload["product_name"]
        previous_price = payload["previous_price"]
        new_price = payload["new_price"]
        is_decrease = payload["is_decrease"]
        
        logger.info(f"Handling PriceChanged: {product_name} ${previous_price} -> ${new_price}")
        
        # Only notify on price DECREASES
        if not is_decrease:
            logger.info("Price increased, no notification needed")
            return
        
        self._send_price_drop_notifications(
            product_id=product_id,
            product_name=product_name,
            previous_price=previous_price,
            new_price=new_price,
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
    
    def _send_price_drop_notifications(
        self,
        product_id: str,
        product_name: str,
        previous_price: float,
        new_price: float,
    ) -> None:
        """
        Send "Price Drop Alert" notifications to eligible customers.
        
        This is the COMPLEX scenario demonstrating centralized notification logic:
        
        1. Find all carts containing this product
        2. For each customer with this product in cart:
           a. Check if they've opted into price alerts
           b. Check if they're in an eligible segment
           c. If both pass, send notification
        
        Key insight: The pricing service just published "price changed".
        All this complex logic is handled HERE in the notification service.
        In the API-driven approach, the pricing service would need to do all this!
        """
        savings = previous_price - new_price
        discount_percent = (savings / previous_price) * 100
        
        # Step 1: Find carts containing this product
        carts = self.data_store.get_carts_containing_product(product_id)
        
        logger.info(f"Found {len(carts)} carts containing {product_name}")
        
        notifications_sent = 0
        customers_skipped_prefs = 0
        customers_skipped_segment = 0
        
        for cart in carts:
            customer_id = cart.customer_id
            
            # Get customer info and preferences
            customer = self.data_store.get_customer(customer_id)
            prefs = self.data_store.get_notification_preferences(customer_id)
            
            if not customer:
                continue
            
            # Step 2a: Check if they've opted into price alerts
            channels_to_use = []
            if prefs:
                channels_to_use = prefs.get_channels_for_type("price_alerts")
            
            if not channels_to_use:
                logger.debug(f"Customer {customer_id} has not opted into price alerts")
                customers_skipped_prefs += 1
                continue
            
            # Step 2b: Check if they're in an eligible segment
            if customer.segment not in PRICE_ALERT_ELIGIBLE_SEGMENTS:
                logger.debug(
                    f"Customer {customer_id} segment '{customer.segment}' "
                    f"not in eligible segments {PRICE_ALERT_ELIGIBLE_SEGMENTS}"
                )
                customers_skipped_segment += 1
                continue
            
            # Step 2c: Send notification via enabled channels
            for channel in channels_to_use:
                try:
                    subject, body = render_notification(
                        NotificationType.PRICE_DROP_ALERT,
                        channel=channel,
                        customer_name=customer.name,
                        product_name=product_name,
                        old_price=previous_price,
                        new_price=new_price,
                        savings=savings,
                        discount_percent=discount_percent,
                    )
                    
                    if channel == "email":
                        self.channels.send_email(customer.email, subject, body)
                    elif channel == "sms":
                        self.channels.send_sms(customer.phone, body)
                    
                    notifications_sent += 1
                    logger.info(f"Sent PRICE_DROP_ALERT via {channel} to {customer_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send {channel} notification: {e}")
        
        logger.info(
            f"Price drop notifications complete: "
            f"{notifications_sent} sent, "
            f"{customers_skipped_prefs} skipped (prefs), "
            f"{customers_skipped_segment} skipped (segment)"
        )
    
    def _send_order_complete_notification(self, order_id: str, customer_id: str) -> None:
        """
        Send "Order Complete" notification when all items have shipped.
        
        This is called by the EventCorrelator when it detects that all
        line items in an order have been shipped.
        
        This is the COMPLEX scenario demonstrating event aggregation:
        - Multiple LineItemStatusChanged events come in over time
        - The correlator tracks them
        - Only when ALL items are shipped do we send this notification
        """
        customer = self.data_store.get_customer(customer_id)
        prefs = self.data_store.get_notification_preferences(customer_id)
        order = self.data_store.get_order(order_id)
        
        if not customer or not order:
            logger.error(f"Customer or order not found: {customer_id}, {order_id}")
            return
        
        # Build item list for the message
        item_list_data = []
        for item in order.line_items:
            product = self.data_store.get_product(item.product_id)
            if product:
                item_list_data.append({
                    "name": product.name,
                    "quantity": item.quantity,
                    "price": item.unit_price,
                })
        
        channels_to_use = ["email"]
        if prefs:
            channels_to_use = prefs.get_channels_for_type("order_updates")
        
        if not channels_to_use:
            return
        
        for channel in channels_to_use:
            try:
                subject, body = render_notification(
                    NotificationType.ORDER_COMPLETE,
                    channel=channel,
                    customer_name=customer.name,
                    order_id=order_id,
                    item_list=format_item_list(item_list_data),
                    item_count=len(order.line_items),
                )
                
                if channel == "email":
                    self.channels.send_email(customer.email, subject, body)
                elif channel == "sms":
                    self.channels.send_sms(customer.phone, body)
                
                logger.info(f"Sent ORDER_COMPLETE notification via {channel} to {customer_id}")
                
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")
