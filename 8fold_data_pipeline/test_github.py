"""
test_github.py — Unit tests for the GitHub Extract stage.

These tests hit the live, unauthenticated GitHub REST API, so they're
inherently rate-limit-dependent. Rather than reporting a misleading
pass/fail when the API is unreachable, they explicitly skip (pytest.skip)
so CI output honestly reflects "could not verify" instead of looking
like a pass.

REGRESSION NOTE: the original version of this file had a `main()`
function pytest never discovers (no `test_` prefix) and no assertions
at all — it ran zero real checks despite appearing in the test suite.
"""
import pytest
from src.extract.github_parser import parse_github


def test_parse_github_known_public_user():
    username = "octocat"  # GitHub's own long-standing public test account
    try:
        observations = parse_github(username)
    except Exception as e:
        pytest.skip(f"GitHub API unreachable or rate-limited: {e}")

    if not observations:
        pytest.skip("GitHub API returned no data — likely rate-limited (no auth token in CI).")

    fields_present = {obs.field for obs in observations}
    assert "github_username" in fields_present or "full_name" in fields_present


def test_parse_github_nonexistent_user_degrades_gracefully():
    """A 404 (user doesn't exist) must not crash extraction — returns empty/degraded, not raise."""
    try:
        observations = parse_github("this_user_should_not_exist_zzz_99999")
    except Exception as e:
        pytest.fail(f"parse_github() raised on a 404 instead of degrading gracefully: {e}")

    assert observations == [] or all(o.value is None for o in observations)
