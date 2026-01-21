"""
Tests for the Order Complete scenario in API-driven approach.

These tests focus on demonstrating that the ordering service must
track shipment state internally.
"""

import pytest
from api_driven.notification_api import NotificationAPI
from api_driven.services.ordering import OrderingService
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def setup_ordering_services(data_store):
    """Set up services for ordering tests."""
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    ordering_service = OrderingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    return {
        "ordering_service": ordering_service,
        "notification_api": notification_api,
        "channels": channels,
        "data_store": data_store,
    }


class TestOrderCompleteStateTracking:
    """
    Tests focusing on how OrderingService must track state.
    
    In event-sourced, EventCorrelator in notification service handles this.
    In API-driven, OrderingService must do it itself.
    """
    
    def test_ordering_service_tracks_shipments(self, setup_ordering_services):
        """Test that ordering service maintains shipment state."""
        services = setup_ordering_services
        ordering = services["ordering_service"]
        
        # Ship first item
        ordering.ship_line_item("ord-001", "prod-001")
        
        # State should be tracked internally
        assert "ord-001" in ordering._order_shipment_state
        assert "prod-001" in ordering._order_shipment_state["ord-001"]
    
    def test_state_cleared_after_completion(self, setup_ordering_services):
        """Test that state is cleaned up after order completes."""
        services = setup_ordering_services
        ordering = services["ordering_service"]
        
        # Ship both items
        ordering.ship_line_item("ord-001", "prod-001")
        ordering.ship_line_item("ord-001", "prod-002")
        
        # State should be cleaned up
        assert "ord-001" not in ordering._order_shipment_state
    
    def test_multiple_orders_tracked_separately(self, setup_ordering_services):
        """Test that multiple orders are tracked independently."""
        services = setup_ordering_services
        ordering = services["ordering_service"]
        
        # Ship items from different orders
        ordering.ship_line_item("ord-001", "prod-001")
        ordering.ship_line_item("ord-002", "prod-003")
        
        # Both should be tracked separately
        assert "ord-001" in ordering._order_shipment_state
        assert "ord-002" in ordering._order_shipment_state


class TestAPIVsEventSourcedStateManagement:
    """
    Tests comparing state management between approaches.
    """
    
    def test_api_ordering_has_internal_state(self, data_store):
        """
        API-driven OrderingService must maintain internal state.
        """
        channels = NotificationChannels()
        api = NotificationAPI(channels=channels, data_store=data_store)
        ordering = OrderingService(notification_api=api, data_store=data_store)
        
        # Has internal state for tracking
        assert hasattr(ordering, "_order_shipment_state")
        assert isinstance(ordering._order_shipment_state, dict)
    
    def test_event_ordering_has_no_internal_state(self, data_store):
        """
        Event-sourced OrderingService has NO internal state for notifications.
        """
        from event_sourced.event_bus import EventBus
        from event_sourced.services.ordering import OrderingService as EventOrderingService
        
        ordering = EventOrderingService(
            event_bus=EventBus(),
            data_store=data_store,
        )
        
        # Should NOT have internal shipment tracking state
        assert not hasattr(ordering, "_order_shipment_state")
    
    def test_complexity_lives_in_different_places(self, data_store):
        """
        Demonstrate where state tracking complexity lives.
        
        API-driven: In OrderingService
        Event-sourced: In EventCorrelator (part of notification service)
        """
        from event_sourced.event_correlator import EventCorrelator
        from api_driven.services.ordering import OrderingService as APIOrderingService
        
        # Event-sourced uses EventCorrelator for state
        correlator = EventCorrelator()
        assert hasattr(correlator, "_order_states")
        assert hasattr(correlator, "process_line_item_shipped")
        
        # API-driven has state in OrderingService
        channels = NotificationChannels()
        api = NotificationAPI(channels=channels, data_store=data_store)
        api_ordering = APIOrderingService(notification_api=api, data_store=data_store)
        assert hasattr(api_ordering, "_order_shipment_state")
