"""
Tests for simple notification scenarios in the event-sourced approach.

These tests verify the "Order Shipped" notification flow:
1. OrderingService publishes event
2. NotificationService receives event
3. Customer gets notified via preferred channels
"""

import pytest
from event_sourced.event_bus import EventBus, reset_event_bus
from event_sourced.notification_service import NotificationService
from event_sourced.services.ordering import OrderingService
from event_sourced.events import EventTypes, order_status_changed, payment_failed
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def event_bus():
    """Fresh event bus for each test."""
    return reset_event_bus()


@pytest.fixture
def setup_services(event_bus, data_store):
    """Set up all services for integration testing."""
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
    
    yield {
        "notification_service": notification_service,
        "ordering_service": ordering_service,
        "channels": channels,
        "event_bus": event_bus,
        "data_store": data_store,
    }
    
    notification_service.stop()


class TestOrderShippedNotification:
    """Tests for the Order Shipped notification scenario."""
    
    def test_shipping_order_sends_notification(self, setup_services):
        """Test that shipping an order triggers a notification."""
        services = setup_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Ship Alice's order (cust-001 has email+sms enabled for order_updates)
        result = ordering.ship_order("ord-001")
        
        assert result is True
        
        # Should have sent both email and SMS (Alice has both enabled)
        sent = channels.get_all_sent_messages()
        assert len(sent) == 2
        
        # Check email was sent
        email = channels.email.find_message_to("alice.johnson@example.com")
        assert email is not None
        assert "shipped" in email.subject.lower()
        assert "ord-001" in email.subject
        
        # Check SMS was sent
        sms = channels.sms.find_message_to("+1-555-0101")
        assert sms is not None
        assert "shipped" in sms.body.lower()
    
    def test_shipping_order_respects_preferences(self, setup_services):
        """Test that notifications respect customer preferences."""
        services = setup_services
        channels = services["channels"]
        event_bus = services["event_bus"]
        
        # Bob (cust-002) has only email enabled for order_updates, not SMS
        event = order_status_changed(
            order_id="ord-002",
            customer_id="cust-002",
            previous_status="PROCESSING",
            new_status="SHIPPED",
        )
        event_bus.publish(event)
        
        # Should have sent only email
        assert channels.email.get_sent_count() == 1
        assert channels.sms.get_sent_count() == 0
        
        email = channels.email.find_message_to("bob.smith@example.com")
        assert email is not None
    
    def test_shipping_nonexistent_order_fails(self, setup_services):
        """Test that shipping a nonexistent order fails gracefully."""
        services = setup_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        result = ordering.ship_order("nonexistent-order")
        
        assert result is False
        assert channels.get_total_sent_count() == 0
    
    def test_event_contains_correct_data(self, setup_services):
        """Test that published events contain the expected data."""
        services = setup_services
        ordering = services["ordering_service"]
        event_bus = services["event_bus"]
        
        ordering.ship_order("ord-001")
        
        # Check the event log
        events = event_bus.get_event_log()
        assert len(events) == 1
        
        event = events[0]
        assert event.event_type == EventTypes.ORDER_STATUS_CHANGED
        assert event.payload["order_id"] == "ord-001"
        assert event.payload["customer_id"] == "cust-001"
        assert event.payload["new_status"] == "SHIPPED"
        assert event.source == "ordering-service"


class TestOrderDeliveredNotification:
    """Tests for the Order Delivered notification scenario."""
    
    def test_delivering_order_sends_notification(self, setup_services):
        """Test that delivering an order triggers a notification."""
        services = setup_services
        ordering = services["ordering_service"]
        channels = services["channels"]
        
        # Deliver Carol's already-shipped order
        result = ordering.deliver_order("ord-003")
        
        assert result is True
        
        # Carol (cust-003) has both email and SMS enabled
        assert channels.get_total_sent_count() == 2


