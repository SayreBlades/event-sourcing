"""
Tests for the DataStore.

These tests verify that the data store correctly loads JSON fixtures
and provides the queries needed by both notification approaches.
"""

import pytest
from shared.data_store import DataStore
from shared.models import LineItemStatus, OrderStatus


class TestDataStoreCustomers:
    """Tests for customer-related data store operations."""
    
    def test_get_customer(self, data_store: DataStore, alice_customer_id: str):
        """Test retrieving a customer by ID."""
        customer = data_store.get_customer(alice_customer_id)
        
        assert customer is not None
        assert customer.id == alice_customer_id
        assert customer.name == "Alice Johnson"
        assert customer.email == "alice.johnson@example.com"
        assert customer.segment == "gold"
    
    def test_get_nonexistent_customer(self, data_store: DataStore):
        """Test that getting a nonexistent customer returns None."""
        customer = data_store.get_customer("nonexistent-id")
        assert customer is None
    
    def test_get_customers(self, data_store: DataStore):
        """Test retrieving all customers."""
        customers = data_store.get_customers()
        
        assert len(customers) == 5
        customer_ids = [c.id for c in customers]
        assert "cust-001" in customer_ids
        assert "cust-005" in customer_ids
    
    def test_get_customers_by_segment(self, data_store: DataStore):
        """Test filtering customers by segment."""
        gold_customers = data_store.get_customers_by_segment("gold")
        
        assert len(gold_customers) == 2  # Alice and Eva
        for customer in gold_customers:
            assert customer.segment == "gold"


class TestDataStoreProducts:
    """Tests for product-related data store operations."""
    
    def test_get_product(self, data_store: DataStore, router_product_id: str):
        """Test retrieving a product by ID."""
        product = data_store.get_product(router_product_id)
        
        assert product is not None
        assert product.id == router_product_id
        assert product.name == "Wireless Router X500"
        assert product.price == 149.99
    
    def test_get_products(self, data_store: DataStore):
        """Test retrieving all products."""
        products = data_store.get_products()
        
        assert len(products) == 6
    
    def test_update_product_price(self, data_store: DataStore, router_product_id: str):
        """Test updating a product's price (in-memory)."""
        original = data_store.get_product(router_product_id)
        assert original.price == 149.99
        
        updated = data_store.update_product_price(router_product_id, 129.99)
        
        assert updated is not None
        assert updated.price == 129.99
        assert updated.name == original.name  # Other fields unchanged
        
        # Verify the change persists in the store
        refetched = data_store.get_product(router_product_id)
        assert refetched.price == 129.99


class TestDataStoreOrders:
    """Tests for order-related data store operations."""
    
    def test_get_order(self, data_store: DataStore, multi_item_order_id: str):
        """Test retrieving an order by ID."""
        order = data_store.get_order(multi_item_order_id)
        
        assert order is not None
        assert order.id == multi_item_order_id
        assert order.customer_id == "cust-001"
        assert len(order.line_items) == 2
    
    def test_get_orders_by_customer(self, data_store: DataStore, alice_customer_id: str):
        """Test retrieving orders for a customer."""
        orders = data_store.get_orders_by_customer(alice_customer_id)
        
        assert len(orders) == 1
        assert orders[0].id == "ord-001"
    
    def test_update_order_status(self, data_store: DataStore, multi_item_order_id: str):
        """Test updating an order's status."""
        original = data_store.get_order(multi_item_order_id)
        assert original.status == "PROCESSING"
        
        updated = data_store.update_order_status(multi_item_order_id, OrderStatus.SHIPPED)
        
        assert updated is not None
        assert updated.status == "SHIPPED"
        assert updated.updated_at is not None
    
    def test_update_line_item_status(self, data_store: DataStore, multi_item_order_id: str):
        """Test updating a specific line item's status."""
        order = data_store.get_order(multi_item_order_id)
        assert order.line_items[0].status == "PENDING"
        
        updated = data_store.update_line_item_status(
            multi_item_order_id,
            "prod-001",
            LineItemStatus.SHIPPED,
        )
        
        assert updated is not None
        # Find the updated line item
        prod_001_item = next(i for i in updated.line_items if i.product_id == "prod-001")
        assert prod_001_item.status == "SHIPPED"
        assert prod_001_item.shipped_at is not None
        
        # Other items unchanged
        prod_002_item = next(i for i in updated.line_items if i.product_id == "prod-002")
        assert prod_002_item.status == "PENDING"


