from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RestrictionType(str, Enum):
    EXPLICIT = "EXPLICIT"
    IMPLICIT = "IMPLICIT"
    NONE = "NONE"


class AgeAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    has_age_restriction: bool
    restriction_type: RestrictionType
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    extracted_evidence: str | None = None
    ai_reasoning: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_restriction_fields(self) -> "AgeAnalysisResult":
        restricted = self.restriction_type is not RestrictionType.NONE
        if self.has_age_restriction != restricted:
            raise ValueError("has_age_restriction must match restriction_type")
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError("min_age must not exceed max_age")
        if restricted and not self.extracted_evidence:
            raise ValueError("Restricted analyses must include supporting evidence")
        if not restricted and (self.min_age is not None or self.max_age is not None):
            raise ValueError("Neutral analyses must not include an age range")
        return self