class TestPaymentFailedNotification:
    """Tests for the Payment Failed notification scenario."""
    
    def test_payment_failed_sends_notification(self, setup_services):
        """Test that a payment failure triggers a notification."""
        services = setup_services
        channels = services["channels"]
        event_bus = services["event_bus"]
        
        # Simulate a payment failure for Alice
        event = payment_failed(
            payment_id="pay-test",
            order_id="ord-001",
            customer_id="cust-001",
            amount=309.97,
            failure_reason="Insufficient funds",
            attempt_number=1,
        )
        event_bus.publish(event)
        
        # Alice has both email and SMS enabled for payment_alerts
        assert channels.get_total_sent_count() == 2
        
        email = channels.email.find_message_to("alice.johnson@example.com")
        assert email is not None
        assert "payment" in email.subject.lower()
        assert "Insufficient funds" in email.body
    
    def test_payment_failed_respects_preferences(self, setup_services):
        """Test that payment notifications respect preferences."""
        services = setup_services
        channels = services["channels"]
        event_bus = services["event_bus"]
        
        # David (cust-004) has only email enabled for payment_alerts
        event = payment_failed(
            payment_id="pay-test",
            order_id="ord-004",
            customer_id="cust-004",
            amount=149.99,
            failure_reason="Card expired",
            attempt_number=1,
        )
        event_bus.publish(event)
        
        assert channels.email.get_sent_count() == 1
        assert channels.sms.get_sent_count() == 0


class TestNotificationServiceLifecycle:
    """Tests for notification service start/stop behavior."""
    
    def test_service_only_receives_events_when_started(self, event_bus, data_store):
        """Test that the service must be started to receive events."""
        channels = NotificationChannels()
        service = NotificationService(
            event_bus=event_bus,
            data_store=data_store,
            channels=channels,
        )
        
        # Don't start the service
        event = order_status_changed(
            order_id="ord-001",
            customer_id="cust-001",
            previous_status="PROCESSING",
            new_status="SHIPPED",
        )
        event_bus.publish(event)
        
        # No notifications should be sent
        assert channels.get_total_sent_count() == 0
        
        # Now start and publish again
        service.start()
        event_bus.publish(event)
        
        assert channels.get_total_sent_count() == 2  # Email + SMS for Alice
        
        service.stop()
    
    def test_service_stops_receiving_after_stop(self, event_bus, data_store):
        """Test that stopping the service stops event processing."""
        channels = NotificationChannels()
        service = NotificationService(
            event_bus=event_bus,
            data_store=data_store,
            channels=channels,
        )
        
        service.start()
        service.stop()
        
        event = order_status_changed(
            order_id="ord-001",
            customer_id="cust-001",
            previous_status="PROCESSING",
            new_status="SHIPPED",
        )
        event_bus.publish(event)
        
        assert channels.get_total_sent_count() == 0


class TestDecouplingDemonstration:
    """
    Tests that demonstrate the decoupling benefit of event-sourcing.
    
    These tests show that the ordering service doesn't need to know
    about notifications - it just publishes events.
    """
    
    def test_ordering_service_works_without_notification_service(self, event_bus, data_store):
        """
        Test that ordering service works even if no one is listening.
        
        This demonstrates loose coupling - the publisher doesn't
        care if there are subscribers.
        """
        ordering = OrderingService(event_bus=event_bus, data_store=data_store)
        
        # No notification service is subscribed
        result = ordering.ship_order("ord-001")
        
        # The action still succeeds
        assert result is True
        
        # Event was still published
        events = event_bus.get_event_log()
        assert len(events) == 1
        assert events[0].event_type == EventTypes.ORDER_STATUS_CHANGED
    
    def test_multiple_services_can_subscribe_to_same_event(self, event_bus, data_store):
        """
        Test that multiple services can react to the same event.
        
        This shows how you could add analytics, audit logging, etc.
        without changing the publishing service.
        """
        channels = NotificationChannels()
        notification_service = NotificationService(
            event_bus=event_bus,
            data_store=data_store,
            channels=channels,
        )
        notification_service.start()
        
        # Add another subscriber (simulating an analytics service)
        analytics_events = []
        event_bus.subscribe(EventTypes.ORDER_STATUS_CHANGED, lambda e: analytics_events.append(e))
        
        ordering = OrderingService(event_bus=event_bus, data_store=data_store)
        ordering.ship_order("ord-001")
        
        # Both services received the event
        assert channels.get_total_sent_count() == 2  # Notification service sent notifications
        assert len(analytics_events) == 1  # Analytics service received event
        
        notification_service.stop()
