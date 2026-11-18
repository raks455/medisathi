"""Cycle reminder dispatch with in-memory fakes."""
import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

from app.application.use_cases.health.cycle_reminders import DispatchCycleRemindersUseCase
from app.domain.entities.womens_health import CyclePeriod, CycleSettings
from app.domain.value_objects.medication_enums import NotificationType


class FakeCycles:
    def __init__(self, settings, periods):
        self.settings = settings
        self.periods = periods

    async def list_reminder_settings(self):
        return [self.settings]

    async def list(self, user_id):
        return sorted(self.periods, key=lambda p: p.start_date, reverse=True)

    async def claim_alert(self, user_id, key):
        if self.settings.alert_key == key:
            return False
        self.settings.alert_key = key
        return True


class FakeDevices:
    async def list_tokens(self, user_id):
        return ["tok"]

    async def remove_tokens(self, tokens):
        pass


class FakeNotifications:
    def __init__(self):
        self.added = []

    async def add(self, user_id, type, title, body, data=None):
        self.added.append((type, title, data))


class FakePush:
    def __init__(self):
        self.sent = []

    async def send(self, tokens, title, body, data=None, collapse_key=None,
                   android_channel_id=None):
        self.sent.append(title)
        return []


def run(now, settings, periods):
    notes, push = FakeNotifications(), FakePush()
    use_case = DispatchCycleRemindersUseCase(
        FakeCycles(settings, periods), FakeDevices(), notes, push, send_from_hour=9)
    return asyncio.run(use_case.execute(now)), notes, push


def test_sends_period_coming_once_in_the_users_morning():
    user = uuid4()
    settings = CycleSettings(user_id=user, timezone="Asia/Kathmandu")
    periods = [
        CyclePeriod(uuid4(), user, date(2026, 10, 1), date(2026, 10, 5)),
        CyclePeriod(uuid4(), user, date(2026, 10, 29), date(2026, 11, 2)),
    ]
    # 02:00 UTC = 07:45 in Kathmandu: too early.
    sent, _, _ = run(datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc), settings, periods)
    assert sent == 0
    # 04:00 UTC = 09:45 local.
    sent, notes, push = run(datetime(2026, 11, 24, 4, 0, tzinfo=timezone.utc), settings, periods)
    assert sent == 1
    assert push.sent == ["Your period is coming"]
    assert notes.added[0][0] == NotificationType.PERIOD_REMINDER
    assert notes.added[0][2]["next_period_start"] == "2026-11-26"
    # Next check the same day: already sent.
    sent, _, _ = run(datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc), settings, periods)
    assert sent == 0


def test_nothing_while_an_open_period_is_in_progress():
    user = uuid4()
    settings = CycleSettings(user_id=user)
    periods = [
        CyclePeriod(uuid4(), user, date(2026, 10, 1), date(2026, 10, 5)),
        CyclePeriod(uuid4(), user, date(2026, 10, 29)),
    ]
    sent, _, _ = run(datetime(2026, 10, 31, 6, 0, tzinfo=timezone.utc), settings, periods)
    assert sent == 0
