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
