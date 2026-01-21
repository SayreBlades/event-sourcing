"""
Tests for shared domain models.

These tests verify that our models correctly represent the domain
and that business logic methods work as expected.
"""

import pytest
from datetime import datetime

from shared.models import (
    Customer,
    Product,
    Order,
    LineItem,
    Cart,
    CartItem,
    NotificationPreference,
    ChannelPreferences,
    OrderStatus,
    LineItemStatus,
    CustomerSegment,
    PaymentStatus,
    Payment,
)


class TestCustomer:
    """Tests for Customer model."""
    
    def test_create_customer(self):
        """Test basic customer creation."""
        customer = Customer(
            id="test-001",
            name="Test User",
            email="test@example.com",
            phone="+1-555-1234",
            segment=CustomerSegment.GOLD,
        )
        
        assert customer.id == "test-001"
        assert customer.name == "Test User"
        assert customer.email == "test@example.com"
        assert customer.phone == "+1-555-1234"
        assert customer.segment == "gold"  # enum serialized to string
    
    def test_default_segment(self):
        """Test that default segment is bronze."""
        customer = Customer(
            id="test-002",
            name="Test User",
            email="test@example.com",
            phone="+1-555-1234",
        )
        assert customer.segment == "bronze"


class TestProduct:
    """Tests for Product model."""
    
    def test_create_product(self):
        """Test basic product creation."""
        product = Product(
            id="prod-test",
            name="Test Product",
            price=99.99,
            category="electronics",
        )
        
        assert product.id == "prod-test"
        assert product.name == "Test Product"
        assert product.price == 99.99
        assert product.category == "electronics"
    
    def test_price_validation(self):
        """Test that negative prices are rejected."""
        with pytest.raises(ValueError):
            Product(
                id="prod-test",
                name="Test Product",
                price=-10.00,
                category="electronics",
            )


class TestLineItem:
    """Tests for LineItem model."""
    
    def test_create_line_item(self):
        """Test basic line item creation."""
        item = LineItem(
            product_id="prod-001",
            quantity=2,
            unit_price=149.99,
        )
        
        assert item.product_id == "prod-001"
        assert item.quantity == 2
        assert item.unit_price == 149.99
        assert item.status == "PENDING"  # default status
        assert item.shipped_at is None
    
    def test_shipped_line_item(self):
        """Test line item with shipped status."""
        shipped_at = datetime.utcnow()
        item = LineItem(
            product_id="prod-001",
            quantity=1,
            unit_price=99.99,
            status=LineItemStatus.SHIPPED,
            shipped_at=shipped_at,
        )
        
        assert item.status == "SHIPPED"
        assert item.shipped_at == shipped_at


class TestOrder:
    """Tests for Order model."""
    
    def test_create_order(self):
        """Test basic order creation."""
        order = Order(
            id="ord-test",
            customer_id="cust-001",
            total_amount=299.97,
            line_items=[
                LineItem(product_id="prod-001", quantity=1, unit_price=149.99),
                LineItem(product_id="prod-002", quantity=2, unit_price=74.99),
            ],
        )
        
        assert order.id == "ord-test"
        assert order.customer_id == "cust-001"
        assert order.status == "PENDING"  # default
        assert len(order.line_items) == 2
        assert order.total_amount == 299.97
    
    def test_all_items_shipped_false_when_pending(self):
        """Test that all_items_shipped returns False when items are pending."""
        order = Order(
            id="ord-test",
            customer_id="cust-001",
            total_amount=149.99,
            line_items=[
                LineItem(product_id="prod-001", quantity=1, unit_price=149.99),
            ],
        )
        
        assert order.all_items_shipped_or_delivered() is False
    
    def test_all_items_shipped_true_when_all_shipped(self):
        """Test that all_items_shipped returns True when all items shipped."""
        order = Order(
            id="ord-test",
            customer_id="cust-001",
            total_amount=299.98,
            line_items=[
                LineItem(
                    product_id="prod-001",
                    quantity=1,
                    unit_price=149.99,
                    status=LineItemStatus.SHIPPED,
                ),
                LineItem(
                    product_id="prod-002",
                    quantity=1,
                    unit_price=149.99,
                    status=LineItemStatus.DELIVERED,
                ),
            ],
        )
        
        assert order.all_items_shipped_or_delivered() is True
    
    def test_all_items_shipped_false_when_partial(self):
        """Test partial shipment scenario."""
        order = Order(
            id="ord-test",
            customer_id="cust-001",
            total_amount=299.98,
            line_items=[
                LineItem(
                    product_id="prod-001",
                    quantity=1,
                    unit_price=149.99,
                    status=LineItemStatus.SHIPPED,
                ),
                LineItem(
                    product_id="prod-002",
                    quantity=1,
                    unit_price=149.99,
                    status=LineItemStatus.PENDING,
                ),
            ],
        )
        
        assert order.all_items_shipped_or_delivered() is False
    
    def test_get_pending_items_count(self):
        """Test counting pending items."""
        order = Order(
            id="ord-test",
            customer_id="cust-001",
            total_amount=449.97,
            line_items=[
                LineItem(product_id="prod-001", quantity=1, unit_price=149.99, status=LineItemStatus.SHIPPED),
                LineItem(product_id="prod-002", quantity=1, unit_price=149.99, status=LineItemStatus.PENDING),
                LineItem(product_id="prod-003", quantity=1, unit_price=149.99, status=LineItemStatus.PROCESSING),
            ],
        )
        
        assert order.get_pending_items_count() == 2  # PENDING + PROCESSING


