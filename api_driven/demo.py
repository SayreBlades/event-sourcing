"""
Demonstration scripts for the API-driven approach.

These functions show the API-driven notification system in action.
Compare to the event-sourced demos to see the difference in where
notification logic lives.
"""

import logging
from api_driven.notification_api import NotificationAPI
from api_driven.services.ordering import OrderingService
from shared.data_store import DataStore
from shared.channels import NotificationChannels

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)


def run_order_shipped_demo():
    """
    Demonstrate the simple "Order Shipped" notification scenario.
    
    Compare to event-sourced version:
    - Event-sourced: OrderingService publishes event, NotificationService handles it
    - API-driven: OrderingService calls NotificationAPI directly
    
    Notice: OrderingService must know about notifications here!
    """
    print("\n" + "=" * 70)
    print("API-DRIVEN DEMO: Order Shipped Notification")
    print("=" * 70 + "\n")
    
    # Set up services
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    ordering_service = OrderingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    print("Setup complete. OrderingService has NotificationAPI dependency.\n")
    print("-" * 70)
    print("ACTION: Shipping order ord-001 (Alice's order with 2 items)")
    print("-" * 70 + "\n")
    
    # Ship the order - this DIRECTLY calls the notification API
    ordering_service.ship_order("ord-001")
    
    print("\n" + "-" * 70)
    print("RESULT: Check the logs above to see:")
    print("  1. OrderingService updated order status")
    print("  2. OrderingService called NotificationAPI directly")
    print("  3. NotificationAPI sent notifications")
    print("")
    print("KEY DIFFERENCE from event-sourced:")
    print("  - OrderingService KNOWS it should send notifications")
    print("  - OrderingService BUILDS the notification context")
    print("  - No event bus, no decoupling")
    print("-" * 70)
    
    print("\nNotifications sent:")
    for msg in channels.get_all_sent_messages():
        print(f"  {msg}")
    
    return channels.get_all_sent_messages()


def run_order_complete_demo():
    """
    Demonstrate the "Order Complete" scenario in API-driven approach.
    
    KEY INSIGHT: In API-driven, the OrderingService must:
    - Track which items have shipped (state management)
    - Decide when to send "Order Complete" notification
    - Build the notification context
    
    Compare to event-sourced where EventCorrelator handles this.
    """
    print("\n" + "=" * 70)
    print("API-DRIVEN DEMO: Order Complete (Service Must Track State)")
    print("=" * 70 + "\n")
    
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    ordering_service = OrderingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    print("Setup complete. Order ord-001 has 2 items:")
    print("  - prod-001: Wireless Router X500")
    print("  - prod-002: USB-C Hub Pro")
    print("")
    print("KEY DIFFERENCE: OrderingService tracks shipment state internally!")
    print("")
    
    print("-" * 70)
    print("ACTION 1: Shipping first item (prod-001 - Router)")
    print("-" * 70 + "\n")
    
    ordering_service.ship_line_item("ord-001", "prod-001")
    
    print(f"\nNotifications so far: {channels.get_total_sent_count()}")
    print("(OrderingService is tracking state, waiting for more items)")
    
    print("\n" + "-" * 70)
    print("ACTION 2: Shipping second item (prod-002 - USB Hub)")
    print("-" * 70 + "\n")
    
    ordering_service.ship_line_item("ord-001", "prod-002")
    
    print("\n" + "-" * 70)
    print("RESULT:")
    print("-" * 70)
    print("\nOrderingService detected all items shipped and called API.")
    
    print("\nNotifications sent:")
    for msg in channels.get_all_sent_messages():
        print(f"  {msg}")
    
    print("\nKEY COMPLEXITY NOTE:")
    print("  The OrderingService had to implement shipment tracking logic.")
    print("  In event-sourced, this is handled by EventCorrelator in")
    print("  the notification service, keeping OrderingService simple.")
    
    return channels.get_all_sent_messages()


def run_price_drop_demo():
    """
    Demonstrate the complex "Price Drop Alert" scenario in API-driven approach.
    
    KEY INSIGHT: The PricingService must:
    1. Update the price (its core job)
    2. Query carts to find affected customers (CROSS-DOMAIN!)
    3. Query preferences to check opt-in (CROSS-DOMAIN!)
    4. Check segment eligibility (CROSS-DOMAIN!)
    5. Call notification API for each eligible customer
    
    Compare to event-sourced where PricingService just publishes "price changed"
    and ALL the eligibility logic is in the notification service.
    """
    from api_driven.services.pricing import PricingService
    
    print("\n" + "=" * 70)
    print("API-DRIVEN DEMO: Price Drop Alert (Shows Cross-Domain Complexity)")
    print("=" * 70 + "\n")
    
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    pricing_service = PricingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    print("Setup complete. The following customers have prod-001 (Router) in cart:")
    print("  - Bob (cust-002): silver segment")
    print("  - Carol (cust-003): platinum segment")
    print("  - Eva (cust-005): gold segment")
    print("")
    print("Eligible segments: gold, platinum")
    print("")
    print("KEY DIFFERENCE from event-sourced:")
    print("  PricingService must query carts, customers, and preferences!")
    print("  In event-sourced, it just publishes an event.")
    print("")
    
    print("-" * 70)
    print("ACTION: Dropping price of Router from $149.99 to $119.99")
    print("-" * 70 + "\n")
    
    pricing_service.update_price("prod-001", 119.99)
    
    print("\n" + "-" * 70)
    print("RESULT:")
    print("-" * 70)
    
    print("\nNotifications sent:")
    for msg in channels.get_all_sent_messages():
        print(f"  {msg}")
    
    # Verify
    sent_to = [msg.recipient for msg in channels.get_all_sent_messages()]
    print("\nVerification:")
    print(f"  Bob (silver) notified: {'bob.smith@example.com' in sent_to}")
    print(f"  Carol (platinum) notified: {'carol.williams@example.com' in sent_to}")
    print(f"  Eva (gold) notified: {'eva.martinez@example.com' in sent_to}")
    
    print("\nCOMPLEXITY NOTE:")
    print("  PricingService had to import and query:")
    print("    - Cart data (to find who has the product)")
    print("    - Customer data (to check segments)")
    print("    - Preference data (to check opt-in)")
    print("  This creates tight coupling between pricing and other domains.")
    
    return channels.get_all_sent_messages()


if __name__ == "__main__":
    print("\nRunning API-Driven Notification Demos")
    print("=" * 70)
    
    run_order_shipped_demo()
    print("\n")
    
    run_order_complete_demo()
    print("\n")
    
    run_price_drop_demo()
