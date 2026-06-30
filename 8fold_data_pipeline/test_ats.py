"""
test_ats.py — Unit tests for the ATS Extract stage (Isolated Ingestion).

REGRESSION NOTE: the original version of this file was bare
module-level script code with no test function and no assertions —
pytest never collected anything from it, so it silently contributed
zero coverage despite sitting in the test suite.
"""
from src.extract.ats_parser import parse_ats


def test_parse_ats_extracts_observations_from_sample_file():
    observations = parse_ats("data/sample_ats.json")
    assert len(observations) > 0

    fields_present = {obs.field for obs in observations}
    assert "full_name" in fields_present
    assert "emails" in fields_present


def test_parse_ats_handles_missing_file_gracefully():
    """A missing file must not crash extraction — it should degrade to an empty list."""
    observations = parse_ats("data/this_file_does_not_exist.json")
    assert observations == []


def test_parse_ats_full_name_value_is_correct():
    observations = parse_ats("data/sample_ats.json")
    name_obs = next((o for o in observations if o.field == "full_name"), None)
    assert name_obs is not None
    # Raw extraction shouldn't normalize yet (that's Transform 1's job) —
    # but it should at least pull the correct raw value out of the nested JSON.
    assert "John" in name_obs.value and "Doe" in name_obs.value