class TestCart:
    """Tests for Cart model."""
    
    def test_create_cart(self):
        """Test basic cart creation."""
        cart = Cart(
            customer_id="cust-001",
            items=[
                CartItem(product_id="prod-001", quantity=1),
                CartItem(product_id="prod-002", quantity=2),
            ],
        )
        
        assert cart.customer_id == "cust-001"
        assert len(cart.items) == 2
    
    def test_contains_product(self):
        """Test checking if cart contains a product."""
        cart = Cart(
            customer_id="cust-001",
            items=[
                CartItem(product_id="prod-001", quantity=1),
            ],
        )
        
        assert cart.contains_product("prod-001") is True
        assert cart.contains_product("prod-999") is False
    
    def test_get_product_ids(self):
        """Test getting all product IDs in cart."""
        cart = Cart(
            customer_id="cust-001",
            items=[
                CartItem(product_id="prod-001", quantity=1),
                CartItem(product_id="prod-002", quantity=2),
                CartItem(product_id="prod-003", quantity=1),
            ],
        )
        
        product_ids = cart.get_product_ids()
        assert product_ids == ["prod-001", "prod-002", "prod-003"]


class TestNotificationPreference:
    """Tests for NotificationPreference model."""
    
    def test_create_with_defaults(self):
        """Test notification preferences with default values."""
        prefs = NotificationPreference(customer_id="cust-001")
        
        # Check defaults
        assert prefs.preferences["order_updates"].email is True
        assert prefs.preferences["order_updates"].sms is True
        assert prefs.preferences["price_alerts"].email is True
        assert prefs.preferences["price_alerts"].sms is False
    
    def test_get_channels_for_type(self):
        """Test getting enabled channels for a notification type."""
        prefs = NotificationPreference(
            customer_id="cust-001",
            preferences={
                "order_updates": ChannelPreferences(email=True, sms=True),
                "price_alerts": ChannelPreferences(email=True, sms=False),
            },
        )
        
        assert prefs.get_channels_for_type("order_updates") == ["email", "sms"]
        assert prefs.get_channels_for_type("price_alerts") == ["email"]
        assert prefs.get_channels_for_type("nonexistent") == []
    
    def test_wants_notification(self):
        """Test checking if customer wants specific notification."""
        prefs = NotificationPreference(
            customer_id="cust-001",
            preferences={
                "order_updates": ChannelPreferences(email=True, sms=False),
            },
        )
        
        assert prefs.wants_notification("order_updates", "email") is True
        assert prefs.wants_notification("order_updates", "sms") is False
        assert prefs.wants_notification("nonexistent", "email") is False


class TestPayment:
    """Tests for Payment model."""
    
    def test_create_payment(self):
        """Test basic payment creation."""
        payment = Payment(
            id="pay-001",
            order_id="ord-001",
            customer_id="cust-001",
            amount=149.99,
        )
        
        assert payment.id == "pay-001"
        assert payment.status == "PENDING"  # default
        assert payment.attempt_number == 1  # default
        assert payment.failure_reason is None
    
    def test_failed_payment(self):
        """Test failed payment with reason."""
        payment = Payment(
            id="pay-002",
            order_id="ord-001",
            customer_id="cust-001",
            amount=149.99,
            status=PaymentStatus.FAILED,
            failure_reason="Insufficient funds",
        )
        
        assert payment.status == "FAILED"
        assert payment.failure_reason == "Insufficient funds"
