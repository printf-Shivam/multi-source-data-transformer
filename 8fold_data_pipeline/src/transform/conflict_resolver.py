from typing import List, Optional, Dict, Any

# ------------------------------------------------------------
# Source Authority Matrix (The Rulebook)
# ------------------------------------------------------------
SOURCE_WEIGHTS = {
    "ats": {
        "default": 0.7,
        "identity": 0.9,      
        "experience": 0.85,   
        "education": 0.9,     
        "location": 0.85, 
        "skills": 0.6,        
    },
    "github": {
        "default": 0.5,
        "identity": 0.4,      
        "experience": 0.3,    
        "education": 0.0,     # ZERO TRUST
        "location": 0.3,      
        "skills": 0.9,        # GROUND TRUTH
    },
    "note": {
        "default": 0.4,
        "identity": 0.7,      # Recruiter might misspell a name, ATS is better
        "experience": 0.0,    
        "education": 0.0,     
        "location": 0.6,      # Recruiter might know they recently moved
        "skills": 0.5,        # Mentions a skill, but GitHub is better proof
    }
}

FIELD_CATEGORY_MAP = {
    "full_name": "identity",
    "emails": "identity",
    "phone": "identity",
    "phones": "identity",
    "candidate_id": "identity",
    "experience": "experience",
    "education": "education",
    "location": "location",
    "skills": "skills",
    "headline": "identity",
    "github_url": "identity",
    "linkedin_url": "identity",
}

def get_best_value(
    field: str,
    observations: List[Any]
) -> tuple[Optional[Any], float, List[str]]:
    """Resolves conflicts dynamically using the Source Authority Matrix."""
    if not observations:
        return None, 0.0, []

    category = FIELD_CATEGORY_MAP.get(field, "default")
    
    # 1. Handle List Fields (Union/Combine)
    if field in ["emails", "phones"]:
        combined, sources = [], []
        for obs in observations:
            if obs.value:
                # Handle if value is a list (e.g., regex found multiple emails)
                vals = obs.value if isinstance(obs.value, list) else [obs.value]
                for v in vals:
                    if v not in combined:
                        combined.append(v)
                        sources.append(obs.source)
        
        if combined:
            avg_conf = sum([SOURCE_WEIGHTS.get(s, {}).get(category, 0.5) for s in sources]) / len(sources)
            return combined, avg_conf, list(set(sources))
        return [], 0.0, []

    # 2. Handle Single Value Fields (Pick the Winner)
    best_value, best_source, best_weight = None, None, -1.0
    valid_obs = [obs for obs in observations if obs.value is not None]

    # Zero-Trust Policy for GitHub Education
    if field == "education":
        valid_obs = [obs for obs in valid_obs if obs.source != "github"]

    for obs in valid_obs:
        # Dynamically look up the weight based on the observation's source tag
        weight = SOURCE_WEIGHTS.get(obs.source, {}).get(category, 0.0)
        if weight > best_weight:
            best_value = obs.value
            best_weight = weight
            best_source = obs.source

    # 3. Consensus Boost Logic
    if best_value is not None:
        # Check if multiple different sources reported this exact same value
        agreeing_sources = [obs.source for obs in valid_obs if str(obs.value) == str(best_value)]
        unique_sources = list(set(agreeing_sources))
        
        if len(unique_sources) > 1:
            return best_value, 1.0, unique_sources  # 1.0 Confidence Boost!
        return best_value, best_weight, unique_sources

    return None, 0.0, []