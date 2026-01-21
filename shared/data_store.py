"""
JSON-backed data store for the notification architecture demo.

This module provides a simple data access layer that reads from JSON fixture files.
In a real system, each domain service would have its own database/API.

Design decisions:
- Read-only for most operations (fixtures are source of truth)
- Write operations update in-memory state only (for demo scenarios)
- Singleton-like behavior via module-level instance caching
- Thread-safe for read operations (writes are demo-only)

The separation of data access from domain models allows us to demonstrate
how the notification service needs to query multiple data sources.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from shared.models import (
    Customer,
    Product,
    Order,
    Cart,
    NotificationPreference,
    Payment,
    LineItem,
    LineItemStatus,
    OrderStatus,
)


class DataStore:
    """
    Central data store that loads and manages JSON fixtures.
    
    In a real microservices architecture, each service would own its data:
    - Customer service owns customers and preferences
    - Catalog service owns products
    - Order service owns orders
    - Cart service owns carts
    
    This unified store simulates querying across services.
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the data store.
        
        Args:
            data_dir: Path to the data directory containing JSON fixtures.
                     Defaults to ./data relative to project root.
        """
        if data_dir is None:
            # Default to data/ directory relative to this file's location
            data_dir = Path(__file__).parent.parent / "data"
        
        self.data_dir = Path(data_dir)
        
        # In-memory caches - loaded lazily
        self._customers: Optional[dict[str, Customer]] = None
        self._products: Optional[dict[str, Product]] = None
        self._orders: Optional[dict[str, Order]] = None
        self._carts: Optional[dict[str, Cart]] = None  # keyed by customer_id
        self._preferences: Optional[dict[str, NotificationPreference]] = None  # keyed by customer_id
        self._payments: Optional[dict[str, Payment]] = None
    
    # =========================================================================
    # Data Loading (lazy)
    # =========================================================================
    
    def _load_json(self, filename: str) -> list[dict]:
        """Load a JSON fixture file."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return []
        with open(filepath, "r") as f:
            return json.load(f)
    
    def _ensure_customers_loaded(self):
        """Lazy load customers from JSON."""
        if self._customers is None:
            data = self._load_json("customers.json")
            self._customers = {c["id"]: Customer(**c) for c in data}
    
    def _ensure_products_loaded(self):
        """Lazy load products from JSON."""
        if self._products is None:
            data = self._load_json("products.json")
            self._products = {p["id"]: Product(**p) for p in data}
    
    def _ensure_orders_loaded(self):
        """Lazy load orders from JSON."""
        if self._orders is None:
            data = self._load_json("orders.json")
            self._orders = {o["id"]: Order(**o) for o in data}
    
    def _ensure_carts_loaded(self):
        """Lazy load carts from JSON (keyed by customer_id)."""
        if self._carts is None:
            data = self._load_json("carts.json")
            self._carts = {c["customer_id"]: Cart(**c) for c in data}
    
    def _ensure_preferences_loaded(self):
        """Lazy load notification preferences from JSON."""
        if self._preferences is None:
            data = self._load_json("notification_preferences.json")
            self._preferences = {p["customer_id"]: NotificationPreference(**p) for p in data}
    
    def _ensure_payments_loaded(self):
        """Lazy load payments from JSON."""
        if self._payments is None:
            data = self._load_json("payments.json")
            self._payments = {p["id"]: Payment(**p) for p in data}
    
    # =========================================================================
    # Customer Operations
    # =========================================================================
    
    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """
        Get a customer by ID.
        
        In event-sourced: Notification service calls this to look up contact info.
        In API-driven: Calling service might need this, or notification service does.
        """
        self._ensure_customers_loaded()
        return self._customers.get(customer_id)
    
    def get_customers(self) -> list[Customer]:
        """Get all customers."""
        self._ensure_customers_loaded()
        return list(self._customers.values())
    
    def get_customers_by_segment(self, segment: str) -> list[Customer]:
        """
        Get customers in a specific segment.
        
        Used for eligibility filtering in the Price Drop Alert scenario.
        """
        self._ensure_customers_loaded()
        return [c for c in self._customers.values() if c.segment == segment]
    
    # =========================================================================
    # Product Operations
    # =========================================================================
    
    def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID."""
        self._ensure_products_loaded()
        return self._products.get(product_id)
    
    def get_products(self) -> list[Product]:
        """Get all products."""
        self._ensure_products_loaded()
        return list(self._products.values())
    
    def update_product_price(self, product_id: str, new_price: float) -> Optional[Product]:
        """
        Update a product's price (in-memory only).
        
        Used to simulate price changes for the Price Drop Alert scenario.
        Returns the updated product or None if not found.
        """
        self._ensure_products_loaded()
        product = self._products.get(product_id)
        if product:
            # Create new product with updated price (Pydantic models are immutable-ish)
            updated = Product(
                id=product.id,
                name=product.name,
                price=new_price,
                category=product.category,
                description=product.description,
            )
            self._products[product_id] = updated
            return updated
        return None
    
    # =========================================================================
    # Order Operations
    # =========================================================================
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        self._ensure_orders_loaded()
        return self._orders.get(order_id)
    
    def get_orders(self) -> list[Order]:
        """Get all orders."""
        self._ensure_orders_loaded()
        return list(self._orders.values())
    
    def get_orders_by_customer(self, customer_id: str) -> list[Order]:
        """Get all orders for a specific customer."""
        self._ensure_orders_loaded()
        return [o for o in self._orders.values() if o.customer_id == customer_id]
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> Optional[Order]:
        """
        Update an order's status (in-memory only).
        
        Used to simulate order lifecycle changes.
        """
        self._ensure_orders_loaded()
        order = self._orders.get(order_id)
        if order:
            updated = Order(
                id=order.id,
                customer_id=order.customer_id,
                status=status,
                line_items=order.line_items,
                total_amount=order.total_amount,
                created_at=order.created_at,
                updated_at=datetime.utcnow(),
            )
            self._orders[order_id] = updated
            return updated
        return None
    
    def update_line_item_status(
        self, 
        order_id: str, 
        product_id: str, 
        status: LineItemStatus
    ) -> Optional[Order]:
        """
        Update a specific line item's status within an order.
        
        Used for the Order Complete scenario where items ship independently.
        Returns the updated order or None if not found.
        """
        self._ensure_orders_loaded()
        order = self._orders.get(order_id)
        if not order:
            return None
        
        # Update the specific line item
        updated_items = []
        for item in order.line_items:
            if item.product_id == product_id:
                updated_item = LineItem(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    status=status,
                    shipped_at=datetime.utcnow() if status == LineItemStatus.SHIPPED else item.shipped_at,
                )
                updated_items.append(updated_item)
            else:
                updated_items.append(item)
        
        updated_order = Order(
            id=order.id,
            customer_id=order.customer_id,
            status=order.status,
            line_items=updated_items,
            total_amount=order.total_amount,
            created_at=order.created_at,
            updated_at=datetime.utcnow(),
        )
        self._orders[order_id] = updated_order
        return updated_order
    
    # =========================================================================
    # Cart Operations
    # =========================================================================
    
    def get_cart(self, customer_id: str) -> Optional[Cart]:
        """
        Get a customer's cart.
        
        Critical for Price Drop Alert - we need to know who has a product in cart.
        """
        self._ensure_carts_loaded()
        return self._carts.get(customer_id)
    
    def get_carts(self) -> list[Cart]:
        """Get all carts."""
        self._ensure_carts_loaded()
        return list(self._carts.values())
    
    def get_carts_containing_product(self, product_id: str) -> list[Cart]:
        """
        Find all carts that contain a specific product.
        
        This is the key query for Price Drop Alert scenario:
        "Find all customers who have this product in their cart"
        
        In event-sourced: Notification service makes this query
        In API-driven: Pricing service would need to make this query (cross-domain!)
        """
        self._ensure_carts_loaded()
        return [
            cart for cart in self._carts.values()
            if cart.contains_product(product_id)
        ]
    
    # =========================================================================
    # Notification Preference Operations
    # =========================================================================
    
    def get_notification_preferences(self, customer_id: str) -> Optional[NotificationPreference]:
        """
        Get a customer's notification preferences.
        
        Used to determine:
        1. Which notification types the customer wants
        2. Which channels (email/SMS) to use for each type
        """
        self._ensure_preferences_loaded()
        return self._preferences.get(customer_id)
    
    def get_all_preferences(self) -> list[NotificationPreference]:
        """Get all notification preferences."""
        self._ensure_preferences_loaded()
        return list(self._preferences.values())
    
    def customer_wants_notification(
        self, 
        customer_id: str, 
        notification_type: str, 
        channel: str
    ) -> bool:
        """
        Check if a customer wants a specific notification type on a specific channel.
        
        Convenience method that handles missing preferences gracefully.
        """
        prefs = self.get_notification_preferences(customer_id)
        if not prefs:
            return False
        return prefs.wants_notification(notification_type, channel)
    
    # =========================================================================
    # Payment Operations
    # =========================================================================
    
    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get a payment by ID."""
        self._ensure_payments_loaded()
        return self._payments.get(payment_id)
    
    def get_payments_by_order(self, order_id: str) -> list[Payment]:
        """Get all payment attempts for an order."""
        self._ensure_payments_loaded()
        return [p for p in self._payments.values() if p.order_id == order_id]
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def reload(self):
        """
        Force reload all data from JSON files.
        
        Useful for tests that modify fixture files.
        """
        self._customers = None
        self._products = None
        self._orders = None
        self._carts = None
        self._preferences = None
        self._payments = None
    
    def get_customer_with_preferences(self, customer_id: str) -> tuple[Optional[Customer], Optional[NotificationPreference]]:
        """
        Get both customer and their preferences in one call.
        
        Convenience method that simulates what would be two API calls
        in a real microservices environment.
        """
        return (
            self.get_customer(customer_id),
            self.get_notification_preferences(customer_id),
        )


# Module-level singleton for convenience
# In tests, create a new DataStore instance with test fixtures
_default_store: Optional[DataStore] = None


def get_data_store() -> DataStore:
    """Get the default data store singleton."""
    global _default_store
    if _default_store is None:
        _default_store = DataStore()
    return _default_store
