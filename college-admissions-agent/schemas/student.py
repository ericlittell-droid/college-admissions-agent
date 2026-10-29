"""Student profile and academic interest schemas.

Defines strict Pydantic v2 schemas for student input data, validation rules,
and serialization for Google Sheets intake.
"""

from typing import Annotated
from schemas.pydantic_compat import BaseModel, Field, field_validator


class StudentProfileSchema(BaseModel):
    """Schema representing an applicant's academic profile and preferences.

    Validates academic metrics and geographic constraints parsed from the
    applicant's input Google Sheet (Tab 1).
    """

    home_state: Annotated[
        str,
        Field(
            description="Two-letter US postal state code or full state name where student resides (e.g., 'CA' or 'California').",
            examples=["CA", "California", "NY", "Texas"],
            min_length=2,
        ),
    ]

    unweighted_gpa: Annotated[
        float,
        Field(
            description="Rough unweighted high school GPA on a 0.0 to 4.0 scale.",
            ge=0.0,
            le=4.0,
            examples=[3.85, 3.5, 4.0],
        ),
    ]

    sat_score: Annotated[
        int | None,
        Field(
            default=None,
            description="Total SAT composite score (400 to 1600). Null if student has not taken the SAT or is applying score-free.",
            ge=400,
            le=1600,
            examples=[1450, 1320, 1560],
        ),
    ]

    intended_major_field: Annotated[
        str,
        Field(
            description="Broad subject area or specific academic major of interest (e.g., 'Computer Science', 'Mechanical Engineering', 'Biology').",
            examples=["Computer Science", "Economics", "Nursing", "Biomedical Engineering"],
            min_length=2,
        ),
    ]

    max_cost_of_attendance_budget: Annotated[
        float | None,
        Field(
            default=None,
            description="Optional target annual budget for total cost of attendance in USD.",
            ge=0.0,
            examples=[50000.0, 75000.0],
        ),
    ]

    home_airport_code: Annotated[
        str | None,
        Field(
            default=None,
            description="3-letter IATA code or name of the student's nearest home airport (e.g., 'SFO', 'LAX', 'ORD').",
            examples=["SFO", "LAX", "JFK"],
        ),
    ]

    @field_validator("home_airport_code")
    @classmethod
    def normalize_airport(cls, v: str | None) -> str | None:
        """Standardizes airport code to uppercase 3-letter string."""
        if not v:
            return None
        cleaned = v.strip().upper()
        return cleaned[:3] if len(cleaned) >= 3 else cleaned

    @field_validator("home_state")
    @classmethod
    def normalize_state(cls, v: str) -> str:
        """Standardizes state input to uppercase abbreviation if 2 letters."""
        cleaned = v.strip()
        if len(cleaned) == 2:
            return cleaned.upper()
        return cleaned.title()

    @field_validator("intended_major_field")
    @classmethod
    def clean_major(cls, v: str) -> str:
        """Strips whitespace and ensures major description is non-empty."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Intended major field cannot be blank.")
        return cleaned
