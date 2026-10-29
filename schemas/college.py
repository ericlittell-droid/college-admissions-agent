"""University recommendation and admissions fact-checking schemas.

Defines strict Pydantic v2 schemas for college matches, admissions policies,
financial statistics (cost of attendance, endowment), and weekly change diffs.
"""

from enum import Enum
from typing import Annotated
from schemas.pydantic_compat import BaseModel, Field, HttpUrl


class InstitutionType(str, Enum):
    """Institutional governance classification."""

    PUBLIC = "Public"
    PRIVATE_NONPROFIT = "Private Nonprofit"
    PRIVATE_FOR_PROFIT = "Private For-Profit"


class AdmissionCategory(str, Enum):
    """Applicant positioning category relative to academic percentiles."""

    SAFETY = "Safety"
    TARGET = "Target"
    REACH = "Reach"


class TestingPolicy(str, Enum):
    """Standardized testing submission policy."""

    TEST_REQUIRED = "Test-Required"
    TEST_OPTIONAL = "Test-Optional"
    TEST_BLIND = "Test-Blind / Score-Free"


class EarlyProgramType(str, Enum):
    """Early application plan availability."""

    EARLY_ACTION = "Early Action (Non-Binding)"
    RESTRICTIVE_EARLY_ACTION = "Restrictive Early Action (Non-Binding)"
    EARLY_DECISION = "Early Decision (Binding)"
    EARLY_DECISION_II = "Early Decision II (Binding)"
    NONE = "None / Regular Only"


class CollegeMatchRecommendation(BaseModel):
    """Comprehensive recommendation record for a prospective university."""

    institution_name: Annotated[
        str,
        Field(
            description="Official name of the university or college.",
            examples=["University of California, Berkeley", "Stanford University"],
        ),
    ]

    institution_type: Annotated[
        InstitutionType,
        Field(description="Classification: Public, Private Nonprofit, or Private For-Profit."),
    ]

    state: Annotated[
        str,
        Field(description="Two-letter US state code where the campus is located.", max_length=2),
    ]

    fit_rationale: Annotated[
        str,
        Field(
            description="Detailed academic and strategic rationale explaining why this university matches the applicant's major, GPA, and SAT.",
            min_length=20,
        ),
    ]

    admission_category: Annotated[
        AdmissionCategory,
        Field(description="Match rating: Safety, Target, or Reach."),
    ]

    total_cost_of_attendance: Annotated[
        float,
        Field(
            description="Estimated annual Total Cost of Attendance (COA) including tuition, fees, room, and board in USD. Automatically applies in-state rates for in-state public universities, and out-of-state rates for out-of-state institutions.",
            ge=0.0,
            examples=[44500.0, 89500.0],
        ),
    ]

    is_in_state: Annotated[
        bool,
        Field(
            default=False,
            description="Whether this institution is in the applicant's home state.",
        ),
    ]

    tuition_status_applied: Annotated[
        str,
        Field(
            default="In-State Rates",
            description="Description of tuition rate applied: 'In-State Public Rates', 'Out-of-State Public Rates', or 'Private Uniform Tuition'.",
        ),
    ]

    nearest_airport_code: Annotated[
        str | None,
        Field(
            default=None,
            description="3-letter IATA code of the closest major commercial airport serving the university campus.",
            examples=["SFO", "DTW", "BOS", "BNA"],
        ),
    ]

    annual_flight_cost_usd: Annotated[
        float | None,
        Field(
            default=0.0,
            description="Estimated annual airfare cost in USD for 4 round trips from the student's home airport ($0 if in-state).",
            ge=0.0,
        ),
    ]

    annual_flight_details: Annotated[
        str | None,
        Field(
            default=None,
            description="Breakdown of travel estimates (e.g. 'In-State / Ground Travel' or '$1,800 (4 round trips SFO <-> DTW @ ~$450/trip)').",
        ),
    ]

    in_state_tuition: Annotated[
        float | None,
        Field(
            default=None,
            description="Published annual in-state tuition and fees if applicable.",
            ge=0.0,
        ),
    ]

    out_of_state_tuition: Annotated[
        float | None,
        Field(
            default=None,
            description="Published annual out-of-state tuition and fees.",
            ge=0.0,
        ),
    ]

    endowment_size_usd: Annotated[
        float | None,
        Field(
            default=None,
            description="Rough total university endowment market value in USD.",
            ge=0.0,
            examples=[42000000000.0, 7400000000.0],
        ),
    ]

    endowment_formatted: Annotated[
        str,
        Field(
            description="Human-readable formatted endowment size (e.g., '$7.4 Billion', '$850 Million').",
            examples=["$7.4 Billion", "$42.1 Billion", "N/A"],
        ),
    ]

    early_program: Annotated[
        EarlyProgramType,
        Field(description="Early application offering: Early Decision, Early Action, or None."),
    ]

    early_application_deadline: Annotated[
        str | None,
        Field(
            default=None,
            description="Due date for Early Decision or Early Action submissions (e.g., 'November 1, 2026').",
            examples=["November 1", "November 15"],
        ),
    ]

    regular_decision_deadline: Annotated[
        str,
        Field(
            description="Final due date for Regular Decision submissions (e.g., 'January 5, 2027').",
            examples=["January 1", "January 5", "February 1"],
        ),
    ]

    testing_policy: Annotated[
        TestingPolicy,
        Field(description="Testing requirement policy: Test-Required, Test-Optional, or Test-Blind."),
    ]

    official_admissions_url: Annotated[
        str | None,
        Field(default=None, description="URL to the institution's official undergraduate admissions page."),
    ]

    weekly_change_notes: Annotated[
        str | None,
        Field(
            default=None,
            description="Audit notes highlighting any detected changes from prior weekly runs (e.g., deadline update, ranking shift).",
        ),
    ]


class CollegeRecommendationsList(BaseModel):
    """Collection containing balanced university recommendations (5 public and 5 private)."""

    student_summary: Annotated[
        str,
        Field(description="Summary of the student profile used to generate these matches."),
    ]

    public_universities: Annotated[
        list[CollegeMatchRecommendation],
        Field(
            description="Exactly 5 public universities matching student profile.",
            min_length=5,
            max_length=5,
        ),
    ]

    private_universities: Annotated[
        list[CollegeMatchRecommendation],
        Field(
            description="Exactly 5 private universities matching student profile.",
            min_length=5,
            max_length=5,
        ),
    ]
