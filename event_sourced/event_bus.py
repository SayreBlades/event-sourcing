"""
In-memory event bus for the event-sourced approach.

This module provides a simple pub/sub mechanism that allows services to publish
events and other services to subscribe to them. In a real system, this would be
replaced by a message broker like Kafka, RabbitMQ, or AWS SNS/SQS.

Design decisions:
- Synchronous delivery for simplicity (real systems are usually async)
- Type-based subscriptions (subscribe to event types, not topics)
- Events are delivered to all subscribers in registration order
- No persistence (events are not stored, just delivered)
- Thread-safe for basic operations

Key insight for the demo:
- Publishers don't know who is listening
- Subscribers don't know who is publishing
- This decoupling is the core benefit of event-sourced architecture
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger("event_bus")


@dataclass
class Event:
    """
    Base class for all events in the system.
    
    Events are immutable records of something that happened. They should contain
    all the information needed for subscribers to react appropriately.
    
    Attributes:
        event_id: Unique identifier for this event instance
        event_type: String name of the event type (used for routing)
        timestamp: When the event occurred
        source: Which service/component published the event
        payload: The event-specific data
    """
    event_type: str
    payload: dict[str, Any]
    source: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        return f"Event({self.event_type}, id={self.event_id[:8]}, source={self.source})"


# Type alias for event handler functions
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Simple in-memory event bus implementing pub/sub pattern.
    
    This is the central nervous system of the event-sourced architecture.
    Services publish events here, and the notification service (among others)
    subscribes to receive them.
    
    Example usage:
        bus = EventBus()
        
        # Subscribe to events
        def handle_order_event(event):
            print(f"Order event received: {event}")
        bus.subscribe("OrderStatusChanged", handle_order_event)
        
        # Publish an event
        bus.publish(Event(
            event_type="OrderStatusChanged",
            source="ordering-service",
            payload={"order_id": "ord-001", "new_status": "SHIPPED"}
        ))
    """
    
    def __init__(self):
        """Initialize the event bus with empty subscriber lists."""
        # Map of event_type -> list of handlers
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        
        # Optional: track all events for debugging/replay
        self._event_log: list[Event] = []
        self._log_events: bool = True
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: The type of event to subscribe to (e.g., "OrderStatusChanged")
            handler: Function to call when an event of this type is published
        
        Note: The same handler can be subscribed multiple times (will be called multiple times).
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to '{event_type}' events")
    
    def subscribe_all(self, handler: EventHandler) -> None:
        """
        Subscribe to ALL events (useful for logging, debugging, or audit).
        
        Args:
            handler: Function to call for every event published
        """
        self._subscribers["*"].append(handler)
        logger.debug("Subscribed handler to ALL events")
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: The event type to unsubscribe from
            handler: The handler function to remove
        
        Returns:
            True if the handler was found and removed, False otherwise
        """
        try:
            self._subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed handler from '{event_type}' events")
            return True
        except ValueError:
            return False
    
    def publish(self, event: Event) -> int:
        """
        Publish an event to all subscribers.
        
        Args:
            event: The event to publish
        
        Returns:
            Number of handlers that received the event
        
        Note: Handlers are called synchronously in the order they subscribed.
        If a handler raises an exception, it's logged but doesn't stop other handlers.
        """
        if self._log_events:
            self._event_log.append(event)
        
        logger.info(f"Publishing: {event}")
        
        handlers_called = 0
        
        # Get handlers for this specific event type
        type_handlers = self._subscribers.get(event.event_type, [])
        
        # Get handlers subscribed to all events
        all_handlers = self._subscribers.get("*", [])
        
        # Call all handlers
        for handler in type_handlers + all_handlers:
            handlers_called += 1
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler raised exception for {event}: {e}")
        
        if handlers_called == 0:
            logger.warning(f"No handlers for event type '{event.event_type}'")
        
        return handlers_called
    
    def get_subscriber_count(self, event_type: str) -> int:
        """Get the number of subscribers for an event type."""
        return len(self._subscribers.get(event_type, []))
    
    def get_event_log(self) -> list[Event]:
        """
        Get the log of all published events.
        
        Useful for debugging and testing. In a real system, this would be
        a persistent event store that supports replay.
        """
        return self._event_log.copy()
    
    def clear_event_log(self) -> None:
        """Clear the event log."""
        self._event_log.clear()
    
    def clear_subscribers(self) -> None:
        """Remove all subscribers (useful for testing)."""
        self._subscribers.clear()
    
    def set_logging(self, enabled: bool) -> None:
        """Enable or disable event logging."""
        self._log_events = enabled


# Module-level singleton for convenience
# In production, you'd likely use dependency injection instead
_default_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the default event bus singleton."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def reset_event_bus() -> EventBus:
    """Reset the default event bus (useful for testing)."""
    global _default_bus
    _default_bus = EventBus()
    return _default_bus
