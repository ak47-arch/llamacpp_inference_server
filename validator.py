"""
Deterministic validation gate for parse results.

Ensures only valid extraction structures reach the immutable save.
"""

import json
from typing import Dict, Any, Tuple


# Valid enum values
VALID_EVENT_TYPES = {
    "interaction", "observation", "decision", "milestone", "reflection", "planning"
}

VALID_IMPACT_LEVELS = {"high", "medium", "low"}

VALID_SOURCE_TYPES = {"self-report", "observation", "third-party"}

REQUIRED_FIELDS = {"title", "circumstance", "actor_names", "source"}


def validate_extraction_output(result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Deterministic validation gate for parse result.
    
    Returns:
        (is_valid: bool, error_message: str)
    
    Validation rules:
    1. Result must be JSON-parseable (if passed as string) and a dict
    2. Required fields present: title, circumstance, actor_names, source
    3. Title: non-empty string (max 200 chars)
    4. Circumstance: non-empty string (max 2000 chars)
    5. Actor_names: non-empty list of strings
    6. Source: must be in VALID_SOURCE_TYPES
    7. Event_type: if present, must be in VALID_EVENT_TYPES
    8. Impact: if present, must be in VALID_IMPACT_LEVELS
    """
    
    errors = []
    
    # If result is a string, try to parse it as JSON
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError as e:
            return False, f"Result is not valid JSON: {e}"
    
    if result is None or not isinstance(result, dict):
        return False, f"Result must be a dict/object, got {type(result).__name__ if result else 'None'}"
    
    # Check required fields (accumulate errors)
    for field in REQUIRED_FIELDS:
        if field not in result:
            errors.append(f"Missing required field: {field}")
    
    # If any required fields are missing, return now with all accumulated errors
    if errors:
        return False, " | ".join(errors)
    
    # Validate title
    title = result.get("title")
    if not isinstance(title, str) or not title.strip():
        return False, f"Title must be non-empty string"
    if len(title) > 200:
        return False, f"Title exceeds max length (200 chars)"
    
    # Validate circumstance
    circumstance = result.get("circumstance")
    if not isinstance(circumstance, str) or not circumstance.strip():
        return False, f"Circumstance must be non-empty string"
    if len(circumstance) > 2000:
        return False, f"Circumstance exceeds max length (2000 chars)"
    
    # Validate source
    source = result.get("source")
    if not isinstance(source, str):
        return False, f"Source must be a string"
    if source not in VALID_SOURCE_TYPES:
        return False, f"Source '{source}' not in {VALID_SOURCE_TYPES} | source"
    
    # Validate actor_names
    actor_names = result.get("actor_names")
    if not isinstance(actor_names, list):
        return False, f"actor_names must be a list, got {type(actor_names).__name__}"
    
    if not actor_names:
        return False, f"actor_names cannot be empty"
    
    for idx, actor_name in enumerate(actor_names):
        if not isinstance(actor_name, str) or not actor_name.strip():
            return False, f"actor_names[{idx}] must be non-empty string"
    
    # Validate event_type if present
    if "event_type" in result:
        event_type = result.get("event_type")
        if event_type not in VALID_EVENT_TYPES:
            return False, f"Event type '{event_type}' not in {VALID_EVENT_TYPES}"
    
    # Validate impact if present
    if "impact" in result:
        impact = result.get("impact")
        if impact not in VALID_IMPACT_LEVELS:
            return False, f"Impact '{impact}' not in {VALID_IMPACT_LEVELS}"
    
    return True, ""
