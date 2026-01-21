"""
Notification message templates.

This module provides templates for all notification types. Templates support
variable substitution using Python's string formatting.

Design decisions:
- Templates are stored as simple strings with {variable} placeholders
- Separate templates for email (longer) and SMS (shorter, 160 char limit)
- Templates are organized by notification type
- Both approaches use the same templates for fair comparison

In a production system, templates might be:
- Stored in a database for runtime editing
- Localized for different languages
- Rendered with a proper templating engine (Jinja2)
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class NotificationType(str, Enum):
    """
    Supported notification types.
    
    Each type corresponds to a business event that triggers a notification.
    """
    # Simple scenarios
    ORDER_SHIPPED = "order_shipped"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CONFIRMED = "order_confirmed"
    
    # Medium complexity
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_SUCCESS = "payment_success"
    
    # Complex scenarios
    PRICE_DROP_ALERT = "price_drop_alert"
    ORDER_COMPLETE = "order_complete"  # All items in multi-item order shipped
    
    # Promotional
    PROMOTION_AVAILABLE = "promotion_available"


@dataclass
class NotificationTemplate:
    """
    A notification template with email and SMS variants.
    
    Email templates can be longer and include more detail.
    SMS templates must be concise (ideally under 160 characters).
    """
    notification_type: NotificationType
    email_subject: str
    email_body: str
    sms_body: str
    
    def render_email(self, **kwargs) -> tuple[str, str]:
        """
        Render the email template with provided variables.
        
        Returns:
            Tuple of (subject, body)
        """
        return (
            self.email_subject.format(**kwargs),
            self.email_body.format(**kwargs),
        )
    
    def render_sms(self, **kwargs) -> str:
        """Render the SMS template with provided variables."""
        return self.sms_body.format(**kwargs)


# =============================================================================
# Template Definitions
# =============================================================================

TEMPLATES: dict[NotificationType, NotificationTemplate] = {
    
    # -------------------------------------------------------------------------
    # Order Lifecycle Notifications
    # -------------------------------------------------------------------------
    
    NotificationType.ORDER_CONFIRMED: NotificationTemplate(
        notification_type=NotificationType.ORDER_CONFIRMED,
        email_subject="Order Confirmed - #{order_id}",
        email_body="""Hi {customer_name},

Thank you for your order! We've received your order #{order_id} and are processing it now.

Order Total: ${total_amount:.2f}

We'll send you another notification when your order ships.

Thanks for shopping with us!
""",
        sms_body="Order #{order_id} confirmed! Total: ${total_amount:.2f}. We'll notify you when it ships.",
    ),
    
    NotificationType.ORDER_SHIPPED: NotificationTemplate(
        notification_type=NotificationType.ORDER_SHIPPED,
        email_subject="Your Order Has Shipped! - #{order_id}",
        email_body="""Hi {customer_name},

Great news! Your order #{order_id} has shipped and is on its way.

Shipped Items:
{item_list}

You can track your package using the carrier's tracking system.

Thanks for shopping with us!
""",
        sms_body="Your order #{order_id} has shipped! Track your package for delivery updates.",
    ),
    
    NotificationType.ORDER_DELIVERED: NotificationTemplate(
        notification_type=NotificationType.ORDER_DELIVERED,
        email_subject="Your Order Has Been Delivered - #{order_id}",
        email_body="""Hi {customer_name},

Your order #{order_id} has been delivered!

We hope you love your purchase. If you have any questions or concerns, please don't hesitate to contact us.

Thanks for shopping with us!
""",
        sms_body="Order #{order_id} delivered! Thanks for shopping with us.",
    ),
    
    NotificationType.ORDER_COMPLETE: NotificationTemplate(
        notification_type=NotificationType.ORDER_COMPLETE,
        email_subject="All Items From Your Order Have Shipped! - #{order_id}",
        email_body="""Hi {customer_name},

All items from your order #{order_id} have now shipped!

Complete Order Contents:
{item_list}

All items are on their way to you. Thanks for your patience with items that shipped separately.

