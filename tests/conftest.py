"""
Shared pytest fixtures for the notification architecture demo tests.

These fixtures provide consistent test data and reset state between tests.
"""

import pytest
from pathlib import Path

from shared.data_store import DataStore
from shared.channels import NotificationChannels, EmailChannel, SMSChannel


@pytest.fixture
def data_dir() -> Path:
    """Path to the test data directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def data_store(data_dir: Path) -> DataStore:
    """
    Fresh DataStore instance for each test.
    
    Uses the real JSON fixtures but creates a new instance
    so tests don't interfere with each other.
    """
    return DataStore(data_dir=data_dir)


@pytest.fixture
def email_channel() -> EmailChannel:
    """Fresh EmailChannel for each test."""
    return EmailChannel(fail_rate=0.0)


@pytest.fixture
def sms_channel() -> SMSChannel:
    """Fresh SMSChannel for each test."""
    return SMSChannel(fail_rate=0.0)


@pytest.fixture
def channels() -> NotificationChannels:
    """Fresh NotificationChannels facade for each test."""
    return NotificationChannels(email_fail_rate=0.0, sms_fail_rate=0.0)


# =============================================================================
# Customer Fixtures
# =============================================================================

@pytest.fixture
def alice_customer_id() -> str:
    """Customer ID for Alice (gold segment, has order ord-001)."""
    return "cust-001"


@pytest.fixture
def bob_customer_id() -> str:
    """Customer ID for Bob (silver segment, has cart with prod-001)."""
    return "cust-002"


@pytest.fixture
def carol_customer_id() -> str:
    """Customer ID for Carol (platinum segment, full notification prefs)."""
    return "cust-003"


@pytest.fixture
def david_customer_id() -> str:
    """Customer ID for David (bronze segment, minimal prefs, has failed payment)."""
    return "cust-004"


@pytest.fixture
def eva_customer_id() -> str:
    """Customer ID for Eva (gold segment, has cart with multiple items)."""
    return "cust-005"


# =============================================================================
# Product Fixtures
# =============================================================================

@pytest.fixture
def router_product_id() -> str:
    """Product ID for Wireless Router X500 - used in price drop tests."""
    return "prod-001"


@pytest.fixture
def keyboard_product_id() -> str:
    """Product ID for Mechanical Keyboard Elite."""
    return "prod-003"


# =============================================================================
# Order Fixtures
# =============================================================================

@pytest.fixture
def multi_item_order_id() -> str:
    """
    Order ID for Alice's multi-item order.
    Used for Order Complete scenario testing.
    Has 2 line items, both pending.
    """
    return "ord-001"


@pytest.fixture
def partial_ship_order_id() -> str:
    """
    Order ID for Bob's order with partial shipment.
    Has 3 line items: 1 shipped, 2 pending.
    """
    return "ord-002"


@pytest.fixture
def shipped_order_id() -> str:
    """Order ID for Carol's shipped order (single item)."""
    return "ord-003"


@pytest.fixture
def pending_order_id() -> str:
    """Order ID for David's pending order with failed payment."""
    return "ord-004"
