"""
Main Application Entry Point

Single script to run the entire Climate Risk Assessment system, configurable
via CLI args - ties together every component built across Phases 1-6
(config/logging setup, database initialization, the continuous monitoring
loop, the scheduler, and portfolio reporting) behind one front door, closing
the gap the Operations Guide (Task 32) flagged: this project previously had
no dedicated main.py/service wrapper, only `python -m src.<module>` per
component.

Usage:
    python src/main.py --mode test              # run one monitoring cycle and exit
    python src/main.py --mode report             # generate and print a portfolio report
    python src/main.py --mode run                # start the continuous scheduler (Ctrl+C to stop)
    python src/main.py --mode run --duration 30   # run for 30 minutes, then stop automatically
    python src/main.py --mode run --interval 1    # override the configured cycle interval (minutes)
"""

import argparse
import signal
import sys
import time
from pathlib import Path

# Allow running as `python src/main.py` directly (not just `python -m src.main`)
# by putting the project root on sys.path before importing from `src`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import setup_logging
from src.database import initialize_database
from src.continuous_monitoring import Monitor, SchedulerManager
from src.portfolio import PortfolioReporter


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Climate Risk Assessment - Continuous Monitoring System",
    )
    parser.add_argument(
        "--mode", choices=["run", "test", "report"], default="test",
        help=(
            "run: start the continuous scheduler (Ctrl+C to stop); "
            "test: run a single monitoring cycle and exit; "
            "report: generate and print a portfolio summary report "
            "(default: test)"
        ),
    )
    parser.add_argument(
        "--duration", type=float, default=None,
        help="For --mode run only: stop automatically after this many minutes (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--interval", type=float, default=None,
        help=(
            "For --mode run only: override the configured monitoring cycle "
            "interval, in minutes (default: alerts.alert_check_interval_minutes "
            "from config/settings.json)"
        ),
    )
    return parser.parse_args(argv)


def run_mode(interval: float = None, duration: float = None) -> None:
    """Start the continuous scheduler and block until stopped (Ctrl+C, an
    optional --duration limit, or a delivered SIGTERM)."""
    scheduler = SchedulerManager()
    if interval is not None:
        scheduler.interval_minutes = interval

    stop_requested = False

    def _handle_shutdown_signal(signum, frame):
        nonlocal stop_requested
        print("\nShutdown signal received - stopping scheduler gracefully...")
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    scheduler.start()
    print(f"Scheduler started (interval: {scheduler.interval_minutes} minute(s)). Press Ctrl+C to stop.")
    if duration is not None:
        print(f"Will stop automatically after {duration} minute(s).")

    start_time = time.monotonic()
    try:
        while not stop_requested:
            if duration is not None and (time.monotonic() - start_time) >= duration * 60:
                print(f"\nDuration limit of {duration} minute(s) reached - stopping.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received - stopping scheduler gracefully...")
    finally:
        scheduler.stop()
        print(f"Scheduler stopped. Cycles run: {scheduler.cycles_run}, failed: {scheduler.cycles_failed}")


def test_mode() -> dict:
    """Run exactly one monitoring cycle and print its summary."""
    summary = Monitor().run_monitoring_cycle()
    print("Monitoring cycle complete:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return summary


def report_mode() -> str:
    """Generate and print a portfolio summary report."""
    report = PortfolioReporter().generate_summary_report()
    print(report)
    return report


def main(argv=None) -> int:
    args = parse_args(argv)

    setup_logging()
    initialize_database()

    if args.mode == "run":
        run_mode(interval=args.interval, duration=args.duration)
    elif args.mode == "test":
        test_mode()
    elif args.mode == "report":
        report_mode()

    return 0


if __name__ == "__main__":
    sys.exit(main())
