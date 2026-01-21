"""
Tests for notification channels.

These tests verify that the mock email and SMS channels
correctly log messages and track sent notifications.
"""

import pytest
from shared.channels import (
    EmailChannel,
    SMSChannel,
    NotificationChannels,
    ChannelType,
    NotificationResult,
)


class TestEmailChannel:
    """Tests for the mock email channel."""
    
    def test_send_email_success(self, email_channel: EmailChannel):
        """Test successful email send."""
        result = email_channel.send(
            to="test@example.com",
            subject="Test Subject",
            body="Test body content",
        )
        
        assert result.success is True
        assert result.channel == ChannelType.EMAIL
        assert result.recipient == "test@example.com"
        assert result.subject == "Test Subject"
        assert result.body == "Test body content"
        assert result.error is None
    
    def test_tracks_sent_messages(self, email_channel: EmailChannel):
        """Test that channel tracks sent messages."""
        email_channel.send("a@example.com", "Subject A", "Body A")
        email_channel.send("b@example.com", "Subject B", "Body B")
        
        assert email_channel.get_sent_count() == 2
        
        messages = email_channel.sent_messages
        assert messages[0].recipient == "a@example.com"
        assert messages[1].recipient == "b@example.com"
    
    def test_find_message_to(self, email_channel: EmailChannel):
        """Test finding a message sent to a specific recipient."""
        email_channel.send("target@example.com", "Hello", "World")
        email_channel.send("other@example.com", "Hi", "There")
        
        found = email_channel.find_message_to("target@example.com")
        
        assert found is not None
        assert found.subject == "Hello"
    
    def test_clear_history(self, email_channel: EmailChannel):
        """Test clearing message history."""
        email_channel.send("test@example.com", "Test", "Body")
        assert email_channel.get_sent_count() == 1
        
        email_channel.clear_history()
        
        assert email_channel.get_sent_count() == 0
    
    def test_simulated_failure(self):
        """Test simulated email failure."""
        # 100% fail rate
        failing_channel = EmailChannel(fail_rate=1.0)
        
        result = failing_channel.send("test@example.com", "Test", "Body")
        
        assert result.success is False
        assert result.error is not None
        assert "failure" in result.error.lower()
    
    def test_get_successful_sends(self):
        """Test filtering to only successful sends."""
        # 50/50 fail rate - send many to get mix
        channel = EmailChannel(fail_rate=0.5)
        
        # Send 20 messages, should have mix of success/failure
        for i in range(20):
            channel.send(f"user{i}@example.com", f"Subject {i}", f"Body {i}")
        
        successful = channel.get_successful_sends()
        
        # With 50% fail rate and 20 attempts, we should have some of each
        assert len(successful) > 0
        assert len(successful) < 20
        assert all(m.success for m in successful)


class TestSMSChannel:
    """Tests for the mock SMS channel."""
    
    def test_send_sms_success(self, sms_channel: SMSChannel):
        """Test successful SMS send."""
        result = sms_channel.send(
            to="+1-555-1234",
            message="Your order has shipped!",
        )
        
        assert result.success is True
        assert result.channel == ChannelType.SMS
        assert result.recipient == "+1-555-1234"
        assert result.body == "Your order has shipped!"
        assert result.subject is None  # SMS doesn't have subject
    
    def test_tracks_sent_messages(self, sms_channel: SMSChannel):
        """Test that channel tracks sent messages."""
        sms_channel.send("+1-555-0001", "Message 1")
        sms_channel.send("+1-555-0002", "Message 2")
        
        assert sms_channel.get_sent_count() == 2
    
    def test_long_message_warning(self, sms_channel: SMSChannel, caplog):
        """Test that long messages trigger a warning."""
        long_message = "A" * 200  # Exceeds 160 char limit
        
        import logging
        with caplog.at_level(logging.WARNING):
            sms_channel.send("+1-555-1234", long_message)
        
        # Check warning was logged
        assert any("exceeds" in record.message.lower() for record in caplog.records)


class TestNotificationChannels:
    """Tests for the unified NotificationChannels facade."""
    
    def test_send_email(self, channels: NotificationChannels):
        """Test sending via email through facade."""
        result = channels.send_email(
            to="test@example.com",
            subject="Test",
            body="Test body",
        )
        
        assert result.success is True
        assert result.channel == ChannelType.EMAIL
    
    def test_send_sms(self, channels: NotificationChannels):
        """Test sending via SMS through facade."""
        result = channels.send_sms(
            to="+1-555-1234",
            message="Test message",
        )
        
        assert result.success is True
        assert result.channel == ChannelType.SMS
    
    def test_send_by_channel_name(self, channels: NotificationChannels):
        """Test sending via channel name string."""
        email_result = channels.send(
            channel="email",
            recipient="test@example.com",
            subject="Test",
            body="Body",
        )
        
        sms_result = channels.send(
            channel="sms",
            recipient="+1-555-1234",
            subject=None,  # Ignored for SMS
            body="SMS body",
        )
        
        assert email_result.success is True
        assert email_result.channel == ChannelType.EMAIL
        
        assert sms_result.success is True
        assert sms_result.channel == ChannelType.SMS
    
    def test_send_unknown_channel_raises(self, channels: NotificationChannels):
        """Test that unknown channel raises ValueError."""
        with pytest.raises(ValueError, match="Unknown channel"):
            channels.send(
                channel="pigeon",
                recipient="somewhere",
                subject="Test",
                body="Body",
            )
    
    def test_get_all_sent_messages(self, channels: NotificationChannels):
        """Test getting messages from all channels."""
        channels.send_email("email@example.com", "Subject", "Body")
        channels.send_sms("+1-555-1234", "SMS message")
        
        all_messages = channels.get_all_sent_messages()
        
        assert len(all_messages) == 2
        channels_used = [m.channel for m in all_messages]
        assert ChannelType.EMAIL in channels_used
        assert ChannelType.SMS in channels_used
    
    def test_get_total_sent_count(self, channels: NotificationChannels):
        """Test total count across all channels."""
        channels.send_email("a@example.com", "A", "A")
        channels.send_email("b@example.com", "B", "B")
        channels.send_sms("+1-555-0001", "1")
        
        assert channels.get_total_sent_count() == 3
    
    def test_clear_all_history(self, channels: NotificationChannels):
        """Test clearing history for all channels."""
        channels.send_email("test@example.com", "Test", "Body")
        channels.send_sms("+1-555-1234", "Test")
        
        assert channels.get_total_sent_count() == 2
        
        channels.clear_all_history()
        
        assert channels.get_total_sent_count() == 0


class TestNotificationResult:
    """Tests for NotificationResult."""
    
    def test_str_email_success(self):
        """Test string representation of successful email."""
        result = NotificationResult(
            success=True,
            channel=ChannelType.EMAIL,
            recipient="test@example.com",
            subject="Test Subject",
            body="Body",
        )
        
        str_repr = str(result)
        assert "✓" in str_repr
        assert "EMAIL" in str_repr
        assert "test@example.com" in str_repr
        assert "Test Subject" in str_repr
    
    def test_str_sms_failure(self):
        """Test string representation of failed SMS."""
        result = NotificationResult(
            success=False,
            channel=ChannelType.SMS,
            recipient="+1-555-1234",
            subject=None,
            body="Test message",
            error="Delivery failed",
        )
        
        str_repr = str(result)
        assert "✗" in str_repr
        assert "SMS" in str_repr
