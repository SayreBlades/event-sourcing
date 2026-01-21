"""
FastAPI notification service for the API-driven approach.

This API receives notification requests from other services and handles:
- Looking up customer contact information
- Looking up customer notification preferences
- Rendering message templates
- Sending via appropriate channels

Design decisions:
- Stateless API - all context must be provided in request
- Uses customer preferences to determine channels (unless overridden)
- Returns detailed results for each channel attempted

Key insight for the demo:
- This service is SIMPLER than the event-sourced NotificationService
- It doesn't subscribe to events or correlate them
- BUT: The calling services must be MORE COMPLEX
- They must determine WHEN to call and WHAT context to provide
"""

import logging
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from api_driven.models import (
    NotificationRequest,
    NotificationResponse,
    NotificationResult,
    NotificationType,
    BulkNotificationRequest,
    BulkNotificationResponse,
)
from shared.channels import NotificationChannels
from shared.data_store import DataStore, get_data_store
from shared.templates import (
    NotificationType as TemplateNotificationType,
    render_notification,
    format_item_list,
)

logger = logging.getLogger("notification_api")

# Create the FastAPI app
app = FastAPI(
    title="Notification Service API",
    description="API-driven notification service for the architecture comparison demo",
    version="1.0.0",
)

# Module-level instances (would use proper DI in production)
_channels: Optional[NotificationChannels] = None
_data_store: Optional[DataStore] = None


def get_channels() -> NotificationChannels:
    """Get the notification channels instance."""
    global _channels
    if _channels is None:
        _channels = NotificationChannels()
    return _channels


def get_store() -> DataStore:
    """Get the data store instance."""
    global _data_store
    if _data_store is None:
        _data_store = get_data_store()
    return _data_store


def reset_api_state(
    channels: Optional[NotificationChannels] = None,
    data_store: Optional[DataStore] = None,
) -> None:
    """Reset API state (for testing)."""
    global _channels, _data_store
    _channels = channels
    _data_store = data_store


# Map API notification types to template notification types
NOTIFICATION_TYPE_MAP = {
    NotificationType.ORDER_SHIPPED: TemplateNotificationType.ORDER_SHIPPED,
    NotificationType.ORDER_DELIVERED: TemplateNotificationType.ORDER_DELIVERED,
    NotificationType.ORDER_COMPLETE: TemplateNotificationType.ORDER_COMPLETE,
    NotificationType.PAYMENT_FAILED: TemplateNotificationType.PAYMENT_FAILED,
    NotificationType.PAYMENT_SUCCESS: TemplateNotificationType.PAYMENT_SUCCESS,
    NotificationType.PRICE_DROP_ALERT: TemplateNotificationType.PRICE_DROP_ALERT,
    NotificationType.PROMOTION_AVAILABLE: TemplateNotificationType.PROMOTION_AVAILABLE,
}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/notify", response_model=NotificationResponse)
def send_notification(
    request: NotificationRequest,
    channels: NotificationChannels = Depends(get_channels),
    data_store: DataStore = Depends(get_store),
) -> NotificationResponse:
    """
    Send a notification to a customer.
    
    The notification service handles:
    - Looking up customer contact info
    - Looking up customer notification preferences (if channels not specified)
    - Rendering the appropriate template
    - Sending via each enabled channel
    
    The CALLER is responsible for:
    - Deciding WHEN to send (e.g., when order ships)
    - Providing the notification type
    - Providing context data for the template
    """
    request_id = str(uuid4())
    
    logger.info(
        f"Notification request {request_id}: "
        f"type={request.notification_type}, customer={request.customer_id}"
    )
    
    # Look up customer
    customer = data_store.get_customer(request.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer not found: {request.customer_id}")
    
    # Determine which channels to use
    if request.channels:
        channels_to_use = request.channels
    else:
        # Use customer preferences
        prefs = data_store.get_notification_preferences(request.customer_id)
        if prefs:
            # Map notification type to preference key
            pref_key = _get_preference_key(request.notification_type)
            channels_to_use = prefs.get_channels_for_type(pref_key)
        else:
            channels_to_use = ["email"]  # Default
    
    if not channels_to_use:
        logger.info(f"Customer {request.customer_id} has disabled this notification type")
        return NotificationResponse(
            request_id=request_id,
            notification_type=request.notification_type,
            customer_id=request.customer_id,
            results=[],
        )
    
    # Get the template type
    template_type = NOTIFICATION_TYPE_MAP.get(request.notification_type)
    if not template_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown notification type: {request.notification_type}"
        )
    
    # Build context with customer name
    context = {"customer_name": customer.name, **request.context}
    
    # Send via each channel
    results = []
    for channel in channels_to_use:
        try:
            subject, body = render_notification(template_type, channel, **context)
            
            if channel == "email":
                result = channels.send_email(customer.email, subject, body)
                results.append(NotificationResult(
                    channel="email",
                    recipient=customer.email,
                    success=result.success,
                    error=result.error,
                ))
            elif channel == "sms":
                result = channels.send_sms(customer.phone, body)
                results.append(NotificationResult(
                    channel="sms",
                    recipient=customer.phone,
                    success=result.success,
                    error=result.error,
                ))
        except Exception as e:
            logger.error(f"Failed to send {channel} notification: {e}")
            results.append(NotificationResult(
                channel=channel,
                recipient=customer.email if channel == "email" else customer.phone,
                success=False,
                error=str(e),
            ))
    
    return NotificationResponse(
        request_id=request_id,
        notification_type=request.notification_type,
        customer_id=request.customer_id,
        results=results,
    )


