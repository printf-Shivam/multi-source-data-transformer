"""
Transform 2: Entity Linking
Verifies if the GitHub profile can be explicitly tied to the ATS profile.
If not, the GitHub data is dropped entirely to prevent false-positive merges.

Rule from design doc:
    "If the GitHub API cannot be explicitly tied to the ATS profile 
    (via a URL or exact email match), it is dropped. Missing data is 
    better than wrong data."
"""

import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from src.models.observation import Observation


def link_entities(
    ats_observations: List[Observation],
    github_observations: List[Observation]
) -> List[Observation]:
    """
    Determines if the GitHub profile belongs to the same person as the ATS profile.
    
    Returns:
        - If linked: The original github_observations list (preserved)
        - If NOT linked: An empty list (GitHub data is dropped)
    
    Three matching strategies (any one is sufficient):
        1. GitHub URL in ATS links matches the GitHub username
        2. Exact email match between ATS and GitHub
        3. GitHub username from the API matches the one in ATS URL
    """
    # If either side is empty, we can't link
    if not ats_observations or not github_observations:
        print("[Entity Linker] Missing one or both sources. Cannot link.")
        return []
    
    # --- Step 1: Extract identifiers from ATS ---
    ats_github_url = _find_value(ats_observations, "github_url")
    ats_emails = _find_values(ats_observations, "emails")
    ats_full_name = _find_value(ats_observations, "full_name")
    
    # --- Step 2: Extract identifiers from GitHub ---
    github_username = _find_value(github_observations, "github_username")
    github_emails = _find_values(github_observations, "emails")
    github_full_name = _find_value(github_observations, "full_name")
    github_url = _find_value(github_observations, "github_url")
    
    # --- Step 3: Attempt matching ---
    matches = []
    
    # Strategy 1: GitHub URL in ATS matches the GitHub username
    if ats_github_url and github_username:
        # Extract username from the URL (e.g., https://github.com/johndoe99 -> johndoe99)
        extracted_username = _extract_github_username_from_url(ats_github_url)
        if extracted_username and extracted_username.lower() == github_username.lower():
            matches.append("github_url_matches_username")
            print(f"[Entity Linker] ✓ Match: ATS GitHub URL contains username '@{github_username}'")
    
    # Strategy 2: Exact email match
    if ats_emails and github_emails:
        ats_email_set = set(email.lower() for email in ats_emails if email)
        github_email_set = set(email.lower() for email in github_emails if email)
        common_emails = ats_email_set & github_email_set
        if common_emails:
            matches.append("email_match")
            print(f"[Entity Linker] ✓ Match: Shared email(s) {common_emails}")
    
    # Strategy 3: GitHub username extracted from ATS URL matches GitHub username
    # (This is essentially the same as Strategy 1, but with a different source)
    if ats_github_url and github_username:
        extracted_username = _extract_github_username_from_url(ats_github_url)
        if extracted_username and extracted_username.lower() == github_username.lower():
            # Already counted in Strategy 1, but we check anyway
            pass
    
    # --- Step 4: Decision ---
    if matches:
        print(f"[Entity Linker]  GitHub data linked to ATS profile via: {', '.join(matches)}")
        return github_observations
    else:
        print("[Entity Linker]  No link found. Dropping GitHub data (missing > wrong).")
        print(f"[Entity Linker]    ATS GitHub URL: {ats_github_url}")
        print(f"[Entity Linker]    GitHub username: {github_username}")
        print(f"[Entity Linker]    ATS emails: {ats_emails}")
        print(f"[Entity Linker]    GitHub emails: {github_emails}")
        return []


# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def _find_value(observations: List[Observation], field_name: str) -> Optional[Any]:
    """
    Finds the first non-None value for a given field in the observations list.
    """
    for obs in observations:
        if obs.field == field_name and obs.value is not None:
            # If it's a list, return the first non-empty item
            if isinstance(obs.value, list):
                for item in obs.value:
                    if item:
                        return item
                continue
            return obs.value
    return None


def _find_values(observations: List[Observation], field_name: str) -> List[Any]:
    """
    Finds all non-None values for a given field in the observations list.
    Useful for collecting all emails (primary + secondary).
    """
    values = []
    for obs in observations:
        if obs.field == field_name and obs.value is not None:
            if isinstance(obs.value, list):
                values.extend([v for v in obs.value if v])
            else:
                values.append(obs.value)
    return values


def _extract_github_username_from_url(url: str) -> Optional[str]:
    """
    Extracts the GitHub username from a URL.
    Handles:
        - https://github.com/username
        - https://github.com/username/
        - github.com/username
        - https://www.github.com/username
    """
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    
    # Parse the URL
    try:
        parsed = urlparse(url)
        # If it doesn't have a scheme, add one so urlparse works
        if not parsed.scheme:
            parsed = urlparse("https://" + url)
        
        path = parsed.path
        # Remove leading/trailing slashes and split
        path_parts = [p for p in path.split("/") if p]
        
        # Check if the DOMAIN is github.com (not just "github" appearing
        # anywhere in the URL — that previously caused false positives
        # like "https://gitlab.com/notgithub" being misread as a GitHub
        # URL just because the path segment contains the substring
        # "github").
        if "github.com" in parsed.netloc.lower():
            if path_parts:
                # First part of the path is the username
                return path_parts[0]
        
        # Fallback: try regex
        match = re.search(r"github\.com[/:]([^/\s?]+)", url)
        if match:
            return match.group(1)
        
        return None
    except Exception:
        return None


def extract_github_username_from_observations(observations: List[Observation]) -> Optional[str]:
    """
    Convenience function: extracts the GitHub username from observations
    either from the 'github_username' field or from the 'github_url' field.
    """
    # Try direct field first
    username = _find_value(observations, "github_username")
    if username:
        return username
    
    # Try extracting from URL
    github_url = _find_value(observations, "github_url")
    if github_url:
        return _extract_github_username_from_url(github_url)
    
    return None


def has_ats_github_link(ats_observations: List[Observation]) -> bool:
    """
    Checks if the ATS observations contain a GitHub URL.
    Used as a quick pre-check before making API calls.
    """
    github_url = _find_value(ats_observations, "github_url")
    return github_url is not None and bool(github_url.strip())