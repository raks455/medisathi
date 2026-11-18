"""Pregnancy dates and weekly progress (Naegele's rule: due = LMP + 280 days)."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

GESTATION_DAYS = 280

# Baby's approximate size by week of pregnancy.
_BABY_SIZE = {
    4: "a poppy seed", 5: "a sesame seed", 6: "a lentil", 7: "a blueberry",
    8: "a raspberry", 9: "a cherry", 10: "a strawberry", 11: "a fig",
    12: "a lime", 13: "a lemon", 14: "a peach", 15: "an apple",
    16: "an avocado", 17: "a pear", 18: "a bell pepper", 19: "a mango",
    20: "a banana", 21: "a carrot", 22: "a papaya", 23: "a grapefruit",
    24: "an ear of corn", 25: "a cauliflower", 26: "a head of lettuce",
    27: "a cabbage", 28: "an eggplant", 29: "a butternut squash",
    30: "a large cabbage", 31: "a coconut", 32: "a squash",
    33: "a pineapple", 34: "a cantaloupe", 35: "a honeydew melon",
    36: "a romaine lettuce", 37: "a bunch of chard", 38: "a leek",
    39: "a small watermelon", 40: "a pumpkin",
}

_TIPS = {
    1: "Take folic acid daily, rest when you can, and book your first antenatal "
       "check-up. Tell your doctor about every medicine you take.",
    2: "Many people feel more energetic now. Keep up antenatal visits, eat iron-"
       "rich foods and stay active with gentle exercise your doctor approves.",
    3: "Count your baby's movements, prepare your hospital bag and know the "
       "signs of labour. Contact your doctor about bleeding, severe headache or "
       "reduced movements.",
}


def due_date_from_lmp(lmp: date) -> date:
    return lmp + timedelta(days=GESTATION_DAYS)


def lmp_from_due_date(due: date) -> date:
    return due - timedelta(days=GESTATION_DAYS)


def trimester_for_week(week: int) -> int:
    if week < 13:
        return 1
    if week < 27:
        return 2
    return 3


@dataclass(frozen=True)
class PregnancyProgress:
    weeks: int
    days: int
    trimester: int
    days_remaining: int
    percent_complete: float
    baby_size: Optional[str]
    tip: str


def progress(lmp: date, due: date, today: date) -> PregnancyProgress:
    total = max((due - lmp).days, 1)
    elapsed = min(max((today - lmp).days, 0), total + 21)
    weeks, days = divmod(elapsed, 7)
    trimester = trimester_for_week(weeks)
    return PregnancyProgress(
        weeks=weeks,
        days=days,
        trimester=trimester,
        days_remaining=(due - today).days,
        percent_complete=round(min(elapsed / total, 1.0) * 100, 1),
        baby_size=_BABY_SIZE.get(min(weeks, 40)),
        tip=_TIPS[trimester],
    )
