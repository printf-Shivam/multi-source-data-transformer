from typing import List, Optional, Dict
from datetime import datetime
from src.models.canonical import CanonicalProfile, ExperienceItem
from src.transform.conflict_resolver import SOURCE_WEIGHTS

def calculate_years_experience(experience: List[ExperienceItem]) -> Optional[float]:
    """Calculates total years of experience from the experience list."""
    if not experience:
        return None
    
    total_months = 0
    current_date = datetime.now()
    
    for exp in experience:
        if not exp.start:
            continue
        try:
            start = datetime.strptime(exp.start, "%Y-%m")
        except (ValueError, TypeError):
            continue
        
        if exp.end and exp.end != "Present":
            try:
                end = datetime.strptime(exp.end, "%Y-%m")
            except (ValueError, TypeError):
                continue
        else:
            end = current_date
        
        months = (end.year - start.year) * 12 + (end.month - start.month)
        total_months += max(0, months)
    
    return round(total_months / 12, 1) if total_months > 0 else None

def calculate_overall_confidence(
    profile: CanonicalProfile,
    field_confidences: Dict[str, float]
) -> Optional[float]:
    """Averages the real per-field confidence scores."""
    confidence_scores = list(field_confidences.values())

    if profile.skills:
        skill_conf = sum(s.confidence for s in profile.skills) / len(profile.skills)
        confidence_scores.append(skill_conf)

    if profile.experience:
        confidence_scores.append(SOURCE_WEIGHTS["ats"]["experience"])
    if profile.education:
        confidence_scores.append(SOURCE_WEIGHTS["ats"]["education"])

    if not confidence_scores:
        return None

    return round(sum(confidence_scores) / len(confidence_scores), 2)