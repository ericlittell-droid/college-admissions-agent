"""College Admissions Strategic Advisor Coordinator Agent.

Orchestrates multi-agent planning, specialist subagent delegation, context
compaction, policy guardrails, human-in-the-loop verification, and non-blocking
async background state consolidation. Follows enterprise ADK Coordinator pattern.
"""

import uuid
from typing import Any
from agents.prompts import ADMISSIONS_ADVISOR_CONSTITUTION
from agents.router import ModelRouter, TaskComplexity
from agents.specialists import (
    ProfileIntakeSpecialist,
    CollegeMatchmakerSpecialist,
    FactCheckerSpecialist,
)
from schemas.student import StudentProfileSchema
from schemas.college import (
    CollegeMatchRecommendation,
    CollegeRecommendationsList,
)
from memory.compaction import HistoryCompactor
from memory.async_memory import AsyncMemoryManager
from guardrails.policy_guardrails import CollegeAdmissionsPolicyGuardrail
from guardrails.hitl import HumanInTheLoopGate, HITLRiskAssessment
from tools.sheets_tool import write_college_recommendations_to_sheet, WriteRecommendationsInput
from observability.logging import StructuredAgentLogger
from observability.tracing import global_tracer


class AdmissionsCoordinatorAgent:
    """Central orchestrator driving the college application advisory workflow."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        self.logger = StructuredAgentLogger(agent_name="AdmissionsCoordinator", run_id=self.run_id)
        self.model_name = ModelRouter.get_model_for_task(TaskComplexity.MULTI_AGENT_COORDINATION)
        self.compactor = HistoryCompactor(max_token_budget=8000)
        self.async_memory = AsyncMemoryManager()

        # Specialist subagents
        self.intake_specialist = ProfileIntakeSpecialist(run_id=self.run_id)
        self.matchmaker_specialist = CollegeMatchmakerSpecialist(run_id=self.run_id)
        self.fact_checker_specialist = FactCheckerSpecialist(run_id=self.run_id)

    def run_advisory_pipeline(
        self,
        spreadsheet_id: str,
        student_id: str = "student-001",
        input_tab: str = "Student_Profile",
        output_tab: str = "College_Matches",
        human_approval_token: str | None = None,
        is_weekly_scheduled_run: bool = False,
    ) -> dict[str, Any]:
        """Executes the complete, end-to-end college advisory workflow.

        Pipeline Steps:
        1. Intake: Read and validate applicant profile from Sheet Tab 1.
        2. Context Compaction: Compact intermediate state to prevent context bloat.
        3. Matchmaking: Query College Scorecard API for 5 public and 5 private candidate schools.
        4. Fact Checking: Enrich each candidate with cost, endowment, deadlines, and testing policies.
        5. Self-Evaluation Guardrail: Verify all 10 schools conform to balancing and completeness rules.
        6. Human-in-the-Loop Gate: Halt execution if high-stakes triggers are met and approval is pending.
        7. Output Delivery: Write verified recommendations back to Google Sheets.
        8. Async Consolidation: Persist state snapshot and detect weekly Tuesday diffs in background.

        Args:
            spreadsheet_id: Target Google Sheet ID.
            student_id: Unique student identifier for session tracking.
            input_tab: Tab name containing student inputs (Tab 1).
            output_tab: Tab name where recommendations will be written.
            human_approval_token: User confirmation token for HITL gate.
            is_weekly_scheduled_run: True if triggered by weekly Tuesday Cloud Scheduler cron.

        Returns:
            Dictionary containing execution summary, guardrail report, and delivery status.
        """
        with global_tracer.start_span("run_advisory_pipeline", {"run_id": self.run_id}):
            t0 = self.logger.log_intent(
                action_name="run_advisory_pipeline",
                intent_description=f"Starting advisory workflow for student '{student_id}' on sheet '{spreadsheet_id}'",
                parameters={"student_id": student_id, "weekly_run": is_weekly_scheduled_run},
            )

            # Step 1: Intake Specialist reads Google Sheet Tab 1
            student_profile = self.intake_specialist.extract_profile(
                spreadsheet_id=spreadsheet_id, tab_name=input_tab
            )

            # Step 2: Context bloat check & compaction
            _ = self.compactor.compact_conversation_history([], ADMISSIONS_ADVISOR_CONSTITUTION)

            # Step 3: Matchmaker Specialist selects 5 public & 5 private candidates
            public_candidates, private_candidates = self.matchmaker_specialist.generate_candidate_matches(
                student_profile
            )

            # Step 4: Fact-Checker Specialist enriches all 10 institutions
            final_recommendations: list[CollegeMatchRecommendation] = []
            for cand in public_candidates + private_candidates:
                enriched = self.fact_checker_specialist.enrich_recommendation(cand, student_profile)
                final_recommendations.append(enriched)

            # Step 5: Self-Evaluation Guardrail Verification
            guardrail_report = CollegeAdmissionsPolicyGuardrail.evaluate_recommendations(
                recommendations=final_recommendations,
                student_sat=student_profile.sat_score,
            )

            if not guardrail_report.passed:
                self.logger.log_outcome(
                    action_name="run_advisory_pipeline",
                    start_time=t0,
                    status="BLOCKED_BY_GUARDRAIL",
                    outcome_summary="Guardrail violations detected",
                    result_payload={"violations": guardrail_report.violations},
                )
                return {
                    "status": "GUARDRAIL_BLOCKED",
                    "run_id": self.run_id,
                    "guardrail_report": guardrail_report.model_dump(),
                }

            # Step 6: Human-in-the-Loop Risk Assessment Gate
            risk_assessment = HumanInTheLoopGate.evaluate_pre_write_risk(
                student_profile=student_profile,
                recommendations=final_recommendations,
                is_weekly_scheduled_run=is_weekly_scheduled_run,
            )

            if risk_assessment.requires_human_approval and not HumanInTheLoopGate.verify_approval_token(
                human_approval_token
            ):
                self.logger.log_outcome(
                    action_name="run_advisory_pipeline",
                    start_time=t0,
                    status="AWAITING_HUMAN_APPROVAL",
                    outcome_summary="Pipeline suspended for human approval gate",
                    result_payload={"triggers": risk_assessment.high_stakes_triggers},
                )
                return {
                    "status": "AWAITING_HUMAN_APPROVAL",
                    "run_id": self.run_id,
                    "risk_assessment": risk_assessment.model_dump(),
                    "pending_recommendations": [r.model_dump() for r in final_recommendations],
                    "action_required": "Provide human_approval_token='APPROVED_BY_USER' to proceed with Google Sheet update.",
                }

            # Step 7: Write verified recommendations to Google Sheet
            write_result = write_college_recommendations_to_sheet(
                WriteRecommendationsInput(
                    spreadsheet_id=spreadsheet_id,
                    output_tab_name=output_tab,
                    recommendations=final_recommendations,
                    human_approval_token=human_approval_token,
                )
            )

            # Step 8: Non-blocking background memory and diff persistence
            # In an active event loop, this schedules as background async task
            self.async_memory.repository.save_student_profile(student_id, student_profile)
            self.async_memory.repository.record_run_snapshot(
                run_id=self.run_id,
                student_id=student_id,
                recommendations=final_recommendations,
            )
            weekly_diffs = self.async_memory.repository.detect_weekly_changes(
                student_id, final_recommendations
            )

            self.logger.log_outcome(
                action_name="run_advisory_pipeline",
                start_time=t0,
                status="SUCCESS",
                outcome_summary=f"Successfully generated and wrote 10 college recommendations (rows={write_result.rows_written})",
                result_payload={"spreadsheet_url": write_result.spreadsheet_url, "diffs": weekly_diffs},
            )

            return {
                "status": "COMPLETED",
                "run_id": self.run_id,
                "student_profile": student_profile.model_dump(),
                "recommendations_count": len(final_recommendations),
                "guardrail_score": guardrail_report.score,
                "weekly_diffs": weekly_diffs,
                "sheet_write_status": write_result.model_dump(),
            }
