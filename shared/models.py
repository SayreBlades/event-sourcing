"""
Domain models for the notification architecture demo.

These models are inspired by TM Forum (TMF) Open APIs but simplified for demonstration.
They represent the core entities that would exist in a BSS/e-commerce platform.

Design decisions:
- Using Pydantic for validation and serialization
- Models are intentionally simple - real TMF models are much more complex
- Each model includes fields needed for our notification scenarios
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Enums - Status values used across the domain
# =============================================================================

class OrderStatus(str, Enum):
    """
    Order lifecycle states.
    Simplified from TMF622 which has many more states.
    """
    PENDING = "PENDING"           # Order created, awaiting processing
    PROCESSING = "PROCESSING"     # Order is being processed
    SHIPPED = "SHIPPED"           # Order has been shipped
    DELIVERED = "DELIVERED"       # Order has been delivered
    CANCELLED = "CANCELLED"       # Order was cancelled


class LineItemStatus(str, Enum):
    """
    Individual line item states within an order.
    Important for the "Order Complete" scenario where items ship separately.
    """
    PENDING = "PENDING"           # Not yet processed
    PROCESSING = "PROCESSING"     # Being prepared
    SHIPPED = "SHIPPED"           # This item has shipped
    DELIVERED = "DELIVERED"       # This item has been delivered
    CANCELLED = "CANCELLED"       # This item was cancelled


class PaymentStatus(str, Enum):
    """Payment attempt states."""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


class CustomerSegment(str, Enum):
    """
    Customer loyalty/value segments.
    Used for eligibility rules in complex notification scenarios.
    """
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


# =============================================================================
# Core Domain Models
# =============================================================================

class Customer(BaseModel):
    """
    Customer entity - the recipient of notifications.
    
    In a real system, this would come from a Customer Management system (TMF629).
    We include contact info and segment for notification routing and eligibility.
    """
    id: str = Field(..., description="Unique customer identifier")
    name: str = Field(..., description="Customer display name")
    email: str = Field(..., description="Primary email address")
    phone: str = Field(..., description="Primary phone number for SMS")
    segment: CustomerSegment = Field(
        default=CustomerSegment.BRONZE,
        description="Loyalty segment - affects notification eligibility"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(use_enum_values=True)


class Product(BaseModel):
    """
    Product entity from the catalog.
    
    In a real system, this would come from Product Catalog (TMF620).
    We track price for the "Price Drop Alert" scenario.
    """
    id: str = Field(..., description="Unique product identifier (SKU)")
    name: str = Field(..., description="Product display name")
    price: float = Field(..., ge=0, description="Current price")
    category: str = Field(..., description="Product category")
    description: Optional[str] = Field(default=None)
    
    
class LineItem(BaseModel):
    """
    A single item within an order.
    
    Tracks individual item status for the "Order Complete" scenario
    where different items in an order may ship at different times.
    """
    product_id: str = Field(..., description="Reference to product")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    unit_price: float = Field(..., ge=0, description="Price at time of order")
    status: LineItemStatus = Field(
        default=LineItemStatus.PENDING,
        description="Fulfillment status of this specific item"
    )
    shipped_at: Optional[datetime] = Field(
        default=None,
        description="When this item was shipped (if applicable)"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class Order(BaseModel):
    """
    Order entity representing a customer purchase.
    
    In a real system, this would come from Order Management (TMF622).
    Contains line items that can have independent fulfillment states.
    """
    id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Reference to customer")
    status: OrderStatus = Field(
        default=OrderStatus.PENDING,
        description="Overall order status"
    )
    line_items: list[LineItem] = Field(
        default_factory=list,
        description="Items in this order"
    )
    total_amount: float = Field(..., ge=0, description="Order total")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    
    model_config = ConfigDict(use_enum_values=True)
    
    def all_items_shipped_or_delivered(self) -> bool:
        """
        Check if all line items have been shipped or delivered.
        Used for the "Order Complete" notification scenario.
        """
        if not self.line_items:
            return False
        return all(
            item.status in (LineItemStatus.SHIPPED, LineItemStatus.DELIVERED)
            for item in self.line_items
        )
    
    def get_pending_items_count(self) -> int:
        """Count items that haven't shipped yet."""
        return sum(
            1 for item in self.line_items
            if item.status in (LineItemStatus.PENDING, LineItemStatus.PROCESSING)
        )


class CartItem(BaseModel):
    """A single item in a customer's shopping cart."""
    product_id: str = Field(..., description="Reference to product")
    quantity: int = Field(..., ge=1, description="Quantity in cart")
    added_at: datetime = Field(default_factory=datetime.utcnow)


class Cart(BaseModel):
    """
    Shopping cart entity.
    
    Used for the "Price Drop Alert" scenario - we notify customers
    when items in their cart have a price reduction.
    """
    customer_id: str = Field(..., description="Cart owner")
    items: list[CartItem] = Field(
        default_factory=list,
        description="Items currently in cart"
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def contains_product(self, product_id: str) -> bool:
        """Check if a specific product is in this cart."""
        return any(item.product_id == product_id for item in self.items)
    
    def get_product_ids(self) -> list[str]:
        """Get all product IDs in this cart."""
        return [item.product_id for item in self.items]


# =============================================================================
# Notification Preferences
# =============================================================================

class ChannelPreferences(BaseModel):
    """
    Per-channel opt-in settings for a notification type.
    Customers can choose to receive notifications via email, SMS, or both.
    """
    email: bool = Field(default=True, description="Receive via email")
    sms: bool = Field(default=False, description="Receive via SMS")


class NotificationPreference(BaseModel):
    """
    Customer notification preferences.
    
    This is a simplified model - real systems often have more granular controls.
    Maps notification types to channel preferences.
    
    Notification types:
    - order_updates: Order status changes (shipped, delivered, etc.)
    - price_alerts: Price drop notifications for cart/wishlist items
    - promotions: Marketing and promotional messages
    - payment_alerts: Payment success/failure notifications
    """
    customer_id: str = Field(..., description="Reference to customer")
    preferences: dict[str, ChannelPreferences] = Field(
        default_factory=lambda: {
            "order_updates": ChannelPreferences(email=True, sms=True),
            "price_alerts": ChannelPreferences(email=True, sms=False),
            "promotions": ChannelPreferences(email=True, sms=False),
            "payment_alerts": ChannelPreferences(email=True, sms=True),
        },
        description="Notification type to channel preference mapping"
    )
    
    def get_channels_for_type(self, notification_type: str) -> list[str]:
        """
        Get the list of channels the customer wants for a notification type.
        Returns empty list if the notification type is not configured.
        """
        pref = self.preferences.get(notification_type)
        if not pref:
            return []
        
        channels = []
        if pref.email:
            channels.append("email")
        if pref.sms:
            channels.append("sms")
        return channels
    
    def wants_notification(self, notification_type: str, channel: str) -> bool:
        """Check if customer wants this notification type on this channel."""
        pref = self.preferences.get(notification_type)
        if not pref:
            return False
        return getattr(pref, channel, False)


# =============================================================================
# Payment (for Payment Failed scenario)
# =============================================================================

class Payment(BaseModel):
    """
    Payment attempt record.
    
    Used for the "Payment Failed" notification scenario.
    """
    id: str = Field(..., description="Unique payment identifier")
    order_id: str = Field(..., description="Associated order")
    customer_id: str = Field(..., description="Customer making payment")
    amount: float = Field(..., ge=0, description="Payment amount")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for failure if status is FAILED"
    )
    attempt_number: int = Field(default=1, description="Which attempt this is")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(use_enum_values=True)
