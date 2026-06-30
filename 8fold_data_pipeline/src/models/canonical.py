from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re

# --- Nested Models (to match the exact output schema) ---

class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2

    @field_validator("country")
    @classmethod
    def validate_country(cls, v):
        if v is not None and not re.match(r"^[A-Z]{2}$", v):
            raise ValueError(f"Country must be ISO-3166 alpha-2 (e.g., US, IN), got {v}")
        return v

class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: List[str] = []

class Skill(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: List[str] = []  # List of source IDs (e.g., ["ats", "github"])

class ExperienceItem(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None  # YYYY-MM
    end: Optional[str] = None    # YYYY-MM or "Present" (handled in normalizer)
    summary: Optional[str] = None

    @field_validator("start", "end")
    @classmethod
    def validate_date_format(cls, v):
        if v is not None and v != "Present" and not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError(f"Date must be YYYY-MM, got {v}")
        return v

class EducationItem(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[str] = None  # YYYY

    @field_validator("end_year")
    @classmethod
    def validate_year(cls, v):
        if v is not None and not re.match(r"^\d{4}$", v):
            raise ValueError(f"End year must be YYYY, got {v}")
        return v

class ProvenanceItem(BaseModel):
    field: str  # Which field does this refer to? (e.g., "full_name", "skills[0]")
    source: str  # "ats" or "github"
    method: str  # "direct_field", "api_parse", "regex_extract"

# --- The Main Canonical Profile ---

class CanonicalProfile(BaseModel):
    """
    The final, merged, trusted candidate profile.
    This is the single source of truth for downstream systems.
    """
    # Identifiers
    candidate_id: Optional[str] = None
    full_name: Optional[str] = None
    
    # Contact
    emails: List[str] = []
    phones: List[str] = []  # E.164 format
    
    # Demographics / Location
    location: Optional[Location] = None
    
    # Web Presence
    links: Optional[Links] = None
    
    # Professional Summary
    headline: Optional[str] = None
    years_experience: Optional[float] = Field(None, ge=0.0)
    
    # Core Competencies
    skills: List[Skill] = []
    
    # Work & Education History
    experience: List[ExperienceItem] = []
    education: List[EducationItem] = []
    
    # --- Trust & Traceability (The "Explainability" Requirement) ---
    provenance: List[ProvenanceItem] = []
    overall_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    class Config:
        # This ensures that if we accidentally pass extra fields, they are ignored
        # (keeps our internal state clean)
        extra = "ignore"