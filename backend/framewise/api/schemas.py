from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LibraryCreate(BaseModel):
    source: str = Field(min_length=1, max_length=2048)
    name: str = Field(default="", max_length=200)
    recursive: bool = True


class DecisionUpdate(BaseModel):
    decision: Literal["auto", "keep", "reject", "review"] | None = None
    stars: int | None = Field(default=None, ge=0, le=5)


class BudgetUpdate(BaseModel):
    budget: int = Field(ge=1, le=100)


class WeightUpdate(BaseModel):
    aesthetic: float = Field(ge=0, le=1, allow_inf_nan=False)
    sharpness: float = Field(ge=0, le=1, allow_inf_nan=False)
    exposure: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_weights(self):
        if self.sharpness + self.exposure <= 0:
            raise ValueError("At least one classical weight must be positive for offline fallback")
        return self


class HighlightConfigUpdate(BaseModel):
    mode: Literal["general"] = "general"
    aesthetic_floor: float = Field(default=6.5, ge=0, le=10, allow_inf_nan=False)
    technical_floor: float = Field(default=35, ge=0, le=100, allow_inf_nan=False)
    flickr_aesthetic_floor: float = Field(default=7, ge=0, le=10, allow_inf_nan=False)
    flickr_percentile: float = Field(default=90, ge=0, le=100, allow_inf_nan=False)
    flickr_max: int | None = Field(default=12, ge=1, le=5000)
    aesthetic_weight: float = Field(default=0.65, ge=0, le=1, allow_inf_nan=False)
    technical_weight: float = Field(default=0.20, ge=0, le=1, allow_inf_nan=False)
    distinctiveness_weight: float = Field(default=0.15, ge=0, le=1, allow_inf_nan=False)
    diversity_penalty: float = Field(default=8, ge=0, le=25, allow_inf_nan=False)
    force_three: bool = False

    @model_validator(mode="after")
    def positive_quality_weight(self):
        if self.aesthetic_weight + self.technical_weight <= 0:
            raise ValueError("At least one quality weight must be positive")
        return self


class HighlightDecisionUpdate(BaseModel):
    flickr: Literal["auto", "keep", "reject"] | None = None
    competition: Literal["auto", "include", "reject", "alternative"] | None = None
    include_lightroom: bool = False


class FinalistUpdate(BaseModel):
    photo_id: str
