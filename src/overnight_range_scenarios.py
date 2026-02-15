"""
Overnight Range Scenarios (06:00–09:00 ET)

Classifies each day into one of 17 scenarios (1–6 original, 7–17 gap scenarios A–K) based on price action
between 06:00 ET and 09:00 ET relative to the overnight range (18:00 prev day – 06:00 ET). Then computes, per scenario,
outcome metrics for 09:00–16:00 ET (above/below mid, 06–09 low/high, 18:00–09:00 low/high). Day = overnight range through 16:00 ET.
"""

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from sqlalchemy.orm import sessionmaker

from src.database_models import RawBar1Min
from src.overnight_range_service import (
    get_overnight_ranges,
    get_engine,
    OvernightRangeResult,
    ET,
    UTC,
    CONFIG_PATH,
)

# 06:00–09:00 ET and 09:00–16:00 ET on session_date
def _day_session_windows(session_date: date):
    start_06_et = datetime(session_date.year, session_date.month, session_date.day, 6, 0, 0, tzinfo=ET)
    end_09_et = datetime(session_date.year, session_date.month, session_date.day, 9, 0, 0, tzinfo=ET)
    end_16_et = datetime(session_date.year, session_date.month, session_date.day, 16, 0, 0, tzinfo=ET)
    return start_06_et, end_09_et, end_16_et


def _classify_scenario(
    bars_06_09: List,
    close_09: float,
    overnight_low: float,
    overnight_mid: float,
    overnight_high: float,
) -> Optional[int]:
    """
    Classify 06:00–09:00 into scenario 1–17. Returns 1–17 or None only when bars_06_09 is empty.
    Mutually exclusive: 1,3,2,4,6,5 then gap 7–11 (A–E), 12–14 (F–H), 17 (K), 15–16 (I–J).
    """
    if not bars_06_09:
        return None
    L = overnight_low
    M = overnight_mid
    H = overnight_high
    min_low_06_09 = min(b.low for b in bars_06_09)
    max_high_06_09 = max(b.high for b in bars_06_09)

    # Original bull: 1, 3, 2
    if min_low_06_09 < L and close_09 > M:
        return 1
    if min_low_06_09 >= M and close_09 > H:
        return 3
    if min_low_06_09 >= L and close_09 > H:
        return 2

    # Original bear: 4, 6, 5
    if max_high_06_09 > H and close_09 < M:
        return 4
    if max_high_06_09 <= M and close_09 < L:
        return 6
    if max_high_06_09 <= H and close_09 < L:
        return 5

    # Gap bull-side: 7=A, 8=B, 9=C, 10=D, 11=E
    if min_low_06_09 < L and close_09 <= M:
        return 7
    if min_low_06_09 >= L and min_low_06_09 < M and close_09 > M and close_09 <= H:
        return 8
    if min_low_06_09 >= L and min_low_06_09 < M and close_09 <= M:
        return 9
    if min_low_06_09 >= M and close_09 < M:
        return 10
    if min_low_06_09 >= M and close_09 >= M and close_09 < H:
        return 11

    # Gap bear-side (spike above H): 12=F, 13=G, 14=H
    if max_high_06_09 > H and close_09 >= M:
        return 12
    if max_high_06_09 > H and close_09 >= L and close_09 < M:
        return 13
    if max_high_06_09 > H and close_09 < L:
        return 14

    # Inside range: 17=K (before I, J so "never left range" gets K)
    if min_low_06_09 >= L and max_high_06_09 <= H and close_09 >= L and close_09 <= H:
        return 17

    # Remainder: 15=I, 16=J
    if max_high_06_09 > M and max_high_06_09 <= H and close_09 >= L:
        return 15
    if max_high_06_09 <= M and close_09 >= L:
        return 16

    return None


@dataclass
class ScenarioStats:
    scenario: int
    total_days: int
    pct_of_total: float  # this scenario's share of all scenario days (sum to 100%)
    # Bull (1–3): above mid, above 06–09 low, above 18:00–09:00 low
    days_above_overnight_mid: int = 0
    pct_above_overnight_mid: float = 0.0
    days_above_0609_low: int = 0
    pct_above_0609_low: float = 0.0
    days_above_18_09_low: int = 0
    pct_above_18_09_low: float = 0.0
    # Bear (4–6): below mid, below 06–09 high, below 18:00–09:00 high
    days_below_overnight_mid: int = 0
    pct_below_overnight_mid: float = 0.0
    days_below_0609_high: int = 0
    pct_below_0609_high: float = 0.0
    days_below_18_09_high: int = 0
    pct_below_18_09_high: float = 0.0
    # Bull: pct of days a new high was put in 09:00–11:30 (high_09_1130 > high_18_to_09)
    days_new_high_09_1130: int = 0
    pct_new_high_09_1130: float = 0.0
    # Bear: pct of days a new low was put in 09:00–11:30 (low_09_1130 < low_18_to_09)
    days_new_low_09_1130: int = 0
    pct_new_low_09_1130: float = 0.0


