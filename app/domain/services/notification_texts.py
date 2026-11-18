"""The words of every push / in-app notification, in English and Nepali.

Kept in one place so the two languages stay side by side. The Nepali is
plain spoken Nepali: many users have it read to them.
"""
from typing import Optional

from app.domain.entities.medication import Medication
from app.domain.value_objects.medication_enums import IntakeTiming, MedicineType

SUPPORTED_LANGUAGES = ("en", "ne")
DEFAULT_LANGUAGE = "en"


def normalize_language(lang: Optional[str]) -> str:
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


_TIMING = {
    "en": {
        IntakeTiming.BEFORE_FOOD: "before food",
        IntakeTiming.AFTER_FOOD: "after food",
        IntakeTiming.WITH_FOOD: "with food",
        IntakeTiming.EMPTY_STOMACH: "on an empty stomach",
        IntakeTiming.BEFORE_SLEEP: "before sleep",
    },
    "ne": {
        IntakeTiming.BEFORE_FOOD: "खाना खानुअघि",
        IntakeTiming.AFTER_FOOD: "खाना खाएपछि",
        IntakeTiming.WITH_FOOD: "खानासँगै",
        IntakeTiming.EMPTY_STOMACH: "खाली पेटमा",
        IntakeTiming.BEFORE_SLEEP: "सुत्नुअघि",
    },
}

_TYPE_NE = {
    MedicineType.TABLET: "चक्की",
    MedicineType.CAPSULE: "क्याप्सुल",
    MedicineType.SYRUP: "झोल औषधि",
    MedicineType.INJECTION: "सुई",
    MedicineType.CREAM: "क्रिम",
    MedicineType.OINTMENT: "मलम",
    MedicineType.GEL: "जेल",
    MedicineType.DROPS: "थोपा औषधि",
    MedicineType.INHALER: "इन्हेलर",
    MedicineType.SPRAY: "स्प्रे",
    MedicineType.POWDER: "धुलो औषधि",
    MedicineType.PATCH: "प्याच",
    MedicineType.SUPPOSITORY: "सपोजिटरी",
    MedicineType.OTHER: "औषधि",
}

# Nepali has no single verb for "take": a tablet is eaten, a cream is put on.
_EAT, _APPLY, _USE = "खाने", "लगाउने", "लिने"
_VERB_NE = {
    MedicineType.TABLET: _EAT,
    MedicineType.CAPSULE: _EAT,
    MedicineType.SYRUP: _EAT,
    MedicineType.POWDER: _EAT,
    MedicineType.INJECTION: _APPLY,
    MedicineType.CREAM: _APPLY,
    MedicineType.OINTMENT: _APPLY,
    MedicineType.GEL: _APPLY,
    MedicineType.PATCH: _APPLY,
    MedicineType.DROPS: "हाल्ने",
}
_DONE_NE = {_EAT: "खानुभयो", _APPLY: "लगाउनुभयो", _USE: "लिनुभयो", "हाल्ने": "हाल्नुभयो"}


def _amount(value: float) -> str:
    """30.0 -> '30', 2.5 -> '2.5'."""
    return f"{value:g}"


def reminder_text(med: Medication, delayed: bool, lang: str = "en") -> tuple[str, str]:
    """Title and body of a "time to take your medicine" reminder."""
    lang = normalize_language(lang)
    timing = _TIMING[lang].get(med.intake_timing)
    if lang == "ne":
        verb = _VERB_NE.get(med.medicine_type, _USE)
        title = (f"{med.name} {_DONE_NE[verb]}?" if delayed
                 else f"{med.name} {verb} समय भयो")
        parts = [f"{med.dose} ({_TYPE_NE.get(med.medicine_type, 'औषधि')})"]
    else:
        title = f"Did you take {med.name}?" if delayed else f"Time to take {med.name}"
        parts = [f"{med.dose} ({med.medicine_type.value})"]
    if timing:
        parts.append(timing)
    body = " - ".join(parts)
    if med.instructions:
        # Written by the user, so it stays in whatever language they used.
        body += f". {med.instructions}"
    return title, body


def refill_text(med: Medication, days_left: int, final: bool,
                lang: str = "en") -> tuple[str, str]:
    amount = _amount(med.inventory.quantity)
    if normalize_language(lang) == "ne":
        left = f"{amount} बाँकी छ"
        if final:
            return (f"{med.name} आज सकिँदैछ",
                    f"{left}। खुराक नछुटोस् भनेर अहिले नै किन्नुहोस्।")
        when = "भोलि" if days_left == 1 else f"{days_left} दिनमा"
        return f"{med.name} चाँडै किन्नुहोस्", f"{left} - {when} सकिन्छ।"
    left = f"{amount} left"
    if final:
        return (f"{med.name} runs out today",
                f"{left}. Refill now so you do not miss a dose.")
    when = "tomorrow" if days_left == 1 else f"in {days_left} days"
    return f"Refill {med.name} soon", f"{left} - it runs out {when}."


def test_text(lang: str = "en") -> tuple[str, str]:
    if normalize_language(lang) == "ne":
        return "MediSathi परीक्षण", "सूचना राम्ररी आइरहेको छ"
    return "Medisathi test", "Push notifications are working"


_MONTHS_NE = ["जनवरी", "फेब्रुअरी", "मार्च", "अप्रिल", "मे", "जुन", "जुलाई",
              "अगस्ट", "सेप्टेम्बर", "अक्टोबर", "नोभेम्बर", "डिसेम्बर"]


def period_soon(days: int, lang: str = "en") -> tuple[str, str]:
    if normalize_language(lang) == "ne":
        when = "भोलि" if days == 1 else f"{days} दिनमा"
        return ("तपाईंको महिनावारी आउँदैछ",
                f"अर्को महिनावारी {when} हुने अनुमान छ। प्याड तयार राख्नुहोस्।")
    when = "tomorrow" if days == 1 else f"in {days} days"
    return ("Your period is coming",
            f"Your next period is expected {when}. Keep pads or tampons handy.")


def period_due(lang: str = "en") -> tuple[str, str]:
    if normalize_language(lang) == "ne":
        return ("आज महिनावारी सुरु हुन सक्छ",
                "सुरु भएपछि MediSathi मा लेख्नुहोस्, अनुमान सही रहन्छ।")
    return ("Your period may start today",
            "Log it in MediSathi when it starts to keep predictions accurate.")


def period_late(lang: str = "en") -> tuple[str, str]:
    if normalize_language(lang) == "ne":
        return ("महिनावारी 3 दिन ढिलो भयो",
                "महिनावारीको समय फरक पर्न सक्छ। सुरु भएपछि लेख्नुहोस्, "
                "चिन्ता लागे डाक्टरसँग सल्लाह गर्नुहोस्।")
    return ("Your period is 3 days late",
            "Cycles can vary. Log your period when it starts, and talk to a "
            "doctor if you are worried.")


def fertile_start(ovulation, lang: str = "en") -> tuple[str, str]:
    if normalize_language(lang) == "ne":
        day = f"{_MONTHS_NE[ovulation.month - 1]} {ovulation.day}"
        return ("आजदेखि गर्भ रहन सक्ने दिन सुरु हुन्छ",
                f"डिम्ब निस्कने दिन {day} तिर हुने अनुमान छ।")
    return ("Your fertile window starts today",
            f"Ovulation is expected around "
            f"{ovulation.strftime('%b %d').replace(' 0', ' ')}.")
