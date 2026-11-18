"""Health measurement ranges and classifications (adult reference values)."""
from typing import Optional

# Accepted input ranges; anything outside is almost certainly a typo.
WEIGHT_KG_RANGE = (1.0, 500.0)
HEIGHT_CM_RANGE = (30.0, 272.0)
SYSTOLIC_RANGE = (50, 300)
DIASTOLIC_RANGE = (30, 200)
PULSE_RANGE = (20, 250)


def bmi(weight_kg: float, height_cm: float) -> float:
    meters = height_cm / 100
    return round(weight_kg / (meters * meters), 1)


def bmi_category(value: float) -> str:
    """WHO adult categories."""
    if value < 18.5:
        return "underweight"
    if value < 25:
        return "normal"
    if value < 30:
        return "overweight"
    return "obese"


def blood_pressure_category(systolic: int, diastolic: int) -> str:
    """American Heart Association categories."""
    if systolic > 180 or diastolic > 120:
        return "crisis"
    if systolic >= 140 or diastolic >= 90:
        return "high_stage_2"
    if systolic >= 130 or diastolic >= 80:
        return "high_stage_1"
    if systolic >= 120:
        return "elevated"
    if systolic < 90 or diastolic < 60:
        return "low"
    return "normal"


def in_range(value: Optional[float], bounds) -> bool:
    return value is not None and bounds[0] <= value <= bounds[1]
