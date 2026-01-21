"""
Pricing service simulator for the API-driven approach.

This service manages product prices AND handles price drop notifications.

KEY INSIGHT FOR THE DEMO:
In API-driven approach, the pricing service must:
1. Update the price (its core responsibility)
2. Query cart data to find affected customers (CROSS-DOMAIN!)
3. Query customer preferences (CROSS-DOMAIN!)
4. Check segment eligibility (CROSS-DOMAIN!)
5. Call notification API for each eligible customer

Compare to event_sourced/services/pricing.py:
- Event-sourced: Just publishes "price changed" event
- API-driven: Must do all the eligibility logic itself

This demonstrates the KEY TRADEOFF:
- PRO: Explicit control, can see all logic in one place
- CON: Pricing service now depends on cart, customer, and notification services
- CON: Pricing service must understand notification eligibility rules
- CON: If eligibility rules change, pricing service must change
"""

import logging
from typing import Optional

from api_driven.notification_api import NotificationAPI
from api_driven.models import (
    NotificationRequest,
    NotificationType,
    BulkNotificationRequest,
)
from shared.data_store import DataStore, get_data_store

logger = logging.getLogger("pricing_service_api")

# Segments eligible for price drop alerts
# NOTE: In API-driven, the PRICING SERVICE must know this business rule!
# In event-sourced, this lives in the notification service.
PRICE_ALERT_ELIGIBLE_SEGMENTS = {"gold", "platinum"}


class PricingService:
    """
    Simulated pricing service that handles price drop notifications.
    
    This demonstrates the complexity of API-driven approach for cross-cutting concerns.
    
    Compare the dependencies:
    - Event-sourced PricingService: depends on EventBus, DataStore (products only)
    - API-driven PricingService: depends on NotificationAPI, DataStore (products, carts, customers, preferences)
    
    The pricing service has become MUCH more complex because it must handle
    notification logic that spans multiple domains.
    """
    
    def __init__(
        self,
        notification_api: Optional[NotificationAPI] = None,
        data_store: Optional[DataStore] = None,
    ):
        """
        Initialize the pricing service.
        
        Note the dependencies:
        - notification_api: To send notifications (wouldn't exist in event-sourced)
        - data_store: To query products, carts, customers, preferences
        """
        self.notification_api = notification_api or NotificationAPI()
        self.data_store = data_store or get_data_store()
    
    def update_price(self, product_id: str, new_price: float) -> bool:
        """
        Update a product's price and notify eligible customers.
        
        This method demonstrates why API-driven approach creates coupling:
        
        1. Core pricing logic (update price)
        2. Cross-domain queries (carts, customers, preferences)
        3. Business rules (eligibility, alert types)
        4. Notification orchestration
        
        All of this is mixed together in one service!
        """
        product = self.data_store.get_product(product_id)
        if not product:
            logger.error(f"Product not found: {product_id}")
            return False
        
        previous_price = product.price
        
        # Don't do anything if price hasn't changed
        if previous_price == new_price:
            logger.info(f"Price unchanged for {product_id}: ${new_price}")
            return True
        
        # Step 1: Update the price (core responsibility)
        updated_product = self.data_store.update_product_price(product_id, new_price)
        if not updated_product:
            return False
        
        is_price_drop = new_price < previous_price
        change_type = "decreased" if is_price_drop else "increased"
        
        logger.info(
            f"Price {change_type} for {product.name}: "
            f"${previous_price:.2f} -> ${new_price:.2f}"
        )
        
        # Step 2-5: Handle price drop notifications
        # THIS IS WHERE THE COMPLEXITY LIVES IN API-DRIVEN APPROACH
        if is_price_drop:
            self._send_price_drop_notifications(
                product_id=product_id,
                product_name=product.name,
                previous_price=previous_price,
                new_price=new_price,
            )
        
        return True
    
    def _send_price_drop_notifications(
        self,
        product_id: str,
        product_name: str,
        previous_price: float,
        new_price: float,
    ) -> None:
        """
        Find eligible customers and send price drop notifications.
        
        THIS METHOD SHOWS THE PROBLEM WITH API-DRIVEN FOR CROSS-CUTTING CONCERNS:
        
        The pricing service must:
        1. Query CART data (another domain!) to find who has this product
        2. Query CUSTOMER data to get segment info
        3. Query PREFERENCE data to check opt-in status
        4. Apply BUSINESS RULES for eligibility
        5. Call NOTIFICATION API
        
        In event-sourced, ALL of this is in the notification service.
        The pricing service just publishes "price changed".
        """
        savings = previous_price - new_price
        discount_percent = (savings / previous_price) * 100
        
        # CROSS-DOMAIN QUERY #1: Find carts containing this product
        # The pricing service shouldn't need to know about carts!
        carts = self.data_store.get_carts_containing_product(product_id)
        
        logger.info(f"Found {len(carts)} carts containing {product_name}")
        
        notifications_sent = 0
        customers_skipped_prefs = 0
        customers_skipped_segment = 0
        
        for cart in carts:
            customer_id = cart.customer_id
            
            # CROSS-DOMAIN QUERY #2: Get customer info
            customer = self.data_store.get_customer(customer_id)
            if not customer:
                continue
            
            # CROSS-DOMAIN QUERY #3: Get notification preferences
            prefs = self.data_store.get_notification_preferences(customer_id)
            
            # BUSINESS RULE #1: Check if opted into price alerts
            # The pricing service must know about notification preferences!
            if not prefs or not prefs.get_channels_for_type("price_alerts"):
                logger.debug(f"Customer {customer_id} has not opted into price alerts")
                customers_skipped_prefs += 1
                continue
            
            # BUSINESS RULE #2: Check segment eligibility
            # The pricing service must know eligibility rules!
            if customer.segment not in PRICE_ALERT_ELIGIBLE_SEGMENTS:
                logger.debug(
                    f"Customer {customer_id} segment '{customer.segment}' "
                    f"not in eligible segments"
                )
                customers_skipped_segment += 1
                continue
            
            # Finally, call the notification API
            try:
                request = NotificationRequest(
                    notification_type=NotificationType.PRICE_DROP_ALERT,
                    customer_id=customer_id,
                    context={
                        "product_name": product_name,
                        "old_price": previous_price,
                        "new_price": new_price,
                        "savings": savings,
                        "discount_percent": discount_percent,
                    },
                )
                
                response = self.notification_api.send_notification(request)
                if response.success:
                    notifications_sent += 1
                    logger.info(f"Sent price drop alert to {customer_id}")
                    
            except Exception as e:
                logger.error(f"Failed to notify {customer_id}: {e}")
        
        logger.info(
            f"Price drop notifications complete: "
            f"{notifications_sent} sent, "
            f"{customers_skipped_prefs} skipped (prefs), "
            f"{customers_skipped_segment} skipped (segment)"
        )
    
    def apply_discount(self, product_id: str, discount_percent: float) -> bool:
        """Apply a percentage discount to a product."""
        if discount_percent < 0 or discount_percent > 100:
            logger.error(f"Invalid discount percentage: {discount_percent}")
            return False
        
        product = self.data_store.get_product(product_id)
        if not product:
            logger.error(f"Product not found: {product_id}")
            return False
        
        new_price = product.price * (1 - discount_percent / 100)
        new_price = round(new_price, 2)
        
        logger.info(f"Applying {discount_percent}% discount to {product.name}")
        return self.update_price(product_id, new_price)
