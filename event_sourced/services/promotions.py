"""
Promotions service simulator for the event-sourced approach.

This service manages promotional campaigns and publishes events
when promotions are activated or deactivated.

Key insight for the demo:
- Promotion events include eligibility criteria (segments)
- The notification service handles determining who should be notified
- This service focuses only on promotion lifecycle management
"""

import logging
from typing import Optional

from event_sourced.event_bus import EventBus, get_event_bus
from event_sourced.events import promotion_activated

logger = logging.getLogger("promotions_service")


class PromotionsService:
    """
    Simulated promotions service that publishes promotion events.
    
    In a real system, this would manage:
    - Promotion creation and scheduling
    - Eligibility rules
    - Usage limits and tracking
    - Integration with pricing for automatic discounts
    
    Example:
        service = PromotionsService()
        
        # Activate a promotion
        service.activate_promotion(
            promotion_id="promo-summer-sale",
            name="Summer Sale",
            description="20% off all networking equipment",
            eligible_segments=["gold", "platinum"],
            promo_code="SUMMER20",
            end_date="2024-08-31",
        )
        
        # The notification service will notify eligible customers
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
    ):
        self.event_bus = event_bus or get_event_bus()
    
    def activate_promotion(
        self,
        promotion_id: str,
        name: str,
        description: str,
        eligible_segments: list[str],
        end_date: str,
        promo_code: Optional[str] = None,
    ) -> None:
        """
        Activate a promotion and publish an event.
        
        Args:
            promotion_id: Unique identifier for the promotion
            name: Display name
            description: Promotion details
            eligible_segments: Customer segments that can use this promotion
            end_date: When the promotion ends (ISO format string)
            promo_code: Optional promotional code
        """
        logger.info(f"Activating promotion: {name} (segments: {eligible_segments})")
        
        event = promotion_activated(
            promotion_id=promotion_id,
            promotion_name=name,
            description=description,
            promo_code=promo_code,
            eligible_segments=eligible_segments,
            end_date=end_date,
        )
        self.event_bus.publish(event)
