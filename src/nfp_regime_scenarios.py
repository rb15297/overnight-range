"""
NFP Regime Scenarios — standalone service.

Splits scenario stats by whether 09:00 ET close was above or below that month's NFP release price,
or runs in "today" mode: detect current regime and output stats for the matching regime over N years.
Does not modify overnight_range_scenarios.py.
"""

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from zoneinfo import ZoneInfo

from sqlalchemy.orm import sessionmaker

from src.database_models import RawBar1Min
from src.nfp_service import (
    classify_regime,
    get_nfp_date_for_month,
    get_nfp_price_for_session,
    get_nfp_release_price,
    get_second_friday,
)
from src.overnight_range_scenarios import (
    ScenarioStats,
    _classify_scenario,
    _day_session_windows,
)
from src.overnight_range_service import (
    CONFIG_PATH,
    ET,
    UTC,
    get_engine,
    get_overnight_ranges,
)

SCENARIO_SUMMARY_DIR = Path(__file__).resolve().parent.parent / "scenario_summary"
SCENARIOS = tuple(range(1, 18))
BULL_SCENARIOS = (1, 2, 3, 7, 8, 9, 10, 11)
BEAR_SCENARIOS = (4, 5, 6, 12, 13, 14, 15, 16)
INSIDE_SCENARIOS = (17,)


@dataclass
class RegimeSplitResult:
    """Result when running in split mode (range with above/below NFP)."""
    stats_above: Dict[int, ScenarioStats]
    stats_below: Dict[int, ScenarioStats]
    no_nfp_count: int


def _build_stats_from_counters(
    count_by_scenario: Dict[int, int],
    above_overnight_mid_by_scenario: Dict[int, int],
    above_0609_low_by_scenario: Dict[int, int],
    above_18_09_low_by_scenario: Dict[int, int],
    below_overnight_mid_by_scenario: Dict[int, int],
    below_0609_high_by_scenario: Dict[int, int],
    below_18_09_high_by_scenario: Dict[int, int],
    new_high_09_1130_by_scenario: Dict[int, int],
    new_low_09_1130_by_scenario: Dict[int, int],
) -> Dict[int, ScenarioStats]:
    """Build ScenarioStats dict from counter dicts (same logic as overnight_range_scenarios)."""
    total_scenario_days = sum(count_by_scenario[s] for s in SCENARIOS)
    stats_by_scenario = {}
    for s in SCENARIOS:
        n = count_by_scenario[s]
        pct_of_total = (100.0 * n / total_scenario_days) if total_scenario_days else 0.0
        m = above_overnight_mid_by_scenario.get(s, 0)
        a06 = above_0609_low_by_scenario.get(s, 0)
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
    return stats_by_scenario


def _empty_counters() -> Tuple[Dict[int, int], ...]:
    """Return a tuple of empty counter dicts for one regime."""
    count_by_scenario = {s: 0 for s in SCENARIOS}
    above_overnight_mid = {s: 0 for s in SCENARIOS}
    above_0609_low = {s: 0 for s in SCENARIOS}
    above_18_09_low = {s: 0 for s in SCENARIOS}
    below_overnight_mid = {s: 0 for s in SCENARIOS}
    below_0609_high = {s: 0 for s in SCENARIOS}
    below_18_09_high = {s: 0 for s in SCENARIOS}
    new_high_09_1130 = {s: 0 for s in SCENARIOS}
    new_low_09_1130 = {s: 0 for s in SCENARIOS}
    return (
        count_by_scenario,
        above_overnight_mid,
        above_0609_low,
        above_18_09_low,
        below_overnight_mid,
        below_0609_high,
        below_18_09_high,
        new_high_09_1130,
        new_low_09_1130,
    )


