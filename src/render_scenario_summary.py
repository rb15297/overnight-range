"""
Render a scenario summary CSV (from overnight_range_scenarios.py) into a PNG
summary graphic: bar chart of scenario distribution plus a compact metrics table.

Usage (from repo root):

    python -m src.render_scenario_summary --csv scenario_summary/NQ_2020-01-01_2024-12-31.csv
    python -m src.render_scenario_summary --csv scenario_summary/NQ_2020-01-01_2024-12-31.csv --out scenario_summary/summary.png
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_csv(csv_path: Path):
    """Load scenario summary CSV into list of dicts with numeric fields."""
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = dict(row)
            for key in ("scenario", "total_days",
                       "days_above_overnight_mid", "pct_above_overnight_mid",
                       "days_above_0609_low", "pct_above_0609_low",
                       "days_above_18_09_low", "pct_above_18_09_low",
                       "days_below_overnight_mid", "pct_below_overnight_mid",
                       "days_below_0609_high", "pct_below_0609_high",
                       "days_below_18_09_high", "pct_below_18_09_high",
                       "days_new_high_09_1130", "pct_new_high_09_1130",
                       "days_new_low_09_1130", "pct_new_low_09_1130",
                       "pct_of_total"):
                if key in r and r[key] != "":
                    try:
                        r[key] = float(r[key])
                    except ValueError:
                        pass
            if "scenario" in r and isinstance(r["scenario"], (int, float)):
                r["scenario"] = int(r["scenario"])
            if "total_days" in r and isinstance(r["total_days"], float):
                r["total_days"] = int(r["total_days"])
            rows.append(r)
    return rows


def _fmt_pct(val):
    if val == "" or val is None:
        return "-"
    try:
        return f"{float(val):.1f}%"
    except (TypeError, ValueError):
        return str(val)


def render_summary(csv_path: Path, out_path: Path, title: str = None) -> None:
    """Render the scenario summary CSV into a PNG: bar chart + table."""
    data = load_csv(csv_path)
    if not data:
        raise SystemExit(f"No data in {csv_path}")

    labels = [r.get("label", str(r.get("scenario", ""))) for r in data]
    pct_total = []
    for r in data:
        v = r.get("pct_of_total", 0)
        try:
            pct_total.append(float(v) if v != "" and v is not None else 0.0)
        except (TypeError, ValueError):
            pct_total.append(0.0)
    total_days = sum(int(r.get("total_days", 0) or 0) for r in data)

    fig = plt.figure(figsize=(14, 10))
    fig.suptitle(title or f"Overnight Range Scenarios Summary (06:00-09:00 ET)  |  Total days: {total_days}", fontsize=12)

    # 1) Bar chart: scenario distribution
    ax1 = fig.add_subplot(2, 1, 1)
    x = np.arange(len(labels))
    colors = ["#2ecc71" if s in (1, 2, 3, 7, 8, 9, 10, 11) else "#e74c3c" if s in (4, 5, 6, 12, 13, 14, 15, 16) else "#95a5a6"
              for s in [r.get("scenario", 0) for r in data]]
    bars = ax1.bar(x, pct_total, color=colors, edgecolor="black", linewidth=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=0, fontsize=9)
    ax1.set_ylabel("% of total days")
    ax1.set_title("Scenario distribution (1-3 bull, 4-6 bear, 7-11 gap bull, 12-16 gap bear, 17 inside)")
    ax1.set_ylim(0, max(pct_total) * 1.15 if pct_total else 1)
    ax1.grid(axis="y", alpha=0.3)

    # 2) Table: key metrics (only scenarios with total_days > 0)
    ax2 = fig.add_subplot(2, 1, 2)
    ax2.axis("off")

    table_data = []
    col_headers = ["Scenario", "n", "% tot", "Bull: above_mid / 06-09 low / 18-09 low", "Bear: below_mid / 06-09 high / 18-09 high", "new_high_09:11:30", "new_low_09:11:30"]
    for r in data:
        n = int(r.get("total_days", 0) or 0)
        if n == 0:
            continue
        bull_str = "-"
        if (r.get("pct_above_overnight_mid") or 0) > 0 or (r.get("pct_above_0609_low") or 0) > 0 or (r.get("pct_above_18_09_low") or 0) > 0:
            bull_str = f"{_fmt_pct(r.get('pct_above_overnight_mid'))} / {_fmt_pct(r.get('pct_above_0609_low'))} / {_fmt_pct(r.get('pct_above_18_09_low'))}"
        bear_str = "-"
        if (r.get("pct_below_overnight_mid") or 0) > 0 or (r.get("pct_below_0609_high") or 0) > 0 or (r.get("pct_below_18_09_high") or 0) > 0:
            bear_str = f"{_fmt_pct(r.get('pct_below_overnight_mid'))} / {_fmt_pct(r.get('pct_below_0609_high'))} / {_fmt_pct(r.get('pct_below_18_09_high'))}"
        nh = _fmt_pct(r.get("pct_new_high_09_1130")) if (r.get("pct_new_high_09_1130") or 0) > 0 else "-"
        nl = _fmt_pct(r.get("pct_new_low_09_1130")) if (r.get("pct_new_low_09_1130") or 0) > 0 else "-"
        table_data.append([
            r.get("label", str(r.get("scenario", ""))),
            str(n),
            f"{float(r.get('pct_of_total') or 0):.1f}%",
            bull_str,
            bear_str,
            nh,
            nl,
        ])

    if table_data:
        table = ax2.table(
            cellText=table_data,
            colLabels=col_headers,
            loc="center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render scenario summary CSV into a PNG summary graphic (bar chart + table)."
    )
    parser.add_argument("--csv", required=True, type=Path, help="Input scenario summary CSV path")
    parser.add_argument("--out", type=Path, default=None, help="Output PNG path (default: same stem as CSV with _summary.png)")
    parser.add_argument("--title", type=str, default=None, help="Optional figure title")
    args = parser.parse_args()

    out_path = args.out
    if out_path is None:
        out_path = args.csv.with_suffix("").with_name(args.csv.stem + "_summary.png")

    render_summary(args.csv, out_path, title=args.title)
    print(f"Wrote summary graphic to {out_path}")


if __name__ == "__main__":
    main()
