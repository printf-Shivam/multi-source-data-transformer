"""
Transform 1: Lexical Normalization
Forces raw text into strict, standardized types.
Optimized with O(1) field-to-function mapping for scalability.
"""

import re
from typing import Optional, Any, Dict, Callable, List
from datetime import datetime
import phonenumbers

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None
    print("Warning: python-dateutil not installed. Date parsing will be limited.")


# ------------------------------------------------------------
# 1. CANONICAL LOOKUP DICTIONARIES
# ------------------------------------------------------------

SKILL_CANONICAL_MAP = {
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "python": "Python",
    "py": "Python",
    "python3": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "java": "Java",
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "git": "Git",
    "ci/cd": "CI/CD",
    "c++": "C++",
    "c#": "C#",
    "ruby": "Ruby",
    "rails": "Ruby on Rails",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "php": "PHP",
    "html": "HTML",
    "css": "CSS",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "node": "Node.js",
    "nodejs": "Node.js",
    "express": "Express.js",
    "django": "Django",
    "flask": "Flask",
}

COUNTRY_ISO_MAP = {
    "united states": "US",
    "usa": "US",
    "us": "US",
    "america": "US",
    "india": "IN",
    "united kingdom": "GB",
    "uk": "GB",
    "england": "GB",
    "germany": "DE",
    "france": "FR",
    "canada": "CA",
    "australia": "AU",
    "singapore": "SG",
    "japan": "JP",
    "china": "CN",
    "brazil": "BR",
    "mexico": "MX",
    "spain": "ES",
    "italy": "IT",
    "netherlands": "NL",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "israel": "IL",
    "new zealand": "NZ",
    "south africa": "ZA",
}


# ------------------------------------------------------------
# 2. NORMALIZATION FUNCTIONS
# ------------------------------------------------------------

def normalize_date(value: Optional[str]) -> Optional[str]:
    """Convert messy date to YYYY-MM."""
    if not value or not str(value).strip():
        return None
    
    value = str(value).strip()
    
    if value.lower() == "present":
        return "Present"
    
    if re.match(r"^\d{4}-\d{2}$", value):
        return value
    
    if re.match(r"^\d{4}$", value):
        return f"{value}"
    
    if date_parser and any(c.isdigit() for c in value):
        try:
            dt = date_parser.parse(value, fuzzy=True)
            return dt.strftime("%Y-%m")
        except (ValueError, TypeError, OverflowError):
            pass
    
    match = re.search(r"(\d{4})[-/](\d{1,2})", value)
    if match:
        year, month = match.groups()
        return f"{year}-{int(month):02d}"
    
    return None


def normalize_phone(value: Optional[str], default_region: str = "US") -> Optional[str]:
    """
    Parse and validate a phone number, returning true E.164 format.
    Returns None if the number cannot be validated as a real, dialable
    number — never returns a stripped-digits guess with a '+' prepended.
    """
    if not value or not str(value).strip():
        return None

    try:
        parsed = phonenumbers.parse(str(value).strip(), default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass

    return None


def canonicalize_skill(value: Optional[str]) -> Optional[str]:
    """O(1) dict lookup, fallback to title case."""
    if not value or not str(value).strip():
        return None
    
    key = str(value).strip().lower()
    return SKILL_CANONICAL_MAP.get(key, key.title())


def normalize_country(value: Optional[str]) -> Optional[str]:
    """O(1) dict lookup for ISO code."""
    if not value or not str(value).strip():
        return None
    
    key = str(value).strip().lower()
    
    if key in COUNTRY_ISO_MAP:
        return COUNTRY_ISO_MAP[key]
    
    if re.match(r"^[A-Za-z]{2}$", value):
        return value.upper()
    
    return None


def normalize_string(value: Optional[str]) -> Optional[str]:
    """Simple trim."""
    if not value or not str(value).strip():
        return None
    return str(value).strip()


# ------------------------------------------------------------
# 3. OPTIMIZED DISPATCHER
# ------------------------------------------------------------

# ------------------------------------------------------------
# 3. FIELD DISPATCHER
# ------------------------------------------------------------
# Note: end_year uses normalize_year (not normalize_date) because
# Education.end_year is strictly YYYY, never YYYY-MM.

def normalize_field(field_name: str, value: Any) -> Any:
    """Routes a raw value to the appropriate normalizer."""
    if value is None:
        return None
    
    if isinstance(value, list):
        return [normalize_field(field_name, item) for item in value if item is not None]
    
    if isinstance(value, dict):
        normalized_dict = {}
        for k, v in value.items():
            normalized_dict[k] = normalize_field(k, v)
        return normalized_dict
    
    if field_name in FIELD_NORMALIZER_MAP:
        return FIELD_NORMALIZER_MAP[field_name](value)
    
    str_value = str(value)

    # Match against whole underscore-delimited tokens in the field name,
    # NOT raw substring containment. Raw "in" matching previously caused
    # false positives — e.g. "validated_by" contains "date" as a substring
    # ("vali-DATE-d"), which incorrectly routed plain strings through
    # normalize_date and silently destroyed them (returned None).
    field_tokens = set(field_name.lower().split("_"))
    for keywords, normalizer in FALLBACK_RULES:
        if field_tokens & set(keywords):
            return normalizer(str_value)
    
    return str_value.strip() if str_value else None


def normalize_observations(observations: List[Any]) -> List[Any]:
    """Normalizes all Observation values in-place."""
    if not observations:
        return observations
    
    for obs in observations:
        obs.value = normalize_field(obs.field, obs.value)
    
    return observations


def normalize_year(value: Optional[str]) -> Optional[str]:
    """
    Extracts and returns only a 4-digit year.
    Used exclusively for Education.end_year (YYYY).
    If input is '2019-01', returns '2019'.
    If input is '2019', returns '2019'.
    """
    if not value or not str(value).strip():
        return None

    value = str(value).strip()

    # Already a clean 4-digit year
    if re.match(r"^\d{4}$", value):
        return value

    # If it's YYYY-MM (e.g., from normalizer), strip the month
    if re.match(r"^\d{4}-\d{2}$", value):
        return value[:4]

    # Try to extract any 4-digit number from the string
    match = re.search(r"\b(\d{4})\b", value)
    if match:
        return match.group(1)

    return None

FIELD_NORMALIZER_MAP: Dict[str, Callable] = {
    # Dates (strictly YYYY-MM)
    "start_date": normalize_date,
    "end_date": normalize_date,
    "created_at": normalize_date,
    "updated_at": normalize_date,
    "github_created_at": normalize_date,
    "github_updated_at": normalize_date,

    # Years (strictly YYYY) - Education only
    "end_year": normalize_year,

    # Others
    "candidate_id": normalize_string,
    "phone": normalize_phone,
    "phones": normalize_phone,
    "skills": canonicalize_skill,
    "skill": canonicalize_skill,
    "country": normalize_country,
}

# Fallback keywords are intentionally specific (whole tokens, matched
# after splitting field_name on "_") to avoid false positives like
# "updated_by" (a person) being mistaken for "updated_at" (a date).
FALLBACK_RULES = [
    (["date", "start", "end", "year"], normalize_date),
    (["phone"], normalize_phone),
    (["skill", "language"], canonicalize_skill),
    (["country"], normalize_country),
]