"""
Unified FastAPI application for the notification architecture demo.

This application provides:
1. The API-driven notification endpoints (/api/notify, /api/notify/bulk)
2. Demo endpoints to run scenarios (/demo/...)
3. Comparison endpoints to see both approaches side-by-side

Run with:
    uv run uvicorn api.main:app --reload

Then visit http://localhost:8000/docs for interactive API documentation.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)

# Import both approaches
from event_sourced.event_bus import reset_event_bus
from event_sourced.event_correlator import reset_event_correlator
from event_sourced.notification_service import NotificationService as ESNotificationService
from event_sourced.services.ordering import OrderingService as ESOrderingService
from event_sourced.services.pricing import PricingService as ESPricingService

from api_driven.notification_api import NotificationAPI
from api_driven.services.ordering import OrderingService as APIOrderingService
from api_driven.services.pricing import PricingService as APIPricingService
from api_driven.models import NotificationRequest, NotificationType

from shared.data_store import DataStore
from shared.channels import NotificationChannels


# Response models
class DemoResult(BaseModel):
    """Result of running a demo scenario."""
    approach: str
    scenario: str
    notifications_sent: int
    recipients: list[str]
    messages: list[dict[str, Any]]


class ComparisonResult(BaseModel):
    """Result of comparing both approaches."""
    scenario: str
    event_sourced: DemoResult
    api_driven: DemoResult
    same_recipients: bool


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logging.info("Starting Notification Architecture Demo API")
    yield
    logging.info("Shutting down")


# Create the FastAPI app
app = FastAPI(
    title="Notification Architecture Demo",
    description="""
    A demonstration comparing event-sourced vs API-driven notification architectures.
    
    ## Approaches
    
    - **Event-Sourced**: Domain services publish events, notification service subscribes
    - **API-Driven**: Domain services call notification API directly
    
    ## Endpoints
    
    - `/demo/event-sourced/*` - Run scenarios using event-sourced approach
    - `/demo/api-driven/*` - Run scenarios using API-driven approach
    - `/demo/compare/*` - Run scenarios in both approaches and compare
    - `/api/*` - Direct access to API-driven notification service
    """,
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "notification-architecture-demo"}


# =============================================================================
# Event-Sourced Demo Endpoints
# =============================================================================

@app.post("/demo/event-sourced/order-shipped", response_model=DemoResult, tags=["Event-Sourced Demo"])
def demo_es_order_shipped(order_id: str = "ord-001"):
    """
    Run the Order Shipped scenario using event-sourced approach.
    
    The OrderingService publishes an event, and the NotificationService
    automatically handles the notification.
    """
    # Set up fresh instances
    event_bus = reset_event_bus()
    correlator = reset_event_correlator()
    data_store = DataStore()
    channels = NotificationChannels()
    
    notification_service = ESNotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
        correlator=correlator,
    )
    ordering_service = ESOrderingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    notification_service.start()
    
    try:
        # Run scenario
        result = ordering_service.ship_order(order_id)
        if not result:
            raise HTTPException(status_code=400, detail=f"Failed to ship order {order_id}")
        
        # Collect results
        messages = channels.get_all_sent_messages()
        return DemoResult(
            approach="event-sourced",
            scenario="order-shipped",
            notifications_sent=len(messages),
            recipients=[m.recipient for m in messages],
            messages=[{"channel": m.channel.value, "recipient": m.recipient, "subject": m.subject} for m in messages],
        )
    finally:
        notification_service.stop()


@app.post("/demo/event-sourced/price-drop", response_model=DemoResult, tags=["Event-Sourced Demo"])
def demo_es_price_drop(product_id: str = "prod-001", new_price: float = 119.99):
    """
    Run the Price Drop Alert scenario using event-sourced approach.
    
    The PricingService publishes a PriceChanged event. The NotificationService
    handles all the complex logic: finding carts, checking preferences, checking
    segment eligibility.
    """
    event_bus = reset_event_bus()
    correlator = reset_event_correlator()
    data_store = DataStore()
    channels = NotificationChannels()
    
    notification_service = ESNotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
        correlator=correlator,
    )
    pricing_service = ESPricingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    notification_service.start()
    
    try:
        pricing_service.update_price(product_id, new_price)
        
        messages = channels.get_all_sent_messages()
        return DemoResult(
            approach="event-sourced",
            scenario="price-drop",
            notifications_sent=len(messages),
            recipients=[m.recipient for m in messages],
            messages=[{"channel": m.channel.value, "recipient": m.recipient, "subject": m.subject} for m in messages],
        )
    finally:
        notification_service.stop()


@app.post("/demo/event-sourced/order-complete", response_model=DemoResult, tags=["Event-Sourced Demo"])
def demo_es_order_complete(order_id: str = "ord-001"):
    """
    Run the Order Complete scenario using event-sourced approach.
    
    Ships all items in an order one by one. The EventCorrelator tracks
    the shipments and triggers a notification only when all items have shipped.
    """
    event_bus = reset_event_bus()
    correlator = reset_event_correlator()
    data_store = DataStore()
    channels = NotificationChannels()
    
    notification_service = ESNotificationService(
        event_bus=event_bus,
        data_store=data_store,
        channels=channels,
        correlator=correlator,
    )
    ordering_service = ESOrderingService(
        event_bus=event_bus,
        data_store=data_store,
    )
    
    notification_service.start()
    
    try:
        # Get order and ship all items
        order = data_store.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
        
        for item in order.line_items:
            ordering_service.ship_line_item(order_id, item.product_id)
        
        messages = channels.get_all_sent_messages()
        return DemoResult(
            approach="event-sourced",
            scenario="order-complete",
            notifications_sent=len(messages),
            recipients=[m.recipient for m in messages],
            messages=[{"channel": m.channel.value, "recipient": m.recipient, "subject": m.subject} for m in messages],
        )
    finally:
        notification_service.stop()


# =============================================================================
# API-Driven Demo Endpoints
# =============================================================================

@app.post("/demo/api-driven/order-shipped", response_model=DemoResult, tags=["API-Driven Demo"])
def demo_api_order_shipped(order_id: str = "ord-001"):
    """
    Run the Order Shipped scenario using API-driven approach.
    
    The OrderingService calls the NotificationAPI directly after
    updating the order status.
    """
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    ordering_service = APIOrderingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    result = ordering_service.ship_order(order_id)
    if not result:
        raise HTTPException(status_code=400, detail=f"Failed to ship order {order_id}")
    
    messages = channels.get_all_sent_messages()
    return DemoResult(
        approach="api-driven",
        scenario="order-shipped",
        notifications_sent=len(messages),
        recipients=[m.recipient for m in messages],
        messages=[{"channel": m.channel.value, "recipient": m.recipient, "subject": m.subject} for m in messages],
    )


@app.post("/demo/api-driven/price-drop", response_model=DemoResult, tags=["API-Driven Demo"])
def demo_api_price_drop(product_id: str = "prod-001", new_price: float = 119.99):
    """
    Run the Price Drop Alert scenario using API-driven approach.
    
    The PricingService must query carts, customers, and preferences
    to determine who to notify, then calls the NotificationAPI.
    """
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    pricing_service = APIPricingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    pricing_service.update_price(product_id, new_price)
    
    messages = channels.get_all_sent_messages()
    return DemoResult(
        approach="api-driven",
        scenario="price-drop",
        notifications_sent=len(messages),
        recipients=[m.recipient for m in messages],
        messages=[{"channel": m.channel.value, "recipient": m.recipient, "subject": m.subject} for m in messages],
    )


@app.post("/demo/api-driven/order-complete", response_model=DemoResult, tags=["API-Driven Demo"])
def demo_api_order_complete(order_id: str = "ord-001"):
    """
    Run the Order Complete scenario using API-driven approach.
    
    The OrderingService must track shipment state internally and
    decide when to call the NotificationAPI.
    """
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    ordering_service = APIOrderingService(
        notification_api=notification_api,
        data_store=data_store,
    )
    
    order = data_store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    
    for item in order.line_items:
        ordering_service.ship_line_item(order_id, item.product_id)
    
    messages = channels.get_all_sent_messages()
    return DemoResult(
        approach="api-driven",
        scenario="order-complete",
        notifications_sent=len(messages),
        recipients=[m.recipient for m in messages],
        messages=[{"channel": m.channel.value, "recipient": m.recipient, "subject": m.subject} for m in messages],
    )


# =============================================================================
# Comparison Endpoints
# =============================================================================

@app.post("/demo/compare/order-shipped", response_model=ComparisonResult, tags=["Comparison"])
def compare_order_shipped(order_id: str = "ord-001"):
    """
    Run Order Shipped in both approaches and compare results.
    """
    es_result = demo_es_order_shipped(order_id)
    api_result = demo_api_order_shipped(order_id)
    
    return ComparisonResult(
        scenario="order-shipped",
        event_sourced=es_result,
        api_driven=api_result,
        same_recipients=sorted(es_result.recipients) == sorted(api_result.recipients),
    )


@app.post("/demo/compare/price-drop", response_model=ComparisonResult, tags=["Comparison"])
def compare_price_drop(product_id: str = "prod-001", new_price: float = 119.99):
    """
    Run Price Drop Alert in both approaches and compare results.
    
    Both approaches should notify the same customers, but the logic
    lives in different places.
    """
    es_result = demo_es_price_drop(product_id, new_price)
    api_result = demo_api_price_drop(product_id, new_price)
    
    return ComparisonResult(
        scenario="price-drop",
        event_sourced=es_result,
        api_driven=api_result,
        same_recipients=sorted(es_result.recipients) == sorted(api_result.recipients),
    )


@app.post("/demo/compare/order-complete", response_model=ComparisonResult, tags=["Comparison"])
def compare_order_complete(order_id: str = "ord-001"):
    """
    Run Order Complete in both approaches and compare results.
    """
    es_result = demo_es_order_complete(order_id)
    api_result = demo_api_order_complete(order_id)
    
    return ComparisonResult(
        scenario="order-complete",
        event_sourced=es_result,
        api_driven=api_result,
        same_recipients=sorted(es_result.recipients) == sorted(api_result.recipients),
    )


# =============================================================================
# Direct API Access (API-Driven Notification Service)
# =============================================================================

@app.post("/api/notify", tags=["Notification API"])
def api_notify(request: NotificationRequest):
    """
    Send a notification directly via the API-driven notification service.
    
    This is the same endpoint as in api_driven/notification_api.py but
    accessible through this unified application.
    """
    data_store = DataStore()
    channels = NotificationChannels()
    notification_api = NotificationAPI(channels=channels, data_store=data_store)
    
    return notification_api.send_notification(request)


# =============================================================================
# Data Endpoints (for exploration)
# =============================================================================

@app.get("/data/customers", tags=["Data"])
def get_customers():
    """Get all customers in the system."""
    data_store = DataStore()
    customers = data_store.get_customers()
    return [{"id": c.id, "name": c.name, "email": c.email, "segment": c.segment} for c in customers]


@app.get("/data/products", tags=["Data"])
def get_products():
    """Get all products in the system."""
    data_store = DataStore()
    products = data_store.get_products()
    return [{"id": p.id, "name": p.name, "price": p.price, "category": p.category} for p in products]


@app.get("/data/orders", tags=["Data"])
def get_orders():
    """Get all orders in the system."""
    data_store = DataStore()
    orders = data_store.get_orders()
    return [
        {
            "id": o.id,
            "customer_id": o.customer_id,
            "status": o.status,
            "total_amount": o.total_amount,
            "line_items": [{"product_id": li.product_id, "quantity": li.quantity, "status": li.status} for li in o.line_items],
        }
        for o in orders
    ]


@app.get("/data/carts", tags=["Data"])
def get_carts():
    """Get all shopping carts in the system."""
    data_store = DataStore()
    carts = data_store.get_carts()
    return [
        {
            "customer_id": c.customer_id,
            "items": [{"product_id": i.product_id, "quantity": i.quantity} for i in c.items],
        }
        for c in carts
    ]
