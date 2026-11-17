"""Dose-reminder and refill-reminder dispatch, with in-memory fakes.

Plain asserts, no plugins: run with `pytest` or `python -m tests.unit.application.test_reminder_dispatch`.
"""
import asyncio
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from app.application.use_cases.reminder.dispatch_due_reminders import (
    DispatchDueRemindersUseCase, DispatchRefillRemindersUseCase,
)
from app.domain.entities.medication import (
    Medication, MedicationInventory, MedicationSchedule, PausedPeriod,
)
from app.domain.services.inventory_forecast import forecast_stock, is_low_stock
from app.domain.value_objects.medication_enums import (
    AlertStyle, IntakeTiming, MedicineType, NotificationType,
)

UTC = timezone.utc
# 12:00 UTC = 17:45 in Kathmandu.
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def make_med(times=("08:00", "20:00"), quantity=None, remind_days_before=3,
             alert_style=AlertStyle.NOTIFICATION, tz="Asia/Kathmandu") -> Medication:
    return Medication(
        id=uuid4(),
        user_id=uuid4(),
        name="Paracetamol",
        medicine_type=MedicineType.TABLET,
        dose="500 mg",
        intake_timing=IntakeTiming.AFTER_FOOD,
        schedule=MedicationSchedule(
            reminder_times=[time.fromisoformat(t) for t in times],
            timezone=tz,
            alert_style=alert_style,
        ),
        inventory=None if quantity is None else MedicationInventory(
            quantity=quantity, remind_days_before=remind_days_before
        ),
        created_at=NOW - timedelta(days=30),
    )


class FakeMedRepo:
    def __init__(self, meds):
        self.meds = meds

    async def list_with_active_reminders(self):
        return self.meds

    async def list_with_refill_reminders(self):
        return [m for m in self.meds if m.inventory and m.inventory.refill_reminder_enabled]

    async def claim_refill_alert(self, medication_id, stage):
        med = next(m for m in self.meds if m.id == medication_id)
        if med.inventory.alert_stage == stage:
            return False
        med.inventory.alert_stage = stage
        return True


class FakeDoseRepo:
    def __init__(self):
        self.claimed = set()

    async def claim_for_notification(self, user_id, medication_id, scheduled_for):
        key = (medication_id, scheduled_for)
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True


class FakeDeviceRepo:
    def __init__(self, tokens=("token-1",)):
        self.tokens = list(tokens)

    async def list_tokens(self, user_id):
        return self.tokens

    async def remove_tokens(self, tokens):
        pass


class FakeNotificationRepo:
    def __init__(self):
        self.saved = []

    async def add(self, user_id, type, title, body, data=None):
        self.saved.append((type, title, body, data or {}))


class FakePush:
    def __init__(self):
        self.sent = []

    async def send(self, tokens, title, body, data=None, collapse_key=None,
                   android_channel_id=None):
        self.sent.append({"title": title, "body": body, "data": data,
                          "collapse_key": collapse_key, "channel": android_channel_id})
        return []


def dose_dispatch(meds, devices=None):
    push, notes = FakePush(), FakeNotificationRepo()
    use_case = DispatchDueRemindersUseCase(
        med_repo=FakeMedRepo(meds), dose_repo=FakeDoseRepo(),
        device_repo=devices or FakeDeviceRepo(), notification_repo=notes, push=push,
        alarm_channel_id="medication_alarms",
    )
    return use_case, push, notes


def refill_dispatch(meds):
    push, notes = FakePush(), FakeNotificationRepo()
    use_case = DispatchRefillRemindersUseCase(
        med_repo=FakeMedRepo(meds), device_repo=FakeDeviceRepo(),
        notification_repo=notes, push=push, send_from_hour=9,
    )
    return use_case, push, notes


# ---- dose reminders -------------------------------------------------------

def test_due_dose_is_pushed_once_and_saved_to_the_list():
    med = make_med(times=("17:45",))           # due exactly at NOW
    use_case, push, notes = dose_dispatch([med])

    assert asyncio.run(use_case.execute(NOW)) == 1
    assert asyncio.run(use_case.execute(NOW + timedelta(minutes=1))) == 0   # not twice

    assert len(push.sent) == 1
    assert push.sent[0]["title"] == "Time to take Paracetamol"
    assert push.sent[0]["data"]["type"] == "medication_reminder"
    assert push.sent[0]["channel"] is None                    # default channel
    assert [n[0] for n in notes.saved] == [NotificationType.MEDICATION_REMINDER]


def test_alarm_style_uses_the_alarm_channel():
    med = make_med(times=("17:45",), alert_style=AlertStyle.ALARM)
    use_case, push, _ = dose_dispatch([med])
    asyncio.run(use_case.execute(NOW))
    assert push.sent[0]["channel"] == "medication_alarms"
    assert push.sent[0]["data"]["alert_style"] == "alarm"


