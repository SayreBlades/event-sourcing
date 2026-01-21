# Notification Architecture Demo

A demonstration comparing **event-sourced** vs **API-driven** notification service architectures for an e-commerce/BSS platform.

## Overview

This project implements the same notification scenarios using two different architectural approaches, allowing direct comparison of their tradeoffs.

### The Two Approaches

1. **Event-Sourced** (`event_sourced/`)
   - Domain services publish events
   - Notification service subscribes and handles all notification logic
   - Loose coupling via event bus

2. **API-Driven** (`api_driven/`)
   - Domain services call notification API directly
   - Caller decides when to notify, API handles how
   - Direct coupling between services

## Quick Start

```bash
# Install dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run demos via CLI
uv run python cli.py demo event-sourced all
uv run python cli.py demo api-driven all

# Compare both approaches
uv run python cli.py compare all

# Start the unified API server
uv run python cli.py serve --reload
# Then visit http://localhost:8000/docs
```

### CLI Commands

```bash
uv run python cli.py demo event-sourced order-shipped
uv run python cli.py demo api-driven price-drop
uv run python cli.py compare order-complete
uv run python cli.py test -v
uv run python cli.py serve --port 8080
```

## Notification Scenarios

| Scenario | Complexity | Key Challenge |
|----------|------------|---------------|
| Order Shipped | Simple | 1:1 event-to-notification |
| Payment Failed | Medium | Include contextual info |
| Price Drop Alert | Complex | Multi-condition eligibility |
| Order Complete | Complex | Event aggregation |

## Architecture Comparison

### Event-Sourced Flow
```
OrderingService                    EventBus                 NotificationService
     │                                │                            │
     │ ship_order()                   │                            │
     │──────────────────────────────>│                            │
     │        publish(OrderStatusChanged)                         │
     │                                │──────────────────────────>│
     │                                │     receives event         │
     │                                │                            │ query customer
     │                                │                            │ query preferences
     │                                │                            │ send email/sms
```

### API-Driven Flow
```
OrderingService                NotificationAPI                  Channels
     │                              │                              │
     │ ship_order()                 │                              │
     │  └─ build context            │                              │
     │  └─ POST /notify ──────────>│                              │
     │                              │ query customer               │
     │                              │ render template              │
     │                              │ send ───────────────────────>│
```

## Key Findings

### Price Drop Alert Comparison

| Aspect | Event-Sourced | API-Driven |
|--------|--------------|------------|
| PricingService queries carts | ❌ No | ✅ Yes |
| PricingService queries customers | ❌ No | ✅ Yes |
| PricingService knows eligibility rules | ❌ No | ✅ Yes |
| Notification logic location | Centralized | Distributed |

### Order Complete Comparison

| Aspect | Event-Sourced | API-Driven |
|--------|--------------|------------|
| Who tracks shipment state? | EventCorrelator | OrderingService |
| Where is completion logic? | NotificationService | OrderingService |
| Domain service complexity | Low | High |

## Project Structure

```
event-stream/
├── shared/                 # Common infrastructure
│   ├── models.py          # Domain models
│   ├── data_store.py      # JSON data access
│   ├── channels.py        # Email/SMS mock
│   └── templates.py       # Message templates
│
├── event_sourced/          # Event-sourced approach
│   ├── event_bus.py       # Pub/sub mechanism
│   ├── events.py          # Event definitions
│   ├── notification_service.py
│   ├── event_correlator.py
│   └── services/          # Domain services
│
├── api_driven/             # API-driven approach
│   ├── notification_api.py # FastAPI service
│   ├── models.py          # API models
│   └── services/          # Domain services
│
├── comparison/             # Analysis
│   └── analysis.md        # Detailed comparison
│
├── data/                   # JSON fixtures
└── tests/                  # Test suite (154 tests)
```

## Test Coverage

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific approach tests
uv run pytest tests/test_event_sourced/
uv run pytest tests/test_api_driven/
```

## Documentation

- [Event-Sourced README](event_sourced/README.md) - Architecture details
- [API-Driven README](api_driven/README.md) - Architecture details  
- [Comparison Analysis](comparison/analysis.md) - Detailed tradeoff analysis
- [Implementation Plan](plan.md) - Original requirements and phases

## Conclusion

For systems with complex, cross-cutting notification requirements:

**Event-Sourced is generally preferred** because:
- Domain services stay simple and focused
- All notification logic is centralized
- Adding new notifications doesn't require changing domain services
- Debugging is easier with centralized logic

**API-Driven works well** when:
- Notifications are simple and direct
- Caller already has all context
- You want explicit control in the calling service

See [comparison/analysis.md](comparison/analysis.md) for the full analysis.
