"""Pure functions that estimate when a medicine's stock runs out."""
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.domain.entities.medication import Medication
from app.domain.services.reminder_schedule import occurrences_between

DEFAULT_HORIZON_DAYS = 365


@dataclass
class StockForecast:
    doses_left: int                      # full doses the current stock covers
    runs_out_on: Optional[date] = None   # local date of the first dose that cannot be taken
    days_left: Optional[int] = None      # days from today until `runs_out_on` (0 = today)


def forecast_stock(
    med: Medication, now: datetime, horizon_days: int = DEFAULT_HORIZON_DAYS
) -> Optional[StockForecast]:
    """Walk the upcoming scheduled doses until the stock is used up.

    Returns None if the medicine has no inventory. `runs_out_on` stays None
    when no date can be estimated: no schedule ("as needed"), the medicine is
    stopped, or the stock outlasts the course / the horizon.
    """
    inv = med.inventory
    if inv is None:
        return None
    # Small epsilon so 10 / 0.5 is 20 doses, not 19 from float rounding.
    doses_left = max(0, math.floor(inv.quantity / inv.units_per_dose + 1e-9))
    forecast = StockForecast(doses_left=doses_left)
    if med.schedule is None or med.is_stopped:
        return forecast

    upcoming = occurrences_between(med.schedule, now, now + timedelta(days=horizon_days))
    if len(upcoming) > doses_left:
        tz = ZoneInfo(med.schedule.timezone)
        forecast.runs_out_on = upcoming[doses_left].astimezone(tz).date()
        forecast.days_left = (forecast.runs_out_on - now.astimezone(tz).date()).days
    return forecast


def is_low_stock(med: Medication, forecast: Optional[StockForecast]) -> bool:
    """True once the stock is inside the user's "remind me N days before" window."""
    if med.inventory is None or forecast is None or forecast.days_left is None:
        return False
    return forecast.days_left <= med.inventory.remind_days_before
