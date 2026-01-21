# Notification Architecture Demo

A demonstration comparing **event-sourced** vs **API-driven** notification service architectures.

## Quick Start

```bash
# Install dependencies (including dev tools)
uv sync --extra dev

# Run tests
uv run pytest

# Start the demo API
uv run uvicorn api.main:app --reload
```

## Overview

This project demonstrates the tradeoffs between two architectural approaches for building a notification service in an e-commerce/BSS platform:

1. **Event-Sourced**: Domain services publish events, notification service subscribes and determines when/how to send notifications
2. **API-Driven**: Domain services call the notification API directly, deciding when to notify

See [plan.md](plan.md) for the detailed implementation plan and tradeoff analysis.

## Project Structure

- `shared/` - Common infrastructure (models, data store, channels, templates)
- `event_sourced/` - Event-sourced approach implementation
- `api_driven/` - API-driven approach implementation
- `comparison/` - Side-by-side analysis
- `data/` - JSON fixtures for testing
- `tests/` - Test suite

## Scenarios Demonstrated

1. **Order Shipped** (Simple) - Direct 1:1 event-to-notification
2. **Payment Failed** (Medium) - Preference lookup + templating
3. **Price Drop Alert** (Complex) - Multi-condition eligibility
4. **Order Complete** (Complex) - Event aggregation across multiple shipments
