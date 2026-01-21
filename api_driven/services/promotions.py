"""
Promotions service simulator for the API-driven approach.

This service manages promotional campaigns and calls notification API
to notify eligible customers.

Similar complexity issues as pricing service - must query multiple
domains to determine who to notify.
"""

import logging
from typing import Optional

from api_driven.notification_api import NotificationAPI
from api_driven.models import NotificationRequest, NotificationType
from shared.data_store import DataStore, get_data_store

logger = logging.getLogger("promotions_service_api")


class PromotionsService:
    """
    Simulated promotions service that calls notification API.
    
    Like the pricing service, this must query multiple domains
    to determine notification eligibility.
    """
    
    def __init__(
        self,
        notification_api: Optional[NotificationAPI] = None,
        data_store: Optional[DataStore] = None,
    ):
        self.notification_api = notification_api or NotificationAPI()
        self.data_store = data_store or get_data_store()
    
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
        Activate a promotion and notify eligible customers.
        
        Must query customer data to find eligible customers by segment,
        then check preferences, then call notification API.
        
        In event-sourced, we just publish "promotion activated" event.
        """
        logger.info(f"Activating promotion: {name} (segments: {eligible_segments})")
        
        # Find customers in eligible segments
        # CROSS-DOMAIN: Promotions service queries customer data
        eligible_customers = []
        for segment in eligible_segments:
            customers = self.data_store.get_customers_by_segment(segment)
            eligible_customers.extend(customers)
        
        logger.info(f"Found {len(eligible_customers)} customers in eligible segments")
        
        notifications_sent = 0
        
        for customer in eligible_customers:
            # Check if customer wants promotion notifications
            prefs = self.data_store.get_notification_preferences(customer.id)
            if not prefs or not prefs.get_channels_for_type("promotions"):
                continue
            
            try:
                request = NotificationRequest(
                    notification_type=NotificationType.PROMOTION_AVAILABLE,
                    customer_id=customer.id,
                    context={
                        "promotion_name": name,
                        "promotion_description": description,
                        "promo_code": promo_code or "N/A",
                        "end_date": end_date,
                    },
                )
                
                response = self.notification_api.send_notification(request)
                if response.success:
                    notifications_sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to notify {customer.id}: {e}")
        
        logger.info(f"Promotion notifications sent: {notifications_sent}")
