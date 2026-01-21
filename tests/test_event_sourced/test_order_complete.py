"""
Tests for the Order Complete complex scenario.

This tests event aggregation:
- Multi-item order ships in separate shipments
- Track state across multiple events
- Only notify when ALL items have shipped
"""

import pytest
from event_sourced.event_bus import reset_event_bus
from event_sourced.event_correlator import EventCorrelator, reset_event_correlator
from event_sourced.notification_service import NotificationService
from event_sourced.services.ordering import OrderingService
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def setup_order_complete_services(data_store):
    """Set up services for order complete testing."""
    event_bus = reset_event_bus()
    correlator = reset_event_correlator()
    channels = NotificationChannels()
    
    notification_service = NotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
        correlator=correlator,
    )
    ordering_service = OrderingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    notification_service.start()
    
    yield {
        "notification_service": notification_service,
        "ordering_service": ordering_service,
        "channels": channels,
        "event_bus": event_bus,
        "correlator": correlator,
        "data_store": data_store,
    }
    
    notification_service.stop()


class TestOrderComplete:
    """Tests for the Order Complete scenario."""
    
    def test_no_notification_until_all_items_shipped(self, setup_order_complete_services):
        """
        Test that notification is NOT sent until all items ship.
        
        Order ord-001 has 2 items. Shipping the first should NOT trigger notification.
        """
        services = setup_order_complete_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Ship first item only
        ordering.ship_line_item("ord-001", "prod-001")
        
        # Should NOT have any notifications yet
        assert channels.get_total_sent_count() == 0
    
    def test_notification_sent_when_all_items_shipped(self, setup_order_complete_services):
        """
        Test that notification IS sent when all items have shipped.
        """
        services = setup_order_complete_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Ship both items
        ordering.ship_line_item("ord-001", "prod-001")
        ordering.ship_line_item("ord-001", "prod-002")
        
        # Now we should have the Order Complete notification
        # Alice (cust-001) has email+sms for order_updates
        assert channels.get_total_sent_count() == 2
        
        # Check it's the right notification
        email = channels.email.find_message_to("alice.johnson@example.com")
        assert email is not None
        assert "complete" in email.subject.lower() or "shipped" in email.subject.lower()
    
    def test_three_item_order(self, setup_order_complete_services):
        """
        Test with a 3-item order (ord-002).
        
        ord-002 has 3 items, one already shipped (prod-003).
        Need to ship prod-005 and prod-006 to complete.
        """
        services = setup_order_complete_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        correlator = services["correlator"]
        
        # Start tracking this order (first item already shipped in fixtures)
        # We need to register the already-shipped item
        correlator.process_line_item_shipped(
            order_id="ord-002",
            customer_id="cust-002",
            product_id="prod-003",
            total_items=3,
        )
        
        # No notification yet
        assert channels.get_total_sent_count() == 0
        
        # Ship second item
        ordering.ship_line_item("ord-002", "prod-005")
        assert channels.get_total_sent_count() == 0
        
        # Ship third (final) item
        ordering.ship_line_item("ord-002", "prod-006")
        
        # Now we should have notification
        # Bob (cust-002) has only email for order_updates
        assert channels.email.get_sent_count() == 1
        assert channels.sms.get_sent_count() == 0
    
    def test_order_complete_notification_content(self, setup_order_complete_services):
        """Test that the Order Complete notification has correct content."""
        services = setup_order_complete_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Complete ord-001
        ordering.ship_line_item("ord-001", "prod-001")
        ordering.ship_line_item("ord-001", "prod-002")
        
        email = channels.email.find_message_to("alice.johnson@example.com")
        
        assert email is not None
        assert "ord-001" in email.subject
        assert "Alice" in email.body


