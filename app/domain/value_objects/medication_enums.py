from enum import Enum


class MedicineType(str, Enum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    SYRUP = "syrup"
    INJECTION = "injection"
    CREAM = "cream"
    OINTMENT = "ointment"
    GEL = "gel"
    DROPS = "drops"
    INHALER = "inhaler"
    SPRAY = "spray"
    POWDER = "powder"
    PATCH = "patch"
    SUPPOSITORY = "suppository"
    OTHER = "other"


class IntakeTiming(str, Enum):
    BEFORE_FOOD = "before_food"
    AFTER_FOOD = "after_food"
    WITH_FOOD = "with_food"
    EMPTY_STOMACH = "empty_stomach"
    BEFORE_SLEEP = "before_sleep"
    ANYTIME = "anytime"


class DoseStatus(str, Enum):
    """Stored status of a dose log."""
    PENDING = "pending"   # created by the server when it sent a push; not answered yet
    TAKEN = "taken"
    SKIPPED = "skipped"


class DoseViewStatus(str, Enum):
    """Status shown to the user for a scheduled dose."""
    UPCOMING = "upcoming"
    DUE = "due"           # time has passed but still within the grace window
    MISSED = "missed"
    TAKEN = "taken"
    SKIPPED = "skipped"