def _accumulate_session(
    scenario: int,
    ov_low: float,
    ov_mid: float,
    ov_high: float,
    min_low_06_09: float,
    max_high_06_09: float,
    min_low_09_16: Optional[float],
    max_high_09_16: Optional[float],
    max_high_09_1130: Optional[float],
    min_low_09_1130: Optional[float],
    count_by_scenario: Dict[int, int],
    above_overnight_mid: Dict[int, int],
    above_0609_low: Dict[int, int],
    above_18_09_low: Dict[int, int],
    below_overnight_mid: Dict[int, int],
    below_0609_high: Dict[int, int],
    below_18_09_high: Dict[int, int],
    new_high_09_1130: Dict[int, int],
    new_low_09_1130: Dict[int, int],
) -> None:
    """Accumulate one session into the given counter dicts (same logic as overnight_range_scenarios loop)."""
    count_by_scenario[scenario] += 1
    low_18_to_09 = min(ov_low, min_low_06_09)
    high_18_to_09 = max(ov_high, max_high_06_09)
    if scenario in BULL_SCENARIOS or scenario in INSIDE_SCENARIOS:
        if min_low_09_16 is not None:
            if min_low_09_16 >= ov_mid:
                above_overnight_mid[scenario] += 1
            if min_low_09_16 >= min_low_06_09:
                above_0609_low[scenario] += 1
            if min_low_09_16 >= low_18_to_09:
                above_18_09_low[scenario] += 1
    if scenario in BEAR_SCENARIOS or scenario in INSIDE_SCENARIOS:
        if max_high_09_16 is not None:
            if max_high_09_16 < ov_mid:
                below_overnight_mid[scenario] += 1
            if max_high_09_16 < max_high_06_09:
                below_0609_high[scenario] += 1
            if max_high_09_16 < high_18_to_09:
                below_18_09_high[scenario] += 1
    if scenario in BULL_SCENARIOS or scenario in INSIDE_SCENARIOS:
        if max_high_09_1130 is not None and max_high_09_1130 > high_18_to_09:
            new_high_09_1130[scenario] += 1
    if scenario in BEAR_SCENARIOS or scenario in INSIDE_SCENARIOS:
        if min_low_09_1130 is not None and min_low_09_1130 < low_18_to_09:
            new_low_09_1130[scenario] += 1


