"""
Billing/Payment service simulator for the API-driven approach.

This service handles payment processing and calls the notification API
for payment-related notifications.

Compare to event-sourced where billing just publishes events.
"""

import logging
from typing import Optional

from api_driven.notification_api import NotificationAPI
from api_driven.models import NotificationRequest, NotificationType
from shared.data_store import DataStore, get_data_store

logger = logging.getLogger("billing_service_api")


class BillingService:
    """
    Simulated billing/payment service that calls notification API.
    
    Unlike the event-sourced version, this service must:
    - Decide when to send notifications
    - Call the notification API directly
    """
    
    def __init__(
        self,
        notification_api: Optional[NotificationAPI] = None,
        data_store: Optional[DataStore] = None,
    ):
        self.notification_api = notification_api or NotificationAPI()
        self.data_store = data_store or get_data_store()
        self._payment_counter = 0
    
    def _generate_payment_id(self) -> str:
        """Generate a unique payment ID."""
        self._payment_counter += 1
        return f"pay-{self._payment_counter:04d}"
    
    def process_payment_success(
        self,
        order_id: str,
        customer_id: str,
        amount: float,
    ) -> str:
        """
        Record a successful payment and notify customer.
        
        Returns:
            The payment ID
        """
        payment_id = self._generate_payment_id()
        
        logger.info(f"Payment {payment_id} succeeded: ${amount:.2f} for order {order_id}")
        
        # Call notification API
        try:
            request = NotificationRequest(
                notification_type=NotificationType.PAYMENT_SUCCESS,
                customer_id=customer_id,
                context={
                    "order_id": order_id,
                    "amount": amount,
                },
            )
            self.notification_api.send_notification(request)
        except Exception as e:
            logger.error(f"Failed to send payment success notification: {e}")
        
        return payment_id
    
    def process_payment_failure(
        self,
        order_id: str,
        customer_id: str,
        amount: float,
        failure_reason: str,
        attempt_number: int = 1,
    ) -> str:
        """
        Record a failed payment and notify customer.
        
        Args:
            order_id: The order this payment was for
            customer_id: The customer making the payment
            amount: The payment amount
            failure_reason: Why the payment failed
            attempt_number: Which attempt this was
        
        Returns:
            The payment ID
        """
        payment_id = self._generate_payment_id()
        
        logger.info(
            f"Payment {payment_id} FAILED: ${amount:.2f} for order {order_id}. "
            f"Reason: {failure_reason}"
        )
        
        # Call notification API
        try:
            request = NotificationRequest(
                notification_type=NotificationType.PAYMENT_FAILED,
                customer_id=customer_id,
                context={
                    "order_id": order_id,
                    "amount": amount,
                    "failure_reason": failure_reason,
                },
            )
            self.notification_api.send_notification(request)
        except Exception as e:
            logger.error(f"Failed to send payment failure notification: {e}")
        
        return payment_id
