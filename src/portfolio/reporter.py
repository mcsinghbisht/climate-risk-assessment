"""
Portfolio Reporter

Generates a human-readable text summary of overall portfolio status,
combining PortfolioAggregator's metrics (Task 25), HotspotDetector's
geographic clusters (Task 26), and an active-alerts summary (AlertDAO,
Task 21b/27) - the first component that answers "what should a human
reviewing this portfolio right now actually see?" rather than exposing
each piece separately.

Text-only for the MVP, but the report is built as a list of lines
(_build_lines()) rather than one big f-string, so a future PDF/HTML
renderer can reuse the same underlying data-gathering without re-deriving
the report's structure.
"""

import logging
from pathlib import Path
from typing import Dict, List

from src.database import AlertDAO
from src.portfolio.aggregator import PortfolioAggregator
from src.portfolio.hotspot_detector import HotspotDetector
from src.utils import get_utc_now

logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = Path("reports")


class PortfolioReporter:
    """Generates text-based portfolio summary reports."""

    def __init__(self, reports_dir: Path = DEFAULT_REPORTS_DIR):
        self.aggregator = PortfolioAggregator()
        self.hotspot_detector = HotspotDetector()
        self.alert_dao = AlertDAO()
        self.reports_dir = Path(reports_dir)

    def generate_summary_report(self, write_to_file: bool = True) -> str:
        """
        Generate a text summary of current portfolio status.

        Args:
            write_to_file: If True (default), also writes the report to
                           reports/portfolio_YYYY-MM-DD.txt (overwriting
                           any earlier report generated the same day).

        Returns:
            The report as a single string.
        """
        metrics = self.aggregator.get_portfolio_metrics()
        hotspots = self.hotspot_detector.detect_hotspots()
        active_alerts = self.alert_dao.get_active_alerts()

        lines = self._build_lines(metrics, hotspots, active_alerts)
        report = "\n".join(lines)

        if write_to_file:
            self._write_report(report)

        return report

    def _build_lines(self, metrics: Dict, hotspots: List[Dict], active_alerts: List[Dict]) -> List[str]:
        lines = []
        lines.extend(self._header_section())
        lines.extend(self._metrics_section(metrics))
        lines.extend(self._hotspots_section(hotspots))
        lines.extend(self._alerts_section(active_alerts))
        return lines

    @staticmethod
    def _header_section() -> List[str]:
        generated_at = get_utc_now().isoformat()
        return [
            "=" * 70,
            "CLIMATE RISK ASSESSMENT - PORTFOLIO SUMMARY REPORT",
            "=" * 70,
            f"Generated: {generated_at}",
            "",
        ]

    @staticmethod
    def _metrics_section(metrics: Dict) -> List[str]:
        lines = [
            "-" * 70,
            "PORTFOLIO METRICS",
            "-" * 70,
            f"Total properties:      {metrics['total_properties']}",
            f"Assessed properties:   {metrics['assessed_properties']}",
            f"Latest assessment:     {metrics['latest_assessment_timestamp'] or 'N/A'}",
            "",
            "Risk level distribution:",
        ]
        for level in ("low", "medium", "high", "critical"):
            data = metrics["risk_level_distribution"][level]
            lines.append(f"  {level.capitalize():10s} {data['count']:4d}  ({data['percentage']:5.1f}%)")

        stats = metrics["score_stats"]
        lines.extend([
            "",
            "Risk score statistics:",
            f"  Average: {stats['average']:.2f}   Median: {stats['median']:.2f}   "
            f"Min: {stats['min']:.2f}   Max: {stats['max']:.2f}",
        ])

        by_state = metrics["geographic_distribution"]["by_state"]
        if by_state:
            lines.append("")
            lines.append("Geographic distribution (by state):")
            for state, count in sorted(by_state.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {state}: {count}")

        lines.append("")
        return lines

    @staticmethod
    def _hotspots_section(hotspots: List[Dict]) -> List[str]:
        lines = [
            "-" * 70,
            "GEOGRAPHIC HOTSPOTS",
            "-" * 70,
        ]
        if not hotspots:
            lines.append("No hotspots detected.")
        else:
            for hs in hotspots:
                lines.append(
                    f"  ({hs['center_lat']:.4f}, {hs['center_lon']:.4f}): "
                    f"{hs['property_count']} properties, avg risk {hs['avg_risk']:.1f}"
                )
        lines.append("")
        return lines

    @staticmethod
    def _alerts_section(active_alerts: List[Dict]) -> List[str]:
        lines = [
            "-" * 70,
            "ACTIVE ALERTS",
            "-" * 70,
        ]
        if not active_alerts:
            lines.append("No active alerts.")
            lines.append("")
            return lines

        portfolio_alerts = [a for a in active_alerts if a["risk_type"] == "portfolio_high_risk_pct"]
        property_alerts = [a for a in active_alerts if a["risk_type"] != "portfolio_high_risk_pct"]

        if portfolio_alerts:
            lines.append("Portfolio-level:")
            for a in portfolio_alerts:
                lines.append(f"  [{a['alert_level'].upper()}] {a['message']}")
            lines.append("")

        if property_alerts:
            lines.append(f"Property-level ({len(property_alerts)} active):")
            critical = sum(1 for a in property_alerts if a["alert_level"] == "critical")
            warning = sum(1 for a in property_alerts if a["alert_level"] == "warning")
            lines.append(f"  {critical} critical, {warning} warning")
            for a in property_alerts:
                lines.append(
                    f"  [{a['alert_level'].upper()}] property_id={a['property_id']} ({a['risk_type']}): {a['message']}"
                )

        lines.append("")
        return lines

    def _write_report(self, report: str) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        filename = f"portfolio_{get_utc_now().strftime('%Y-%m-%d')}.txt"
        path = self.reports_dir / filename
        path.write_text(report, encoding="utf-8")
        logger.info("Portfolio report written to %s", path)
        return path


if __name__ == "__main__":
    from src.config import setup_logging

    setup_logging()

    print("Generating portfolio summary report...")
    reporter = PortfolioReporter()
    report = reporter.generate_summary_report()
    print(report)
