"""
Tests for the event bus.

These tests verify the pub/sub mechanism that enables
the event-sourced architecture.
"""

import pytest
from event_sourced.event_bus import Event, EventBus, reset_event_bus


class TestEvent:
    """Tests for Event class."""
    
    def test_create_event(self):
        """Test basic event creation."""
        event = Event(
            event_type="TestEvent",
            source="test-service",
            payload={"key": "value"},
        )
        
        assert event.event_type == "TestEvent"
        assert event.source == "test-service"
        assert event.payload == {"key": "value"}
        assert event.event_id is not None
        assert event.timestamp is not None
    
    def test_event_ids_are_unique(self):
        """Test that each event gets a unique ID."""
        event1 = Event(event_type="Test", source="test", payload={})
        event2 = Event(event_type="Test", source="test", payload={})
        
        assert event1.event_id != event2.event_id
    
    def test_event_str(self):
        """Test event string representation."""
        event = Event(event_type="OrderShipped", source="ordering", payload={})
        
        str_repr = str(event)
        assert "OrderShipped" in str_repr
        assert "ordering" in str_repr


class TestEventBus:
    """Tests for EventBus pub/sub functionality."""
    
    @pytest.fixture
    def bus(self):
        """Create a fresh event bus for each test."""
        return EventBus()
    
    def test_subscribe_and_publish(self, bus: EventBus):
        """Test basic subscribe and publish flow."""
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        bus.subscribe("TestEvent", handler)
        
        event = Event(event_type="TestEvent", source="test", payload={"data": 123})
        bus.publish(event)
        
        assert len(received_events) == 1
        assert received_events[0].payload["data"] == 123
    
    def test_multiple_subscribers(self, bus: EventBus):
        """Test that multiple subscribers all receive the event."""
        results = {"handler1": 0, "handler2": 0}
        
        def handler1(event):
            results["handler1"] += 1
        
        def handler2(event):
            results["handler2"] += 1
        
        bus.subscribe("TestEvent", handler1)
        bus.subscribe("TestEvent", handler2)
        
        bus.publish(Event(event_type="TestEvent", source="test", payload={}))
        
        assert results["handler1"] == 1
        assert results["handler2"] == 1
    
    def test_subscribe_to_specific_type(self, bus: EventBus):
        """Test that handlers only receive events of their subscribed type."""
        received = []
        
        def handler(event):
            received.append(event.event_type)
        
        bus.subscribe("TypeA", handler)
        
        bus.publish(Event(event_type="TypeA", source="test", payload={}))
        bus.publish(Event(event_type="TypeB", source="test", payload={}))
        bus.publish(Event(event_type="TypeA", source="test", payload={}))
        
        assert received == ["TypeA", "TypeA"]
    
    def test_subscribe_all(self, bus: EventBus):
        """Test subscribing to all events with wildcard."""
        received = []
        
        def handler(event):
            received.append(event.event_type)
        
        bus.subscribe_all(handler)
        
        bus.publish(Event(event_type="TypeA", source="test", payload={}))
        bus.publish(Event(event_type="TypeB", source="test", payload={}))
        bus.publish(Event(event_type="TypeC", source="test", payload={}))
        
        assert received == ["TypeA", "TypeB", "TypeC"]
    
    def test_unsubscribe(self, bus: EventBus):
        """Test unsubscribing a handler."""
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe("Test", handler)
        bus.publish(Event(event_type="Test", source="test", payload={}))
        
        assert len(received) == 1
        
        result = bus.unsubscribe("Test", handler)
        assert result is True
        
        bus.publish(Event(event_type="Test", source="test", payload={}))
        assert len(received) == 1  # Still 1, handler wasn't called
    
    def test_unsubscribe_nonexistent_handler(self, bus: EventBus):
        """Test unsubscribing a handler that wasn't subscribed."""
        def handler(event):
            pass
        
        result = bus.unsubscribe("Test", handler)
        assert result is False
    
    def test_publish_returns_handler_count(self, bus: EventBus):
        """Test that publish returns the number of handlers called."""
        bus.subscribe("Test", lambda e: None)
        bus.subscribe("Test", lambda e: None)
        bus.subscribe("Other", lambda e: None)
        
        count = bus.publish(Event(event_type="Test", source="test", payload={}))
        
        assert count == 2
    
    def test_event_log(self, bus: EventBus):
        """Test that events are logged."""
        bus.publish(Event(event_type="Event1", source="test", payload={}))
        bus.publish(Event(event_type="Event2", source="test", payload={}))
        
        log = bus.get_event_log()
        
        assert len(log) == 2
        assert log[0].event_type == "Event1"
        assert log[1].event_type == "Event2"
    
    def test_clear_event_log(self, bus: EventBus):
        """Test clearing the event log."""
        bus.publish(Event(event_type="Test", source="test", payload={}))
        assert len(bus.get_event_log()) == 1
        
        bus.clear_event_log()
        
        assert len(bus.get_event_log()) == 0
    
    def test_handler_exception_doesnt_stop_others(self, bus: EventBus):
        """Test that one handler's exception doesn't prevent others from running."""
        results = []
        
        def bad_handler(event):
            raise ValueError("I'm broken!")
        
        def good_handler(event):
            results.append("success")
        
        bus.subscribe("Test", bad_handler)
        bus.subscribe("Test", good_handler)
        
        # Should not raise, and good_handler should still run
        count = bus.publish(Event(event_type="Test", source="test", payload={}))
        
        assert "success" in results
        assert count == 2  # Both handlers were called
    
    def test_get_subscriber_count(self, bus: EventBus):
        """Test getting subscriber count for an event type."""
        assert bus.get_subscriber_count("Test") == 0
        
        bus.subscribe("Test", lambda e: None)
        bus.subscribe("Test", lambda e: None)
        
        assert bus.get_subscriber_count("Test") == 2
        assert bus.get_subscriber_count("Other") == 0


class TestEventBusSingleton:
    """Tests for the module-level singleton functions."""
    
    def test_reset_event_bus(self):
        """Test that reset_event_bus creates a new instance."""
        from event_sourced.event_bus import get_event_bus, reset_event_bus
        
        bus1 = get_event_bus()
        bus1.subscribe("Test", lambda e: None)
        
        bus2 = reset_event_bus()
        
        assert bus2.get_subscriber_count("Test") == 0