class TestDataStoreCarts:
    """Tests for cart-related data store operations."""
    
    def test_get_cart(self, data_store: DataStore, bob_customer_id: str):
        """Test retrieving a customer's cart."""
        cart = data_store.get_cart(bob_customer_id)
        
        assert cart is not None
        assert cart.customer_id == bob_customer_id
        assert len(cart.items) == 2
        assert cart.contains_product("prod-001")
    
    def test_get_cart_nonexistent(self, data_store: DataStore, alice_customer_id: str):
        """Test that getting a cart for customer without one returns None."""
        cart = data_store.get_cart(alice_customer_id)
        assert cart is None  # Alice doesn't have a cart in fixtures
    
    def test_get_carts_containing_product(self, data_store: DataStore, router_product_id: str):
        """
        Test finding all carts containing a specific product.
        
        This is the key query for the Price Drop Alert scenario.
        """
        carts = data_store.get_carts_containing_product(router_product_id)
        
        # Router (prod-001) is in carts for: Bob, Carol, Eva
        assert len(carts) == 3
        customer_ids = [c.customer_id for c in carts]
        assert "cust-002" in customer_ids  # Bob
        assert "cust-003" in customer_ids  # Carol
        assert "cust-005" in customer_ids  # Eva


class TestDataStoreNotificationPreferences:
    """Tests for notification preference operations."""
    
    def test_get_notification_preferences(self, data_store: DataStore, alice_customer_id: str):
        """Test retrieving notification preferences."""
        prefs = data_store.get_notification_preferences(alice_customer_id)
        
        assert prefs is not None
        assert prefs.customer_id == alice_customer_id
        assert prefs.wants_notification("order_updates", "email") is True
        assert prefs.wants_notification("order_updates", "sms") is True
        assert prefs.wants_notification("price_alerts", "sms") is False
    
    def test_customer_wants_notification(self, data_store: DataStore, bob_customer_id: str):
        """Test the convenience method for checking notification preferences."""
        # Bob wants price alerts via email and SMS
        assert data_store.customer_wants_notification(bob_customer_id, "price_alerts", "email") is True
        assert data_store.customer_wants_notification(bob_customer_id, "price_alerts", "sms") is True
        
        # Bob doesn't want promotions
        assert data_store.customer_wants_notification(bob_customer_id, "promotions", "email") is False
    
    def test_customer_with_no_prefs(self, data_store: DataStore):
        """Test handling customer without preference record."""
        result = data_store.customer_wants_notification("nonexistent", "order_updates", "email")
        assert result is False


class TestDataStorePayments:
    """Tests for payment-related data store operations."""
    
    def test_get_payment(self, data_store: DataStore):
        """Test retrieving a payment by ID."""
        payment = data_store.get_payment("pay-001")
        
        assert payment is not None
        assert payment.order_id == "ord-001"
        assert payment.status == "SUCCESS"
    
    def test_get_payments_by_order(self, data_store: DataStore, pending_order_id: str):
        """Test retrieving all payments for an order."""
        payments = data_store.get_payments_by_order(pending_order_id)
        
        # David's order has 2 payment attempts
        assert len(payments) == 2
        
        # One failed, one pending
        statuses = [p.status for p in payments]
        assert "FAILED" in statuses
        assert "PENDING" in statuses


class TestDataStoreConvenienceMethods:
    """Tests for convenience methods."""
    
    def test_get_customer_with_preferences(self, data_store: DataStore, alice_customer_id: str):
        """Test getting customer and preferences together."""
        customer, prefs = data_store.get_customer_with_preferences(alice_customer_id)
        
        assert customer is not None
        assert prefs is not None
        assert customer.id == prefs.customer_id
    
    def test_reload(self, data_store: DataStore, router_product_id: str):
        """Test that reload clears cached data."""
        # Modify a product
        data_store.update_product_price(router_product_id, 99.99)
        product = data_store.get_product(router_product_id)
        assert product.price == 99.99
        
        # Reload should reset to original fixture data
        data_store.reload()
        product = data_store.get_product(router_product_id)
        assert product.price == 149.99  # Original price from JSON
