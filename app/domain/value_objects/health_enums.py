from enum import Enum


class RecordFolder(str, Enum):
    """The two drives under Health Records."""
    PRESCRIPTIONS = "prescriptions"
    HEALTH_RECORDS = "health_records"


class RecordCategory(str, Enum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    IMAGING = "imaging"              # X-ray, scan, ultrasound reports
    DISCHARGE_SUMMARY = "discharge_summary"
    VACCINATION = "vaccination"
    INSURANCE = "insurance"
    OTHER = "other"


class VitalType(str, Enum):
    WEIGHT = "weight"                # value = kg
    HEIGHT = "height"                # value = cm
    BLOOD_PRESSURE = "blood_pressure"  # value = systolic, value2 = diastolic (mmHg)


class Mood(str, Enum):
    GREAT = "great"
    GOOD = "good"
    OKAY = "okay"
    LOW = "low"
    BAD = "bad"


class Flow(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class FeedbackTopic(str, Enum):
    SUGGESTION = "suggestion"
    PROBLEM = "problem"
    COMPLIMENT = "compliment"
    OTHER = "other"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class BloodGroup(str, Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
