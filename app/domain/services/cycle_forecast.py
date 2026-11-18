"""Menstrual cycle averages and predictions.

Pure functions over logged periods, so they are easy to test. Predictions use
the common calendar method: ovulation about 14 days before the next period,
fertile window from 5 days before ovulation to 1 day after.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean
from typing import List, Optional, Sequence

from app.domain.services import notification_texts as texts

DEFAULT_CYCLE_LENGTH = 28
DEFAULT_PERIOD_LENGTH = 5
# Gaps outside this range are treated as missed logs, not real cycles.
MIN_CYCLE_LENGTH = 15
MAX_CYCLE_LENGTH = 60
MAX_PERIOD_LENGTH = 15
LUTEAL_PHASE_DAYS = 14
HISTORY_FOR_AVERAGES = 6


@dataclass(frozen=True)
class LoggedPeriod:
    start_date: date
    end_date: Optional[date] = None


@dataclass(frozen=True)
class CycleWindow:
    period_start: date
    period_end: date
    ovulation_date: date
    fertile_start: date
    fertile_end: date
    predicted: bool


@dataclass
class CycleForecast:
    average_cycle_length: int
    average_period_length: int
    cycles_logged: int
    last_period_start: Optional[date] = None
    next_period_start: Optional[date] = None
    days_until_next_period: Optional[int] = None  # negative = late
    cycle_day: Optional[int] = None
    phase: Optional[str] = None  # menstrual | follicular | fertile | ovulation | luteal
    windows: List[CycleWindow] = field(default_factory=list)


def cycle_lengths(periods: Sequence[LoggedPeriod]) -> List[int]:
    starts = sorted({p.start_date for p in periods})
    gaps = [(b - a).days for a, b in zip(starts, starts[1:])]
    return [g for g in gaps if MIN_CYCLE_LENGTH <= g <= MAX_CYCLE_LENGTH]


def period_lengths(periods: Sequence[LoggedPeriod]) -> List[int]:
    lengths = [
        (p.end_date - p.start_date).days + 1
        for p in sorted(periods, key=lambda p: p.start_date)
        if p.end_date is not None
    ]
    return [n for n in lengths if 1 <= n <= MAX_PERIOD_LENGTH]


def average_cycle_length(periods: Sequence[LoggedPeriod]) -> int:
    recent = cycle_lengths(periods)[-HISTORY_FOR_AVERAGES:]
    return round(mean(recent)) if recent else DEFAULT_CYCLE_LENGTH


def average_period_length(periods: Sequence[LoggedPeriod]) -> int:
    recent = period_lengths(periods)[-HISTORY_FOR_AVERAGES:]
    return round(mean(recent)) if recent else DEFAULT_PERIOD_LENGTH


def _window(start: date, cycle: int, period: int, predicted: bool,
            period_end: Optional[date] = None) -> CycleWindow:
    ovulation = start + timedelta(days=max(cycle - LUTEAL_PHASE_DAYS, 1))
    return CycleWindow(
        period_start=start,
        period_end=period_end or start + timedelta(days=period - 1),
        ovulation_date=ovulation,
        fertile_start=ovulation - timedelta(days=5),
        fertile_end=ovulation + timedelta(days=1),
        predicted=predicted,
    )


def forecast(periods: Sequence[LoggedPeriod], today: date,
             cycles_ahead: int = 3) -> CycleForecast:
    cycle = average_cycle_length(periods)
    period = average_period_length(periods)
    result = CycleForecast(
        average_cycle_length=cycle,
        average_period_length=period,
        cycles_logged=len(periods),
    )
    if not periods:
        return result

    last = max(periods, key=lambda p: p.start_date)
    result.last_period_start = last.start_date
    current = _window(last.start_date, cycle, period, predicted=False,
                      period_end=last.end_date)
    result.windows.append(current)

    next_start = last.start_date + timedelta(days=cycle)
    result.next_period_start = next_start
    result.days_until_next_period = (next_start - today).days
    for k in range(cycles_ahead):
        start = next_start + timedelta(days=cycle * k)
        result.windows.append(_window(start, cycle, period, predicted=True))

    if today >= last.start_date:
        result.cycle_day = (today - last.start_date).days + 1
        if today <= current.period_end:
            result.phase = "menstrual"
        elif today == current.ovulation_date:
            result.phase = "ovulation"
        elif current.fertile_start <= today <= current.fertile_end:
            result.phase = "fertile"
        elif today < current.fertile_start:
            result.phase = "follicular"
        else:
            result.phase = "luteal"
    return result


@dataclass(frozen=True)
class CycleReminder:
    key: str      # unique per reminder, so each is sent once
    title: str
    body: str


def due_reminder(f: CycleForecast, today: date, remind_days_before: int,
                 period_reminders: bool = True,
                 fertile_reminders: bool = False,
                 lang: str = "en") -> Optional[CycleReminder]:
    """The cycle reminder to send today, if any.

    Period: once a few days before, once on the expected day, and once when
    it is 3 days late. Fertile window: on its first day. Nothing while a
    period is in progress.
    """
    if f.next_period_start is None or f.days_until_next_period is None:
        return None
    if f.phase == "menstrual":
        return None
    days = f.days_until_next_period
    start = f.next_period_start.isoformat()

    if period_reminders:
        if 1 <= days <= remind_days_before:
            return CycleReminder(f"period:{start}:soon", *texts.period_soon(days, lang))
        if days == 0:
            return CycleReminder(f"period:{start}:due", *texts.period_due(lang))
        if days == -3:
            return CycleReminder(f"period:{start}:late", *texts.period_late(lang))
    if fertile_reminders:
        current = next((w for w in f.windows if not w.predicted), None)
        if current is not None and today == current.fertile_start:
            return CycleReminder(
                f"fertile:{current.fertile_start.isoformat()}",
                *texts.fertile_start(current.ovulation_date, lang),
            )
    return None