@app.post("/notify/bulk", response_model=BulkNotificationResponse)
def send_bulk_notification(
    request: BulkNotificationRequest,
    channels: NotificationChannels = Depends(get_channels),
    data_store: DataStore = Depends(get_store),
) -> BulkNotificationResponse:
    """
    Send the same notification to multiple customers.
    
    Used for scenarios like Price Drop Alert where many customers
    need to be notified about the same thing.
    
    Key insight: In API-driven approach, the CALLER must determine
    which customers to notify. The notification service just sends.
    """
    request_id = str(uuid4())
    results = []
    successful = 0
    failed = 0
    
    for customer_id in request.customer_ids:
        try:
            single_request = NotificationRequest(
                notification_type=request.notification_type,
                customer_id=customer_id,
                context=request.context,
            )
            response = send_notification(single_request, channels, data_store)
            results.append(response)
            if response.success:
                successful += 1
            else:
                failed += 1
        except HTTPException:
            failed += 1
        except Exception as e:
            logger.error(f"Failed to notify {customer_id}: {e}")
            failed += 1
    
    return BulkNotificationResponse(
        request_id=request_id,
        notification_type=request.notification_type,
        total_customers=len(request.customer_ids),
        successful_customers=successful,
        failed_customers=failed,
        results=results,
    )


def _get_preference_key(notification_type: NotificationType) -> str:
    """Map notification type to preference key."""
    mapping = {
        NotificationType.ORDER_SHIPPED: "order_updates",
        NotificationType.ORDER_DELIVERED: "order_updates",
        NotificationType.ORDER_COMPLETE: "order_updates",
        NotificationType.PAYMENT_FAILED: "payment_alerts",
        NotificationType.PAYMENT_SUCCESS: "payment_alerts",
        NotificationType.PRICE_DROP_ALERT: "price_alerts",
        NotificationType.PROMOTION_AVAILABLE: "promotions",
    }
    return mapping.get(notification_type, "order_updates")


# Convenience class for non-FastAPI usage (testing, scripts)
class NotificationAPI:
    """
    Wrapper class for using the notification API programmatically.
    
    This is used by the service simulators in tests and demos.
    """
    
    def __init__(
        self,
        channels: Optional[NotificationChannels] = None,
        data_store: Optional[DataStore] = None,
    ):
        self.channels = channels or NotificationChannels()
        self.data_store = data_store or get_data_store()
    
    def send_notification(self, request: NotificationRequest) -> NotificationResponse:
        """Send a single notification."""
        # Temporarily set module state for the API function
        old_channels, old_store = _channels, _data_store
        reset_api_state(self.channels, self.data_store)
        try:
            return send_notification(request, self.channels, self.data_store)
        finally:
            reset_api_state(old_channels, old_store)
    
    def send_bulk_notification(self, request: BulkNotificationRequest) -> BulkNotificationResponse:
        """Send bulk notifications."""
        old_channels, old_store = _channels, _data_store
        reset_api_state(self.channels, self.data_store)
        try:
            return send_bulk_notification(request, self.channels, self.data_store)
        finally:
            reset_api_state(old_channels, old_store)
