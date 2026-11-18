"""Notification wording in English and Nepali.

Plain asserts: run with `pytest`.
"""
from datetime import date, time
from uuid import uuid4

from app.domain.entities.medication import Medication, MedicationInventory, MedicationSchedule
from app.domain.services import cycle_forecast as cf
from app.domain.services.notification_texts import (
    normalize_language, refill_text, reminder_text, test_text as push_test_text,
)
from app.domain.value_objects.medication_enums import IntakeTiming, MedicineType


def _med(medicine_type=MedicineType.TABLET, timing=IntakeTiming.AFTER_FOOD,
         instructions=None, quantity=4) -> Medication:
    return Medication(
        id=uuid4(), user_id=uuid4(), name="Cetamol", medicine_type=medicine_type,
        dose="500 mg", intake_timing=timing, instructions=instructions,
        schedule=MedicationSchedule(reminder_times=[time(8, 0)]),
        inventory=MedicationInventory(quantity=quantity),
    )


def test_unknown_language_falls_back_to_english():
    assert normalize_language("ne") == "ne"
    assert normalize_language("fr") == "en"
    assert normalize_language(None) == "en"
    assert reminder_text(_med(), False, "fr") == reminder_text(_med(), False)


def test_english_reminder_is_unchanged():
    title, body = reminder_text(_med(instructions="With water"), delayed=False)
    assert title == "Time to take Cetamol"
    assert body == "500 mg (tablet) - after food. With water"
    assert reminder_text(_med(), delayed=True)[0] == "Did you take Cetamol?"


def test_nepali_reminder_keeps_the_name_and_dose():
    title, body = reminder_text(_med(), delayed=False, lang="ne")
    assert title == "Cetamol खाने समय भयो"
    assert body == "500 mg (चक्की) - खाना खाएपछि"
    assert reminder_text(_med(), delayed=True, lang="ne")[0] == "Cetamol खानुभयो?"


def test_nepali_verb_follows_the_form_of_the_medicine():
    # A cream is put on, drops are put in: neither is "eaten".
    assert "लगाउने" in reminder_text(_med(MedicineType.CREAM), False, "ne")[0]
    assert "हाल्ने" in reminder_text(_med(MedicineType.DROPS), False, "ne")[0]
    assert "लिने" in reminder_text(_med(MedicineType.INHALER), False, "ne")[0]
    assert "लगाउनुभयो" in reminder_text(_med(MedicineType.CREAM), True, "ne")[0]


def test_anytime_has_no_timing_text():
    assert reminder_text(_med(timing=IntakeTiming.ANYTIME), False, "ne")[1] == "500 mg (चक्की)"
    assert reminder_text(_med(timing=IntakeTiming.ANYTIME), False)[1] == "500 mg (tablet)"


def test_refill_texts():
    assert refill_text(_med(), 2, final=False) == (
        "Refill Cetamol soon", "4 left - it runs out in 2 days.")
    assert refill_text(_med(), 1, final=False, lang="ne") == (
        "Cetamol चाँडै किन्नुहोस्", "4 बाँकी छ - भोलि सकिन्छ।")
    assert refill_text(_med(), 0, final=True, lang="ne")[0] == "Cetamol आज सकिँदैछ"


def test_push_test_text():
    assert push_test_text()[1] == "Push notifications are working"
    assert push_test_text("ne")[0] == "MediSathi परीक्षण"


def test_cycle_reminders_in_nepali_keep_their_keys():
    periods = [cf.LoggedPeriod(date(2026, 10, 1), date(2026, 10, 5)),
               cf.LoggedPeriod(date(2026, 10, 29), date(2026, 11, 2))]

    def reminder(day, lang, fertile=False):
        d = date.fromisoformat(day)
        return cf.due_reminder(cf.forecast(periods, d), d, 2, True, fertile, lang=lang)

    en, ne = reminder("2026-11-24", "en"), reminder("2026-11-24", "ne")
    # The key decides "already sent", so it must not depend on the language.
    assert en.key == ne.key == "period:2026-11-26:soon"
    assert "in 2 days" in en.body and "2 दिनमा" in ne.body
    assert "भोलि" in reminder("2026-11-25", "ne").body
    assert reminder("2026-11-26", "ne").title == "आज महिनावारी सुरु हुन सक्छ"
    assert "नोभेम्बर 12" in reminder("2026-11-07", "ne", fertile=True).body
