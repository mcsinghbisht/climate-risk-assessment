"""
Generate architecture diagrams for the solution document.
Outputs PNG files to docs/diagrams/
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path
import matplotlib.patches as mpatches
from pathlib import Path as FSPath

OUT_DIR = FSPath(__file__).parent.parent / "docs" / "diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Color palette (brand-neutral, professional)
COLOR_AUTOMATION = "#2E5A88"      # deep blue - deterministic layer
COLOR_AUTOMATION_LIGHT = "#DCE7F2"
COLOR_AI = "#7A4FA3"              # purple - AI/LLM layer
COLOR_AI_LIGHT = "#EDE3F5"
COLOR_DATA = "#3C8C6E"            # green - data
COLOR_DATA_LIGHT = "#DCEEE6"
COLOR_OUTPUT = "#C9782F"          # amber - outputs/stakeholders
COLOR_OUTPUT_LIGHT = "#F7E7D6"
COLOR_TEXT = "#1F2937"
COLOR_ARROW = "#555555"


def draw_box(ax, xy, w, h, text, facecolor, edgecolor=None, fontsize=10.5,
             fontweight="normal", textcolor=COLOR_TEXT, style="round,pad=0.02,rounding_size=0.02"):
    edgecolor = edgecolor or facecolor
    box = FancyBboxPatch(
        xy, w, h,
        boxstyle=style,
        linewidth=1.6,
        edgecolor=edgecolor,
        facecolor=facecolor,
    )
    ax.add_patch(box)
    cx, cy = xy[0] + w / 2, xy[1] + h / 2
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize,
             fontweight=fontweight, color=textcolor, wrap=True)
    return (cx, cy)


def draw_arrow(ax, start, end, color=COLOR_ARROW, style="-|>", lw=1.6, connectionstyle="arc3,rad=0.0", ls="solid"):
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle=style,
        mutation_scale=14,
        linewidth=lw,
        color=color,
        connectionstyle=connectionstyle,
        linestyle=ls,
    )
    ax.add_patch(arrow)


def new_fig(w=13, h=8):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


# ============================================================
# DIAGRAM 1: High-Level Solution Architecture
# ============================================================
def diagram_1_high_level():
    fig, ax = new_fig(14, 9)

    # Title
    ax.text(7, 8.6, "Climate Risk Assessment Platform — High-Level Architecture",
            ha="center", fontsize=15, fontweight="bold", color=COLOR_TEXT)

    # Row 1: External Data Sources
    ax.text(7, 7.9, "EXTERNAL DATA SOURCES (Public APIs)", ha="center", fontsize=10,
            fontweight="bold", color=COLOR_TEXT)
    sources = ["NASA FIRMS\n(Wildfire)", "NOAA\n(Weather)", "USGS\n(River Gauges)", "FEMA\n(Floodplain Maps)"]
    src_centers = []
    x0 = 0.8
    for i, s in enumerate(sources):
        c = draw_box(ax, (x0 + i * 3.2, 7.0), 2.7, 0.7, s, COLOR_DATA_LIGHT, COLOR_DATA, fontsize=9.5)
        src_centers.append(c)

    # Row 2: Data Ingestion Layer
    ing_c = draw_box(ax, (2.5, 5.9), 9, 0.75, "DATA INGESTION LAYER\n(Scheduled every 5 minutes — configurable)",
                       COLOR_DATA_LIGHT, COLOR_DATA, fontsize=10.5, fontweight="bold")
    for sc in src_centers:
        draw_arrow(ax, (sc[0], 7.0), (sc[0], 6.65), color=COLOR_DATA)

    # Row 3: Database
    db_c = draw_box(ax, (2.5, 4.85), 9, 0.7, "SQLite DATABASE\nproperties | hazard_data | risk_assessments | alerts | alert_history",
                     "#FFFFFF", COLOR_TEXT, fontsize=9.5)
    draw_arrow(ax, (7, 5.9), (7, 5.55), color=COLOR_DATA)

    # Row 4: Core processing - split automation vs AI
    auto_c = draw_box(ax, (1.0, 3.5), 5.6, 0.95,
                       "DETERMINISTIC AUTOMATION LAYER\nRisk Scoring · Threshold Alerts ·\nContinuous Monitoring · Portfolio Aggregation",
                       COLOR_AUTOMATION_LIGHT, COLOR_AUTOMATION, fontsize=9.5, fontweight="bold")
    ai_c = draw_box(ax, (7.4, 3.5), 5.6, 0.95,
                     "AGENTIC AI / LLM LAYER\nRecommendation Agent · Portfolio Insight Agent ·\nAnomaly Detection · NL Alert Generation",
                     COLOR_AI_LIGHT, COLOR_AI, fontsize=9.5, fontweight="bold")
    draw_arrow(ax, (4.5, 4.85), (3.8, 4.45), color=COLOR_AUTOMATION)
    draw_arrow(ax, (7, 4.85), (8.5, 4.45), color=COLOR_AI)
    draw_arrow(ax, (6.6, 3.97), (7.4, 3.97), color=COLOR_ARROW, connectionstyle="arc3,rad=-0.2")
    ax.text(7, 4.15, "risk context", ha="center", fontsize=7.5, color=COLOR_ARROW, style="italic")

    # Row 5: Outputs
    outs = ["Alerts\n(Underwriters)", "Portfolio Dashboards\n(Risk Managers)",
            "Underwriting/Claims\nIntegration (future)"]
    out_centers = []
    x0 = 1.5
    for i, o in enumerate(outs):
        c = draw_box(ax, (x0 + i * 3.7, 2.2), 3.2, 0.75, o, COLOR_OUTPUT_LIGHT, COLOR_OUTPUT, fontsize=9.5)
        out_centers.append(c)

    draw_arrow(ax, (3.8, 3.5), (out_centers[0][0], 2.95), color=COLOR_ARROW)
    draw_arrow(ax, (7, 3.5), (out_centers[1][0], 2.95), color=COLOR_ARROW)
    draw_arrow(ax, (10.2, 3.5), (out_centers[2][0], 2.95), color=COLOR_ARROW)

    # Legend
    legend_items = [
        mpatches.Patch(facecolor=COLOR_DATA_LIGHT, edgecolor=COLOR_DATA, label="Data Layer"),
        mpatches.Patch(facecolor=COLOR_AUTOMATION_LIGHT, edgecolor=COLOR_AUTOMATION, label="Deterministic Automation Layer"),
        mpatches.Patch(facecolor=COLOR_AI_LIGHT, edgecolor=COLOR_AI, label="Agentic AI / LLM Layer"),
        mpatches.Patch(facecolor=COLOR_OUTPUT_LIGHT, edgecolor=COLOR_OUTPUT, label="Stakeholder Outputs"),
    ]
    ax.legend(handles=legend_items, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02),
              frameon=False, fontsize=8.5)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "01_high_level_architecture.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ============================================================
# DIAGRAM 2: Hybrid Architecture (Automation + Agentic AI detail)
# ============================================================
def diagram_2_hybrid_detail():
    fig, ax = new_fig(14.5, 9.5)

    ax.text(7, 9.1, "Hybrid Architecture: Deterministic Automation + Agentic AI Layer",
            ha="center", fontsize=15, fontweight="bold", color=COLOR_TEXT)

    # PHASE 1 band
    ax.add_patch(FancyBboxPatch((0.3, 5.3), 13.4, 3.15, boxstyle="round,pad=0.02,rounding_size=0.03",
                                  linewidth=1.5, edgecolor=COLOR_AUTOMATION, facecolor=COLOR_AUTOMATION_LIGHT, alpha=0.35))
    ax.text(1.0, 8.15, "DETERMINISTIC AUTOMATION LAYER", fontsize=11, fontweight="bold", color=COLOR_AUTOMATION)

    p1_boxes = [
        ("Data Ingestion\n(APIs every 5 min)", 0.8, 6.4),
        ("Rule-Based Risk\nScoring Engine", 3.35, 6.4),
        ("Threshold\nAlert Engine", 5.9, 6.4),
        ("Continuous\nMonitoring Loop", 8.45, 6.4),
        ("Portfolio\nAggregation", 11.0, 6.4),
    ]
    p1_centers = []
    for label, x, y in p1_boxes:
        c = draw_box(ax, (x, y), 2.2, 1.1, label, "#FFFFFF", COLOR_AUTOMATION, fontsize=9)
        p1_centers.append(c)
    for i in range(len(p1_centers) - 1):
        draw_arrow(ax, (p1_centers[i][0] + 1.1, p1_centers[i][1]), (p1_centers[i+1][0] - 1.15, p1_centers[i+1][1]), color=COLOR_AUTOMATION)

    # PHASE 2 band
    ax.add_patch(FancyBboxPatch((0.3, 1.3), 13.4, 3.4, boxstyle="round,pad=0.02,rounding_size=0.03",
                                  linewidth=1.5, edgecolor=COLOR_AI, facecolor=COLOR_AI_LIGHT, alpha=0.35))
    ax.text(1.0, 4.4, "AGENTIC AI / LLM LAYER (hybrid intelligence add-on)", fontsize=11, fontweight="bold", color=COLOR_AI)

    p2_boxes = [
        ("Recommendation\nAgent", 0.8, 2.3),
        ("Portfolio Insight\nAgent", 3.35, 2.3),
        ("Anomaly Detection\nAgent", 5.9, 2.3),
        ("Natural-Language\nAlert Generator", 8.45, 2.3),
        ("Underwriting\nAssistant (future)", 11.0, 2.3),
    ]
    p2_centers = []
    for label, x, y in p2_boxes:
        c = draw_box(ax, (x, y), 2.2, 1.1, label, "#FFFFFF", COLOR_AI, fontsize=8.7)
        p2_centers.append(c)

    # Orchestration arrows: Phase 1 outputs feed Phase 2 agents (risk_assessments + hazard context)
    for i, pc in enumerate(p1_centers[1:4]):  # scoring, alert, monitoring feed AI layer
        target = p2_centers[i]
        draw_arrow(ax, (pc[0], pc[1] - 0.55), (target[0], target[1] + 0.55), color=COLOR_ARROW,
                   connectionstyle="arc3,rad=0.05", ls="dashed")

    ax.text(7, 5.05, "structured risk data (JSON) passed as agent context — not raw automation replaced",
            ha="center", fontsize=8.5, style="italic", color=COLOR_ARROW)

    # Outputs from Phase 2
    out_c = draw_box(ax, (4.7, 0.15), 4.6, 0.75,
                      "Contextual, natural-language outputs to underwriters & risk managers",
                      COLOR_OUTPUT_LIGHT, COLOR_OUTPUT, fontsize=9)
    for pc in p2_centers:
        draw_arrow(ax, (pc[0], pc[1] - 0.55), (out_c[0], out_c[1] + 0.4), color=COLOR_OUTPUT, connectionstyle="arc3,rad=0.02")

    fig.tight_layout()
    fig.savefig(OUT_DIR / "02_hybrid_architecture.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ============================================================
# DIAGRAM 3: 5-Minute Continuous Monitoring Cycle (data flow)
# ============================================================
def diagram_3_monitoring_cycle():
    fig, ax = new_fig(13, 8.2)
    ax.text(6.5, 7.8, "Continuous Monitoring Cycle (Runs Every 5 Minutes — Configurable)",
            ha="center", fontsize=14.5, fontweight="bold", color=COLOR_TEXT)

    # Steps listed in flow order (1 -> 8)
    steps = [
        "1. Fetch hazard data\n(wildfire, weather, flood APIs)",
        "2. Normalize & store\nin hazard_data table",
        "3. Load property data\n(100 properties)",
        "4. Calculate risk scores\n(wildfire + flood)",
        "5. Evaluate alert\nthresholds",
        "6. Trigger alerts\n(if breached)",
        "7. Store risk snapshot\n(audit trail)",
        "8. Aggregate portfolio\nmetrics & hotspots",
    ]

    box_w, box_h = 2.7, 1.25
    xgap = 0.35
    col_x = [0.55 + c * (box_w + xgap) for c in range(4)]
    top_y = 5.5
    bot_y = 3.1

    # Boustrophedon (snake) layout so numbers read naturally along the flow:
    #   top row L->R : 1 2 3 4
    #   down right side: 4 -> 5
    #   bottom row R->L: 5 6 7 8   (5 sits below 4, 8 sits below 1)
    #   up left side (loop): 8 -> 1
    positions = [
        (col_x[0], top_y),  # 1
        (col_x[1], top_y),  # 2
        (col_x[2], top_y),  # 3
        (col_x[3], top_y),  # 4
        (col_x[3], bot_y),  # 5  (below 4)
        (col_x[2], bot_y),  # 6
        (col_x[1], bot_y),  # 7
        (col_x[0], bot_y),  # 8  (below 1)
    ]

    centers = []
    for i, step in enumerate(steps):
        x, y = positions[i]
        c = draw_box(ax, (x, y), box_w, box_h, step, "#FFFFFF", COLOR_AUTOMATION, fontsize=8.8)
        centers.append(c)

    # 1 -> 2 -> 3 -> 4  (rightward along top)
    for i in range(3):
        draw_arrow(ax, (centers[i][0] + box_w / 2, centers[i][1]),
                   (centers[i + 1][0] - box_w / 2, centers[i + 1][1]), color=COLOR_AUTOMATION)
    # 4 -> 5  (down the right side)
    draw_arrow(ax, (centers[3][0], centers[3][1] - box_h / 2),
               (centers[4][0], centers[4][1] + box_h / 2), color=COLOR_AUTOMATION)
    # 5 -> 6 -> 7 -> 8  (leftward along bottom)
    for i in range(4, 7):
        draw_arrow(ax, (centers[i][0] - box_w / 2, centers[i][1]),
                   (centers[i + 1][0] + box_w / 2, centers[i + 1][1]), color=COLOR_AUTOMATION)
    # 8 -> 1  (loop back up the left side, dashed to signal repetition)
    draw_arrow(ax, (centers[7][0], centers[7][1] + box_h / 2),
               (centers[0][0], centers[0][1] - box_h / 2), color=COLOR_ARROW, ls="dashed")

    # "loop repeats" annotation beside the left-side return arrow
    mid_y = (top_y + bot_y + box_h) / 2
    ax.text(col_x[0] - 0.42, mid_y, "loop\nrepeats", ha="center", va="center",
            fontsize=8, style="italic", color=COLOR_ARROW, rotation=90)

    ax.text(6.5, 1.7, "The 8-step cycle runs end-to-end, then repeats every 5 minutes "
            "(interval configurable via settings.json).",
            ha="center", fontsize=9.5, style="italic", color=COLOR_ARROW)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "03_monitoring_cycle.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ============================================================
# DIAGRAM 4: Data Product Value Chain
# ============================================================
def diagram_4_data_product_chain():
    fig, ax = new_fig(13, 6)
    ax.text(6.5, 5.6, "Data Product Value Chain", ha="center", fontsize=15, fontweight="bold", color=COLOR_TEXT)

    stages = [
        ("RAW DATA", "Fragmented public\nhazard feeds", COLOR_DATA_LIGHT, COLOR_DATA),
        ("INGESTED &\nMODELED DATA", "Structured, validated,\ngeospatially indexed", COLOR_DATA_LIGHT, COLOR_DATA),
        ("RISK\nINTELLIGENCE", "Property-level scores +\nconfidence + explanation", COLOR_AUTOMATION_LIGHT, COLOR_AUTOMATION),
        ("AI-ENRICHED\nINSIGHT", "Contextual recommendations,\nnatural language", COLOR_AI_LIGHT, COLOR_AI),
        ("BUSINESS\nDECISION", "Dynamic pricing, alerts,\nportfolio actions", COLOR_OUTPUT_LIGHT, COLOR_OUTPUT),
    ]
    w, h = 2.15, 1.7
    gap = 0.35
    x0 = 0.4
    centers = []
    for i, (title, desc, fc, ec) in enumerate(stages):
        x = x0 + i * (w + gap)
        y = 2.3
        draw_box(ax, (x, y + 0.75), w, 0.55, title, fc, ec, fontsize=9.3, fontweight="bold")
        c2 = draw_box(ax, (x, y), w, 0.65, desc, "#FFFFFF", ec, fontsize=8)
        centers.append((x + w/2, y + 0.75))
    for i in range(len(centers) - 1):
        draw_arrow(ax, (centers[i][0] + w/2, centers[i][1]), (centers[i+1][0] - w/2, centers[i+1][1]), color=COLOR_ARROW, lw=2)

    ax.text(6.5, 1.0, "Each stage adds measurable value — this progression (data → decision) is the\ncore definition of a Data Product, not just a reporting pipeline.",
            ha="center", fontsize=9.5, style="italic", color=COLOR_TEXT)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "04_data_product_chain.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    diagram_1_high_level()
    diagram_2_hybrid_detail()
    diagram_3_monitoring_cycle()
    diagram_4_data_product_chain()
    print(f"[OK] Diagrams generated in {OUT_DIR}")
    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"  - {f.name}")
