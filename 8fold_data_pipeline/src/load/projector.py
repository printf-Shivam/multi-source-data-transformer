"""
Load Stage: Dynamic Schema Mapping (Projection)
Takes the internal CanonicalProfile and a runtime config, applies field mappings,
renames, handles missing values, and validates the output schema.
"""

import re
from typing import Any, Dict, List, Optional, Union
from copy import deepcopy

from src.models.canonical import CanonicalProfile
from src.models.config_model import RuntimeConfig
from src.transform.normalizer import normalize_phone
from src.transform.normalizer import canonicalize_skill


# ------------------------------------------------------------
# Path Resolver (Handles "emails[0]", "skills[0].name", etc.)
# ------------------------------------------------------------

def resolve_path(obj: Any, path: str) -> Any:
    """
    Resolves a path like "emails[0]", "skills[0].name", or
    "skills[].name" from a dict/list.

    "[]" (an empty bracket) means "map the rest of the path over every
    item in this list" — e.g. "skills[].name" returns a list of every
    skill's name, not just the first one. This is the syntax the
    assignment's own example config uses, so it must be supported
    rather than raising.

    Returns the resolved value (or list of values, for "[]"), or None
    if any part of the path doesn't resolve.
    """
    if not path or obj is None:
        return None
    
    # Parse the path into tokens
    # e.g., "skills[0].name" -> ["skills", 0, "name"]
    # e.g., "skills[].name"  -> ["skills", MAP, "name"]
    MAP = object()  # sentinel: "map over every item in this list"
    tokens = []
    current = ""
    i = 0
    
    while i < len(path):
        char = path[i]
        if char == '[':
            # Store the current token (if any) before the bracket
            if current:
                tokens.append(current)
                current = ""
            # Find the closing bracket
            j = i + 1
            while j < len(path) and path[j] != ']':
                j += 1
            if j < len(path):
                index_str = path[i+1:j]
                if index_str == "":
                    tokens.append(MAP)
                elif index_str.isdigit():
                    tokens.append(int(index_str))
                else:
                    raise ValueError(f"Invalid index in path: {path}")
                i = j + 1
                continue
            else:
                raise ValueError(f"Unclosed bracket in path: {path}")
        elif char == '.':
            # Store the current token and move on
            if current:
                tokens.append(current)
                current = ""
            i += 1
            continue
        else:
            current += char
            i += 1
    
    # Add the last token
    if current:
        tokens.append(current)

    return _walk_tokens(obj, tokens, MAP)


def _walk_tokens(current_obj: Any, tokens: list, MAP: object) -> Any:
    """Traverse an object by a pre-parsed token list, handling MAP (map-over-list)."""
    for idx, token in enumerate(tokens):
        if current_obj is None:
            return None

        if token is MAP:
            # Map the REMAINING tokens over every item in this list.
            if not isinstance(current_obj, list):
                return None
            remaining = tokens[idx + 1:]
            return [_walk_tokens(item, remaining, MAP) for item in current_obj]

        if isinstance(token, int):
            if isinstance(current_obj, list) and token < len(current_obj):
                current_obj = current_obj[token]
            else:
                return None
        else:
            if isinstance(current_obj, dict):
                current_obj = current_obj.get(token)
            else:
                # Try attribute access (for Pydantic models)
                try:
                    current_obj = getattr(current_obj, token)
                except AttributeError:
                    return None
    
    return current_obj


# ------------------------------------------------------------
# Type Validator (Basic type checking)
# ------------------------------------------------------------

def validate_output_type(value: Any, expected_type: str) -> bool:
    """
    Basic type validation against a simplified type string.
    Handles: string, string[], number, boolean, null.
    """
    if value is None:
        return True  # Null is allowed unless required
    
    # Parse type hints like "string[]" or "number[5]"
    is_list = expected_type.endswith('[]')
    base_type = expected_type.replace('[]', '')
    
    if is_list:
        if not isinstance(value, list):
            return False
        # Check all items match the base type
        for item in value:
            if not _validate_single_type(item, base_type):
                return False
        return True
    else:
        return _validate_single_type(value, base_type)


def _validate_single_type(value: Any, type_str: str) -> bool:
    """Validates a single value against a type string."""
    type_str = type_str.lower()
    
    if type_str in ["string", "str"]:
        return isinstance(value, str)
    elif type_str in ["number", "float", "int"]:
        return isinstance(value, (int, float))
    elif type_str == "boolean":
        return isinstance(value, bool)
    elif type_str == "null":
        return value is None
    elif type_str == "object":
        return isinstance(value, dict)
    else:
        # Unknown type, assume valid
        return True