def run_nfp_regime_analysis(
    symbol: str,
    start_date: date,
    end_date: Optional[date] = None,
    db_path_or_config: Optional[str] = None,
    config_path: Optional[Path] = None,
    nfp_regime_filter: Optional[str] = None,
) -> Union[Tuple[RegimeSplitResult, None], Tuple[None, Tuple[Dict[int, ScenarioStats], Dict[int, List[date]]]]]:
    """
    Run scenario analysis with NFP regime split or filter.

    If nfp_regime_filter is None: split mode. Return (RegimeSplitResult(stats_above, stats_below, no_nfp_count), None).
    If nfp_regime_filter is "above" or "below": single-regime mode. Return (None, (stats_by_scenario, dates_by_scenario)).
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

    if nfp_regime_filter is None:
        (
            count_above, ao_above, a06_above, a18_above, bo_above, b06_above, b18_above, nh_above, nl_above,
        ) = _empty_counters()
        (
            count_below, ao_below, a06_below, a18_below, bo_below, b06_below, b18_below, nh_below, nl_below,
        ) = _empty_counters()
    else:
        (
            count_one, ao_one, a06_one, a18_one, bo_one, b06_one, b18_one, nh_one, nl_one,
        ) = _empty_counters()
        dates_by_scenario = {s: [] for s in SCENARIOS}
    no_nfp_count = 0

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

        _, nfp_price = get_nfp_price_for_session(symbol, session_date, engine)
        regime = classify_regime(close_09, nfp_price)
        if regime is None:
            no_nfp_count += 1
            continue

        if nfp_regime_filter is None:
            if regime == "above":
                _accumulate_session(
                    scenario, ov.low, ov.middle, ov.high,
                    min_low_06_09, max_high_06_09, min_low_09_16, max_high_09_16,
                    max_high_09_1130, min_low_09_1130,
                    count_above, ao_above, a06_above, a18_above, bo_above, b06_above, b18_above, nh_above, nl_above,
                )
            else:
                _accumulate_session(
                    scenario, ov.low, ov.middle, ov.high,
                    min_low_06_09, max_high_06_09, min_low_09_16, max_high_09_16,
                    max_high_09_1130, min_low_09_1130,
                    count_below, ao_below, a06_below, a18_below, bo_below, b06_below, b18_below, nh_below, nl_below,
                )
        else:
            if regime != nfp_regime_filter:
                continue
            dates_by_scenario[scenario].append(session_date)
            _accumulate_session(
                scenario, ov.low, ov.middle, ov.high,
                min_low_06_09, max_high_06_09, min_low_09_16, max_high_09_16,
                max_high_09_1130, min_low_09_1130,
                count_one, ao_one, a06_one, a18_one, bo_one, b06_one, b18_one, nh_one, nl_one,
            )

    if nfp_regime_filter is None:
        stats_above = _build_stats_from_counters(
            count_above, ao_above, a06_above, a18_above, bo_above, b06_above, b18_above, nh_above, nl_above,
        )
        stats_below = _build_stats_from_counters(
            count_below, ao_below, a06_below, a18_below, bo_below, b06_below, b18_below, nh_below, nl_below,
        )
        return (RegimeSplitResult(stats_above, stats_below, no_nfp_count), None)
    else:
        stats_one = _build_stats_from_counters(
            count_one, ao_one, a06_one, a18_one, bo_one, b06_one, b18_one, nh_one, nl_one,
        )
        return (None, (stats_one, dates_by_scenario))


def _get_reference_date_and_09_close(
    symbol: str,
    engine,
) -> Tuple[date, Optional[float]]:
    """Return (most recent session_date with 09:00 bar data, close_09). close_09 = last bar of 06:00-09:00 ET."""
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        last_bar = (
            session.query(RawBar1Min)
            .filter(RawBar1Min.symbol == symbol)
            .order_by(RawBar1Min.timestamp.desc())
            .first()
        )
    if last_bar is None:
        return (date.today(), None)
    bar_ts = last_bar.timestamp
    if bar_ts.tzinfo is None:
        bar_ts = bar_ts.replace(tzinfo=UTC)
    ref_date = bar_ts.astimezone(ET).date()
    start_06_et = datetime(ref_date.year, ref_date.month, ref_date.day, 6, 0, 0, tzinfo=ET)
    end_09_et = datetime(ref_date.year, ref_date.month, ref_date.day, 9, 0, 0, tzinfo=ET)
    start_06_utc = start_06_et.astimezone(UTC)
    end_09_utc = end_09_et.astimezone(UTC)
    with SessionLocal() as session:
        bars_06_09 = (
            session.query(RawBar1Min)
            .filter(
                RawBar1Min.symbol == symbol,
                RawBar1Min.timestamp >= start_06_utc,
                RawBar1Min.timestamp < end_09_utc,
            )
            .order_by(RawBar1Min.timestamp)
            .all()
        )
    if not bars_06_09:
        return (ref_date, None)
    close_09 = bars_06_09[-1].close
    return (ref_date, close_09)


def _get_today_regime(
    symbol: str,
    engine,
) -> Tuple[date, Optional[float], Optional[float], Optional[str]]:
    """Return (reference_date, close_09, nfp_price, regime). Regime is 'above' or 'below' or None."""
    ref_date, close_09 = _get_reference_date_and_09_close(symbol, engine)
    if close_09 is None:
        return (ref_date, None, None, None)
    year, month = ref_date.year, ref_date.month
    nfp_date_this = get_nfp_date_for_month(year, month)
    nfp_price_this = get_nfp_release_price(symbol, nfp_date_this, engine)
    if nfp_price_this is None:
        second_fri = get_second_friday(year, month)
        nfp_price_this = get_nfp_release_price(symbol, second_fri, engine)
    if ref_date >= nfp_date_this and nfp_price_this is not None:
        regime = classify_regime(close_09, nfp_price_this)
        return (ref_date, close_09, nfp_price_this, regime)
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    _, nfp_price_prev = get_nfp_price_for_session(symbol, date(prev_year, prev_month, 15), engine)
    regime = classify_regime(close_09, nfp_price_prev)
    return (ref_date, close_09, nfp_price_prev, regime)


LABELS = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7 (A)", 8: "8 (B)", 9: "9 (C)", 10: "10 (D)", 11: "11 (E)",
    12: "12 (F)", 13: "13 (G)", 14: "14 (H)", 15: "15 (I)", 16: "16 (J)", 17: "17 (K)",
}

FIELDNAMES = [
    "scenario", "label", "total_days", "pct_of_total",
    "days_above_overnight_mid", "pct_above_overnight_mid",
    "days_above_0609_low", "pct_above_0609_low",
    "days_above_18_09_low", "pct_above_18_09_low",
    "days_below_overnight_mid", "pct_below_overnight_mid",
    "days_below_0609_high", "pct_below_0609_high",
    "days_below_18_09_high", "pct_below_18_09_high",
    "days_new_high_09_1130", "pct_new_high_09_1130",
    "days_new_low_09_1130", "pct_new_low_09_1130",
]


def _write_csv(stats_by_scenario: Dict[int, ScenarioStats], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for s in SCENARIOS:
            st = stats_by_scenario[s]
            writer.writerow({
                "scenario": st.scenario,
                "label": LABELS.get(s, str(s)),
                "total_days": st.total_days,
                "pct_of_total": f"{st.pct_of_total:.4f}",
                "days_above_overnight_mid": st.days_above_overnight_mid,
                "pct_above_overnight_mid": f"{st.pct_above_overnight_mid:.4f}",
                "days_above_0609_low": st.days_above_0609_low,
                "pct_above_0609_low": f"{st.pct_above_0609_low:.4f}",
                "days_above_18_09_low": st.days_above_18_09_low,
                "pct_above_18_09_low": f"{st.pct_above_18_09_low:.4f}",
                "days_below_overnight_mid": st.days_below_overnight_mid,
                "pct_below_overnight_mid": f"{st.pct_below_overnight_mid:.4f}",
                "days_below_0609_high": st.days_below_0609_high,
                "pct_below_0609_high": f"{st.pct_below_0609_high:.4f}",
                "days_below_18_09_high": st.days_below_18_09_high,
                "pct_below_18_09_high": f"{st.pct_below_18_09_high:.4f}",
                "days_new_high_09_1130": st.days_new_high_09_1130,
                "pct_new_high_09_1130": f"{st.pct_new_high_09_1130:.4f}",
                "days_new_low_09_1130": st.days_new_low_09_1130,
                "pct_new_low_09_1130": f"{st.pct_new_low_09_1130:.4f}",
            })


def _print_stats(stats_by_scenario: Dict[int, ScenarioStats], title: str) -> None:
    total_days = sum(stats_by_scenario[s].total_days for s in SCENARIOS)
    print(f"\n{title}")
    print(f"Total days: {total_days}\n")
    for s in SCENARIOS:
        st = stats_by_scenario[s]
        if s in BULL_SCENARIOS:
            print(
                f"  Scenario {s}:  n={st.total_days} ({st.pct_of_total:.1f}%)  "
                f"above_mid={st.days_above_overnight_mid} ({st.pct_above_overnight_mid:.1f}%)  "
                f"above_0609_low={st.days_above_0609_low} ({st.pct_above_0609_low:.1f}%)  "
                f"above_18_09_low={st.days_above_18_09_low} ({st.pct_above_18_09_low:.1f}%)  "
                f"new_high_09_1130={st.days_new_high_09_1130} ({st.pct_new_high_09_1130:.1f}%)"
            )
        elif s in BEAR_SCENARIOS:
            print(
                f"  Scenario {s}:  n={st.total_days} ({st.pct_of_total:.1f}%)  "
                f"below_mid={st.days_below_overnight_mid} ({st.pct_below_overnight_mid:.1f}%)  "
                f"below_0609_high={st.days_below_0609_high} ({st.pct_below_0609_high:.1f}%)  "
                f"below_18_09_high={st.days_below_18_09_high} ({st.pct_below_18_09_high:.1f}%)  "
                f"new_low_09_1130={st.days_new_low_09_1130} ({st.pct_new_low_09_1130:.1f}%)"
            )
        else:
            print(
                f"  Scenario {s}:  n={st.total_days} ({st.pct_of_total:.1f}%)  "
                f"above_mid={st.days_above_overnight_mid} ({st.pct_above_overnight_mid:.1f}%)  "
                f"below_mid={st.days_below_overnight_mid} ({st.pct_below_overnight_mid:.1f}%)  "
                f"new_high_09_1130={st.days_new_high_09_1130}  new_low_09_1130={st.days_new_low_09_1130}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NFP regime scenarios: split stats by 09:00 close above/below NFP release price, or today + matching regime over N years.",
    )
    parser.add_argument("--symbol", required=True, help="Symbol e.g. NQ, ES")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", help="Range start (YYYY-MM-DD)")
    group.add_argument("--today", action="store_true", help="Today mode: detect regime, stats for matching regime over --years")
    parser.add_argument("--end", help="Range end (YYYY-MM-DD), use with --start")
    parser.add_argument("--years", type=float, help="Lookback in years (required with --today)")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Path to config.json")
    parser.add_argument("--db", help="Override database path")
    parser.add_argument("--out", type=Path, help="Override path for scenario summary CSV(s)")
    args = parser.parse_args()

    def parse_date(s: str) -> date:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()

    config_path = args.config if args.config.exists() else None
    db_path = args.db

    if args.today:
        if args.years is None:
            parser.error("--years is required with --today")
        engine = get_engine(db_path, config_path)
        ref_date, close_09, nfp_price, regime = _get_today_regime(args.symbol, engine)
        if close_09 is None or nfp_price is None or regime is None:
            print(f"Could not determine regime: ref_date={ref_date}, close_09={close_09}, nfp_price={nfp_price}")
            return
        print(f"Today ({ref_date}): 09:00 close = {close_09}, NFP price = {nfp_price} -> {regime.capitalize()} NFP")
        start_date = ref_date - timedelta(days=int(args.years * 365.25))
        split_result, single_result = run_nfp_regime_analysis(
            symbol=args.symbol,
            start_date=start_date,
            end_date=ref_date,
            db_path_or_config=db_path,
            config_path=config_path,
            nfp_regime_filter=regime,
        )
        assert single_result is not None
        stats_one, _ = single_result
        _print_stats(stats_one, f"Stats for {regime} NFP regime (last {args.years} years)")
        out_path = args.out
        if out_path is None:
            SCENARIO_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
            out_path = SCENARIO_SUMMARY_DIR / f"{args.symbol}_nfp_today_{regime}_{int(args.years)}y.csv"
        _write_csv(stats_one, out_path)
        print(f"Wrote {out_path}")
        return

    start_date = parse_date(args.start)
    end_date = parse_date(args.end) if args.end else None
    if end_date is None or end_date < start_date:
        parser.error("--end is required with --start and must be >= --start")

    split_result, _ = run_nfp_regime_analysis(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        db_path_or_config=db_path,
        config_path=config_path,
        nfp_regime_filter=None,
    )
    assert split_result is not None
    end_str = end_date.isoformat()
    if split_result.no_nfp_count:
        print(f"Sessions with no NFP data: {split_result.no_nfp_count}")
    _print_stats(split_result.stats_above, "Above NFP (09:00 close > NFP release price)")
    _print_stats(split_result.stats_below, "Below NFP (09:00 close < NFP release price)")

    if args.out is not None:
        base = args.out
        if base.suffix.lower() == ".csv":
            base = base.with_suffix("")
        above_path = Path(str(base) + "_nfp_above.csv")
        below_path = Path(str(base) + "_nfp_below.csv")
        _write_csv(split_result.stats_above, above_path)
        _write_csv(split_result.stats_below, below_path)
        print(f"Wrote {above_path} and {below_path}")
    else:
        SCENARIO_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        above_path = SCENARIO_SUMMARY_DIR / f"{args.symbol}_{start_date}_{end_str}_nfp_above.csv"
        below_path = SCENARIO_SUMMARY_DIR / f"{args.symbol}_{start_date}_{end_str}_nfp_below.csv"
        _write_csv(split_result.stats_above, above_path)
        _write_csv(split_result.stats_below, below_path)
        print(f"Wrote {above_path} and {below_path}")


if __name__ == "__main__":
    main()