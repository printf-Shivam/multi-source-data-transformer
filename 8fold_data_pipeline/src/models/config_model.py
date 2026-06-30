"""
Runtime Configuration Model
Validates the JSON config that reshapes the output.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class FieldMapping(BaseModel):
    """
    Defines how a single output field is mapped from the internal profile.
    """
    path: str
    from_: Optional[str] = Field(None, alias="from")
    type: str = "string"
    required: bool = False
    normalize: Optional[Literal["E164", "canonical"]] = None

    class Config:
        populate_by_name = True


class RuntimeConfig(BaseModel):
    """
    The full runtime configuration for reshaping the output.
    """
    fields: List[FieldMapping] = []
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: Literal["null", "omit", "error"] = "null"

    @field_validator("fields")
    @classmethod
    def validate_field_paths(cls, v):
        for field in v:
            if field.from_ is None:
                field.from_ = field.path
        return v