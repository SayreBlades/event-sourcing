"""
Pricing service simulator for the event-sourced approach.

This service manages product prices and publishes events when prices change.
It represents what a real pricing/catalog system would do.

Key insight for the demo:
- This service ONLY publishes PriceChanged events
- It does NOT know about notifications, carts, or customer preferences
- The notification service handles all the complex logic:
  - Who has this product in their cart?
  - Who has opted into price alerts?
  - Who is in an eligible segment?
- This keeps the pricing service simple and focused
"""

import logging
from typing import Optional

from event_sourced.event_bus import EventBus, get_event_bus
from event_sourced.events import price_changed
from shared.data_store import DataStore, get_data_store

logger = logging.getLogger("pricing_service")


class PricingService:
    """
    Simulated pricing service that publishes price change events.
    
    In a real system, this would be part of a Product Catalog service
    with its own database. Price changes might come from:
    - Manual updates by merchandising team
    - Automated competitive pricing
    - Promotional campaigns
    - Dynamic pricing algorithms
    
    Example:
        service = PricingService()
        
        # Drop the price - this publishes an event
        service.update_price("prod-001", 129.99)
        
        # The notification service will handle:
        # - Finding customers with this product in cart
        # - Checking their price alert preferences
        # - Checking segment eligibility
        # - Sending notifications
        # 
        # But this service knows nothing about any of that!
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        data_store: Optional[DataStore] = None,
    ):
        """
        Initialize the pricing service.
        
        Args:
            event_bus: Event bus for publishing events
            data_store: Data store for product data
        """
        self.event_bus = event_bus or get_event_bus()
        self.data_store = data_store or get_data_store()
    
    def update_price(self, product_id: str, new_price: float) -> bool:
        """
        Update a product's price and publish an event.
        
        Args:
            product_id: The product to update
            new_price: The new price
        
        Returns:
            True if successful, False if product not found
        """
        product = self.data_store.get_product(product_id)
        if not product:
            logger.error(f"Product not found: {product_id}")
            return False
        
        previous_price = product.price
        
        # Don't publish event if price hasn't changed
        if previous_price == new_price:
            logger.info(f"Price unchanged for {product_id}: ${new_price}")
            return True
        
        # Update the price in the data store
        updated_product = self.data_store.update_product_price(product_id, new_price)
        if not updated_product:
            return False
        
        change_type = "decreased" if new_price < previous_price else "increased"
        logger.info(
            f"Price {change_type} for {product.name}: "
            f"${previous_price:.2f} -> ${new_price:.2f}"
        )
        
        # Publish the event
        # Note: We include product_name so subscribers don't need to look it up
        event = price_changed(
            product_id=product_id,
            product_name=product.name,
            previous_price=previous_price,
            new_price=new_price,
        )
        self.event_bus.publish(event)
        
        return True
    
    def apply_discount(self, product_id: str, discount_percent: float) -> bool:
        """
        Apply a percentage discount to a product.
        
        Convenience method that calculates the new price and updates it.
        
        Args:
            product_id: The product to discount
            discount_percent: Discount as a percentage (e.g., 20 for 20% off)
        
        Returns:
            True if successful, False otherwise
        """
        if discount_percent < 0 or discount_percent > 100:
            logger.error(f"Invalid discount percentage: {discount_percent}")
            return False
        
        product = self.data_store.get_product(product_id)
        if not product:
            logger.error(f"Product not found: {product_id}")
            return False
        
        new_price = product.price * (1 - discount_percent / 100)
        new_price = round(new_price, 2)  # Round to cents
        
        logger.info(f"Applying {discount_percent}% discount to {product.name}")
        return self.update_price(product_id, new_price)
