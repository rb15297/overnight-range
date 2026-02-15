"""
Overnight Range Service

Reads historical 1-minute bars from Trading.db (raw_bars_1min), lets you select a symbol
and single day or date range, and computes the overnight range (18:00 ET to 06:00 ET)
high, low, and middle for each session. Uses America/New_York for correct EDT/EST handling.
"""

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database_models import RawBar1Min

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


@dataclass
class OvernightRangeResult:
    """Result for one overnight session (18:00 ET previous day -> 06:00 ET session_date)."""
    session_date: date  # Date D: session ends at 06:00 ET on this day
    start_et: datetime
    end_et: datetime
    high: Optional[float] = None
    low: Optional[float] = None
    middle: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None
    bar_count: int = 0
    tz_abbrev: str = ""

    def __post_init__(self):
        if self.high is not None and self.low is not None and self.middle is None:
            self.middle = (self.high + self.low) / 2
        if self.start_et.tzinfo and not self.tz_abbrev:
            self.tz_abbrev = self.start_et.strftime("%Z") or "ET"


def _load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from JSON file."""
    path = config_path or CONFIG_PATH
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def get_engine(db_path_or_config: Optional[str] = None, config_path: Optional[Path] = None):
    """Create SQLAlchemy engine from config or explicit path. Public for use by scenario analysis."""
    return _get_engine(db_path_or_config, config_path)


def _get_engine(db_path_or_config: Optional[str] = None, config_path: Optional[Path] = None):
    """Create SQLAlchemy engine from config or explicit path."""
    if db_path_or_config:
        s = db_path_or_config.strip()
        if s.startswith("sqlite:///"):
            return create_engine(s, echo=False)
        return create_engine(f"sqlite:///{s}", echo=False)
    
    config = _load_config(config_path)
    db_config = config.get("database", {})
    db_path = db_config.get("path")
    
    if not db_path:
        raise ValueError(
            "Database path not configured. Please set 'database.path' in config.json "
            "or use --db argument to specify database path."
        )
    
    if db_path.startswith("sqlite:///"):
        return create_engine(db_path, echo=False)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def _overnight_window_et(session_date: date) -> Tuple[datetime, datetime]:
    """
    Return (start_et, end_et) for the overnight session that ends at 06:00 ET on session_date.
    Session: previous day 18:00 ET -> session_date 06:00 ET.
    """
    prev = session_date - timedelta(days=1)
    start_et = datetime(prev.year, prev.month, prev.day, 18, 0, 0, tzinfo=ET)
    end_et = datetime(session_date.year, session_date.month, session_date.day, 6, 0, 0, tzinfo=ET)
    return start_et, end_et


def _session_dates(start_date: date, end_date: Optional[date]) -> List[date]:
    """Return list of session dates (inclusive). Single day if end_date is None."""
    if end_date is None:
        return [start_date]
    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += timedelta(days=1)
    return dates


def _tz_abbrev(dt: datetime) -> str:
    """Return EDT or EST for display."""
    return dt.strftime("%Z") if dt.tzinfo else "ET"


def get_overnight_ranges(
    symbol: str,
    start_date: date,
    end_date: Optional[date] = None,
    db_path_or_config: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> List[OvernightRangeResult]:
    """
    Compute overnight range (high, low, middle) for each session in the date range.

    Convention: "date D" = overnight session that ends at 06:00 ET on D
    (i.e. 18:00 ET on D-1 -> 06:00 ET on D).

    Args:
        symbol: Symbol e.g. "NQ", "ES".
        start_date: First session date (session ending 06:00 ET on this day).
        end_date: Last session date (inclusive). If None, single day (start_date only).
        db_path_or_config: Optional DB path or sqlite URL. If None, use config.json.
        config_path: Optional path to config.json.

    Returns:
        List of OvernightRangeResult, one per session. Missing data yields high/low/middle None, bar_count=0.
    """
    engine = _get_engine(db_path_or_config, config_path)
    SessionLocal = sessionmaker(bind=engine)
    results = []

    for session_date in _session_dates(start_date, end_date):
        start_et, end_et = _overnight_window_et(session_date)
        start_utc = start_et.astimezone(UTC)
        end_utc = end_et.astimezone(UTC)
        tz_abbrev = _tz_abbrev(start_et)

        with SessionLocal() as session:
            bars = (
                session.query(RawBar1Min)
                .filter(
                    RawBar1Min.symbol == symbol,
                    RawBar1Min.timestamp >= start_utc,
                    RawBar1Min.timestamp < end_utc,
                )
                .order_by(RawBar1Min.timestamp)
                .all()
            )

        if not bars:
            results.append(
                OvernightRangeResult(
                    session_date=session_date,
                    start_et=start_et,
                    end_et=end_et,
                    high=None,
                    low=None,
                    middle=None,
                    open=None,
                    close=None,
                    bar_count=0,
                    tz_abbrev=tz_abbrev,
                )
            )
            continue

        high = max(b.high for b in bars)
        low = min(b.low for b in bars)
        middle = (high + low) / 2
        open_price = bars[0].open
        close_price = bars[-1].close

        results.append(
            OvernightRangeResult(
                session_date=session_date,
                start_et=start_et,
                end_et=end_et,
                high=high,
                low=low,
                middle=middle,
                open=open_price,
                close=close_price,
                bar_count=len(bars),
                tz_abbrev=tz_abbrev,
            )
        )
    return results


def list_symbols(
    db_path_or_config: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> List[str]:
    """Return distinct symbols present in raw_bars_1min."""
    engine = _get_engine(db_path_or_config, config_path)
    with engine.connect() as conn:
        from sqlalchemy import text
        r = conn.execute(text("SELECT DISTINCT symbol FROM raw_bars_1min ORDER BY symbol"))
        return [row[0] for row in r]


def main():
    parser = argparse.ArgumentParser(
        description="Compute overnight range (18:00 ET - 06:00 ET) high, low, middle from raw_bars_1min."
    )
    parser.add_argument("--symbol", required=True, help="Symbol e.g. NQ, ES")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="Single session date (YYYY-MM-DD), session ends 06:00 ET this day")
    group.add_argument("--start", help="Range start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Range end date (YYYY-MM-DD), use with --start")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Path to config.json")
    parser.add_argument("--db", help="Override database path or sqlite:/// URL")
    parser.add_argument("--json", action="store_true", help="Output JSON")
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

    db_path = args.db
    config_path = args.config if args.config.exists() else None

    results = get_overnight_ranges(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        db_path_or_config=db_path,
        config_path=config_path,
    )

    if args.json:
        import json as json_mod
        out = []
        for r in results:
            out.append({
                "session_date": r.session_date.isoformat(),
                "start_et": r.start_et.isoformat(),
                "end_et": r.end_et.isoformat(),
                "high": r.high,
                "low": r.low,
                "middle": r.middle,
                "open": r.open,
                "close": r.close,
                "bar_count": r.bar_count,
                "tz_abbrev": r.tz_abbrev,
            })
        print(json_mod.dumps(out, indent=2))
        return

    # Table output
    print(f"\nOvernight range ({args.symbol}): 18:00 ET previous day -> 06:00 ET session_date\n")
    for r in results:
        start_str = r.start_et.strftime("%Y-%m-%d %H:%M")
        end_str = r.end_et.strftime("%Y-%m-%d %H:%M")
        if r.bar_count:
            print(f"  {r.session_date}  {start_str} - {end_str} {r.tz_abbrev}  H={r.high} L={r.low} Mid={r.middle}  bars={r.bar_count}")
        else:
            print(f"  {r.session_date}  {start_str} - {end_str} {r.tz_abbrev}  (no data)")
    print()


if __name__ == "__main__":
    main()
