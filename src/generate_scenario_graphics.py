"""
Generate individual day graphics for overnight range scenarios.

For each trading day analyzed, creates a chart showing:
- Overnight range (18:00 ET prev day → 06:00 ET) with high/mid/low reference lines
- 06:00-09:00 ET window with 1-minute candlesticks
- 09:00-11:30 ET window with 1-minute candlesticks

Graphics are saved to scenario-specific folders: scenario_graphics/scenario_N/
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates

from sqlalchemy.orm import sessionmaker

from src.database_models import RawBar1Min
from src.overnight_range_service import (
    get_engine,
    OvernightRangeResult,
    ET,
    UTC,
    CONFIG_PATH,
)
from src.overnight_range_scenarios import (
    run_scenario_analysis,
    _day_session_windows,
)


def plot_candlestick(ax, times, bars, width_minutes=0.8):
    """
    Plot 1-minute candlesticks on the given axes.
    
    Args:
        ax: matplotlib axes
        times: list of datetime objects (bar timestamps)
        bars: list of RawBar1Min objects
        width_minutes: width of candlestick body in minutes
    """
    if not bars:
        return
    
    # Convert width in minutes to days for matplotlib
    width_days = width_minutes / (24 * 60)
    
    for i, (t, bar) in enumerate(zip(times, bars)):
        # Determine color
        if bar.close >= bar.open:
            color = 'green'
            body_low = bar.open
            body_high = bar.close
        else:
            color = 'red'
            body_low = bar.close
            body_high = bar.open
        
        # Draw high-low line (wick)
        ax.plot([t, t], [bar.low, bar.high], color='black', linewidth=0.5)
        
        # Draw open-close rectangle (body)
        if body_high != body_low:
            rect = Rectangle(
                (mdates.date2num(t) - width_days/2, body_low),
                width_days,
                body_high - body_low,
                facecolor=color,
                edgecolor='black',
                linewidth=0.5
            )
            ax.add_patch(rect)
        else:
            # Doji - draw horizontal line
            ax.plot([mdates.date2num(t) - width_days/2, mdates.date2num(t) + width_days/2],
                   [bar.close, bar.close], color='black', linewidth=1)


def generate_day_graphic(
    session_date: date,
    scenario: int,
    overnight_range: OvernightRangeResult,
    bars_06_1130: List[RawBar1Min],
    symbol: str,
    output_dir: Path,
):
    """
    Generate a single day's graphic showing overnight range and price action 06:00-11:30.
    
    Args:
        session_date: The trading session date
        scenario: Scenario number (1-17)
        overnight_range: OvernightRangeResult with high/mid/low
        bars_06_1130: List of 1-minute bars from 06:00 to 11:30 ET
        symbol: Trading symbol (e.g., NQ)
        output_dir: Directory to save the graphic
    """
    if not bars_06_1130:
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Get time boundaries
    start_06_et, end_09_et, _ = _day_session_windows(session_date)
    end_1130_et = datetime(session_date.year, session_date.month, session_date.day, 11, 30, 0, tzinfo=ET)
    
    # Convert to matplotlib dates for plotting
    start_06_num = mdates.date2num(start_06_et)
    end_09_num = mdates.date2num(end_09_et)
    end_1130_num = mdates.date2num(end_1130_et)
    
    # Calculate price range for y-axis
    all_highs = [b.high for b in bars_06_1130]
    all_lows = [b.low for b in bars_06_1130]
    price_min = min(all_lows + [overnight_range.low])
    price_max = max(all_highs + [overnight_range.high])
    price_range = price_max - price_min
    y_margin = price_range * 0.1
    
    # Set axis limits
    ax.set_xlim(start_06_num, end_1130_num)
    ax.set_ylim(price_min - y_margin, price_max + y_margin)
    
    # Draw background shading for time windows
    # Overnight range reference - yellow box on left side (visual indicator)
    overnight_width = (end_09_num - start_06_num) * 0.15  # 15% of 06-09 width
    overnight_rect = Rectangle(
        (start_06_num - overnight_width, overnight_range.low),
        overnight_width,
        overnight_range.high - overnight_range.low,
        facecolor='yellow',
        alpha=0.3,
        edgecolor='none',
        zorder=1
    )
    ax.add_patch(overnight_rect)
    
    # 06:00-09:00 ET window - medium gray
    rect_0609 = Rectangle(
        (start_06_num, price_min - y_margin),
        end_09_num - start_06_num,
        (price_max + y_margin) - (price_min - y_margin),
        facecolor='gray',
        alpha=0.2,
        edgecolor='none',
        zorder=1
    )
    ax.add_patch(rect_0609)
    
    # 09:00-11:30 ET window - light gray
    rect_091130 = Rectangle(
        (end_09_num, price_min - y_margin),
        end_1130_num - end_09_num,
        (price_max + y_margin) - (price_min - y_margin),
        facecolor='gray',
        alpha=0.1,
        edgecolor='none',
        zorder=1
    )
    ax.add_patch(rect_091130)
    
    # Draw overnight range reference lines
    ax.axhline(overnight_range.high, color='darkblue', linestyle='--', linewidth=1.5, 
               label=f'ON High: {overnight_range.high:.2f}', zorder=2)
    ax.axhline(overnight_range.middle, color='blue', linestyle='--', linewidth=1.5,
               label=f'ON Mid: {overnight_range.middle:.2f}', zorder=2)
    ax.axhline(overnight_range.low, color='darkblue', linestyle='--', linewidth=1.5,
               label=f'ON Low: {overnight_range.low:.2f}', zorder=2)
    
    # Draw vertical lines to mark time boundaries
    ax.axvline(start_06_num, color='black', linestyle='-', linewidth=1, alpha=0.5, zorder=2)
    ax.axvline(end_09_num, color='black', linestyle='-', linewidth=1.5, alpha=0.7, zorder=2)
    ax.axvline(end_1130_num, color='black', linestyle='-', linewidth=1, alpha=0.5, zorder=2)
    
    # Plot candlesticks
    bar_times = [b.timestamp.astimezone(ET) for b in bars_06_1130]
    plot_candlestick(ax, bar_times, bars_06_1130, width_minutes=0.8)
    
    # Add time window labels
    # Calculate label positions
    mid_0609 = start_06_num + (end_09_num - start_06_num) / 2
    mid_091130 = end_09_num + (end_1130_num - end_09_num) / 2
    label_y = price_max + y_margin * 0.5
    
    ax.text(mid_0609, label_y, '06-09', ha='center', va='center', 
            fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax.text(mid_091130, label_y, '09-11:30', ha='center', va='center',
            fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Add overnight range label on the yellow box
    overnight_label_x = start_06_num - overnight_width / 2
    overnight_label_y = overnight_range.middle
    ax.text(overnight_label_x, overnight_label_y, 'overnight\nrange', ha='center', va='center',
            fontsize=9, rotation=0, bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))
    
    # Format x-axis with time labels
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=ET))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Labels and title
    ax.set_xlabel('Time (ET)', fontsize=12)
    ax.set_ylabel('Price', fontsize=12)
    ax.set_title(f'{symbol} - {session_date} - Scenario {scenario}', fontsize=14, fontweight='bold')
    
    # Add legend
    ax.legend(loc='upper left', fontsize=9)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle=':', zorder=0)
    
    # Tight layout
    fig.tight_layout()
    
    # Save figure
    filename = f"{session_date}_scenario_{scenario}.png"
    filepath = output_dir / filename
    fig.savefig(filepath, dpi=120, bbox_inches='tight')
    plt.close(fig)
    
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Generate individual day graphics for overnight range scenarios"
    )
    parser.add_argument("--symbol", required=True, help="Symbol e.g. NQ, ES")
    
    # Date arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="Single date YYYY-MM-DD")
    group.add_argument("--start", help="Start date YYYY-MM-DD (use with --end)")
    parser.add_argument("--end", help="End date YYYY-MM-DD (use with --start)")
    
    # Optional filters
    parser.add_argument("--scenarios", help="Comma-separated scenario numbers to generate (e.g., 1,2,3)")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--db", help="Path to Trading.db")
    
    args = parser.parse_args()
    
    # Parse date range
    if args.date:
        start_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        end_date = start_date
    else:
        if not args.end:
            parser.error("--end is required when using --start")
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    
    # Parse scenario filter
    scenario_filter = None
    if args.scenarios:
        scenario_filter = set(int(s.strip()) for s in args.scenarios.split(','))
    
    # Setup output directories
    base_dir = Path(__file__).parent.parent / "scenario_graphics"
    base_dir.mkdir(exist_ok=True)
    
    # Clear existing graphics in scenario folders
    scenario_dirs = {}
    for i in range(1, 18):
        scenario_dir = base_dir / f"scenario_{i}"
        
        # Remove existing PNG files in this scenario folder
        if scenario_dir.exists():
            for png_file in scenario_dir.glob("*.png"):
                png_file.unlink()
                
        scenario_dir.mkdir(exist_ok=True)
        scenario_dirs[i] = scenario_dir
    
    print(f"Cleared existing graphics from scenario folders")
    
    print(f"Generating graphics for {args.symbol} from {start_date} to {end_date}")
    if scenario_filter:
        print(f"Filtering to scenarios: {sorted(scenario_filter)}")
    
    # Run scenario analysis to get classifications
    config_path = Path(args.config) if args.config else None
    overnight_results, stats_by_scenario, dates_by_scenario = run_scenario_analysis(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        db_path_or_config=args.db,
        config_path=config_path,
    )
    
    # Create a lookup for overnight ranges by session_date
    overnight_by_date = {ov.session_date: ov for ov in overnight_results}
    
    # Get database engine for querying bars
    engine = get_engine(args.db, config_path)
    SessionLocal = sessionmaker(bind=engine)
    
    # Generate graphics for each day
    total_generated = 0
    
    for scenario, dates in dates_by_scenario.items():
        if scenario_filter and scenario not in scenario_filter:
            continue
        
        if not dates:
            continue
        
        print(f"\nScenario {scenario}: {len(dates)} days")
        
        for session_date in dates:
            overnight_range = overnight_by_date.get(session_date)
            if not overnight_range or overnight_range.high is None:
                continue
            
            # Get time windows
            start_06_et, end_09_et, _ = _day_session_windows(session_date)
            end_1130_et = datetime(session_date.year, session_date.month, session_date.day, 11, 30, 0, tzinfo=ET)
            
            start_06_utc = start_06_et.astimezone(UTC)
            end_1130_utc = end_1130_et.astimezone(UTC)
            
            # Query bars 06:00-11:30
            with SessionLocal() as session:
                bars_06_1130 = (
                    session.query(RawBar1Min)
                    .filter(
                        RawBar1Min.symbol == args.symbol,
                        RawBar1Min.timestamp >= start_06_utc,
                        RawBar1Min.timestamp < end_1130_utc,
                    )
                    .order_by(RawBar1Min.timestamp)
                    .all()
                )
            
            if not bars_06_1130:
                print(f"  Skipping {session_date}: no bars")
                continue
            
            # Generate graphic
            output_path = generate_day_graphic(
                session_date=session_date,
                scenario=scenario,
                overnight_range=overnight_range,
                bars_06_1130=bars_06_1130,
                symbol=args.symbol,
                output_dir=scenario_dirs[scenario],
            )
            
            total_generated += 1
            if total_generated % 10 == 0:
                print(f"  Generated {total_generated} graphics...")
    
    print(f"\nComplete! Generated {total_generated} graphics in {base_dir}")


if __name__ == "__main__":
    main()
