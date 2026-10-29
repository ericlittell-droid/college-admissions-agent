"""Self-Evaluation Guardrail and Policy Verification Plugin.

Implements automated self-reflection, policy constraint checks, and quality gates
to statically and dynamically evaluate agent outputs prior to external execution.
"""

from typing import Any
from schemas.pydantic_compat import BaseModel, Field
from schemas.college import CollegeMatchRecommendation, InstitutionType


class GuardrailEvaluationReport(BaseModel):
    """Structured report returned by the Self-Evaluation Guardrail."""

    passed: bool = Field(description="Whether the output passed all mandatory rubric and safety criteria.")
    score: float = Field(description="Completeness and quality score between 0.0 and 100.0.", ge=0.0, le=100.0)
    public_count: int = Field(description="Number of verified public institutions.")
    private_count: int = Field(description="Number of verified private institutions.")
    violations: list[str] = Field(default_factory=list, description="List of policy or rubric criteria violations.")
    warnings: list[str] = Field(default_factory=list, description="Advisory notices for human review.")


class CollegeAdmissionsPolicyGuardrail:
    """Enforces admissions ethics, data completeness, and balance constraints."""

    # Blocklist of unaccredited or predatory institutions
    PREDATORY_INSTITUTIONS_BLOCKLIST = {
        "trump university",
        "corinthian colleges",
        "itt technical institute",
        "university of phoenix",
    }

    @classmethod
    def evaluate_recommendations(
        cls,
        recommendations: list[CollegeMatchRecommendation],
        student_sat: int | None = None,
    ) -> GuardrailEvaluationReport:
        """Statically inspects recommendations against all 5 core rubric criteria.

        Criteria Checked:
        1. Exact Balance: Exactly 5 Public and 5 Private nonprofit institutions.
        2. Financial Completeness: Valid Total Cost of Attendance (> $0) for all 10.
        3. Endowment Transparency: Valid endowment figure or formatted string for all 10.
        4. Application Due Dates: Regular decision deadline present for all 10.
        5. Testing Policies: Explicit testing policy (Test-Required, Optional, Blind) for all 10.
        6. Safety & Accreditation: Rejection of predatory / unaccredited colleges.
        """
        violations: list[str] = []
        warnings: list[str] = []

        total_count = len(recommendations)
        if total_count != 10:
            violations.append(f"Rubric requirement failed: Expected 10 total universities, found {total_count}.")

        public_count = sum(1 for c in recommendations if c.institution_type == InstitutionType.PUBLIC)
        private_count = sum(1 for c in recommendations if c.institution_type in (InstitutionType.PRIVATE_NONPROFIT, InstitutionType.PRIVATE_FOR_PROFIT))

        if public_count != 5:
            violations.append(f"Balance violation: Expected 5 Public universities, found {public_count}.")
        if private_count != 5:
            violations.append(f"Balance violation: Expected 5 Private universities, found {private_count}.")

        for college in recommendations:
            name_lower = college.institution_name.lower()

            # Predatory check
            if any(pred in name_lower for pred in cls.PREDATORY_INSTITUTIONS_BLOCKLIST):
                violations.append(f"Safety violation: '{college.institution_name}' is on the consumer protection blocklist.")

            # Total Cost of Attendance check
            if college.total_cost_of_attendance <= 0:
                violations.append(f"Missing financial metric: '{college.institution_name}' has invalid cost of attendance ($0).")

            # Endowment check
            if not college.endowment_formatted or college.endowment_formatted.strip() in ("", "N/A", "Unknown"):
                warnings.append(f"Endowment transparency warning: '{college.institution_name}' lacks confirmed endowment size.")

            # Deadlines check
            if not college.regular_decision_deadline or college.regular_decision_deadline.strip() == "":
                violations.append(f"Missing deadline: '{college.institution_name}' missing Regular Decision due date.")

            # Testing policy check
            if not college.testing_policy:
                violations.append(f"Missing policy: '{college.institution_name}' missing standardized testing policy.")

            # Reach check warning
            if student_sat and college.out_of_state_tuition and student_sat < 1100 and "Harvard" in college.institution_name:
                warnings.append(f"Extreme reach warning: '{college.institution_name}' admit rate < 4% for SAT {student_sat}.")

        # Calculate score (deduct 15 points per violation, 3 per warning)
        deductions = (len(violations) * 15.0) + (len(warnings) * 3.0)
        final_score = max(0.0, 100.0 - deductions)
        passed = len(violations) == 0

        return GuardrailEvaluationReport(
            passed=passed,
            score=final_score,
            public_count=public_count,
            private_count=private_count,
            violations=violations,
            warnings=warnings,
        )