class TestEventCorrelator:
    """Tests for the EventCorrelator itself."""
    
    def test_correlator_tracks_shipments(self):
        """Test that correlator correctly tracks shipment state."""
        correlator = EventCorrelator()
        
        # First shipment - not complete
        complete = correlator.process_line_item_shipped(
            order_id="test-order",
            customer_id="test-customer",
            product_id="item-1",
            total_items=2,
        )
        assert complete is False
        
        state = correlator.get_order_state("test-order")
        assert state is not None
        assert state.items_remaining == 1
        assert "item-1" in state.shipped_items
    
    def test_correlator_detects_completion(self):
        """Test that correlator detects when order is complete."""
        correlator = EventCorrelator()
        callbacks_received = []
        
        correlator.on_order_complete(
            lambda order_id, customer_id: callbacks_received.append((order_id, customer_id))
        )
        
        correlator.process_line_item_shipped("order-1", "cust-1", "item-1", 2)
        assert len(callbacks_received) == 0
        
        correlator.process_line_item_shipped("order-1", "cust-1", "item-2", 2)
        assert len(callbacks_received) == 1
        assert callbacks_received[0] == ("order-1", "cust-1")
    
    def test_correlator_cleans_up_completed_orders(self):
        """Test that correlator removes state for completed orders."""
        correlator = EventCorrelator()
        
        correlator.process_line_item_shipped("order-1", "cust-1", "item-1", 1)
        
        # State should be removed after completion
        assert correlator.get_order_state("order-1") is None
    
    def test_correlator_handles_duplicate_shipments(self):
        """Test that shipping the same item twice doesn't break things."""
        correlator = EventCorrelator()
        callbacks_received = []
        
        correlator.on_order_complete(lambda o, c: callbacks_received.append(o))
        
        # Ship item-1 twice
        correlator.process_line_item_shipped("order-1", "cust-1", "item-1", 2)
        correlator.process_line_item_shipped("order-1", "cust-1", "item-1", 2)
        
        # Still not complete (item-2 not shipped)
        assert len(callbacks_received) == 0
        
        state = correlator.get_order_state("order-1")
        assert len(state.shipped_items) == 1  # Set prevents duplicates
    
    def test_correlator_tracks_multiple_orders(self):
        """Test that correlator can track multiple orders simultaneously."""
        correlator = EventCorrelator()
        completed_orders = []
        
        correlator.on_order_complete(lambda o, c: completed_orders.append(o))
        
        # Start shipping for two orders
        correlator.process_line_item_shipped("order-A", "cust-1", "item-1", 2)
        correlator.process_line_item_shipped("order-B", "cust-2", "item-1", 2)
        
        # Complete order A
        correlator.process_line_item_shipped("order-A", "cust-1", "item-2", 2)
        assert completed_orders == ["order-A"]
        
        # Complete order B
        correlator.process_line_item_shipped("order-B", "cust-2", "item-2", 2)
        assert completed_orders == ["order-A", "order-B"]


class TestOrderingServiceLineItems:
    """Tests for the OrderingService line item functionality."""
    
    def test_ship_line_item_publishes_event(self, setup_order_complete_services):
        """Test that shipping a line item publishes the correct event."""
        services = setup_order_complete_services
        ordering = services["ordering_service"]
        event_bus = services["event_bus"]
        
        ordering.ship_line_item("ord-001", "prod-001")
        
        events = event_bus.get_event_log()
        assert len(events) == 1
        
        event = events[0]
        assert event.event_type == "LineItemStatusChanged"
        assert event.payload["order_id"] == "ord-001"
        assert event.payload["product_id"] == "prod-001"
        assert event.payload["new_status"] == "SHIPPED"
    
    def test_ship_nonexistent_item_fails(self, setup_order_complete_services):
        """Test that shipping a nonexistent item fails gracefully."""
        services = setup_order_complete_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        result = ordering.ship_line_item("ord-001", "nonexistent-product")
        
        assert result is False
        assert channels.get_total_sent_count() == 0


class TestEventAggregationDecoupling:
    """Tests demonstrating that event aggregation keeps services decoupled."""
    
    def test_ordering_service_doesnt_track_completion(self, data_store):
        """
        Verify that ordering service doesn't need to know about order completion logic.
        
        In API-driven approach, ordering would need to track all items
        and decide when to call the notification API.
        Here, it just publishes events for each item.
        """
        event_bus = reset_event_bus()
        ordering = OrderingService(event_bus=event_bus, data_store=data_store)
        
        # Ordering service just ships items - it doesn't care about "completion"
        ordering.ship_line_item("ord-001", "prod-001")
        
        # Check the event - it just reports what happened
        event = event_bus.get_event_log()[0]
        assert event.payload["new_status"] == "SHIPPED"
        
        # The event includes items_remaining for observers to use
        # but ordering service doesn't decide what to do with that info
        assert "items_remaining" in event.payload
