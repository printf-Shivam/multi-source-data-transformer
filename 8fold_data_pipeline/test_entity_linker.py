from src.transform.entity_linker import (
    link_entities,
    _extract_github_username_from_url,
    has_ats_github_link
)
from src.models.observation import Observation

def test_extract_username():
    print("Testing _extract_github_username_from_url:")
    test_cases = [
        ("https://github.com/johndoe99", "johndoe99"),
        ("https://github.com/johndoe99/", "johndoe99"),
        ("github.com/johndoe99", "johndoe99"),
        ("https://www.github.com/johndoe99", "johndoe99"),
        ("https://github.com/octocat/Hello-World", "octocat"),
        ("https://gitlab.com/notgithub", None),
        ("", None),
        (None, None),
    ]
    for url, expected in test_cases:
        result = _extract_github_username_from_url(url)
        assert result == expected, f"'{url}' -> '{result}' (expected: '{expected}')"


def test_link_entities_success():
    print("\n--- Test: Successful Link (Email Match) ---")
    
    ats_obs = [
        Observation(field="github_url", value="https://github.com/johndoe99", source="ats"),
        Observation(field="emails", value="john.doe@email.com", source="ats"),
        Observation(field="full_name", value="John Doe", source="ats"),
    ]
    
    github_obs = [
        Observation(field="github_username", value="johndoe99", source="github"),
        Observation(field="emails", value="john.doe@email.com", source="github"),  # Same email!
        Observation(field="full_name", value="John Doe", source="github"),
    ]
    
    result = link_entities(ats_obs, github_obs)
    print(f"Result: {len(result)} observations returned (should be 3)")
    assert len(result) == 3, "Should keep GitHub data"


def test_link_entities_failure():
    print("\n--- Test: Failed Link (No Match) ---")
    
    ats_obs = [
        Observation(field="github_url", value="https://github.com/johndoe99", source="ats"),
        Observation(field="emails", value="john.doe@email.com", source="ats"),
        Observation(field="full_name", value="John Doe", source="ats"),
    ]
    
    github_obs = [
        Observation(field="github_username", value="differentuser", source="github"),
        Observation(field="emails", value="other@email.com", source="github"),  # Different email!
        Observation(field="full_name", value="Jane Smith", source="github"),
    ]
    
    result = link_entities(ats_obs, github_obs)
    print(f"Result: {len(result)} observations returned (should be 0)")
    assert len(result) == 0, "Should drop GitHub data"


def test_link_entities_url_match():
    print("\n--- Test: Successful Link (URL Match) ---")
    
    ats_obs = [
        Observation(field="github_url", value="https://github.com/octocat", source="ats"),
        Observation(field="emails", value="john@email.com", source="ats"),
    ]
    
    github_obs = [
        Observation(field="github_username", value="octocat", source="github"),
        Observation(field="emails", value="public@email.com", source="github"),
    ]
    
    result = link_entities(ats_obs, github_obs)
    print(f"Result: {len(result)} observations returned (should be 2)")
    assert len(result) == 2, "Should keep GitHub data"


def test_has_ats_github_link():
    print("\n--- Test: has_ats_github_link ---")
    
    ats_with_url = [
        Observation(field="github_url", value="https://github.com/octocat", source="ats"),
    ]
    ats_without_url = [
        Observation(field="full_name", value="John Doe", source="ats"),
    ]
    
    assert has_ats_github_link(ats_with_url) is True
    assert has_ats_github_link(ats_without_url) is False


def test_link_entities_no_ats_data_drops_github():
    """
    REGRESSION TEST for the orphaned-entity contradiction found in main.py.

    main.py previously had a "CRITICAL FIX" that kept GitHub data
    unconditionally when no ATS record was present, bypassing
    link_entities() entirely. This test confirms link_entities()
    itself has always correctly refused to link (and therefore drops
    GitHub data) when there's no ATS data to verify identity against —
    the fix in main.py was to stop bypassing this function, not to
    change this function's own behavior.
    """
    github_obs = [
        Observation(field="full_name", value="Some Person", source="github"),
        Observation(field="github_username", value="someuser", source="github"),
    ]
    result = link_entities([], github_obs)
    assert result == [], "GitHub data must be dropped when there's no ATS record to verify against"


if __name__ == "__main__":
    test_extract_username()
    test_link_entities_success()
    test_link_entities_failure()
    test_link_entities_url_match()
    test_has_ats_github_link()
    print("\n✅ All tests completed!")