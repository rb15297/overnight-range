"""
Draw schematic diagrams for the six overnight range scenarios (1–3 bull, 4–6 bear inverse).
Saves PNGs to live_trading/docs/ for use in OVERNIGHT_RANGE_SCENARIOS.md.
"""

from pathlib import Path
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib not installed; run: pip install matplotlib")
    raise

DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)

# Shared: 3 levels, time 0 = 06:00 to 3 = 09:00 (hours)
def _base_axes(ax, title):
    ax.set_xlim(0, 3)
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xticklabels(["06:00", "07:00", "08:00", "09:00"])
    ax.set_xlabel("Time (ET)")
    ax.set_ylabel("Price")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    # Reference lines: high=2, mid=1, low=0 (normalized)
    ax.axhline(2, color="gray", linestyle="--", linewidth=1, label="Overnight high")
    ax.axhline(1, color="gray", linestyle="--", linewidth=1, label="Overnight mid")
    ax.axhline(0, color="gray", linestyle="--", linewidth=1, label="Overnight low")


def draw_scenario_1():
    """Price goes below overnight low, then closes above mid at 09:00."""
    fig, ax = plt.subplots(figsize=(6, 4))
    _base_axes(ax, "Scenario 1: Below low, close above mid")
    t = np.array([0, 0.8, 1.5, 2.2, 3.0])
    price = np.array([1.1, -0.2, 0.3, 0.8, 1.3])  # dip below 0 (low), end above 1 (mid)
    ax.plot(t, price, "b-", linewidth=2)
    ax.plot(t[-1], price[-1], "go", markersize=10, label="Close at 09:00")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "overnight_scenario_1.png", dpi=120)
    plt.close(fig)


def draw_scenario_2():
    """Price stays above overnight low, closes above high at 09:00."""
    fig, ax = plt.subplots(figsize=(6, 4))
    _base_axes(ax, "Scenario 2: Above low, close above high")
    t = np.array([0, 0.7, 1.4, 2.2, 3.0])
    price = np.array([0.4, 0.6, 1.2, 1.6, 2.2])  # above 0 (low), end above 2 (high)
    ax.plot(t, price, "b-", linewidth=2)
    ax.plot(t[-1], price[-1], "go", markersize=10, label="Close at 09:00")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "overnight_scenario_2.png", dpi=120)
    plt.close(fig)


def draw_scenario_3():
    """Price stays above overnight mid, closes above high at 09:00."""
    fig, ax = plt.subplots(figsize=(6, 4))
    _base_axes(ax, "Scenario 3: Above mid, close above high")
    t = np.array([0, 0.8, 1.6, 2.4, 3.0])
    price = np.array([1.2, 1.4, 1.7, 2.0, 2.3])  # above 1 (mid) throughout, end above 2 (high)
    ax.plot(t, price, "b-", linewidth=2)
    ax.plot(t[-1], price[-1], "go", markersize=10, label="Close at 09:00")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "overnight_scenario_3.png", dpi=120)
    plt.close(fig)


def draw_scenario_4():
    """Price goes above overnight high, then closes below mid at 09:00 (inverse of 1)."""
    fig, ax = plt.subplots(figsize=(6, 4))
    _base_axes(ax, "Scenario 4: Above high, close below mid (Inv 1)")
    t = np.array([0, 0.8, 1.5, 2.2, 3.0])
    price = np.array([0.9, 2.3, 1.5, 1.0, 0.6])  # spike above 2 (high), end below 1 (mid)
    ax.plot(t, price, "b-", linewidth=2)
    ax.plot(t[-1], price[-1], "ro", markersize=10, label="Close at 09:00")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "overnight_scenario_4.png", dpi=120)
    plt.close(fig)


def draw_scenario_5():
    """Price stays below overnight high, closes below low at 09:00 (inverse of 2)."""
    fig, ax = plt.subplots(figsize=(6, 4))
    _base_axes(ax, "Scenario 5: Below high, close below low (Inv 2)")
    t = np.array([0, 0.7, 1.4, 2.2, 3.0])
    price = np.array([1.6, 1.4, 0.8, 0.3, -0.2])  # below 2 (high), end below 0 (low)
    ax.plot(t, price, "b-", linewidth=2)
    ax.plot(t[-1], price[-1], "ro", markersize=10, label="Close at 09:00")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "overnight_scenario_5.png", dpi=120)
    plt.close(fig)


def draw_scenario_6():
    """Price stays below overnight mid, closes below low at 09:00 (inverse of 3)."""
    fig, ax = plt.subplots(figsize=(6, 4))
    _base_axes(ax, "Scenario 6: Below mid, close below low (Inv 3)")
    t = np.array([0, 0.8, 1.6, 2.4, 3.0])
    price = np.array([0.8, 0.6, 0.3, 0.1, -0.3])  # below 1 (mid) throughout, end below 0 (low)
    ax.plot(t, price, "b-", linewidth=2)
    ax.plot(t[-1], price[-1], "ro", markersize=10, label="Close at 09:00")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS_DIR / "overnight_scenario_6.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    draw_scenario_1()
    draw_scenario_2()
    draw_scenario_3()
    draw_scenario_4()
    draw_scenario_5()
    draw_scenario_6()
    print(f"Saved 6 diagrams to {DOCS_DIR}")
