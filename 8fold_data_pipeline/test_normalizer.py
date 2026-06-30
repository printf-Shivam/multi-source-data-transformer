"""
test_normalizer.py — Unit tests for Transform 1 (Lexical Normalization).

Includes regression tests for two bugs found and fixed during review:
  1. normalize_phone previously stripped digits and prepended "+"
     without validating the result was a real, dialable number.
  2. The fallback keyword matcher used raw substring containment,
     causing false positives like "validated_by" (contains "date")
     being silently destroyed by normalize_date.
"""
from src.transform.normalizer import (
    normalize_date,
    normalize_phone,
    canonicalize_skill,
    normalize_country,
    normalize_field,
    normalize_observations,
)
from src.models.observation import Observation


def test_normalize_date():
    assert normalize_date("Jan 2023") == "2023-01"
    assert normalize_date("2023") == "2023-01"
    assert normalize_date("2023-01-15") == "2023-01"
    assert normalize_date("Present") == "Present"
    assert normalize_date("garbage") is None
    assert normalize_date("") is None
    assert normalize_date("2023/01") == "2023-01"
    assert normalize_date("01/2023") == "2023-01"
    assert normalize_date("Jan 15, 2023") == "2023-01"


def test_normalize_phone_valid_numbers():
    """Real, valid phone numbers should produce true E.164 output."""
    assert normalize_phone("+1 415 555 0101") == "+14155550101"
    assert normalize_phone("(415) 555-0101") == "+14155550101"
    assert normalize_phone("415-555-0101") == "+14155550101"
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_normalize_phone_rejects_invalid_numbers():
    """
    REGRESSION TEST for the strip-and-prepend bug.

    The old normalize_phone() stripped non-digits and prepended "+",
    so "(555) 123-4567" (a fictional/reserved US test number, and also
    missing a country code) became the fake-looking-valid
    "+5551234567". The correct behavior is to return None for any
    number that doesn't pass real E.164 validation — "unknown values
    become null, never invented" per the design doc.
    """
    assert normalize_phone("(555) 123-4567") is None  # reserved/fictional prefix
    assert normalize_phone("not-a-phone") is None
    assert normalize_phone("123") is None  # too short to be a real number


def test_canonicalize_skill():
    assert canonicalize_skill("react.js") == "React"
    assert canonicalize_skill("reactjs") == "React"
    assert canonicalize_skill("python") == "Python"
    assert canonicalize_skill("py") == "Python"
    assert canonicalize_skill("javascript") == "JavaScript"
    assert canonicalize_skill("js") == "JavaScript"
    assert canonicalize_skill("C++") == "C++"
    assert canonicalize_skill("golang") == "Go"
    assert canonicalize_skill("unknown") == "Unknown"
    assert canonicalize_skill("") is None


def test_normalize_country():
    assert normalize_country("usa") == "US"
    assert normalize_country("united states") == "US"
    assert normalize_country("US") == "US"
    assert normalize_country("india") == "IN"
    assert normalize_country("IN") == "IN"
    assert normalize_country("invalid") is None
    assert normalize_country("") is None


def test_normalize_field_no_false_positive_on_substring_match():
    """
    REGRESSION TEST for the substring false-positive bug.

    The old FALLBACK_RULES matched any keyword found ANYWHERE in the
    field name via `kw in field_name.lower()`. "validated_by" contains
    "date" as a raw substring ("vali-DATE-d"), so it was incorrectly
    routed through normalize_date and silently destroyed (returned
    None) even though it's a plain string field, not a date.

    The fix matches whole underscore-delimited tokens instead.
    """
    assert normalize_field("validated_by", "recruiter_jane") == "recruiter_jane"
    assert normalize_field("candidate", "some_text") == "some_text"
    # Legitimate date fields must still normalize correctly:
    assert normalize_field("start_date", "Jan 2021") == "2021-01"
    assert normalize_field("updated_at", "2021-03-15") == "2021-03"


def test_normalize_field_end_year_is_strictly_yyyy():
    """Education.end_year must be YYYY, not YYYY-MM (see normalize_year)."""
    assert normalize_field("end_year", "2019") == "2019"
    assert normalize_field("end_year", "2019-06") == "2019"


def test_normalize_observations_in_place():
    observations = [
        Observation(field="full_name", value="  John Michael Doe  ", source="ats"),
        Observation(field="start_date", value="Jan 2020", source="ats"),
        Observation(field="end_date", value="2022-12", source="ats"),
        Observation(field="phones", value="(415) 555-0101", source="ats"),
        Observation(field="skills", value="react.js", source="ats"),
        Observation(field="location", value={"city": "San Francisco", "country": "usa"}, source="ats"),
    ]

    normalized = normalize_observations(observations)

    by_field = {obs.field: obs for obs in normalized}
    assert by_field["start_date"].value == "2020-01"
    assert by_field["end_date"].value == "2022-12"
    assert by_field["phones"].value == "+14155550101"
    assert by_field["skills"].value == "React"
    assert by_field["location"].value["country"] == "US"
