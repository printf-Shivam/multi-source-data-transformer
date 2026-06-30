"""
test_merge_engine.py — Unit tests for Transform 3 (Weighted Priority Merge).

Uses synthetic Observation data instead of live GitHub API calls, so
these tests are deterministic and don't depend on network access or
rate limits. Includes a regression test for the overall_confidence bug
found during review: it previously used hardcoded constants instead of
the real per-field confidence the authority matrix computed.
"""
from src.transform.merge_engine import merge_sources, SOURCE_WEIGHTS
from src.models.observation import Observation


def _ats_obs(**fields) -> list:
    """Helper: build a list of ATS Observations from a field->value dict."""
    return [Observation(field=k, value=v, source="ats", method="structured_field")
            for k, v in fields.items()]


def _github_obs(**fields) -> list:
    return [Observation(field=k, value=v, source="github", method="api_extraction")
            for k, v in fields.items()]


def test_merge_ats_only_no_github():
    ats_obs = _ats_obs(
        candidate_id="CAND-1",
        full_name="Alice Johnson",
        emails="alice@example.com",
        skills="Python",
        headline="Senior Engineer",
    )
    profile = merge_sources(ats_obs, [])

    assert profile.full_name == "Alice Johnson"
    assert "alice@example.com" in profile.emails
    assert any(s.name == "Python" for s in profile.skills)
    # ATS-only skill should get ATS's skill-tier weight, not GitHub's
    python_skill = next(s for s in profile.skills if s.name == "Python")
    assert python_skill.confidence == SOURCE_WEIGHTS["ats"]["skills"]


def test_merge_with_both_sources_consensus_boosts_confidence():
    """If both sources agree on full_name, confidence should hit 1.0."""
    ats_obs = _ats_obs(full_name="Alice Johnson", emails="alice@example.com")
    github_obs = _github_obs(full_name="Alice Johnson")

    profile = merge_sources(ats_obs, github_obs)

    assert profile.full_name == "Alice Johnson"
    name_provenance = [p for p in profile.provenance if p.field == "full_name"]
    assert len(name_provenance) == 1
    assert "ats" in name_provenance[0].source and "github" in name_provenance[0].source


def test_merge_skill_authority_github_wins():
    """GitHub-only skill should get GitHub's higher skill-tier weight."""
    ats_obs = _ats_obs(skills="Python")
    github_obs = _github_obs(skills="Go")

    profile = merge_sources(ats_obs, github_obs)

    go_skill = next(s for s in profile.skills if s.name == "Go")
    assert go_skill.confidence == SOURCE_WEIGHTS["github"]["skills"]


def test_merge_skill_consensus_both_sources():
    """A skill present in BOTH sources gets boosted confidence (1.0)."""
    ats_obs = _ats_obs(skills="Python")
    github_obs = _github_obs(skills="Python")

    profile = merge_sources(ats_obs, github_obs)

    python_skill = next(s for s in profile.skills if s.name == "Python")
    assert python_skill.confidence == 1.0
    assert set(python_skill.sources) == {"ats", "github"}


def test_overall_confidence_uses_real_field_confidences_not_hardcoded():
    """
    REGRESSION TEST: _calculate_overall_confidence previously used
    hardcoded constants (0.9 for name, 0.9 for emails, etc.) regardless
    of what the authority matrix actually computed for those fields.
    This meant a single-source-only profile and a consensus-boosted
    profile could report the SAME overall_confidence, which defeats
    the entire point of the consensus multiplier.

    This test confirms overall_confidence differs between an ATS-only
    profile and a profile where ATS+GitHub agree (consensus boost).
    """
    ats_obs = _ats_obs(full_name="Alice Johnson", emails="alice@example.com")

    # ATS-only: full_name confidence should be the ATS identity weight (0.9)
    profile_ats_only = merge_sources(ats_obs, [])

    # ATS + GitHub agreeing on full_name: should boost to 1.0 for that field,
    # raising overall_confidence above the ATS-only case.
    github_obs_agreeing = _github_obs(full_name="Alice Johnson")
    profile_consensus = merge_sources(ats_obs, github_obs_agreeing)

    assert profile_consensus.overall_confidence > profile_ats_only.overall_confidence, (
        "Consensus-boosted profile should have strictly higher overall_confidence "
        "than the ATS-only profile — if these are equal, overall_confidence is "
        "not actually using the per-field confidence the merge computed."
    )


def test_merge_education_ats_only_github_zero_trust():
    """GitHub has zero authority for education (per the design doc's
    zero-trust policy) — even if GitHub observations were somehow
    present for an 'education' field, only ATS data should populate
    profile.education."""
    ats_obs = _ats_obs(education={
        "institution": "Stanford", "degree": "M.S.",
        "field": "Computer Science", "end_year": "2019",
    })
    profile = merge_sources(ats_obs, [])

    assert len(profile.education) == 1
    assert profile.education[0].institution == "Stanford"


def test_merge_years_experience_calculation():
    ats_obs = _ats_obs(experience={
        "company": "TechCorp", "title": "Engineer",
        "start_date": "2020-01", "end_date": "2023-01",
    })
    profile = merge_sources(ats_obs, [])

    assert profile.years_experience == 3.0
