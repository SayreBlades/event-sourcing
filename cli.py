#!/usr/bin/env python3
"""
Command-line interface for the notification architecture demo.

Usage:
    uv run python cli.py [command] [options]

Commands:
    demo        Run demo scenarios
    compare     Compare both approaches
    test        Run the test suite
    serve       Start the API server

Examples:
    uv run python cli.py demo event-sourced order-shipped
    uv run python cli.py demo api-driven price-drop
    uv run python cli.py compare all
    uv run python cli.py serve
"""

import argparse
import subprocess
import sys


def run_demo(approach: str, scenario: str) -> None:
    """Run a demo scenario."""
    if approach == "event-sourced":
        if scenario == "order-shipped":
            from event_sourced.demo import run_order_shipped_demo
            run_order_shipped_demo()
        elif scenario == "price-drop":
            from event_sourced.demo import run_price_drop_demo
            run_price_drop_demo()
        elif scenario == "order-complete":
            from event_sourced.demo import run_order_complete_demo
            run_order_complete_demo()
        elif scenario == "all":
            from event_sourced.demo import (
                run_order_shipped_demo,
                run_price_drop_demo,
                run_order_complete_demo,
            )
            run_order_shipped_demo()
            run_price_drop_demo()
            run_order_complete_demo()
        else:
            print(f"Unknown scenario: {scenario}")
            sys.exit(1)
    
    elif approach == "api-driven":
        if scenario == "order-shipped":
            from api_driven.demo import run_order_shipped_demo
            run_order_shipped_demo()
        elif scenario == "price-drop":
            from api_driven.demo import run_price_drop_demo
            run_price_drop_demo()
        elif scenario == "order-complete":
            from api_driven.demo import run_order_complete_demo
            run_order_complete_demo()
        elif scenario == "all":
            from api_driven.demo import (
                run_order_shipped_demo,
                run_price_drop_demo,
                run_order_complete_demo,
            )
            run_order_shipped_demo()
            run_price_drop_demo()
            run_order_complete_demo()
        else:
            print(f"Unknown scenario: {scenario}")
            sys.exit(1)
    
    else:
        print(f"Unknown approach: {approach}")
        print("Valid approaches: event-sourced, api-driven")
        sys.exit(1)


def run_compare(scenario: str) -> None:
    """Run comparison between approaches."""
    from comparison.run_scenarios import (
        run_order_shipped_comparison,
        run_price_drop_comparison,
        run_order_complete_comparison,
        main as run_all_comparisons,
    )
    
    if scenario == "order-shipped":
        run_order_shipped_comparison()
    elif scenario == "price-drop":
        run_price_drop_comparison()
    elif scenario == "order-complete":
        run_order_complete_comparison()
    elif scenario == "all":
        run_all_comparisons()
    else:
        print(f"Unknown scenario: {scenario}")
        sys.exit(1)


def run_tests(args: list[str]) -> None:
    """Run the test suite."""
    cmd = ["uv", "run", "pytest"] + args
    subprocess.run(cmd)


def run_server(host: str, port: int, reload: bool) -> None:
    """Start the API server."""
    cmd = ["uv", "run", "uvicorn", "api.main:app", f"--host={host}", f"--port={port}"]
    if reload:
        cmd.append("--reload")
    
    print(f"Starting server at http://{host}:{port}")
    print(f"API docs available at http://{host}:{port}/docs")
    subprocess.run(cmd)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Notification Architecture Demo CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s demo event-sourced order-shipped
  %(prog)s demo api-driven price-drop
  %(prog)s demo event-sourced all
  %(prog)s compare all
  %(prog)s test -v
  %(prog)s serve --reload
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run demo scenarios")
    demo_parser.add_argument(
        "approach",
        choices=["event-sourced", "api-driven"],
        help="Which approach to use",
    )
    demo_parser.add_argument(
        "scenario",
        choices=["order-shipped", "price-drop", "order-complete", "all"],
        help="Which scenario to run",
    )
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare both approaches")
    compare_parser.add_argument(
        "scenario",
        choices=["order-shipped", "price-drop", "order-complete", "all"],
        help="Which scenario to compare",
    )
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run the test suite")
    test_parser.add_argument(
        "pytest_args",
        nargs="*",
        default=[],
        help="Arguments to pass to pytest",
    )
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    if args.command == "demo":
        run_demo(args.approach, args.scenario)
    elif args.command == "compare":
        run_compare(args.scenario)
    elif args.command == "test":
        run_tests(args.pytest_args)
    elif args.command == "serve":
        run_server(args.host, args.port, args.reload)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
