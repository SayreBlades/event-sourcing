"""
Tests for the Price Drop Alert scenario in API-driven approach.

These tests demonstrate how the pricing service must handle
cross-domain queries and eligibility logic.
"""

import pytest
from api_driven.notification_api import NotificationAPI
from api_driven.services.pricing import PricingService, PRICE_ALERT_ELIGIBLE_SEGMENTS
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def setup_pricing_services(data_store):
    """Set up services for pricing tests."""
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    pricing_service = PricingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    return {
        "pricing_service": pricing_service,
        "notification_api": notification_api,
        "channels": channels,
        "data_store": data_store,
    }


class TestPriceDropAlert:
    """Tests for Price Drop Alert in API-driven approach."""
    
    def test_price_drop_notifies_eligible_customers(self, setup_pricing_services):
        """Test that price drop notifies eligible customers."""
        services = setup_pricing_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        # Drop price on prod-001 (Router)
        pricing.update_price("prod-001", 119.99)
        
        # Check who was notified
        sent_emails = [msg.recipient for msg in channels.email.sent_messages]
        
        # Carol (platinum) should be notified
        assert "carol.williams@example.com" in sent_emails
        
        # Eva (gold) should be notified
        assert "eva.martinez@example.com" in sent_emails
        
        # Bob (silver) should NOT be notified
        assert "bob.smith@example.com" not in sent_emails
    
    def test_price_increase_does_not_notify(self, setup_pricing_services):
        """Test that price increases don't trigger notifications."""
        services = setup_pricing_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        pricing.update_price("prod-001", 199.99)
        
        assert channels.get_total_sent_count() == 0
    
    def test_price_drop_notification_content(self, setup_pricing_services):
        """Test notification content is correct."""
        services = setup_pricing_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        pricing.update_price("prod-001", 119.99)
        
        # Find Carol's email
        carol_email = channels.email.find_message_to("carol.williams@example.com")
        
        assert carol_email is not None
        assert "119.99" in carol_email.subject
        assert "149.99" in carol_email.body
        assert "119.99" in carol_email.body


class TestPricingServiceCrossDomainQueries:
    """
    Tests that highlight the cross-domain queries required in API-driven approach.
    
    These tests document the coupling that API-driven creates.
    """
    
    def test_pricing_service_queries_carts(self, setup_pricing_services):
        """
        Verify that pricing service must query cart data.
        
        In event-sourced, pricing service has NO knowledge of carts.
        """
        services = setup_pricing_services
        pricing = services["pricing_service"]
        data_store = services["data_store"]
        
        # The pricing service uses the data store to query carts
        # This is a cross-domain dependency!
        carts = data_store.get_carts_containing_product("prod-001")
        
        # Verify the query works (pricing service depends on this)
        assert len(carts) == 3  # Bob, Carol, Eva have prod-001 in cart
    
    def test_pricing_service_queries_customer_segments(self, setup_pricing_services):
        """
        Verify that pricing service must query customer segments.
        
        In event-sourced, pricing service has NO knowledge of customer segments.
        """
        services = setup_pricing_services
        data_store = services["data_store"]
        
        # Pricing service must check customer segments for eligibility
        customer = data_store.get_customer("cust-003")  # Carol
        
        assert customer.segment == "platinum"
        assert customer.segment in PRICE_ALERT_ELIGIBLE_SEGMENTS
    
    def test_pricing_service_queries_preferences(self, setup_pricing_services):
        """
        Verify that pricing service must query notification preferences.
        
        In event-sourced, pricing service has NO knowledge of preferences.
        """
        services = setup_pricing_services
        data_store = services["data_store"]
        
        # Pricing service must check preferences
        prefs = data_store.get_notification_preferences("cust-003")
        
        assert prefs is not None
        assert prefs.get_channels_for_type("price_alerts")  # Carol has this enabled
    
    def test_pricing_service_has_notification_dependency(self, setup_pricing_services):
        """
        Verify that pricing service depends on notification API.
        
        In event-sourced, pricing service only depends on event bus.
        """
        services = setup_pricing_services
        pricing = services["pricing_service"]
        
        # The pricing service has a notification_api attribute
        assert hasattr(pricing, "notification_api")
        assert pricing.notification_api is not None


class TestAPIVsEventSourcedComplexity:
    """
    Tests that compare complexity between approaches.
    """
    
    def test_api_pricing_service_is_more_complex(self, data_store):
        """
        Compare the API-driven pricing service to the event-sourced one.
        
        API-driven has more dependencies and methods.
        """
        from api_driven.services.pricing import PricingService as APIPricingService
        from event_sourced.services.pricing import PricingService as EventPricingService
        
        # Create both
        channels = NotificationChannels()
        api_pricing = APIPricingService(
            notification_api=NotificationAPI(channels=channels, data_store=data_store),
            data_store=data_store,
        )
        
        from event_sourced.event_bus import EventBus
        event_pricing = EventPricingService(
            event_bus=EventBus(),
            data_store=data_store,
        )
        
        # API-driven has notification_api dependency
        assert hasattr(api_pricing, "notification_api")
        
        # Event-sourced has event_bus dependency instead
        assert hasattr(event_pricing, "event_bus")
        assert not hasattr(event_pricing, "notification_api")
        
        # API-driven has the complex _send_price_drop_notifications method
        assert hasattr(api_pricing, "_send_price_drop_notifications")
        
        # Event-sourced doesn't have this method - that logic is elsewhere
        assert not hasattr(event_pricing, "_send_price_drop_notifications")
    
    def test_eligibility_rules_location(self, setup_pricing_services):
        """
        Verify where eligibility rules live in each approach.
        
        API-driven: In the pricing service
        Event-sourced: In the notification service
        """
        from api_driven.services.pricing import PRICE_ALERT_ELIGIBLE_SEGMENTS as API_SEGMENTS
        from event_sourced.notification_service import PRICE_ALERT_ELIGIBLE_SEGMENTS as EVENT_SEGMENTS
        
        # Both have the same rules, but they're in different places
        assert API_SEGMENTS == EVENT_SEGMENTS
        
        # In API-driven, pricing service must know about this
        # In event-sourced, pricing service doesn't need to know
