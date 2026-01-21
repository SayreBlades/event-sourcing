"""
Demonstration scripts for the event-sourced approach.

These functions show the event-sourced notification system in action.
Run them to see events being published and notifications being sent.
"""

import logging
from event_sourced.event_bus import reset_event_bus
from event_sourced.notification_service import NotificationService
from event_sourced.services.ordering import OrderingService
from shared.data_store import DataStore
from shared.channels import NotificationChannels

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)


def run_order_shipped_demo():
    """
    Demonstrate the simple "Order Shipped" notification scenario.
    
    This shows:
    1. OrderingService ships an order (publishes event)
    2. NotificationService receives the event
    3. NotificationService looks up customer and preferences
    4. NotificationService sends email/SMS
    
    The key insight: OrderingService doesn't know about notifications!
    """
    print("\n" + "=" * 70)
    print("EVENT-SOURCED DEMO: Order Shipped Notification")
    print("=" * 70 + "\n")
    
    # Reset to clean state
    event_bus = reset_event_bus()
    data_store = DataStore()
    channels = NotificationChannels()
    
    # Create services
    notification_service = NotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
    )
    ordering_service = OrderingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    # Start the notification service (subscribes to events)
    notification_service.start()
    
    print("Setup complete. NotificationService is listening for events.\n")
    print("-" * 70)
    print("ACTION: Shipping order ord-001 (Alice's order with 2 items)")
    print("-" * 70 + "\n")
    
    # Ship the order - this publishes an event
    # The notification service will automatically receive it and send notifications
    ordering_service.ship_order("ord-001")
    
    print("\n" + "-" * 70)
    print("RESULT: Check the logs above to see:")
    print("  1. OrderingService published OrderStatusChanged event")
    print("  2. NotificationService received and processed the event")
    print("  3. Email and SMS notifications were sent to Alice")
    print("-" * 70)
    
    # Show what was sent
    print("\nNotifications sent:")
    for msg in channels.get_all_sent_messages():
        print(f"  {msg}")
    
    # Cleanup
    notification_service.stop()
    
    return channels.get_all_sent_messages()


def run_order_delivered_demo():
    """
    Demonstrate the "Order Delivered" notification scenario.
    """
    print("\n" + "=" * 70)
    print("EVENT-SOURCED DEMO: Order Delivered Notification")
    print("=" * 70 + "\n")
    
    event_bus = reset_event_bus()
    data_store = DataStore()
    channels = NotificationChannels()
    
    notification_service = NotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
    )
    ordering_service = OrderingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    notification_service.start()
    
    # First ship, then deliver
    print("Shipping order ord-003 (Carol's single-item order)...")
    ordering_service.ship_order("ord-003")
    
    print("\nDelivering order ord-003...")
    ordering_service.deliver_order("ord-003")
    
    print("\nNotifications sent:")
    for msg in channels.get_all_sent_messages():
        print(f"  {msg}")
    
    notification_service.stop()
    return channels.get_all_sent_messages()


def run_payment_failed_demo():
    """
    Demonstrate the "Payment Failed" notification scenario.
    
    This shows the medium-complexity scenario where we need to include
    contextual information (failure reason) in the notification.
    """
    print("\n" + "=" * 70)
    print("EVENT-SOURCED DEMO: Payment Failed Notification")
    print("=" * 70 + "\n")
    
    from event_sourced.events import payment_failed
    
    event_bus = reset_event_bus()
    data_store = DataStore()
    channels = NotificationChannels()
    
    notification_service = NotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
    )
    
    notification_service.start()
    
    print("Simulating payment failure for David's order...")
    print("-" * 70 + "\n")
    
    # Simulate a payment service publishing a failure event
    event = payment_failed(
        payment_id="pay-006",
        order_id="ord-004",
        customer_id="cust-004",  # David
        amount=149.99,
        failure_reason="Card declined - insufficient funds",
        attempt_number=1,
    )
    event_bus.publish(event)
    
    print("\nNotifications sent:")
    for msg in channels.get_all_sent_messages():
        print(f"  {msg}")
    
    notification_service.stop()
    return channels.get_all_sent_messages()


if __name__ == "__main__":
    print("\nRunning Event-Sourced Notification Demos")
    print("=" * 70)
    
    run_order_shipped_demo()
    print("\n")
    
    run_payment_failed_demo()
