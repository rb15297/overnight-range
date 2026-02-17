"""
NFP (Non-Farm Payroll) service.

First Friday of each month at 8:30 ET = NFP release; if that day has no bar data (e.g. holiday),
use the second Friday. Provides NFP date, release price from 1-min bars, and regime classification
(09:00 close above vs below NFP release price).
"""

from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from zoneinfo import ZoneInfo

from sqlalchemy.orm import sessionmaker

from src.database_models import RawBar1Min

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def get_nfp_date_for_month(year: int, month: int) -> date:
    """Return the first Friday of the given month (calendar logic only)."""
    first = date(year, month, 1)
    # weekday(): Monday=0, Friday=4
    days_until_friday = (4 - first.weekday()) % 7
    if days_until_friday == 0 and first.weekday() != 4:
        days_until_friday = 7
    return first.replace(day=1 + days_until_friday)


def get_second_friday(year: int, month: int) -> date:
    """Return the second Friday of the given month."""
    first_friday = get_nfp_date_for_month(year, month)
    return first_friday + timedelta(days=7)


def get_nfp_release_price(
    symbol: str,
    nfp_date: date,
    engine,
) -> Optional[float]:
    """
    Query RawBar1Min for the bar that contains 8:30 ET on nfp_date.
    Return that bar's close, or None if missing.
    """
    start_et = datetime(nfp_date.year, nfp_date.month, nfp_date.day, 8, 30, 0, tzinfo=ET)
    end_et = datetime(nfp_date.year, nfp_date.month, nfp_date.day, 8, 31, 0, tzinfo=ET)
    start_utc = start_et.astimezone(UTC)
    end_utc = end_et.astimezone(UTC)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        bar = (
            session.query(RawBar1Min)
            .filter(
                RawBar1Min.symbol == symbol,
                RawBar1Min.timestamp >= start_utc,
                RawBar1Min.timestamp < end_utc,
            )
            .order_by(RawBar1Min.timestamp)
            .first()
        )
    return bar.close if bar is not None else None


def get_nfp_price_for_session(
    symbol: str,
    session_date: date,
    engine,
) -> Tuple[Optional[date], Optional[float]]:
    """
    For the month of session_date, get the effective NFP date and release price.
    Try first Friday; if no bar data (e.g. holiday), try second Friday.
    Return (nfp_date, price) or (None, None) if still no data.
    """
    year, month = session_date.year, session_date.month
    nfp_date = get_nfp_date_for_month(year, month)
    price = get_nfp_release_price(symbol, nfp_date, engine)
    if price is not None:
        return (nfp_date, price)
    second_fri = get_second_friday(year, month)
    price2 = get_nfp_release_price(symbol, second_fri, engine)
    if price2 is not None:
        return (second_fri, price2)
    return (None, None)


def classify_regime(close_09: float, nfp_price: Optional[float]) -> Optional[str]:
    """
    Given 09:00 close and NFP release price, return 'above', 'below', or None
    if nfp_price is None or close_09 == nfp_price.
    """
    if nfp_price is None:
        return None
    if close_09 > nfp_price:
        return "above"
    if close_09 < nfp_price:
        return "below"
    return None
