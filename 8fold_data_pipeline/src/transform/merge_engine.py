"""
Transform 3: Weighted Priority Merge (Source-Agnostic)
Orchestrates the assembly of the CanonicalProfile by aggregating data from 
all available sources and applying Source Authority Matrix rules.
"""

from typing import List, Optional, Dict, Any
from src.models.observation import Observation
from src.models.canonical import (
    CanonicalProfile, 
    Location, 
    Links, 
    Skill, 
    ExperienceItem, 
    EducationItem, 
    ProvenanceItem
)
from src.transform.normalizer import normalize_observations, normalize_field
from src.transform.conflict_resolver import get_best_value, SOURCE_WEIGHTS
from src.transform.derived_metrics import calculate_years_experience, calculate_overall_confidence

# ------------------------------------------------------------
# Merge Engine
# ------------------------------------------------------------

def merge_sources(all_observations: List[Observation]) -> CanonicalProfile:
    """Orchestrates the merging of normalized observations into a CanonicalProfile."""
    # Normalize all observations regardless of source
    normalized_obs = normalize_observations(all_observations) if all_observations else []
    
    # Group observations by field: {"skills": [obs1, obs2], "emails": [obs3]}
    grouped_obs = _group_observations(normalized_obs)
    
    profile = CanonicalProfile()
    field_confidences: Dict[str, float] = {}
    
    # Execute modular merge helpers
    _merge_identity_fields(profile, grouped_obs, field_confidences)
    _merge_location(profile, grouped_obs, field_confidences)
    _merge_links(profile, grouped_obs)
    _merge_skills(profile, grouped_obs)
    _merge_experience(profile, grouped_obs)
    _merge_education(profile, grouped_obs)
    
    # Finalize derived metrics
    profile.years_experience = calculate_years_experience(profile.experience)
    profile.overall_confidence = calculate_overall_confidence(profile, field_confidences)
    
    return profile

def _group_observations(observations: List[Observation]) -> Dict[str, List[Observation]]:
    grouped = {}
    for obs in observations:
        grouped.setdefault(obs.field, []).append(obs)
    return grouped

# ------------------------------------------------------------
# Merge Helpers
# ------------------------------------------------------------

def _merge_identity_fields(profile: CanonicalProfile, grouped_obs: Dict[str, List[Observation]], field_confidences: Dict):
    for field in ["candidate_id", "full_name", "headline"]:
        value, conf, sources = get_best_value(field, grouped_obs.get(field, []))
        setattr(profile, field, value)
        if value:
            field_confidences[field] = conf
            profile.provenance.append(ProvenanceItem(field=field, source=", ".join(sources), method="merge"))
            
    for field in ["emails", "phones"]:
        value, conf, sources = get_best_value(field, grouped_obs.get(field, []))
        if value and isinstance(value, list):
            setattr(profile, field, value)
            field_confidences[field] = conf

def _merge_location(profile: CanonicalProfile, grouped_obs: Dict[str, List[Observation]], field_confidences: Dict):
    value, conf, sources = get_best_value("location", grouped_obs.get("location", []))
    if value and isinstance(value, dict):
        profile.location = Location(
            city=value.get("city"),
            region=value.get("region") or value.get("state"),
            country=value.get("country")
        )
        field_confidences["location"] = conf
        profile.provenance.append(ProvenanceItem(field="location", source=", ".join(sources), method="merge"))

def _merge_links(profile: CanonicalProfile, grouped_obs: Dict[str, List[Observation]]):
    links = Links(other=[])
    for field, attr in [("github_url", "github"), ("linkedin_url", "linkedin"), ("blog_url", "portfolio")]:
        val, _, _ = get_best_value(field, grouped_obs.get(field, []))
        if val: setattr(links, attr, val)
    profile.links = links

def _merge_skills(profile: CanonicalProfile, grouped_obs: Dict[str, List[Observation]]):
    skill_map = {} 
    for obs in grouped_obs.get("skills", []):
        if not obs.value: continue
        vals = obs.value if isinstance(obs.value, list) else [obs.value]
        for v in vals:
            name = normalize_field("skills", v)
            if not name: continue
            weight = SOURCE_WEIGHTS.get(obs.source, {}).get("skills", 0.5)
            if name not in skill_map:
                skill_map[name] = Skill(name=name, confidence=weight, sources=[obs.source])
            else:
                if obs.source not in skill_map[name].sources:
                    skill_map[name].sources.append(obs.source)
                    skill_map[name].confidence = 1.0 # Consensus boost
    profile.skills = list(skill_map.values())

def _merge_experience(profile: CanonicalProfile, grouped_obs: Dict[str, List[Observation]]):
    """Aggregates experience from all sources."""
    seen = set()
    for obs in grouped_obs.get("experience", []):
        # Handle both list and dict values
        items = []
        if isinstance(obs.value, list):
            items = obs.value
        elif isinstance(obs.value, dict):
            items = [obs.value]
        else:
            continue

        for item in items:
            # Map keys from ATS (start_date, end_date) to schema (start, end)
            company = item.get("company")
            title = item.get("title")
            start = item.get("start_date") or item.get("start")
            end = item.get("end_date") or item.get("end")
            summary = item.get("summary")

            # Skip if company or title is missing (avoid empty entries)
            if not company and not title:
                continue

            key = f"{company}_{title}".lower()
            if key not in seen:
                profile.experience.append(ExperienceItem(
                    company=company,
                    title=title,
                    start=start,
                    end=end,
                    summary=summary
                ))
                seen.add(key)

    # Fallback: GitHub repos as experience if no ATS experience
    if not profile.experience:
        for obs in grouped_obs.get("github_repos", [])[:3]:
            if isinstance(obs.value, dict):
                profile.experience.append(ExperienceItem(
                    company="GitHub",
                    title=f"Repo: {obs.value.get('name', 'Unknown')}",
                    summary=obs.value.get("description")
                ))

                
def _merge_education(profile: CanonicalProfile, grouped_obs: Dict[str, List[Observation]]):
    """Aggregates education, enforcing Zero-Trust for GitHub."""
    seen = set()
    valid_obs = [o for o in grouped_obs.get("education", []) if o.source != "github"]
    for obs in valid_obs:
        if isinstance(obs.value, list):
            for edu in obs.value:
                key = f"{edu.get('institution')}_{edu.get('degree')}".lower()
                if key not in seen:
                    profile.education.append(EducationItem(**edu))
                    seen.add(key)