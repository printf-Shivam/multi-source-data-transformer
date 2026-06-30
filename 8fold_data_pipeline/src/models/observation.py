from typing import Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

class Observation(BaseModel):
    """
    A generic wrapper for any piece of extracted data.
    This allows us to trace every value back to its origin.
    """
    field: str
    value: Any  # The actual extracted value (string, list, dict, etc.)
    source: Literal["ats", "github", "note"]  # Where did this come from?
    
    extracted_at: datetime = Field(default_factory=datetime.now)  # Timestamp for staleness checks
    extraction_certainty: float = Field(ge=0.0, le=1.0, default=1.0)
    method: str = "direct_extract"                   # Bonus: How we got it (regex, API, etc.)
    raw: Optional[Any] = None                        # Bonus: Original messy text for debugging

    
    class Config:
        # Allows us to store complex nested structures without Pydantic complaining
        arbitrary_types_allowed = True