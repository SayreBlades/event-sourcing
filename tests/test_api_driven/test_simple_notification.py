"""
Tests for simple notification scenarios in the API-driven approach.

These tests verify the Order Shipped notification flow and compare
the implementation to the event-sourced approach.
"""

import pytest
from api_driven.notification_api import NotificationAPI
from api_driven.services.ordering import OrderingService
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def setup_api_services(data_store):
    """Set up services for API-driven testing."""
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    ordering_service = OrderingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    return {
        "notification_api": notification_api,
        "ordering_service": ordering_service,
        "channels": channels,
        "data_store": data_store,
    }


class TestOrderShippedNotification:
    """Tests for Order Shipped notification via API."""
    
    def test_shipping_order_sends_notification(self, setup_api_services):
        """Test that shipping an order calls the notification API."""
        services = setup_api_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        result = ordering.ship_order("ord-001")
        
        assert result is True
        
        # Alice has email + sms enabled
        assert channels.get_total_sent_count() == 2
        
        email = channels.email.find_message_to("alice.johnson@example.com")
        assert email is not None
        assert "shipped" in email.subject.lower()
    
    def test_shipping_respects_preferences(self, setup_api_services):
        """Test that API respects customer notification preferences."""
        services = setup_api_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Ship Bob's order (cust-002) - he only has email for order_updates
        ordering.ship_order("ord-002")
        
        assert channels.email.get_sent_count() == 1
        assert channels.sms.get_sent_count() == 0
    
    def test_shipping_nonexistent_order(self, setup_api_services):
        """Test shipping a nonexistent order fails."""
        services = setup_api_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        result = ordering.ship_order("nonexistent")
        
        assert result is False
        assert channels.get_total_sent_count() == 0


class TestOrderDeliveredNotification:
    """Tests for Order Delivered notification."""
    
    def test_delivering_order_sends_notification(self, setup_api_services):
        """Test that delivering an order sends notification."""
        services = setup_api_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        result = ordering.deliver_order("ord-003")
        
        assert result is True
        
        # Carol has email + sms enabled
        assert channels.get_total_sent_count() == 2


class TestOrderCompleteNotification:
    """Tests for Order Complete notification (multi-item tracking)."""
    
    def test_no_notification_until_all_items_shipped(self, setup_api_services):
        """Test that notification waits for all items."""
        services = setup_api_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Ship first item only
        ordering.ship_line_item("ord-001", "prod-001")
        
        # No notification yet
        assert channels.get_total_sent_count() == 0
    
    def test_notification_when_all_items_shipped(self, setup_api_services):
        """Test that notification is sent when all items ship."""
        services = setup_api_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Ship both items
        ordering.ship_line_item("ord-001", "prod-001")
        ordering.ship_line_item("ord-001", "prod-002")
        
        # Now we should have notification
        assert channels.get_total_sent_count() == 2  # Email + SMS
        
        email = channels.email.find_message_to("alice.johnson@example.com")
        assert email is not None
        assert "complete" in email.subject.lower() or "shipped" in email.subject.lower()


class TestAPIVsEventSourcedComparison:
    """
    Tests that highlight differences between API and event-sourced approaches.
    """
    
    def test_ordering_service_has_notification_dependency(self, setup_api_services):
        """
        Verify that OrderingService depends on NotificationAPI.
        
        In event-sourced, OrderingService has no such dependency.
        """
        services = setup_api_services
        ordering = services["ordering_service"]
        
        # The ordering service has a notification_api attribute
        assert hasattr(ordering, "notification_api")
        assert ordering.notification_api is not None
    
    def test_ordering_service_tracks_shipment_state(self, setup_api_services):
        """
        Verify that OrderingService must track shipment state internally.
        
        In event-sourced, EventCorrelator in notification service handles this.
        """
        services = setup_api_services
        ordering = services["ordering_service"]
        
        # The ordering service has internal state for tracking
        assert hasattr(ordering, "_order_shipment_state")
        
        # Ship one item
        ordering.ship_line_item("ord-001", "prod-001")
        
        # State should be tracked
        assert "ord-001" in ordering._order_shipment_state
        assert "prod-001" in ordering._order_shipment_state["ord-001"]
    
    def test_notification_api_is_simpler(self, data_store):
        """
        Demonstrate that NotificationAPI is simpler than event-sourced NotificationService.
        
        - No event subscriptions
        - No event correlation
        - Just receives requests and sends notifications
        """
        channels = NotificationChannels()
        api = NotificationAPI(channels=channels, data_store=data_store)
        
        # The API doesn't have event-related methods
        assert not hasattr(api, "start")
        assert not hasattr(api, "stop")
        assert not hasattr(api, "correlator")
        assert not hasattr(api, "event_bus")
