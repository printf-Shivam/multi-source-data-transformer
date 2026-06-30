"""
Extract Stage 1: GitHub API Parser
Isolated ingestion. If the API is rate-limited or the user doesn't exist,
we catch the exception and return an empty list. The pipeline never crashes.
"""

import requests
import time
from typing import List, Optional, Dict, Any
from src.models.observation import Observation

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com/users/"


def parse_github(username: str) -> List[Observation]:
    """
    Fetches a GitHub user's public profile, repos, and languages.
    Returns Observations with source="github".
    Returns empty list if the user doesn't exist or API is rate-limited.
    """
    observations = []
    
    if not username or not username.strip():
        print("[GitHub Parser] No username provided. Returning empty.")
        return []
    
    username = username.strip()
    
    # --- Step 1: Fetch user profile ---
    user_data = _fetch_user_profile(username)
    if not user_data:
        return []  # Already logged the error inside
    
    # --- Step 2: Extract profile fields as Observations ---
    _extract_user_fields(user_data, observations)
    
    # --- Step 3: Fetch repositories (only if user exists) ---
    repos = _fetch_user_repos(username)
    if repos:
        _extract_repo_fields(repos, observations)
    
    print(f"[GitHub Parser] Extracted {len(observations)} observations for @{username}")
    return observations


# ------------------------------------------------------------
# Helper: Fetch User Profile
# ------------------------------------------------------------

def _fetch_user_profile(username: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the user's public profile from GitHub API.
    Handles:
        - HTTP 200: Success
        - HTTP 404: User not found
        - HTTP 403/429: Rate limited
        - Any other error: Returns None
    """
    url = GITHUB_API_BASE + username
    
    try:
        response = requests.get(url, timeout=10)
        
        # Success
        if response.status_code == 200:
            return response.json()
        
        # User not found
        if response.status_code == 404:
            print(f"[GitHub Parser] User '@{username}' not found. Returning empty.")
            return None
        
        # Rate limited
        if response.status_code in [403, 429]:
            print(f"[GitHub Parser] Rate limited for '@{username}'. Returning empty.")
            # Optional: Check when rate limit resets
            reset_time = response.headers.get("X-RateLimit-Reset")
            if reset_time:
                reset_seconds = int(reset_time) - int(time.time())
                print(f"[GitHub Parser] Rate limit resets in {reset_seconds} seconds.")
            return None
        
        # Any other HTTP error
        print(f"[GitHub Parser] HTTP {response.status_code} for '@{username}'. Returning empty.")
        return None
    
    except requests.exceptions.Timeout:
        print(f"[GitHub Parser] Timeout fetching '@{username}'. Returning empty.")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[GitHub Parser] Connection error for '@{username}'. Returning empty.")
        return None
    except Exception as e:
        print(f"[GitHub Parser] Unexpected error: {e}. Returning empty.")
        return None


# ------------------------------------------------------------
# Helper: Fetch User Repositories
# ------------------------------------------------------------

def _fetch_user_repos(username: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches the user's public repositories (up to 30 most recent).
    Returns None if the request fails.
    """
    url = GITHUB_API_BASE + username + "/repos"
    params = {
        "sort": "updated",
        "per_page": 30,  # Limit to 30 repos to avoid rate limits and over-fetching
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        
        # Don't spam logs for rate limits (already logged in profile fetch)
        if response.status_code in [403, 429]:
            return None
        
        print(f"[GitHub Parser] Failed to fetch repos: HTTP {response.status_code}")
        return None
    
    except Exception as e:
        print(f"[GitHub Parser] Error fetching repos: {e}")
        return None


# ------------------------------------------------------------
# Helper: Extract Fields from User Profile
# ------------------------------------------------------------

def _extract_user_fields(user_data: Dict[str, Any], observations: List[Observation]):
    """
    Extracts fields from the GitHub user profile and appends Observations.
    """
    
    def add_obs(field: str, value, method: str = "api_field"):
        if value is not None and value != "":
            observations.append(Observation(
                field=field,
                value=value,
                source="github",
                method=method,
                extraction_certainty=1.0
            ))
    
    # Core identity
    add_obs("github_username", user_data.get("login"))
    add_obs("github_id", user_data.get("id"))
    add_obs("full_name", user_data.get("name"))
    add_obs("headline", user_data.get("bio"))
    
    # Location
    add_obs("location", user_data.get("location"))
    
    # Contact (only if public)
    add_obs("emails", user_data.get("email"))  # Note: GitHub often returns null for privacy
    
    # URLs
    add_obs("github_url", user_data.get("html_url"))
    add_obs("github_avatar", user_data.get("avatar_url"))
    add_obs("blog_url", user_data.get("blog"))
    
    # Stats (these become skills later)
    add_obs("public_repos_count", user_data.get("public_repos"))
    add_obs("followers", user_data.get("followers"))
    add_obs("following", user_data.get("following"))
    
    # Dates
    add_obs("github_created_at", user_data.get("created_at"))
    add_obs("github_updated_at", user_data.get("updated_at"))


# ------------------------------------------------------------
# Helper: Extract Languages from Repositories
# ------------------------------------------------------------

def _extract_repo_fields(repos: List[Dict[str, Any]], observations: List[Observation]):
    """
    Extracts languages and repository names from the user's repos.
    Languages are tagged as "skills" since they represent technical knowledge.
    """
    
    def add_obs(field: str, value, method: str = "repo_language"):
        if value is not None and value != "":
            observations.append(Observation(
                field=field,
                value=value,
                source="github",
                method=method,
                extraction_certainty=1.0
            ))
    
    # Track unique languages to avoid duplicates
    seen_languages = set()
    repo_count = 0
    
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        
        repo_count += 1
        
        # Add each repository name as an experience item
        repo_name = repo.get("name")
        repo_full_name = repo.get("full_name")
        repo_description = repo.get("description")
        repo_language = repo.get("language")  # Primary language
        
        # Track languages as "skills" (GitHub gets high weight for technical skills)
        if repo_language and repo_language not in seen_languages:
            seen_languages.add(repo_language)
            add_obs("skills", repo_language, method="repo_language")
        
        # Also track repos as "experience" or "projects" for provenance
        # We'll add them as a structured dict
        if repo_name:
            repo_info = {
                "name": repo_name,
                "full_name": repo_full_name,
                "description": repo_description,
                "language": repo_language,
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "url": repo.get("html_url"),
            }
            observations.append(Observation(
                field="github_repos",
                value=repo_info,
                source="github",
                method="repo_list",
                extraction_certainty=1.0
            ))
    
    # Add total repo count for reference
    if repo_count > 0:
        observations.append(Observation(
            field="total_repos_fetched",
            value=repo_count,
            source="github",
            method="repo_count",
            extraction_certainty=1.0
        ))