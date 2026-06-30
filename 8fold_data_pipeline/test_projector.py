"""
test_projector.py — Unit tests for the Load stage (Dynamic Schema Mapping).

Uses a directly-constructed CanonicalProfile instead of running the
full extract->merge pipeline against live APIs, so these tests are
deterministic and fast. Includes regression tests for two bugs found
during review:
  1. resolve_path() raised ValueError on "skills[].name" — the exact
     map-over-list syntax used in the assignment's own example config.
  2. include_confidence / include_provenance were conflated (provenance
     was only ever removed as a side effect of include_confidence, and
     neither toggle actually ADDED the field when set to true).
"""
from src.load.projector import project_output, resolve_path
from src.models.canonical import CanonicalProfile, Skill, Location


def _sample_profile() -> CanonicalProfile:
    return CanonicalProfile(
        candidate_id="CAND-1",
        full_name="John Michael Doe",
        emails=["john.doe@email.com"],
        phones=["+14155550101"],
        location=Location(city="San Francisco", region="CA", country="US"),
        headline="Lead Engineer",
        years_experience=6.3,
        skills=[
            Skill(name="JavaScript", confidence=0.6, sources=["ats"]),
            Skill(name="Python", confidence=0.9, sources=["github"]),
        ],
        overall_confidence=0.85,
    )


def test_resolve_path_indexed_access():
    data = {"emails": ["a@x.com", "b@x.com"]}
    assert resolve_path(data, "emails[0]") == "a@x.com"


def test_resolve_path_nested_indexed_access():
    data = {"skills": [{"name": "Python"}]}
    assert resolve_path(data, "skills[0].name") == "Python"


def test_resolve_path_map_over_list_syntax():
    """
    REGRESSION TEST: resolve_path previously raised ValueError on
    "skills[].name" (empty brackets = map over every list item) — the
    exact syntax the assignment's own example config uses:
        { "from": "skills[].name", "type": "string[]", "normalize": "canonical" }
    This must resolve to a list of every skill's name, not crash and
    not just return the first one.
    """
    data = {"skills": [{"name": "Python"}, {"name": "Go"}, {"name": "React"}]}
    result = resolve_path(data, "skills[].name")
    assert result == ["Python", "Go", "React"]


def test_resolve_path_map_over_empty_list():
    assert resolve_path({"skills": []}, "skills[].name") == []


def test_resolve_path_missing_key_returns_none():
    assert resolve_path({}, "skills[].name") is None


def test_project_basic_field_selection_and_rename():
    profile = _sample_profile()
    config = {
        "fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "primary_email", "from": "emails[0]", "type": "string"},
        ],
        "include_confidence": False,
        "include_provenance": False,
        "on_missing": "null",
    }
    output = project_output(profile, config)
    assert output["full_name"] == "John Michael Doe"
    assert output["primary_email"] == "john.doe@email.com"


def test_project_skills_map_syntax_end_to_end():
    """The assignment's own example config syntax must work through the full projector."""
    profile = _sample_profile()
    config = {
        "fields": [
            {"path": "all_skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"},
        ],
        "include_confidence": False,
        "include_provenance": False,
        "on_missing": "null",
    }
    output = project_output(profile, config)
    assert output["all_skills"] == ["JavaScript", "Python"]


def test_project_on_missing_omit():
    profile = _sample_profile()
    profile.phones = []
    config = {
        "fields": [{"path": "phone", "from": "phones[0]", "type": "string"}],
        "include_confidence": False,
        "include_provenance": False,
        "on_missing": "omit",
    }
    output = project_output(profile, config)
    assert "phone" not in output


def test_project_on_missing_error_raises():
    profile = _sample_profile()
    profile.full_name = None
    config = {
        "fields": [{"path": "full_name", "type": "string", "required": True}],
        "include_confidence": False,
        "include_provenance": False,
        "on_missing": "error",
    }
    try:
        project_output(profile, config)
        assert False, "Expected ValueError to be raised for a missing required field"
    except ValueError:
        pass


def test_include_confidence_and_provenance_are_independent():
    """
    REGRESSION TEST: include_confidence and include_provenance were
    previously conflated — provenance was only removed as a side
    effect of include_confidence=False. This confirms each toggle
    works independently of the other.
    """
    profile = _sample_profile()
    profile.provenance = []  # not the focus of this test; keep it simple

    config_conf_only = {
        "fields": [{"path": "full_name", "type": "string"}],
        "include_confidence": True,
        "include_provenance": False,
        "on_missing": "null",
    }
    output = project_output(profile, config_conf_only)
    assert "overall_confidence" in output
    assert "provenance" not in output

    config_prov_only = {
        "fields": [{"path": "full_name", "type": "string"}],
        "include_confidence": False,
        "include_provenance": True,
        "on_missing": "null",
    }
    output2 = project_output(profile, config_prov_only)
    assert "overall_confidence" not in output2
    assert "provenance" in output2


def test_include_confidence_true_actually_adds_the_field():
    """
    REGRESSION TEST: previously include_confidence=True was a silent
    no-op unless "overall_confidence" was also explicitly listed in
    config.fields — the toggle only ever REMOVED the field, never
    added it. This confirms the toggle is meaningful on its own.
    """
    profile = _sample_profile()
    config = {
        "fields": [{"path": "full_name", "type": "string"}],  # overall_confidence NOT listed
        "include_confidence": True,
        "include_provenance": False,
        "on_missing": "null",
    }
    output = project_output(profile, config)
    assert output["overall_confidence"] == profile.overall_confidence


def test_per_field_e164_normalization():
    profile = _sample_profile()
    profile.phones = ["+14155550101"]
    config = {
        "fields": [{"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"}],
        "include_confidence": False,
        "include_provenance": False,
        "on_missing": "null",
    }
    output = project_output(profile, config)
    assert output["phone"] == "+14155550101"
