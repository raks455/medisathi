"""Cycle forecast, pregnancy progress, vitals rules and file sniffing.

Plain asserts: run with `pytest tests/unit`.
"""
from datetime import date

from app.domain.services import cycle_forecast as cf
from app.domain.services import pregnancy_progress as pp
from app.domain.services import vitals
from app.domain.services.file_types import sniff_content_type


def P(start, end=None):
    return cf.LoggedPeriod(date.fromisoformat(start), date.fromisoformat(end) if end else None)


# ---- cycle ----------------------------------------------------------------

def test_no_periods_uses_defaults_and_predicts_nothing():
    f = cf.forecast([], date(2026, 11, 18))
    assert f.average_cycle_length == 28
    assert f.average_period_length == 5
    assert f.next_period_start is None
    assert f.windows == []


def test_averages_ignore_outlier_gaps():
    periods = [P("2026-07-01", "2026-07-05"), P("2026-07-31", "2026-08-03"),
               P("2026-08-30", "2026-09-04"),
               # 80-day gap: a missed log, not a real cycle
               P("2026-11-18")]
    assert cf.cycle_lengths(periods) == [30, 30]
    assert cf.average_cycle_length(periods) == 30
    assert cf.period_lengths(periods) == [5, 4, 6]
    assert cf.average_period_length(periods) == 5


def test_forecast_predicts_next_period_ovulation_and_fertile_window():
    periods = [P("2026-09-01", "2026-09-05"), P("2026-09-29", "2026-10-03"),
               P("2026-10-27", "2026-10-31")]
    f = cf.forecast(periods, date(2026, 11, 8), cycles_ahead=2)
    assert f.average_cycle_length == 28
    assert f.next_period_start == date(2026, 11, 24)
    assert f.days_until_next_period == 16
    assert f.cycle_day == 13
    current = f.windows[0]
    assert not current.predicted
    assert current.ovulation_date == date(2026, 11, 10)
    assert (current.fertile_start, current.fertile_end) == (date(2026, 11, 5), date(2026, 11, 11))
    assert f.phase == "fertile"
    assert [w.period_start for w in f.windows[1:]] == [date(2026, 11, 24), date(2026, 12, 22)]
    assert all(w.predicted for w in f.windows[1:])


def test_phases():
    periods = [P("2026-10-01", "2026-10-05"), P("2026-10-29", "2026-11-02")]
    phase = lambda d: cf.forecast(periods, date.fromisoformat(d)).phase  # noqa: E731
    assert phase("2026-10-30") == "menstrual"
    assert phase("2026-11-04") == "follicular"
    assert phase("2026-11-12") == "ovulation"
    assert phase("2026-11-20") == "luteal"


def test_late_period_has_negative_days_until():
    f = cf.forecast([P("2026-10-01", "2026-10-05")], date(2026, 11, 3))
    assert f.next_period_start == date(2026, 10, 29)
    assert f.days_until_next_period == -5


# ---- pregnancy ------------------------------------------------------------

def test_due_date_naegele():
    assert pp.due_date_from_lmp(date(2026, 1, 1)) == date(2026, 10, 8)
    assert pp.lmp_from_due_date(date(2026, 10, 8)) == date(2026, 1, 1)


def test_progress_weeks_trimester_and_size():
    lmp = date(2026, 6, 1)
    p = pp.progress(lmp, pp.due_date_from_lmp(lmp), date(2026, 9, 10))  # 101 days
    assert (p.weeks, p.days) == (14, 3)
    assert p.trimester == 2
    assert p.baby_size == "a peach"
    assert p.days_remaining == 179
    assert p.percent_complete == 36.1


def test_progress_clamps_before_start_and_after_due():
    lmp = date(2026, 6, 1)
    due = pp.due_date_from_lmp(lmp)
    early = pp.progress(lmp, due, date(2026, 5, 20))
    assert (early.weeks, early.days, early.percent_complete) == (0, 0, 0)
    late = pp.progress(lmp, due, date(2027, 3, 20))
    assert late.percent_complete == 100
    assert late.baby_size == "a pumpkin"


# ---- vitals ---------------------------------------------------------------

def test_bmi_and_categories():
    assert vitals.bmi(70, 175) == 22.9
    assert vitals.bmi_category(22.9) == "normal"
    assert vitals.bmi_category(17) == "underweight"
    assert vitals.bmi_category(31) == "obese"


def test_blood_pressure_categories():
    assert vitals.blood_pressure_category(115, 75) == "normal"
    assert vitals.blood_pressure_category(125, 75) == "elevated"
    assert vitals.blood_pressure_category(132, 78) == "high_stage_1"
    assert vitals.blood_pressure_category(118, 92) == "high_stage_2"
    assert vitals.blood_pressure_category(190, 100) == "crisis"
    assert vitals.blood_pressure_category(85, 55) == "low"


# ---- files ----------------------------------------------------------------

def test_sniff_content_type():
    assert sniff_content_type(b"%PDF-1.7\n...") == "application/pdf"
    assert sniff_content_type(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"
    assert sniff_content_type(b"\x89PNG\r\n\x1a\n\x00\x00") == "image/png"
    assert sniff_content_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff_content_type(b"\x00\x00\x00\x18ftypheic\x00") == "image/heic"
    assert sniff_content_type(b"<html><script>") is None
    assert sniff_content_type(b"MZ\x90\x00") is None


# ---- cycle reminders ------------------------------------------------------

def _reminder(today, periods=None, days_before=2, fertile=False, period=True):
    periods = periods or [P("2026-10-01", "2026-10-05"), P("2026-10-29", "2026-11-02")]
    d = date.fromisoformat(today)
    return cf.due_reminder(cf.forecast(periods, d), d, days_before, period, fertile)


def test_period_coming_due_and_late_reminders():
    # Next period expected 2026-11-26.
    assert _reminder("2026-11-23") is None
    soon = _reminder("2026-11-24")
    assert soon.key == "period:2026-11-26:soon" and "in 2 days" in soon.body
    assert _reminder("2026-11-25").key == "period:2026-11-26:soon"  # same key: sent once
    assert "tomorrow" in _reminder("2026-11-25").body
    assert _reminder("2026-11-26").key == "period:2026-11-26:due"
    assert _reminder("2026-11-27") is None
    assert _reminder("2026-11-29").key == "period:2026-11-26:late"


def test_no_reminder_during_a_period_or_when_turned_off():
    assert _reminder("2026-10-30") is None
    assert _reminder("2026-11-24", period=False) is None


def test_fertile_window_reminder_is_opt_in():
    # Current cycle (from Oct 29): ovulation Nov 12, fertile from Nov 7.
    assert _reminder("2026-11-07") is None
    r = _reminder("2026-11-07", fertile=True)
    assert r.key == "fertile:2026-11-07"
    assert "Nov 12" in r.body