def run_scenario_analysis(
    symbol: str,
    start_date: date,
    end_date: Optional[date] = None,
    db_path_or_config: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> Tuple[List[OvernightRangeResult], Dict[int, ScenarioStats], Dict[int, List[date]]]:
    """
    Run scenario analysis for the given symbol and date range.

    Returns:
        overnight_results: list of overnight range results in range
        stats_by_scenario: scenario number -> ScenarioStats (total_days, days_low_held, pct)
        dates_by_scenario: scenario number -> list of session_date that matched
    """
    overnight_results = get_overnight_ranges(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        db_path_or_config=db_path_or_config,
        config_path=config_path,
    )
    engine = get_engine(db_path_or_config, config_path)
    SessionLocal = sessionmaker(bind=engine)

    SCENARIOS = tuple(range(1, 18))
    BULL_SCENARIOS = (1, 2, 3, 7, 8, 9, 10, 11)
    BEAR_SCENARIOS = (4, 5, 6, 12, 13, 14, 15, 16)
    INSIDE_SCENARIOS = (17,)
    dates_by_scenario = {s: [] for s in SCENARIOS}
    above_overnight_mid_by_scenario = {s: 0 for s in SCENARIOS}
    above_0609_low_by_scenario = {s: 0 for s in SCENARIOS}
    above_18_09_low_by_scenario = {s: 0 for s in SCENARIOS}
    below_overnight_mid_by_scenario = {s: 0 for s in SCENARIOS}
    below_0609_high_by_scenario = {s: 0 for s in SCENARIOS}
    below_18_09_high_by_scenario = {s: 0 for s in SCENARIOS}
    new_high_09_1130_by_scenario = {s: 0 for s in SCENARIOS}
    new_low_09_1130_by_scenario = {s: 0 for s in SCENARIOS}
    count_by_scenario = {s: 0 for s in SCENARIOS}

    for ov in overnight_results:
        if ov.high is None or ov.low is None or ov.middle is None:
            continue
        session_date = ov.session_date
        start_06_et, end_09_et, end_16_et = _day_session_windows(session_date)
        start_06_utc = start_06_et.astimezone(UTC)
        end_09_utc = end_09_et.astimezone(UTC)
        end_1130_et = datetime(session_date.year, session_date.month, session_date.day, 11, 30, 0, tzinfo=ET)
        end_1130_utc = end_1130_et.astimezone(UTC)
        end_16_utc = end_16_et.astimezone(UTC)

        with SessionLocal() as session:
            bars = (
                session.query(RawBar1Min)
                .filter(
                    RawBar1Min.symbol == symbol,
                    RawBar1Min.timestamp >= start_06_utc,
                    RawBar1Min.timestamp < end_16_utc,
                )
                .order_by(RawBar1Min.timestamp)
                .all()
            )

        bars_06_09 = [b for b in bars if start_06_utc <= b.timestamp < end_09_utc]
        bars_09_1130 = [b for b in bars if end_09_utc <= b.timestamp < end_1130_utc]
        bars_09_16 = [b for b in bars if end_09_utc <= b.timestamp < end_16_utc]

        if not bars_06_09:
            continue
        close_09 = bars_06_09[-1].close
        min_low_06_09 = min(b.low for b in bars_06_09)
        max_high_06_09 = max(b.high for b in bars_06_09)
        min_low_09_16 = min(b.low for b in bars_09_16) if bars_09_16 else None
        max_high_09_16 = max(b.high for b in bars_09_16) if bars_09_16 else None
        max_high_09_1130 = max(b.high for b in bars_09_1130) if bars_09_1130 else None
        min_low_09_1130 = min(b.low for b in bars_09_1130) if bars_09_1130 else None

        scenario = _classify_scenario(
            bars_06_09,
            close_09,
            ov.low,
            ov.middle,
            ov.high,
        )
        if scenario is None:
            continue

        dates_by_scenario[scenario].append(session_date)
        count_by_scenario[scenario] += 1
        low_18_to_09 = min(ov.low, min_low_06_09)
        high_18_to_09 = max(ov.high, max_high_06_09)
        # Bull-type (1–3, 7–11) and inside (17): above mid, above 06–09 low, above 18:00–09:00 low
        if scenario in BULL_SCENARIOS or scenario in INSIDE_SCENARIOS:
            if min_low_09_16 is not None:
                if min_low_09_16 >= ov.middle:
                    above_overnight_mid_by_scenario[scenario] += 1
                if min_low_09_16 >= min_low_06_09:
                    above_0609_low_by_scenario[scenario] += 1
                if min_low_09_16 >= low_18_to_09:
                    above_18_09_low_by_scenario[scenario] += 1
        # Bear-type (4–6, 12–16) and inside (17): below mid, below 06–09 high, below 18:00–09:00 high
        if scenario in BEAR_SCENARIOS or scenario in INSIDE_SCENARIOS:
            if max_high_09_16 is not None:
                if max_high_09_16 < ov.middle:
                    below_overnight_mid_by_scenario[scenario] += 1
                if max_high_09_16 < max_high_06_09:
                    below_0609_high_by_scenario[scenario] += 1
                if max_high_09_16 < high_18_to_09:
                    below_18_09_high_by_scenario[scenario] += 1
        # Bull: new high in 09:00–11:30 (high_09_1130 > high_18_to_09)
        if scenario in BULL_SCENARIOS or scenario in INSIDE_SCENARIOS:
            if max_high_09_1130 is not None and max_high_09_1130 > high_18_to_09:
                new_high_09_1130_by_scenario[scenario] += 1
        # Bear: new low in 09:00–11:30 (low_09_1130 < low_18_to_09)
        if scenario in BEAR_SCENARIOS or scenario in INSIDE_SCENARIOS:
            if min_low_09_1130 is not None and min_low_09_1130 < low_18_to_09:
                new_low_09_1130_by_scenario[scenario] += 1

    total_scenario_days = sum(count_by_scenario[s] for s in SCENARIOS)
    stats_by_scenario = {}
    for s in SCENARIOS:
        n = count_by_scenario[s]
        pct_of_total = (100.0 * n / total_scenario_days) if total_scenario_days else 0.0
        m = above_overnight_mid_by_scenario[s]
        a06 = above_0609_low_by_scenario[s]
        a18 = above_18_09_low_by_scenario.get(s, 0)
        b_mid = below_overnight_mid_by_scenario.get(s, 0)
        b06 = below_0609_high_by_scenario.get(s, 0)
        b18 = below_18_09_high_by_scenario.get(s, 0)
        nh = new_high_09_1130_by_scenario.get(s, 0)
        nl = new_low_09_1130_by_scenario.get(s, 0)
        is_bull_type = s in BULL_SCENARIOS or s in INSIDE_SCENARIOS
        is_bear_type = s in BEAR_SCENARIOS or s in INSIDE_SCENARIOS
        stats_by_scenario[s] = ScenarioStats(
            scenario=s,
            total_days=n,
            pct_of_total=pct_of_total,
            days_above_overnight_mid=m,
            pct_above_overnight_mid=(100.0 * m / n) if n and is_bull_type else 0.0,
            days_above_0609_low=a06,
            pct_above_0609_low=(100.0 * a06 / n) if n and is_bull_type else 0.0,
            days_above_18_09_low=a18,
            pct_above_18_09_low=(100.0 * a18 / n) if n and is_bull_type else 0.0,
            days_below_overnight_mid=b_mid,
            pct_below_overnight_mid=(100.0 * b_mid / n) if n and is_bear_type else 0.0,
            days_below_0609_high=b06,
            pct_below_0609_high=(100.0 * b06 / n) if n and is_bear_type else 0.0,
            days_below_18_09_high=b18,
            pct_below_18_09_high=(100.0 * b18 / n) if n and is_bear_type else 0.0,
            days_new_high_09_1130=nh,
            pct_new_high_09_1130=(100.0 * nh / n) if n and is_bull_type else 0.0,
            days_new_low_09_1130=nl,
            pct_new_low_09_1130=(100.0 * nl / n) if n and is_bear_type else 0.0,
        )

    return overnight_results, stats_by_scenario, dates_by_scenario


def main():
    parser = argparse.ArgumentParser(
        description="Overnight range scenarios 06:00–09:00 ET and %% of time 06–09 low stays above 09–16 low."
    )
    parser.add_argument("--symbol", required=True, help="Symbol e.g. NQ, ES")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="Single session date (YYYY-MM-DD)")
    group.add_argument("--start", help="Range start (YYYY-MM-DD)")
    parser.add_argument("--end", help="Range end (YYYY-MM-DD), use with --start")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Path to config.json")
    parser.add_argument("--db", help="Override database path")
    args = parser.parse_args()

    def parse_date(s: str) -> date:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()

    if args.date:
        start_date = parse_date(args.date)
        end_date = None
    else:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end) if args.end else None
        if end_date and end_date < start_date:
            parser.error("--end must be >= --start")

    config_path = args.config if args.config.exists() else None
    _, stats_by_scenario, dates_by_scenario = run_scenario_analysis(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        db_path_or_config=args.db,
        config_path=config_path,
    )

    SCENARIOS = tuple(range(1, 18))
    BULL_SCENARIOS = (1, 2, 3, 7, 8, 9, 10, 11)
    BEAR_SCENARIOS = (4, 5, 6, 12, 13, 14, 15, 16)
    total_days = sum(stats_by_scenario[s].total_days for s in SCENARIOS)
    print("\nScenarios (06:00–09:00 ET):")
    print("  1–3 = bull; 4–6 = bear; 7=A, 8=B, 9=C, 10=D, 11=E; 12=F, 13=G, 14=H; 15=I, 16=J; 17=K inside")
    print("  7=A: below low close<=mid  8=B: above low close in (M,H]  9=C: above low close<=mid")
    print("  10=D: above mid close<mid  11=E: above mid close in [M,H)  12=F: above high close>=mid")
    print("  13=G: above high close in [L,M)  14=H: above high close<L  15=I: below high close>=L  16=J: below mid close>=L  17=K: inside range")
    print(f"\nTotal days with a scenario: {total_days}")
    print("Bull: above_mid, above_0609_low, above_18_09_low, new_high_09_1130. Bear: below_mid, below_0609_high, below_18_09_high, new_low_09_1130. 17=both (09:00–16:00 ET)\n")

    for s in SCENARIOS:
        st = stats_by_scenario[s]
        if s in BULL_SCENARIOS:
            print(
                f"  Scenario {s}:  n={st.total_days} ({st.pct_of_total:.1f}% of total)  "
                f"above_mid={st.days_above_overnight_mid} ({st.pct_above_overnight_mid:.1f}%)  "
                f"above_0609_low={st.days_above_0609_low} ({st.pct_above_0609_low:.1f}%)  "
                f"above_18_09_low={st.days_above_18_09_low} ({st.pct_above_18_09_low:.1f}%)  "
                f"new_high_09_1130={st.days_new_high_09_1130} ({st.pct_new_high_09_1130:.1f}%)"
            )
        elif s in BEAR_SCENARIOS:
            print(
                f"  Scenario {s}:  n={st.total_days} ({st.pct_of_total:.1f}% of total)  "
                f"below_mid={st.days_below_overnight_mid} ({st.pct_below_overnight_mid:.1f}%)  "
                f"below_0609_high={st.days_below_0609_high} ({st.pct_below_0609_high:.1f}%)  "
                f"below_18_09_high={st.days_below_18_09_high} ({st.pct_below_18_09_high:.1f}%)  "
                f"new_low_09_1130={st.days_new_low_09_1130} ({st.pct_new_low_09_1130:.1f}%)"
            )
        else:
            # 17 = K: both metric sets
            print(
                f"  Scenario {s}:  n={st.total_days} ({st.pct_of_total:.1f}% of total)  "
                f"above_mid={st.days_above_overnight_mid} ({st.pct_above_overnight_mid:.1f}%)  "
                f"above_0609_low={st.days_above_0609_low} ({st.pct_above_0609_low:.1f}%)  "
                f"above_18_09_low={st.days_above_18_09_low} ({st.pct_above_18_09_low:.1f}%)  "
                f"new_high_09_1130={st.days_new_high_09_1130} ({st.pct_new_high_09_1130:.1f}%)  |  "
                f"below_mid={st.days_below_overnight_mid} ({st.pct_below_overnight_mid:.1f}%)  "
                f"below_0609_high={st.days_below_0609_high} ({st.pct_below_0609_high:.1f}%)  "
                f"below_18_09_high={st.days_below_18_09_high} ({st.pct_below_18_09_high:.1f}%)  "
                f"new_low_09_1130={st.days_new_low_09_1130} ({st.pct_new_low_09_1130:.1f}%)"
            )
    print()


if __name__ == "__main__":
    main()
