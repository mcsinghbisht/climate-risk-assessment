"""
Generate 'Day in the Life' persona journey diagrams.
Outputs PNG files to docs/diagrams/
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patches as mpatches
from pathlib import Path as FSPath

OUT_DIR = FSPath(__file__).parent.parent / "docs" / "diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLOR_AUTOMATION = "#2E5A88"
COLOR_AI = "#7A4FA3"
COLOR_OUTPUT = "#C9782F"
COLOR_TEXT = "#1F2937"
COLOR_ARROW = "#8A8A8A"
WHITE = "#FFFFFF"

CAP_COLORS = {
    "automation": COLOR_AUTOMATION,
    "ai": COLOR_AI,
    "output": COLOR_OUTPUT,
}
CAP_LABEL = {
    "automation": "Deterministic Automation",
    "ai": "Agentic AI / LLM",
    "output": "Output / Reporting",
}


def draw_journey(fig_title, subtitle, moments, filename):
    n = len(moments)
    fig_w = 14.0
    fig, ax = plt.subplots(figsize=(fig_w, 7))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(fig_w / 2, 6.55, fig_title, ha="center", fontsize=16.5,
            fontweight="bold", color=COLOR_TEXT)
    ax.text(fig_w / 2, 6.05, subtitle, ha="center", fontsize=11.5,
            style="italic", color=COLOR_ARROW)

    card_w = 2.4
    margin = 0.4
    gap = (fig_w - 2 * margin - n * card_w) / (n - 1)
    x0 = margin

    header_top = 5.3
    header_h = 0.55
    body_h = 1.7
    header_bottom = header_top - header_h
    body_top = header_bottom
    body_bottom = body_top - body_h
    arrow_y = (body_top + body_bottom) / 2

    edges = []
    for i, m in enumerate(moments):
        x = x0 + i * (card_w + gap)
        cap_color = CAP_COLORS[m["cap"]]

        # colored header band (time)
        header = FancyBboxPatch((x, header_bottom), card_w, header_h,
                                boxstyle="round,pad=0.01,rounding_size=0.03",
                                linewidth=0, facecolor=cap_color)
        ax.add_patch(header)
        ax.text(x + card_w / 2, header_bottom + header_h / 2, m["time"],
                ha="center", va="center", fontsize=10.5, fontweight="bold", color=WHITE)

        # white body
        body = FancyBboxPatch((x, body_bottom), card_w, body_h,
                              boxstyle="round,pad=0.01,rounding_size=0.03",
                              linewidth=1.5, edgecolor=cap_color, facecolor=WHITE)
        ax.add_patch(body)
        ax.text(x + card_w / 2, body_top - 0.35, m["title"], ha="center", va="center",
                fontsize=10, fontweight="bold", color=COLOR_TEXT)
        ax.text(x + card_w / 2, body_top - 1.08, m["desc"], ha="center", va="center",
                fontsize=8.4, color=COLOR_TEXT)

        # capability tag under card
        ax.text(x + card_w / 2, body_bottom - 0.32, "● " + CAP_LABEL[m["cap"]],
                ha="center", va="center", fontsize=8.2, color=cap_color, fontweight="bold")

        edges.append((x, x + card_w))

    # arrows in the gaps between cards
    for i in range(n - 1):
        arr = FancyArrowPatch((edges[i][1] + 0.02, arrow_y), (edges[i + 1][0] - 0.02, arrow_y),
                              arrowstyle="-|>", mutation_scale=14, linewidth=1.7, color=COLOR_ARROW)
        ax.add_patch(arr)

    # legend (only capabilities used)
    used = list(dict.fromkeys([m["cap"] for m in moments]))
    legend_items = [mpatches.Patch(facecolor=CAP_COLORS[c], edgecolor=CAP_COLORS[c],
                                   label=CAP_LABEL[c]) for c in used]
    ax.legend(handles=legend_items, loc="lower center", ncol=len(used),
              bbox_to_anchor=(0.5, 0.02), frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------
# UNDERWRITER
# ---------------------------------------------------------------
underwriter = [
    {"time": "8:00 AM", "title": "Morning Alert Digest",
     "desc": "Reads a plain-language\nsummary of policies whose\nrisk changed overnight", "cap": "ai"},
    {"time": "10:30 AM", "title": "New Policy Quote",
     "desc": "Checks the live wildfire /\nflood risk score before\nbinding coverage", "cap": "automation"},
    {"time": "1:00 PM", "title": "Risk-Spike Response",
     "desc": "A fire nears an insured home;\nreviews the Recommendation\nAgent's suggested actions", "cap": "ai"},
    {"time": "3:30 PM", "title": "Renewal Repricing",
     "desc": "Uses the 30-day risk trend\nto justify an adjusted\npremium at renewal", "cap": "automation"},
    {"time": "5:00 PM", "title": "Audit Close-out",
     "desc": "Confirms each decision is\nlogged with its supporting\nrisk data", "cap": "output"},
]
draw_journey(
    "A Day in the Life: Underwriter",
    "Prices and manages individual policies using live, explainable property-level risk",
    underwriter,
    "05_day_underwriter.png",
)

# ---------------------------------------------------------------
# RISK MANAGER
# ---------------------------------------------------------------
risk_manager = [
    {"time": "9:00 AM", "title": "Portfolio Health Check",
     "desc": "Reviews the book's risk\ndistribution on the\nportfolio dashboard", "cap": "automation"},
    {"time": "11:00 AM", "title": "Hotspot Alert",
     "desc": "Reads the Portfolio Insight\nAgent's narrative on a new\nhigh-risk cluster", "cap": "ai"},
    {"time": "1:30 PM", "title": "Anomaly Review",
     "desc": "Assesses an unprecedented\nrainfall event flagged by the\nAnomaly Detection Agent", "cap": "ai"},
    {"time": "3:00 PM", "title": "CAT Scenario Simulation",
     "desc": "Runs a catastrophe stress\ntest to plan reinsurance\ncover", "cap": "automation"},
    {"time": "4:30 PM", "title": "Executive Reporting",
     "desc": "Exports a portfolio risk\nsummary for leadership\nand reinsurers", "cap": "output"},
]
draw_journey(
    "A Day in the Life: Risk Manager",
    "Monitors accumulation and concentration risk across the entire portfolio",
    risk_manager,
    "06_day_risk_manager.png",
)

# ---------------------------------------------------------------
# BROKER / CUSTOMER LIAISON
# ---------------------------------------------------------------
broker = [
    {"time": "8:30 AM", "title": "Client Watchlist",
     "desc": "Sees which clients' properties\nhave rising risk overnight", "cap": "output"},
    {"time": "11:00 AM", "title": "Proactive Outreach",
     "desc": "Contacts an insured about\nevacuation readiness from a\ncustomer-facing alert", "cap": "ai"},
    {"time": "2:00 PM", "title": "Coverage Conversation",
     "desc": "Explains a risk-driven premium\nchange using the platform's\nplain-language rationale", "cap": "ai"},
    {"time": "4:00 PM", "title": "Mitigation Guidance",
     "desc": "Shares recommended mitigation\nsteps from the Recommendation\nAgent with the client", "cap": "ai"},
]
draw_journey(
    "A Day in the Life: Broker / Customer Liaison",
    "Turns risk intelligence into proactive, plain-language conversations with insureds",
    broker,
    "07_day_broker.png",
)

print(f"[OK] Persona diagrams generated in {OUT_DIR}")
for f in ["05_day_underwriter.png", "06_day_risk_manager.png", "07_day_broker.png"]:
    print(f"  - {f}")