Thanks for shopping with us!
""",
        sms_body="All {item_count} items from order #{order_id} have shipped! Your complete order is on the way.",
    ),
    
    # -------------------------------------------------------------------------
    # Payment Notifications
    # -------------------------------------------------------------------------
    
    NotificationType.PAYMENT_SUCCESS: NotificationTemplate(
        notification_type=NotificationType.PAYMENT_SUCCESS,
        email_subject="Payment Received - Order #{order_id}",
        email_body="""Hi {customer_name},

We've successfully processed your payment of ${amount:.2f} for order #{order_id}.

Thank you for your purchase!
""",
        sms_body="Payment of ${amount:.2f} received for order #{order_id}. Thank you!",
    ),
    
    NotificationType.PAYMENT_FAILED: NotificationTemplate(
        notification_type=NotificationType.PAYMENT_FAILED,
        email_subject="Payment Issue - Action Required for Order #{order_id}",
        email_body="""Hi {customer_name},

We were unable to process your payment of ${amount:.2f} for order #{order_id}.

Reason: {failure_reason}

Please update your payment method or try again to avoid delays with your order.

If you need assistance, our support team is here to help.
""",
        sms_body="Payment of ${amount:.2f} failed for order #{order_id}. Please update your payment method.",
    ),
    
    # -------------------------------------------------------------------------
    # Price Drop Alert (Complex Scenario)
    # -------------------------------------------------------------------------
    
    NotificationType.PRICE_DROP_ALERT: NotificationTemplate(
        notification_type=NotificationType.PRICE_DROP_ALERT,
        email_subject="Price Drop Alert: {product_name} is now ${new_price:.2f}!",
        email_body="""Hi {customer_name},

Great news! An item in your cart just dropped in price.

{product_name}
Was: ${old_price:.2f}
Now: ${new_price:.2f}
You save: ${savings:.2f} ({discount_percent:.0f}% off)

Don't miss out - prices can change at any time!

Complete your purchase now to lock in this lower price.
""",
        sms_body="{product_name} in your cart dropped from ${old_price:.2f} to ${new_price:.2f}! Save ${savings:.2f} now.",
    ),
    
    # -------------------------------------------------------------------------
    # Promotional Notifications
    # -------------------------------------------------------------------------
    
    NotificationType.PROMOTION_AVAILABLE: NotificationTemplate(
        notification_type=NotificationType.PROMOTION_AVAILABLE,
        email_subject="Special Offer: {promotion_name}",
        email_body="""Hi {customer_name},

You're eligible for a special promotion!

{promotion_name}
{promotion_description}

Valid until: {end_date}

Use code: {promo_code}

Don't miss out on these savings!
""",
        sms_body="Special offer: {promotion_name}! Use code {promo_code}. Valid until {end_date}.",
    ),
}


# =============================================================================
# Template Access Functions
# =============================================================================

def get_template(notification_type: NotificationType) -> Optional[NotificationTemplate]:
    """Get a template by notification type."""
    return TEMPLATES.get(notification_type)


def render_notification(
    notification_type: NotificationType,
    channel: str,
    **context
) -> tuple[Optional[str], str]:
    """
    Render a notification for a specific channel.
    
    Args:
        notification_type: The type of notification
        channel: "email" or "sms"
        **context: Variables to substitute in the template
    
    Returns:
        For email: (subject, body)
        For SMS: (None, body)
    
    Raises:
        ValueError: If template not found or channel invalid
    """
    template = get_template(notification_type)
    if not template:
        raise ValueError(f"No template found for notification type: {notification_type}")
    
    if channel == "email":
        return template.render_email(**context)
    elif channel == "sms":
        return (None, template.render_sms(**context))
    else:
        raise ValueError(f"Unknown channel: {channel}")


def format_item_list(items: list[dict]) -> str:
    """
    Format a list of items for inclusion in email templates.
    
    Args:
        items: List of dicts with 'name', 'quantity', and optionally 'price'
    
    Returns:
        Formatted string for email body
    """
    lines = []
    for item in items:
        if "price" in item:
            lines.append(f"  - {item['name']} (x{item['quantity']}) - ${item['price']:.2f}")
        else:
            lines.append(f"  - {item['name']} (x{item['quantity']})")
    return "\n".join(lines)