# ------------------------------------------------------------
# Per-Field Normalization (Runtime)
# ------------------------------------------------------------

def apply_normalization(value: Any, normalize_type: Optional[str]) -> Any:
    """
    Applies runtime per-field normalization.
    This is in addition to the normalization done during Transform 1.
    """
    if value is None or normalize_type is None:
        return value
    
    # For E.164 - already normalized during Transform 1, but re-validate
    # as a safety net in case the projection source bypassed Transform 1.
    if normalize_type == "E164":
        if isinstance(value, str):
            result = normalize_phone(value)
            return result if result else value
        return value
    
    # Canonical skill name - also already normalized, but we can re-apply
    if normalize_type == "canonical":
        if isinstance(value, str):
            return canonicalize_skill(value)
        return value
    
    return value


# ------------------------------------------------------------
# Main Projector Function
# ------------------------------------------------------------

def project_output(canonical_profile: CanonicalProfile, config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Projects the internal CanonicalProfile to the output schema
    defined in the runtime config.
    
    Steps:
        1. Validate the config against RuntimeConfig schema
        2. Convert profile to dict for easier traversal
        3. For each field in config.fields:
            a. Resolve the source path ("from" or "path")
            b. Apply per-field normalization (if specified)
            c. Handle missing values based on on_missing
            d. Validate the output type
        4. Apply include_confidence toggle
        5. Return the projected dict
    """
    # 1. Validate config
    try:
        config = RuntimeConfig(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid runtime config: {e}")
    
    # 2. Convert profile to dict (Pydantic model -> dict)
    profile_dict = canonical_profile.model_dump(exclude_none=False)
    
    # 3. Build output dict
    output = {}
    
    for field_spec in config.fields:
        # Determine source path (use "from" if provided, else default to "path")
        source_path = field_spec.from_ if field_spec.from_ else field_spec.path
        output_field = field_spec.path
        
        # Resolve the value
        try:
            value = resolve_path(profile_dict, source_path)
        except (KeyError, IndexError, ValueError):
            value = None
        
        # Handle missing values
        if value is None or value == [] or value == {}:
            if field_spec.required and config.on_missing == "error":
                raise ValueError(f"Required field '{output_field}' is missing (path: {source_path})")
            elif config.on_missing == "omit":
                continue
            else:  # "null"
                output[output_field] = None
                continue
        
        # Per-field normalization (just pass through, already normalized)
        # If needed, we could re-apply normalization here, but our merge engine already did it.
        # We'll just keep it as is.

        # Apply per-field normalization (NEW)
        if field_spec.normalize:
            value = apply_normalization(value, field_spec.normalize)
            print(f"[Projector] Applied '{field_spec.normalize}' normalization to '{output_field}'")
        
        # Validate type (if specified)
        if field_spec.type:
            if not validate_output_type(value, field_spec.type):
                raise ValueError(
                    f"Field '{output_field}' has type '{type(value)}' "
                    f"but expected '{field_spec.type}'"
                )
        
        # Add to output
        output[output_field] = value
    
    # 4. Handle include_confidence and include_provenance INDEPENDENTLY.
    # These ADD the field when true (so the toggle is meaningful even if
    # the field wasn't explicitly listed in config.fields) and REMOVE it
    # when false (even if it was explicitly listed) — the toggle always
    # wins. Previously this only ever removed fields, so
    # include_confidence=true was a silent no-op unless the caller also
    # remembered to list "overall_confidence" in fields.
    if config.include_confidence:
        if "overall_confidence" not in output:
            output["overall_confidence"] = profile_dict.get("overall_confidence")
    else:
        output.pop("overall_confidence", None)
        if "skills" in output and isinstance(output["skills"], list):
            for skill in output["skills"]:
                if isinstance(skill, dict) and "confidence" in skill:
                    skill.pop("confidence")

    if config.include_provenance:
        if "provenance" not in output:
            output["provenance"] = profile_dict.get("provenance", [])
    else:
        output.pop("provenance", None)
    
    return output


# ------------------------------------------------------------
# Helper: Load config from file
# ------------------------------------------------------------

def load_config(file_path: str) -> Dict[str, Any]:
    """Loads a JSON config file."""
    import json
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)