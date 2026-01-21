"""
Tests for the notification API.

These tests verify the FastAPI notification service endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from api_driven.notification_api import app, reset_api_state, NotificationAPI
from api_driven.models import NotificationRequest, NotificationType
from shared.data_store import DataStore
from shared.channels import NotificationChannels


@pytest.fixture
def channels():
    """Fresh notification channels."""
    return NotificationChannels()


@pytest.fixture
def api_client(data_store, channels):
    """Create a test client with fresh state."""
    reset_api_state(channels=channels, data_store=data_store)
    yield TestClient(app)
    reset_api_state(None, None)


@pytest.fixture
def notification_api(data_store, channels):
    """Create a NotificationAPI instance for direct testing."""
    return NotificationAPI(channels=channels, data_store=data_store)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, api_client):
        """Test that health endpoint returns healthy."""
        response = api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestNotifyEndpoint:
    """Tests for the /notify endpoint."""
    
    def test_send_notification_success(self, api_client, channels):
        """Test sending a notification via API."""
        response = api_client.post("/notify", json={
            "notification_type": "ORDER_SHIPPED",
            "customer_id": "cust-001",
            "context": {
                "order_id": "ord-001",
                "item_list": "  - Test Item (x1)",
            },
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["notification_type"] == "ORDER_SHIPPED"
        assert data["customer_id"] == "cust-001"
        assert len(data["results"]) == 2  # Alice has email + sms
        
        # Verify notifications were sent
        assert channels.get_total_sent_count() == 2
    
    def test_customer_not_found(self, api_client):
        """Test that unknown customer returns 404."""
        response = api_client.post("/notify", json={
            "notification_type": "ORDER_SHIPPED",
            "customer_id": "nonexistent",
            "context": {"order_id": "ord-001"},
        })
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_respects_customer_preferences(self, api_client, channels):
        """Test that notifications respect customer preferences."""
        # Bob (cust-002) has only email for order_updates, not SMS
        response = api_client.post("/notify", json={
            "notification_type": "ORDER_SHIPPED",
            "customer_id": "cust-002",
            "context": {"order_id": "ord-002", "item_list": ""},
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only have 1 result (email only)
        assert len(data["results"]) == 1
        assert data["results"][0]["channel"] == "email"
    
    def test_override_channels(self, api_client, channels):
        """Test that caller can override channels."""
        # Alice normally gets email + sms, but we'll specify only sms
        response = api_client.post("/notify", json={
            "notification_type": "ORDER_SHIPPED",
            "customer_id": "cust-001",
            "context": {"order_id": "ord-001", "item_list": ""},
            "channels": ["sms"],
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["results"]) == 1
        assert data["results"][0]["channel"] == "sms"
    
    def test_payment_failed_notification(self, api_client, channels):
        """Test sending a payment failed notification."""
        response = api_client.post("/notify", json={
            "notification_type": "PAYMENT_FAILED",
            "customer_id": "cust-001",
            "context": {
                "order_id": "ord-001",
                "amount": 299.99,
                "failure_reason": "Card declined",
            },
        })
        
        assert response.status_code == 200
        
        # Check notification content
        email = channels.email.find_message_to("alice.johnson@example.com")
        assert email is not None
        assert "payment" in email.subject.lower()


class TestBulkNotifyEndpoint:
    """Tests for the /notify/bulk endpoint."""
    
    def test_bulk_notification(self, api_client, channels):
        """Test sending notifications to multiple customers."""
        response = api_client.post("/notify/bulk", json={
            "notification_type": "PRICE_DROP_ALERT",
            "customer_ids": ["cust-001", "cust-003"],
            "context": {
                "product_name": "Test Product",
                "old_price": 100.00,
                "new_price": 80.00,
                "savings": 20.00,
                "discount_percent": 20,
            },
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_customers"] == 2
        assert data["successful_customers"] == 2
        assert data["failed_customers"] == 0
    
    def test_bulk_with_invalid_customer(self, api_client, channels):
        """Test bulk notification with mix of valid/invalid customers."""
        response = api_client.post("/notify/bulk", json={
            "notification_type": "ORDER_SHIPPED",
            "customer_ids": ["cust-001", "invalid-customer"],
            "context": {"order_id": "ord-001", "item_list": ""},
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_customers"] == 2
        assert data["successful_customers"] == 1
        assert data["failed_customers"] == 1


class TestNotificationAPIClass:
    """Tests for the NotificationAPI wrapper class."""
    
    def test_send_notification(self, notification_api, channels):
        """Test sending notification via wrapper class."""
        request = NotificationRequest(
            notification_type=NotificationType.ORDER_SHIPPED,
            customer_id="cust-001",
            context={"order_id": "ord-001", "item_list": ""},
        )
        
        response = notification_api.send_notification(request)
        
        assert response.success
        assert response.customer_id == "cust-001"
        assert channels.get_total_sent_count() > 0
    
    def test_notification_response_properties(self, notification_api, channels):
        """Test NotificationResponse computed properties."""
        request = NotificationRequest(
            notification_type=NotificationType.ORDER_SHIPPED,
            customer_id="cust-001",
            context={"order_id": "ord-001", "item_list": ""},
        )
        
        response = notification_api.send_notification(request)
        
        assert response.success is True
        assert response.channels_sent == 2  # Email + SMS for Alice
