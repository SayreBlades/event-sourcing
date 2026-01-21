"""
Billing/Payment service simulator for the event-sourced approach.

This service handles payment processing and publishes events for
payment outcomes (success, failure).

Key insight for the demo:
- Payment events include all context needed by subscribers
- The notification service handles looking up customer preferences
- This service focuses only on payment processing
"""

import logging
from typing import Optional

from event_sourced.event_bus import EventBus, get_event_bus
from event_sourced.events import payment_failed, payment_succeeded
from shared.data_store import DataStore, get_data_store

logger = logging.getLogger("billing_service")


class BillingService:
    """
    Simulated billing/payment service that publishes payment events.
    
    In a real system, this would integrate with payment processors
    (Stripe, Braintree, etc.) and handle complex payment flows.
    
    Example:
        service = BillingService()
        
        # Process a payment (might succeed or fail)
        service.process_payment(
            order_id="ord-001",
            customer_id="cust-001", 
            amount=299.99
        )
        
        # If it fails, a PaymentFailed event is published
        # The notification service will send an alert to the customer
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        data_store: Optional[DataStore] = None,
    ):
        self.event_bus = event_bus or get_event_bus()
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
        Record a successful payment and publish event.
        
        Returns:
            The payment ID
        """
        payment_id = self._generate_payment_id()
        
        logger.info(f"Payment {payment_id} succeeded: ${amount:.2f} for order {order_id}")
        
        event = payment_succeeded(
            payment_id=payment_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
        )
        self.event_bus.publish(event)
        
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
        Record a failed payment and publish event.
        
        Args:
            order_id: The order this payment was for
            customer_id: The customer making the payment
            amount: The payment amount
            failure_reason: Why the payment failed
            attempt_number: Which attempt this was (for retry tracking)
        
        Returns:
            The payment ID
        """
        payment_id = self._generate_payment_id()
        
        logger.info(
            f"Payment {payment_id} FAILED: ${amount:.2f} for order {order_id}. "
            f"Reason: {failure_reason}"
        )
        
        event = payment_failed(
            payment_id=payment_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            failure_reason=failure_reason,
            attempt_number=attempt_number,
        )
        self.event_bus.publish(event)
        
        return payment_id
