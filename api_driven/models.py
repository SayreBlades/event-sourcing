"""
API models for the API-driven notification approach.

These Pydantic models define the contract between calling services
and the notification API.

Design decisions:
- Request models are flexible - caller provides what they have
- Response models confirm what was sent
- NotificationType enum matches the event-sourced approach for comparison
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    """
    Types of notifications that can be requested.
    
    In API-driven approach, the CALLER must specify the notification type.
    Compare to event-sourced where the notification service decides based on events.
    """
    ORDER_SHIPPED = "ORDER_SHIPPED"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    ORDER_COMPLETE = "ORDER_COMPLETE"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PRICE_DROP_ALERT = "PRICE_DROP_ALERT"
    PROMOTION_AVAILABLE = "PROMOTION_AVAILABLE"


class NotificationRequest(BaseModel):
    """
    Request to send a notification.
    
    The calling service must provide:
    - notification_type: What kind of notification
    - customer_id: Who to notify
    - context: Data needed for the notification template
    
    Key insight for the demo:
    - The caller must know WHEN to send notifications
    - The caller must gather the context data
    - The notification service just formats and sends
    """
    notification_type: NotificationType = Field(
        ...,
        description="Type of notification to send"
    )
    customer_id: str = Field(
        ...,
        description="Customer to notify"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Context data for the notification template"
    )
    
    # Optional: caller can specify channels (otherwise use customer preferences)
    channels: Optional[list[str]] = Field(
        default=None,
        description="Specific channels to use (email, sms). If not provided, uses customer preferences."
    )


class NotificationResult(BaseModel):
    """Result of sending via a single channel."""
    channel: str
    recipient: str
    success: bool
    error: Optional[str] = None


class NotificationResponse(BaseModel):
    """
    Response from the notification API.
    
    Returns details about what was sent and to whom.
    """
    request_id: str = Field(..., description="Unique ID for this request")
    notification_type: NotificationType
    customer_id: str
    results: list[NotificationResult] = Field(
        default_factory=list,
        description="Results for each channel attempted"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def success(self) -> bool:
        """True if at least one channel succeeded."""
        return any(r.success for r in self.results)
    
    @property
    def channels_sent(self) -> int:
        """Number of channels that succeeded."""
        return sum(1 for r in self.results if r.success)


class BulkNotificationRequest(BaseModel):
    """
    Request to send notifications to multiple customers.
    
    Used for scenarios like Price Drop Alert where we need to notify
    many customers about the same thing.
    
    Key insight: In API-driven approach, the CALLER must determine
    the list of customers to notify. Compare to event-sourced where
    the notification service figures this out.
    """
    notification_type: NotificationType
    customer_ids: list[str] = Field(
        ...,
        description="List of customers to notify"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Context data (same for all customers)"
    )


class BulkNotificationResponse(BaseModel):
    """Response from bulk notification request."""
    request_id: str
    notification_type: NotificationType
    total_customers: int
    successful_customers: int
    failed_customers: int
    results: list[NotificationResponse] = Field(default_factory=list)
