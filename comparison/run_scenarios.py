"""
Run scenarios side-by-side in both approaches for comparison.

This script executes the same notification scenarios using both
event-sourced and API-driven approaches, showing the differences
in output and behavior.
"""

import logging
from typing import Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)

# Suppress some verbose loggers
logging.getLogger("event_bus").setLevel(logging.WARNING)
logging.getLogger("notification_api").setLevel(logging.WARNING)


def run_comparison(
    scenario_name: str,
    event_sourced_fn: Callable,
    api_driven_fn: Callable,
) -> None:
    """Run a scenario in both approaches and compare."""
    print("\n" + "=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    
    # Run event-sourced
    print("\n" + "-" * 40)
    print("EVENT-SOURCED APPROACH")
    print("-" * 40)
    es_results = event_sourced_fn()
    es_count = len(es_results)
    
    # Run API-driven
    print("\n" + "-" * 40)
    print("API-DRIVEN APPROACH")
    print("-" * 40)
    api_results = api_driven_fn()
    api_count = len(api_results)
    
    # Compare
    print("\n" + "-" * 40)
    print("COMPARISON")
    print("-" * 40)
    print(f"  Event-Sourced notifications sent: {es_count}")
    print(f"  API-Driven notifications sent:    {api_count}")
    
    es_recipients = sorted([r.recipient for r in es_results])
    api_recipients = sorted([r.recipient for r in api_results])
    
    if es_recipients == api_recipients:
        print("  ✓ Same recipients notified")
    else:
        print("  ✗ Different recipients!")
        print(f"    Event-Sourced: {es_recipients}")
        print(f"    API-Driven:    {api_recipients}")


def run_order_shipped_comparison():
    """Compare Order Shipped scenario."""
    from event_sourced.demo import run_order_shipped_demo as es_demo
    from api_driven.demo import run_order_shipped_demo as api_demo
    
    run_comparison("Order Shipped", es_demo, api_demo)


def run_price_drop_comparison():
    """Compare Price Drop Alert scenario."""
    from event_sourced.demo import run_price_drop_demo as es_demo
    from api_driven.demo import run_price_drop_demo as api_demo
    
    run_comparison("Price Drop Alert", es_demo, api_demo)


def run_order_complete_comparison():
    """Compare Order Complete scenario."""
    from event_sourced.demo import run_order_complete_demo as es_demo
    from api_driven.demo import run_order_complete_demo as api_demo
    
    run_comparison("Order Complete", es_demo, api_demo)


def main():
    """Run all scenario comparisons."""
    print("\n" + "#" * 80)
    print("# NOTIFICATION ARCHITECTURE COMPARISON")
    print("# Event-Sourced vs API-Driven")
    print("#" * 80)
    
    run_order_shipped_comparison()
    run_price_drop_comparison()
    run_order_complete_comparison()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
Both approaches produce the SAME notifications for the same scenarios.
The difference is WHERE the logic lives:

┌─────────────────────┬────────────────────────┬────────────────────────┐
│ Logic               │ Event-Sourced          │ API-Driven             │
├─────────────────────┼────────────────────────┼────────────────────────┤
│ When to notify      │ NotificationService    │ Domain Service         │
│ Who to notify       │ NotificationService    │ Domain Service         │
│ Eligibility rules   │ NotificationService    │ Domain Service         │
│ State tracking      │ EventCorrelator        │ Domain Service         │
│ Template rendering  │ NotificationService    │ NotificationAPI        │
│ Channel delivery    │ NotificationService    │ NotificationAPI        │
└─────────────────────┴────────────────────────┴────────────────────────┘

See comparison/analysis.md for detailed tradeoff analysis.
""")


if __name__ == "__main__":
    main()
