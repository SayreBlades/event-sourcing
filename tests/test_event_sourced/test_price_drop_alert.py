"""
Tests for the Price Drop Alert complex scenario.

This tests the multi-condition notification:
- Price drops on a product
- Customer has product in cart
- Customer has opted into price alerts
- Customer is in eligible segment
"""

import pytest
from event_sourced.event_bus import reset_event_bus
from event_sourced.event_correlator import reset_event_correlator
from event_sourced.notification_service import NotificationService, PRICE_ALERT_ELIGIBLE_SEGMENTS
from event_sourced.services.pricing import PricingService
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def setup_price_drop_services(data_store):
    """Set up services for price drop testing."""
    event_bus = reset_event_bus()
    correlator = reset_event_correlator()
    channels = NotificationChannels()
    
    notification_service = NotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
        correlator=correlator,
    )
    pricing_service = PricingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    notification_service.start()
    
    yield {
        "notification_service": notification_service,
        "pricing_service": pricing_service,
        "channels": channels,
        "event_bus": event_bus,
        "data_store": data_store,
    }
    
    notification_service.stop()


class TestPriceDropAlert:
    """Tests for the Price Drop Alert scenario."""
    
    def test_price_drop_notifies_eligible_customers(self, setup_price_drop_services):
        """
        Test that price drop notifies customers who:
        - Have the product in cart
        - Have opted into price alerts
        - Are in an eligible segment
        """
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        # Drop price on prod-001 (Router)
        # In cart for: Bob (silver), Carol (platinum), Eva (gold)
        # Eligible segments: gold, platinum
        # Expected: Carol and Eva get notified, Bob doesn't
        pricing.update_price("prod-001", 119.99)
        
        # Check who was notified
        sent_emails = [msg.recipient for msg in channels.email.sent_messages]
        
        # Carol (platinum) should be notified
        assert "carol.williams@example.com" in sent_emails
        
        # Eva (gold) should be notified
        assert "eva.martinez@example.com" in sent_emails
        
        # Bob (silver) should NOT be notified (not in eligible segment)
        assert "bob.smith@example.com" not in sent_emails
    
    def test_price_drop_checks_preferences(self, setup_price_drop_services):
        """Test that customers without price alerts enabled are not notified."""
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        # David (cust-004) has price_alerts disabled
        # He's bronze segment anyway, but even if he were gold, prefs would block it
        
        # All customers who COULD be notified for prod-001:
        # - Bob: silver (ineligible), has price alerts
        # - Carol: platinum (eligible), has price alerts
        # - Eva: gold (eligible), has price alerts
        
        pricing.update_price("prod-001", 119.99)
        
        # Only 2 customers should get email (Carol has both, Eva has email only)
        # Carol: email + sms for price_alerts
        # Eva: email only for price_alerts
        assert channels.email.get_sent_count() == 2
    
    def test_price_increase_does_not_notify(self, setup_price_drop_services):
        """Test that price increases don't trigger notifications."""
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        # Increase price instead of decreasing
        pricing.update_price("prod-001", 199.99)
        
        # No notifications should be sent
        assert channels.get_total_sent_count() == 0
    
    def test_price_drop_notification_content(self, setup_price_drop_services):
        """Test that the notification contains correct price information."""
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        # Drop price from 149.99 to 119.99
        pricing.update_price("prod-001", 119.99)
        
        # Find Carol's email (she's platinum, will definitely get it)
        carol_email = channels.email.find_message_to("carol.williams@example.com")
        
        assert carol_email is not None
        assert "119.99" in carol_email.subject  # New price in subject
        assert "149.99" in carol_email.body     # Old price in body
        assert "119.99" in carol_email.body     # New price in body
        assert "30.00" in carol_email.body      # Savings
    
    def test_product_not_in_any_cart(self, setup_price_drop_services):
        """Test that price drop on product not in any cart sends no notifications."""
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        # prod-004 (4K Webcam) is not in any cart
        pricing.update_price("prod-004", 149.99)
        
        assert channels.get_total_sent_count() == 0
    
    def test_apply_discount(self, setup_price_drop_services):
        """Test applying a percentage discount."""
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        data_store = services["data_store"]
        
        # Apply 20% discount to prod-001 (149.99 -> 119.99)
        result = pricing.apply_discount("prod-001", 20)
        
        assert result is True
        
        # Check price was updated
        product = data_store.get_product("prod-001")
        assert product.price == 119.99
        
        # Notifications should have been sent
        assert channels.get_total_sent_count() > 0


class TestPriceDropEligibility:
    """Tests focused on eligibility rules."""
    
    def test_eligible_segments_configured(self):
        """Verify the eligible segments are configured correctly."""
        assert "gold" in PRICE_ALERT_ELIGIBLE_SEGMENTS
        assert "platinum" in PRICE_ALERT_ELIGIBLE_SEGMENTS
        assert "silver" not in PRICE_ALERT_ELIGIBLE_SEGMENTS
        assert "bronze" not in PRICE_ALERT_ELIGIBLE_SEGMENTS
    
    def test_only_eligible_segments_notified(self, setup_price_drop_services):
        """
        Comprehensive test that only eligible segments are notified.
        
        This is the key business rule for the price drop alert scenario.
        """
        services = setup_price_drop_services
        pricing = services["pricing_service"]
        channels = services["channels"]
        
        pricing.update_price("prod-001", 99.99)
        
        # Get all recipients
        recipients = [msg.recipient for msg in channels.get_all_sent_messages()]
        
        # Map recipients to their segments (from our fixtures)
        # cust-002 Bob = silver (bob.smith@example.com, +1-555-0102)
        # cust-003 Carol = platinum (carol.williams@example.com, +1-555-0103)
        # cust-005 Eva = gold (eva.martinez@example.com, +1-555-0105)
        
        bob_notified = any("bob" in r.lower() or "0102" in r for r in recipients)
        carol_notified = any("carol" in r.lower() or "0103" in r for r in recipients)
        eva_notified = any("eva" in r.lower() or "0105" in r for r in recipients)
        
        assert not bob_notified, "Bob (silver) should not be notified"
        assert carol_notified, "Carol (platinum) should be notified"
        assert eva_notified, "Eva (gold) should be notified"


class TestPricingServiceDecoupling:
    """Tests demonstrating that pricing service is decoupled from notifications."""
    
    def test_pricing_service_works_without_notification_service(self, data_store):
        """
        Test that pricing service works even if notification service isn't running.
        
        This demonstrates the loose coupling of event-sourced architecture.
        """
        event_bus = reset_event_bus()
        pricing = PricingService(event_bus=event_bus, data_store=data_store)
        
        # No notification service subscribed
        result = pricing.update_price("prod-001", 99.99)
        
        # Price update still succeeds
        assert result is True
        
        # Event was still published
        events = event_bus.get_event_log()
        assert len(events) == 1
        assert events[0].event_type == "PriceChanged"
    
    def test_pricing_service_has_no_cart_dependency(self, data_store):
        """
        Verify that pricing service doesn't need to know about carts.
        
        In API-driven approach, pricing would need to query carts.
        Here, it just publishes an event.
        """
        event_bus = reset_event_bus()
        pricing = PricingService(event_bus=event_bus, data_store=data_store)
        
        # The pricing service only interacts with products
        # It doesn't import or use the cart functionality
        result = pricing.update_price("prod-001", 99.99)
        
        assert result is True
        
        # Check the event - it only contains product info
        event = event_bus.get_event_log()[0]
        assert "product_id" in event.payload
        assert "product_name" in event.payload
        assert "cart" not in str(event.payload).lower()
        assert "customer" not in str(event.payload).lower()