def test_reminder_is_listed_even_without_a_registered_phone():
    med = make_med(times=("17:45",))
    use_case, push, notes = dose_dispatch([med], devices=FakeDeviceRepo(tokens=()))
    assert asyncio.run(use_case.execute(NOW)) == 1
    assert push.sent == [] and len(notes.saved) == 1


def test_stopped_medicine_gets_no_reminder():
    med = make_med(times=("17:45",))
    med.paused_periods = [PausedPeriod(since=NOW - timedelta(hours=1))]
    use_case, push, notes = dose_dispatch([med])
    assert asyncio.run(use_case.execute(NOW)) == 0
    assert push.sent == [] and notes.saved == []


def test_resumed_medicine_is_reminded_again():
    med = make_med(times=("17:45",))
    med.paused_periods = [
        PausedPeriod(since=NOW - timedelta(days=2), until=NOW - timedelta(hours=1))
    ]
    use_case, push, _ = dose_dispatch([med])
    assert asyncio.run(use_case.execute(NOW)) == 1


# ---- stock forecast -------------------------------------------------------

def test_forecast_counts_upcoming_doses():
    # 2 doses a day; today's 20:00 dose is still ahead. 5 tablets cover
    # today 20:00, +1 day x2, +2 days x2 -> the 6th dose (day +3, 08:00) is short.
    med = make_med(quantity=5)
    f = forecast_stock(med, NOW)
    assert f.doses_left == 5
    assert f.days_left == 3
    assert is_low_stock(med, f)                       # 3 <= remind_days_before 3

    plenty = make_med(quantity=60)
    f = forecast_stock(plenty, NOW)
    assert f.days_left == 30 and not is_low_stock(plenty, f)


def test_forecast_has_no_date_without_schedule_or_when_stopped():
    med = make_med(quantity=5)
    med.schedule = None
    assert forecast_stock(med, NOW).days_left is None

    stopped = make_med(quantity=5)
    stopped.paused_periods = [PausedPeriod(since=NOW - timedelta(days=1))]
    assert forecast_stock(stopped, NOW).days_left is None

    assert forecast_stock(make_med(), NOW) is None    # no inventory at all


def test_forecast_respects_units_per_dose():
    med = make_med(quantity=10)
    med.inventory.units_per_dose = 0.5
    assert forecast_stock(med, NOW).doses_left == 20


# ---- refill reminders -----------------------------------------------------

def test_early_refill_reminder_is_sent_once():
    med = make_med(quantity=5, remind_days_before=3)      # runs out in 3 days
    use_case, push, notes = refill_dispatch([med])

    assert asyncio.run(use_case.execute(NOW)) == 1
    assert asyncio.run(use_case.execute(NOW + timedelta(minutes=1))) == 0

    assert push.sent[0]["title"] == "Refill Paracetamol soon"
    assert "5 left" in push.sent[0]["body"] and "in 3 days" in push.sent[0]["body"]
    assert push.sent[0]["data"]["type"] == "refill_reminder"
    assert notes.saved[0][0] == NotificationType.REFILL_REMINDER
    assert med.inventory.alert_stage == "early"


def test_no_refill_reminder_while_stock_is_outside_the_window():
    med = make_med(quantity=60, remind_days_before=3)
    use_case, push, _ = refill_dispatch([med])
    assert asyncio.run(use_case.execute(NOW)) == 0 and push.sent == []


def test_final_refill_reminder_on_the_day_it_runs_out():
    med = make_med(quantity=5, remind_days_before=3)
    use_case, push, _ = refill_dispatch([med])
    asyncio.run(use_case.execute(NOW))                    # early alert

    med.inventory.quantity = 1                            # only tonight's dose left
    later = NOW + timedelta(minutes=5)
    # Tonight's dose is covered; tomorrow 08:00 is not -> runs out tomorrow.
    assert asyncio.run(use_case.execute(later)) == 0

    med.inventory.quantity = 0                            # tonight's dose is short
    assert asyncio.run(use_case.execute(later)) == 1
    assert push.sent[-1]["title"] == "Paracetamol runs out today"
    assert asyncio.run(use_case.execute(later + timedelta(hours=1))) == 0   # once


def test_refill_reminders_wait_for_the_morning():
    med = make_med(quantity=5, remind_days_before=3)
    use_case, push, _ = refill_dispatch([med])
    night = datetime(2026, 11, 17, 20, 0, tzinfo=UTC)     # 01:45 in Kathmandu
    assert asyncio.run(use_case.execute(night)) == 0
    morning = datetime(2026, 11, 18, 3, 30, tzinfo=UTC)   # 09:15 in Kathmandu
    assert asyncio.run(use_case.execute(morning)) == 1


def test_no_refill_reminder_when_disabled_or_stopped():
    off = make_med(quantity=5)
    off.inventory.refill_reminder_enabled = False
    stopped = make_med(quantity=5)
    stopped.paused_periods = [PausedPeriod(since=NOW - timedelta(days=1))]
    use_case, push, _ = refill_dispatch([off, stopped])
    assert asyncio.run(use_case.execute(NOW)) == 0 and push.sent == []


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok ", name)
    print(f"{len(tests)} passed")
