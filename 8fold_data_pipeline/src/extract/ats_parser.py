"""
ATS JSON Parser – Extract Stage (Isolated Ingestion)

This module reads an ATS JSON export and transforms it into a list of Observation
objects. It supports two extraction modes:

1. Schema Mapping Mode (recommended): Uses a configuration dictionary that maps
   canonical field names to one or more possible JSON paths (dot‑notation supported).
   This makes the parser source‑agnostic and extensible to any ATS system.

2. Hardcoded Fallback Mode: Uses the original hardcoded logic, which works with the
   sample data but is rigid. This mode is used when no mapping is provided.

The parser is fault‑tolerant: missing files, malformed JSON, or empty data never
cause a crash – they return an empty list and log a warning.
"""

import json
import os
from typing import List, Optional, Dict, Any

from src.models.observation import Observation


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def parse_ats(file_path: str, schema_mapping: Optional[Dict] = None) -> List[Observation]:
    """
    Extract observations from an ATS JSON file.

    Args:
        file_path: Path to the ATS JSON file.
        schema_mapping: Optional dictionary that maps canonical field names
                        to a list of possible source paths (dot‑notation allowed).
                        Example: {"full_name": ["name", "candidate_name", "personal_info.name"]}
                        If not provided, falls back to hardcoded extraction.

    Returns:
        List of Observation objects. Returns an empty list on any error (missing file,
        malformed JSON, or no data) – the pipeline never crashes.
    """
    # 1. Guard: check file existence
    if not os.path.exists(file_path):
        print(f"[ATS Parser] File not found: {file_path}. Returning empty.")
        return []

    # 2. Read and parse JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ATS Parser] JSON decode error: {e}. Returning empty.")
        return []
    except Exception as e:
        print(f"[ATS Parser] Unexpected error reading file: {e}. Returning empty.")
        return []

    # 3. Validate data structure
    if not raw_data or not isinstance(raw_data, dict):
        print("[ATS Parser] Invalid JSON structure (not a dict). Returning empty.")
        return []

    # 4. Extract using either mapping or hardcoded logic
    if schema_mapping:
        # Extract only the 'ats' part of the mapping (the rest might be used for other sources)
        ats_mapping = schema_mapping.get("ats", {})
        observations = _extract_with_mapping(raw_data, ats_mapping)
    else:
        observations = _extract_with_hardcoded(raw_data)

    return observations


def load_schema_mapping(file_path: str) -> Dict:
    """
    Helper: load a schema mapping JSON file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# -----------------------------------------------------------------------------
# Extraction Strategies
# -----------------------------------------------------------------------------

def _extract_with_mapping(data: Dict, mapping: Dict) -> List[Observation]:
    """
    Extract fields using a configurable mapping.

    The mapping is a dict: { canonical_field: [possible_paths] }
    where 'possible_paths' are strings with dot notation (e.g., 'personal_info.name').
    The first path that yields a non‑None value is used.

    Special handling for list fields (skills, experience, education): we wrap each
    item separately so that the merge engine can process them individually.
    """
    observations = []

    for canonical_field, possible_paths in mapping.items():
        value = None

        # Try each path until we find a value
        for path in possible_paths:
            extracted = _extract_nested_value(data, path)
            if extracted is not None and extracted != "":
                value = extracted
                break

        # If no value was found, skip this field
        if value is None:
            continue

        # For list‑type canonical fields, we wrap each list item as a separate Observation.
        # This is required because the merge engine expects individual items (e.g., each skill,
        # each experience entry) to be processed and merged independently.
        if canonical_field in {"skills", "experience", "education"}:
            if isinstance(value, list):
                for item in value:
                    observations.append(Observation(
                        field=canonical_field,
                        value=item,
                        source="ats",
                        method="schema_mapping",
                        extraction_certainty=1.0
                    ))
            else:
                # If the mapping returns a single item but we expected a list, still wrap it.
                observations.append(Observation(
                    field=canonical_field,
                    value=value,
                    source="ats",
                    method="schema_mapping",
                    extraction_certainty=1.0
                ))
        else:
            # Scalar fields: one Observation per field.
            observations.append(Observation(
                field=canonical_field,
                value=value,
                source="ats",
                method="schema_mapping",
                extraction_certainty=1.0
            ))

    return observations


def _extract_with_hardcoded(data: Dict) -> List[Observation]:
    """
    Original hardcoded extraction logic – used as a fallback when no mapping is provided.

    This implementation is tied to the structure of the sample ATS data provided in the
    assignment. It serves as a reliable fallback and demonstrates the manual approach.
    """
    observations = []

    # Helper: add a single Observation if value is not None/empty
    def add_observation(field: str, value, method: str = "direct_field"):
        if value is None or value == "":
            return

        # For list of primitives (e.g., skills), add one Observation per item
        if isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value):
            for item in value:
                observations.append(Observation(
                    field=field,
                    value=item,
                    source="ats",
                    method=method,
                    extraction_certainty=1.0
                ))
        else:
            observations.append(Observation(
                field=field,
                value=value,
                source="ats",
                method=method,
                extraction_certainty=1.0
            ))

    # ---- Extract fields ----

    # Candidate ID
    add_observation("candidate_id", data.get("candidate_id"))

    # Personal info (nested)
    personal = data.get("personal_info", {})
    add_observation("full_name", personal.get("name"))
    add_observation("emails", personal.get("email"))
    add_observation("emails", personal.get("secondary_email"))   # may be a secondary email
    add_observation("phones", personal.get("phone"))

    # Location (nested dict)
    loc = personal.get("location", {})
    if loc:
        add_observation("location", loc)

    # Professional summary (nested)
    prof = data.get("professional_summary", {})
    add_observation("headline", prof.get("headline"))
    add_observation("current_company", prof.get("current_company"))  # not in output but useful
    add_observation("current_title", prof.get("current_title"))

    # Links (nested)
    links = data.get("links", {})
    add_observation("github_url", links.get("github"))
    add_observation("linkedin_url", links.get("linkedin"))

    # Work experience (array of objects)
    experiences = data.get("work_experience", [])
    if isinstance(experiences, list):
        for exp in experiences:
            if isinstance(exp, dict):
                add_observation("experience", exp, method="array_item")

    # Education (array of objects)
    educations = data.get("education", [])
    if isinstance(educations, list):
        for edu in educations:
            if isinstance(edu, dict):
                add_observation("education", edu, method="array_item")

    # Skills (array of strings)
    skills = data.get("skills", [])
    if isinstance(skills, list):
        for skill in skills:
            add_observation("skills", skill, method="array_item")

    return observations


# -----------------------------------------------------------------------------
# Utility: Nested Value Extraction
# -----------------------------------------------------------------------------

def _extract_nested_value(data: Any, path: str) -> Any:
    """
    Extract a value from a nested JSON structure using dot notation.

    Examples:
        path = "personal_info.name"       -> data["personal_info"]["name"]
        path = "links.github"             -> data["links"]["github"]
        path = "location.country"         -> data["location"]["country"]

    If any intermediate key is missing or the structure is not a dict,
    returns None gracefully.
    """
    if not path or data is None:
        return None

    # Simple path (no dots)
    if '.' not in path:
        if isinstance(data, dict):
            return data.get(path)
        return None

    # Walk through the keys
    keys = path.split('.')
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return None
        else:
            # If we hit a non‑dict before consuming all keys, the path is invalid
            return None

    return current