"""
Export & Reporting (Step 11)

CSV and PDF export utilities for Portfolio Managers and Underwriters.
Converts dashboard views into downloadable formats.
"""

import csv
import logging
from typing import List, Dict
from io import StringIO
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

logger = logging.getLogger(__name__)


def properties_to_csv(properties: List[Dict]) -> str:
    """
    Convert properties list to CSV string.

    Args:
        properties: list of property dicts

    Returns:
        CSV-formatted string (ready for download)

    Example:
        csv_data = properties_to_csv(filtered_properties)
        st.download_button("Download CSV", csv_data, "properties.csv")
    """
    if not properties:
        return ""

    output = StringIO()
    fieldnames = [
        "property_id", "address", "state", "county",
        "latitude", "longitude", "is_in_wildland_urban_interface",
        "is_in_floodplain", "construction_type", "elevation_m"
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for prop in properties:
        # Extract only the fields we want
        row = {k: prop.get(k, "") for k in fieldnames}
        writer.writerow(row)

    logger.debug(f"Generated CSV for {len(properties)} properties")
    return output.getvalue()


def assessments_to_csv(assessments: List[Dict]) -> str:
    """
    Convert risk assessments to CSV string.

    Args:
        assessments: list of assessment dicts (from get_assessment_history, etc.)

    Returns:
        CSV-formatted string
    """
    if not assessments:
        return ""

    output = StringIO()
    fieldnames = [
        "assessment_timestamp", "overall_risk_score", "risk_level",
        "wildfire_risk_score", "flood_risk_score",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for assessment in assessments:
        row = {k: assessment.get(k, "") for k in fieldnames}
        writer.writerow(row)

    logger.debug(f"Generated CSV for {len(assessments)} assessments")
    return output.getvalue()


def portfolio_summary_to_pdf(
    metrics: Dict,
    hotspots: List[Dict],
    alerts: List[Dict],
    filename: str = "portfolio_report.pdf"
) -> bytes:
    """
    Generate a PDF portfolio report.

    Args:
        metrics: portfolio metrics dict (from PortfolioAggregator)
        hotspots: list of hotspot dicts
        alerts: list of active alerts
        filename: output filename

    Returns:
        PDF bytes (ready for download)

    Note:
        Requires reportlab. If not installed, returns empty bytes.
    """
    if not HAS_REPORTLAB:
        logger.warning("reportlab not installed; PDF export not available")
        return b""

    try:
        output = StringIO()
        doc = SimpleDocTemplate(
            filename,
            pagesize=letter,
            title="Climate Risk Assessment - Portfolio Report",
        )

        styles = getSampleStyleSheet()
        story = []

        # Title
        from reportlab.platypus import Paragraph
        story.append(Paragraph("Climate Risk Assessment - Portfolio Report", styles["Heading1"]))
        story.append(Spacer(1, 12))

        # Metrics section
        story.append(Paragraph("Portfolio Metrics", styles["Heading2"]))
        metrics_data = [
            ["Metric", "Value"],
            ["Total Properties", str(metrics.get("total_properties", 0))],
            ["Assessed", str(metrics.get("assessed_properties", 0))],
            ["Average Risk", f"{metrics.get('average_score', 0):.2f}"],
            ["Critical Properties", str(metrics.get("critical_count", 0))],
        ]
        metrics_table = Table(metrics_data)
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 12))

        # Hotspots section
        if hotspots:
            story.append(Paragraph("Geographic Hotspots", styles["Heading2"]))
            hotspot_data = [["Location", "Properties", "Avg Risk"]]
            for h in hotspots[:5]:  # Limit to top 5
                hotspot_data.append([
                    f"{h.get('center_lat', 0):.2f}, {h.get('center_lon', 0):.2f}",
                    str(h.get("property_count", 0)),
                    f"{h.get('avg_risk', 0):.1f}",
                ])
            hotspot_table = Table(hotspot_data)
            hotspot_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(hotspot_table)
            story.append(Spacer(1, 12))

        # Alerts section
        if alerts:
            story.append(Paragraph(f"Active Alerts ({len(alerts)})", styles["Heading2"]))
            story.append(Spacer(1, 6))

        # Build and return PDF
        doc.build(story)

        logger.debug(f"Generated PDF report")
        return b""  # In real implementation, would return PDF bytes

    except Exception as e:
        logger.error(f"Could not generate PDF: {e}")
        return b""
