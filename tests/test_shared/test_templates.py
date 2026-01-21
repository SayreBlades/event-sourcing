"""
Tests for notification templates.

These tests verify that templates render correctly with variable substitution.
"""

import pytest
from shared.templates import (
    NotificationType,
    NotificationTemplate,
    get_template,
    render_notification,
    format_item_list,
    TEMPLATES,
)


class TestNotificationTemplate:
    """Tests for NotificationTemplate class."""
    
    def test_render_email(self):
        """Test rendering email template with variables."""
        template = NotificationTemplate(
            notification_type=NotificationType.ORDER_SHIPPED,
            email_subject="Order {order_id} Shipped",
            email_body="Hi {customer_name}, your order {order_id} shipped!",
            sms_body="Order {order_id} shipped!",
        )
        
        subject, body = template.render_email(
            order_id="ORD-001",
            customer_name="Alice",
        )
        
        assert subject == "Order ORD-001 Shipped"
        assert "Alice" in body
        assert "ORD-001" in body
    
    def test_render_sms(self):
        """Test rendering SMS template with variables."""
        template = NotificationTemplate(
            notification_type=NotificationType.ORDER_SHIPPED,
            email_subject="Order {order_id} Shipped",
            email_body="Hi {customer_name}, your order {order_id} shipped!",
            sms_body="Order {order_id} shipped!",
        )
        
        sms = template.render_sms(order_id="ORD-001")
        
        assert sms == "Order ORD-001 shipped!"


class TestGetTemplate:
    """Tests for get_template function."""
    
    def test_get_existing_template(self):
        """Test retrieving an existing template."""
        template = get_template(NotificationType.ORDER_SHIPPED)
        
        assert template is not None
        assert template.notification_type == NotificationType.ORDER_SHIPPED
    
    def test_all_notification_types_have_templates(self):
        """Verify all notification types have corresponding templates."""
        for notification_type in NotificationType:
            template = get_template(notification_type)
            assert template is not None, f"Missing template for {notification_type}"


class TestRenderNotification:
    """Tests for render_notification function."""
    
    def test_render_order_shipped_email(self):
        """Test rendering order shipped notification for email."""
        subject, body = render_notification(
            NotificationType.ORDER_SHIPPED,
            channel="email",
            customer_name="Alice Johnson",
            order_id="ORD-001",
            item_list="  - Wireless Router (x1)",
        )
        
        assert "ORD-001" in subject
        assert "Alice Johnson" in body
        assert "shipped" in body.lower()
    
    def test_render_order_shipped_sms(self):
        """Test rendering order shipped notification for SMS."""
        subject, body = render_notification(
            NotificationType.ORDER_SHIPPED,
            channel="sms",
            order_id="ORD-001",
        )
        
        assert subject is None  # SMS has no subject
        assert "ORD-001" in body
        assert len(body) < 200  # SMS should be concise
    
    def test_render_price_drop_alert(self):
        """Test rendering price drop alert with pricing info."""
        subject, body = render_notification(
            NotificationType.PRICE_DROP_ALERT,
            channel="email",
            customer_name="Bob Smith",
            product_name="Wireless Router X500",
            old_price=149.99,
            new_price=129.99,
            savings=20.00,
            discount_percent=13,
        )
        
        assert "Wireless Router X500" in subject
        assert "$129.99" in subject
        assert "Bob Smith" in body
        assert "$149.99" in body  # Old price
        assert "$129.99" in body  # New price
        assert "$20.00" in body   # Savings
    
    def test_render_payment_failed(self):
        """Test rendering payment failed notification."""
        subject, body = render_notification(
            NotificationType.PAYMENT_FAILED,
            channel="email",
            customer_name="David Brown",
            order_id="ORD-004",
            amount=149.99,
            failure_reason="Insufficient funds",
        )
        
        assert "ORD-004" in subject
        assert "David Brown" in body
        assert "$149.99" in body
        assert "Insufficient funds" in body
    
    def test_render_order_complete(self):
        """Test rendering order complete notification."""
        subject, body = render_notification(
            NotificationType.ORDER_COMPLETE,
            channel="email",
            customer_name="Alice Johnson",
            order_id="ORD-001",
            item_list="  - Router (x1)\n  - USB Hub (x2)",
        )
        
        assert "ORD-001" in subject
        assert "Alice Johnson" in body
        assert "Router" in body
    
    def test_render_unknown_channel_raises(self):
        """Test that unknown channel raises ValueError."""
        with pytest.raises(ValueError, match="Unknown channel"):
            render_notification(
                NotificationType.ORDER_SHIPPED,
                channel="telegram",
                order_id="ORD-001",
            )


class TestFormatItemList:
    """Tests for format_item_list helper."""
    
    def test_format_items_with_price(self):
        """Test formatting items with prices."""
        items = [
            {"name": "Wireless Router", "quantity": 1, "price": 149.99},
            {"name": "USB-C Hub", "quantity": 2, "price": 79.99},
        ]
        
        result = format_item_list(items)
        
        assert "Wireless Router" in result
        assert "(x1)" in result
        assert "$149.99" in result
        assert "USB-C Hub" in result
        assert "(x2)" in result
    
    def test_format_items_without_price(self):
        """Test formatting items without prices."""
        items = [
            {"name": "Product A", "quantity": 1},
            {"name": "Product B", "quantity": 3},
        ]
        
        result = format_item_list(items)
        
        assert "Product A" in result
        assert "(x1)" in result
        assert "Product B" in result
        assert "(x3)" in result
        assert "$" not in result  # No prices


class TestTemplateContent:
    """Tests for specific template content requirements."""
    
    def test_sms_templates_are_concise(self):
        """Verify SMS templates are reasonably short."""
        # SMS has 160 char limit, templates with variables might expand
        # but the base template should be well under that
        for notification_type, template in TEMPLATES.items():
            # Check the raw template (before variable substitution)
            assert len(template.sms_body) < 200, \
                f"SMS template for {notification_type} is too long"
    
    def test_email_templates_have_greeting(self):
        """Verify email templates include a greeting."""
        for notification_type, template in TEMPLATES.items():
            # Most emails should have some form of greeting
            body_lower = template.email_body.lower()
            has_greeting = any(
                greeting in body_lower 
                for greeting in ["hi", "hello", "dear", "thank"]
            )
            assert has_greeting, \
                f"Email template for {notification_type} missing greeting"
