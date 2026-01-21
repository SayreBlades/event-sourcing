"""
Mock notification channels for the demo.

These channels simulate sending emails and SMS messages by logging the output.
In a real system, these would integrate with services like:
- Email: SendGrid, AWS SES, Mailgun
- SMS: Twilio, AWS SNS, Vonage

Design decisions:
- All sends are logged to console for visibility
- Channels track sent messages for test assertions
- Async-ready but synchronous for simplicity
- Channel failures can be simulated for testing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

# Configure logging for notification channels
logger = logging.getLogger("notifications")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class ChannelType(str, Enum):
    """Supported notification channels."""
    EMAIL = "email"
    SMS = "sms"


@dataclass
class NotificationResult:
    """
    Result of a notification send attempt.
    
    Captures success/failure and metadata for debugging and testing.
    """
    success: bool
    channel: ChannelType
    recipient: str
    subject: Optional[str]  # Email only
    body: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        if self.channel == ChannelType.EMAIL:
            return f"{status} EMAIL to {self.recipient}: {self.subject}"
        return f"{status} SMS to {self.recipient}: {self.body[:50]}..."


class EmailChannel:
    """
    Mock email channel.
    
    Logs email sends to console and tracks them for test assertions.
    Can simulate failures for testing error handling.
    """
    
    def __init__(self, fail_rate: float = 0.0):
        """
        Initialize the email channel.
        
        Args:
            fail_rate: Probability of send failure (0.0 to 1.0), for testing.
        """
        self.fail_rate = fail_rate
        self.sent_messages: list[NotificationResult] = []
    
    def send(
        self, 
        to: str, 
        subject: str, 
        body: str,
        from_addr: str = "notifications@ecommerce-demo.com"
    ) -> NotificationResult:
        """
        Send an email (mock implementation).
        
        Args:
            to: Recipient email address
            subject: Email subject line
            body: Email body content
            from_addr: Sender address (for logging)
        
        Returns:
            NotificationResult indicating success/failure
        """
        import random
        
        # Simulate potential failure
        if random.random() < self.fail_rate:
            result = NotificationResult(
                success=False,
                channel=ChannelType.EMAIL,
                recipient=to,
                subject=subject,
                body=body,
                error="Simulated email delivery failure",
            )
            logger.error(f"[EMAIL FAILED] To: {to} | Subject: {subject} | Error: {result.error}")
        else:
            result = NotificationResult(
                success=True,
                channel=ChannelType.EMAIL,
                recipient=to,
                subject=subject,
                body=body,
            )
            # Log with clear formatting for demo visibility
            logger.info(f"[EMAIL] To: {to} | Subject: {subject}")
            logger.debug(f"[EMAIL BODY] {body}")
        
        self.sent_messages.append(result)
        return result
    
    def get_sent_count(self) -> int:
        """Get the number of messages sent (for testing)."""
        return len(self.sent_messages)
    
    def get_successful_sends(self) -> list[NotificationResult]:
        """Get all successful sends."""
        return [m for m in self.sent_messages if m.success]
    
    def clear_history(self):
        """Clear sent message history (useful between tests)."""
        self.sent_messages.clear()
    
    def find_message_to(self, recipient: str) -> Optional[NotificationResult]:
        """Find a message sent to a specific recipient."""
        for msg in self.sent_messages:
            if msg.recipient == recipient:
                return msg
        return None


class SMSChannel:
    """
    Mock SMS channel.
    
    Logs SMS sends to console and tracks them for test assertions.
    SMS messages are typically shorter than emails.
    """
    
    # SMS typically have character limits
    MAX_LENGTH = 160
    
    def __init__(self, fail_rate: float = 0.0):
        """
        Initialize the SMS channel.
        
        Args:
            fail_rate: Probability of send failure (0.0 to 1.0), for testing.
        """
        self.fail_rate = fail_rate
        self.sent_messages: list[NotificationResult] = []
    
    def send(self, to: str, message: str) -> NotificationResult:
        """
        Send an SMS (mock implementation).
        
        Args:
            to: Recipient phone number
            message: SMS message content
        
        Returns:
            NotificationResult indicating success/failure
        """
        import random
        
        # Warn if message exceeds typical SMS length
        if len(message) > self.MAX_LENGTH:
            logger.warning(
                f"[SMS] Message length ({len(message)}) exceeds {self.MAX_LENGTH} chars, "
                "may be split into multiple messages"
            )
        
        # Simulate potential failure
        if random.random() < self.fail_rate:
            result = NotificationResult(
                success=False,
                channel=ChannelType.SMS,
                recipient=to,
                subject=None,
                body=message,
                error="Simulated SMS delivery failure",
            )
            logger.error(f"[SMS FAILED] To: {to} | Error: {result.error}")
        else:
            result = NotificationResult(
                success=True,
                channel=ChannelType.SMS,
                recipient=to,
                subject=None,
                body=message,
            )
            logger.info(f"[SMS] To: {to} | Message: {message}")
        
        self.sent_messages.append(result)
        return result
    
    def get_sent_count(self) -> int:
        """Get the number of messages sent (for testing)."""
        return len(self.sent_messages)
    
    def get_successful_sends(self) -> list[NotificationResult]:
        """Get all successful sends."""
        return [m for m in self.sent_messages if m.success]
    
    def clear_history(self):
        """Clear sent message history (useful between tests)."""
        self.sent_messages.clear()
    
    def find_message_to(self, recipient: str) -> Optional[NotificationResult]:
        """Find a message sent to a specific recipient."""
        for msg in self.sent_messages:
            if msg.recipient == recipient:
                return msg
        return None


class NotificationChannels:
    """
    Facade for all notification channels.
    
    Provides a unified interface for sending notifications and manages
    channel instances. Both approaches (event-sourced and API-driven)
    use this to actually send notifications.
    """
    
    def __init__(self, email_fail_rate: float = 0.0, sms_fail_rate: float = 0.0):
        """
        Initialize all channels.
        
        Args:
            email_fail_rate: Simulated email failure rate
            sms_fail_rate: Simulated SMS failure rate
        """
        self.email = EmailChannel(fail_rate=email_fail_rate)
        self.sms = SMSChannel(fail_rate=sms_fail_rate)
    
    def send_email(self, to: str, subject: str, body: str) -> NotificationResult:
        """Send via email channel."""
        return self.email.send(to, subject, body)
    
    def send_sms(self, to: str, message: str) -> NotificationResult:
        """Send via SMS channel."""
        return self.sms.send(to, message)
    
    def send(
        self, 
        channel: str, 
        recipient: str, 
        subject: Optional[str], 
        body: str
    ) -> NotificationResult:
        """
        Send via a named channel.
        
        Args:
            channel: "email" or "sms"
            recipient: Email address or phone number
            subject: Subject line (email only, ignored for SMS)
            body: Message content
        
        Returns:
            NotificationResult
        
        Raises:
            ValueError: If channel is not recognized
        """
        if channel == "email":
            return self.email.send(recipient, subject or "(no subject)", body)
        elif channel == "sms":
            return self.sms.send(recipient, body)
        else:
            raise ValueError(f"Unknown channel: {channel}")
    
    def get_all_sent_messages(self) -> list[NotificationResult]:
        """Get all sent messages across all channels."""
        return self.email.sent_messages + self.sms.sent_messages
    
    def get_total_sent_count(self) -> int:
        """Get total number of messages sent across all channels."""
        return self.email.get_sent_count() + self.sms.get_sent_count()
    
    def clear_all_history(self):
        """Clear history for all channels."""
        self.email.clear_history()
        self.sms.clear_history()
