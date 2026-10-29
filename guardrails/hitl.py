"""Human-in-the-Loop (HITL) Execution Gate and Approval Hooks.

Implements explicit code stops requiring human confirmation before executing
high-stakes actions (modifying external Google Sheets, confirming binding
Early Decision commitments, or accepting high-reach school portfolios).
"""

from typing import Any
from schemas.pydantic_compat import BaseModel, Field
from schemas.student import StudentProfileSchema
from schemas.college import CollegeMatchRecommendation, EarlyProgramType


class HITLRiskAssessment(BaseModel):
    """Assessment of whether an agent proposal requires human approval."""

    requires_human_approval: bool = Field(description="Whether execution must halt for human review.")
    risk_level: str = Field(description="Risk classification: 'LOW', 'MEDIUM', 'HIGH', or 'CRITICAL'.")
    high_stakes_triggers: list[str] = Field(default_factory=list, description="Specific triggers requiring human sign-off.")
    action_description: str = Field(description="Description of the pending external action.")


class HumanInTheLoopGate:
    """Explicit code stop that halts agent execution for high-stakes actions."""

    APPROVAL_PASSTHROUGH_TOKEN = "APPROVED_BY_USER"

    @classmethod
    def evaluate_pre_write_risk(
        cls,
        student_profile: StudentProfileSchema,
        recommendations: list[CollegeMatchRecommendation],
        is_weekly_scheduled_run: bool = False,
    ) -> HITLRiskAssessment:
        """Inspects proposed actions for high-stakes consequences before updating external sheets.

        High-Stakes Triggers:
        1. Destructive modification / overwrite of user's Google Sheet.
        2. Inclusion of legally/contractually binding Early Decision (ED) programs.
        3. Severe academic mismatch (e.g. Extreme Reach with <5% admit probability).
        4. Weekly Tuesday automated diff updates with significant cost or deadline shifts.
        """
        triggers: list[str] = []

        # 1. Base trigger: Overwriting external user data in Google Sheets
        triggers.append("Overwriting live Google Sheet tab with 10 college recommendation records.")

        # 2. Check for binding Early Decision programs
        for college in recommendations:
            if college.early_program in (EarlyProgramType.EARLY_DECISION, EarlyProgramType.EARLY_DECISION_II):
                triggers.append(
                    f"Binding commitment: '{college.institution_name}' requires legally binding Early Decision. "
                    "Student must confirm willingness to enroll if admitted."
                )

        # 3. Check for reach balance
        reach_count = sum(1 for c in recommendations if c.admission_category.value == "Reach")
        if reach_count >= 5:
            triggers.append(
                f"Portfolio Risk: {reach_count} of 10 colleges are classified as 'Reach'. "
                "Student confirmation required to proceed with aggressive reach strategy."
            )

        # 4. Weekly scheduled run trigger
        if is_weekly_scheduled_run:
            triggers.append("Scheduled Weekly Tuesday Update: Review detected changes before applying to live sheet.")

        risk_level = "CRITICAL" if any("Binding commitment" in t for t in triggers) else "HIGH" if triggers else "LOW"

        return HITLRiskAssessment(
            requires_human_approval=True,
            risk_level=risk_level,
            high_stakes_triggers=triggers,
            action_description="Commit recommendations to Google Sheets",
        )

    @classmethod
    def verify_approval_token(cls, token: str | None) -> bool:
        """Validates that a human confirmation token is present and valid."""
        return token == cls.APPROVAL_PASSTHROUGH_TOKEN
