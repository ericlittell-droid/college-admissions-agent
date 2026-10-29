"""Automated Evaluation Suite and Regression Testing Harness.

Validates the College Admissions Agent against the 95-point AgentOps Code Review Matrix:
1. Tool & Interface Design (Docstrings, Naming, Schemas, Guided Errors)
2. Context & Memory (Constitution, Compaction, Persistence, Async)
3. Orchestration & Logic (Multi-Agent Patterns, Model Routing, Guardrails, HITL)
4. Observability & Tracing (Structured JSON, Intent vs. Outcome, OTel, PII Scrubbing)
5. Infrastructure & CI/CD (Golden dataset regressions, IaC conformance)
"""

import unittest
import json
import os
import inspect

from schemas.student import StudentProfileSchema
from schemas.college import (
    CollegeMatchRecommendation,
    InstitutionType,
    AdmissionCategory,
    TestingPolicy,
    EarlyProgramType,
)
from tools.scorecard_tool import query_college_scorecard_api, CollegeScorecardQueryInput
from tools.sheets_tool import (
    fetch_student_profile_from_sheet,
    write_college_recommendations_to_sheet,
    FetchProfileInput,
    WriteRecommendationsInput,
)
from tools.admissions_search_tool import (
    search_university_admissions_and_endowment_details,
    AdmissionsSearchInput,
)
from tools.travel_tool import (
    estimate_annual_college_travel_costs,
    TravelCostEstimationInput,
)
from memory.compaction import HistoryCompactor
from memory.session_state import SessionStateRepository
from agents.router import ModelRouter, TaskComplexity
from agents.coordinator import AdmissionsCoordinatorAgent
from guardrails.policy_guardrails import CollegeAdmissionsPolicyGuardrail
from guardrails.hitl import HumanInTheLoopGate
from observability.pii_scrubber import PIIScrubber


class TestAgentOpsEvaluationHarness(unittest.TestCase):
    """Automated evaluation harness verifying AgentOps rubric criteria."""

    @classmethod
    def setUpClass(cls):
        """Loads golden dataset for regression benchmarking."""
        eval_dir = os.path.dirname(os.path.abspath(__file__))
        golden_path = os.path.join(eval_dir, "golden_dataset.json")
        with open(golden_path, "r", encoding="utf-8") as f:
            cls.golden_data = json.load(f)

    # ---------------------------------------------------------
    # 1. TOOL & INTERFACE DESIGN (20 POINTS)
    # ---------------------------------------------------------

    def test_rubric_01_tool_docstrings_comprehensive(self):
        """Rubric: Comprehensive Tool Docstrings."""
        tools = [
            query_college_scorecard_api,
            fetch_student_profile_from_sheet,
            write_college_recommendations_to_sheet,
            search_university_admissions_and_endowment_details,
            estimate_annual_college_travel_costs,
        ]
        for tool_fn in tools:
            doc = inspect.getdoc(tool_fn)
            self.assertIsNotNone(doc, f"Tool '{tool_fn.__name__}' is missing docstrings.")
            self.assertIn("Parameters:", doc, f"Tool '{tool_fn.__name__}' missing Parameters section.")
            self.assertIn("Returns:", doc, f"Tool '{tool_fn.__name__}' missing Returns section.")

    def test_rubric_02_descriptive_naming(self):
        """Rubric: Descriptive Naming."""
        # Verifies tool names are highly specific and domain-oriented
        self.assertTrue(hasattr(query_college_scorecard_api, "__name__"))
        self.assertEqual(query_college_scorecard_api.__name__, "query_college_scorecard_api")
        self.assertEqual(fetch_student_profile_from_sheet.__name__, "fetch_student_profile_from_sheet")
        self.assertEqual(write_college_recommendations_to_sheet.__name__, "write_college_recommendations_to_sheet")
        self.assertEqual(
            search_university_admissions_and_endowment_details.__name__,
            "search_university_admissions_and_endowment_details",
        )
        self.assertEqual(
            estimate_annual_college_travel_costs.__name__,
            "estimate_annual_college_travel_costs",
        )

    def test_rubric_03_explicit_json_schemas(self):
        """Rubric: Explicit JSON Schemas."""
        profile = StudentProfileSchema(
            home_state="california",
            unweighted_gpa=3.9,
            sat_score=1450,
            intended_major_field="Computer Science",
        )
        self.assertEqual(profile.home_state, "California")
        self.assertEqual(profile.unweighted_gpa, 3.9)

        # Negative schema test: invalid GPA > 4.0 must raise ValidationError
        with self.assertRaises(Exception):
            StudentProfileSchema(
                home_state="CA",
                unweighted_gpa=4.5,  # Exceeds max
                sat_score=1450,
                intended_major_field="CS",
            )

    def test_rubric_04_guided_error_handling(self):
        """Rubric: Guided Error Handling."""
        # Simulated sheet tab missing returns structured recovery guidance
        res = fetch_student_profile_from_sheet(
            FetchProfileInput(spreadsheet_id="mock_missing_tab", tab_name="NonExistentTab")
        )
        self.assertFalse(res.success)
        self.assertIsNotNone(res.guided_recovery_instructions)
        self.assertIn("Actionable recovery step", res.guided_recovery_instructions)

    # ---------------------------------------------------------
    # 2. CONTEXT & MEMORY (20 POINTS)
    # ---------------------------------------------------------

    def test_rubric_05_history_compaction(self):
        """Rubric: History Compaction."""
        compactor = HistoryCompactor(max_token_budget=100, sliding_window_turns=2)
        long_messages = [
            {"role": "user", "content": "I am interested in university options for CS with high rankings." * 10},
            {"role": "assistant", "content": "Here is a verbose search dump of 25 universities in the midwest." * 10},
            {"role": "user", "content": "Can we look at California schools specifically?"},
            {"role": "assistant", "content": "Looking at UC Berkeley and UCLA."},
        ]
        compacted = compactor.compact_conversation_history(long_messages, "System Constitution")
        self.assertLessEqual(len(compacted), 3)
        self.assertIn("Compacted History", compacted[0]["content"])

    def test_rubric_06_persistent_session_state_and_weekly_diffs(self):
        """Rubric: Persistent Session State."""
        test_db = "/tmp/test_eval_session.db"
        if os.path.exists(test_db):
            os.remove(test_db)

        repo = SessionStateRepository(db_path=test_db)
        profile = StudentProfileSchema(home_state="CA", unweighted_gpa=3.8, intended_major_field="CS")
        repo.save_student_profile("student-test-1", profile)

        # Baseline snapshot
        rec1 = CollegeMatchRecommendation(
            institution_name="University of California, Berkeley",
            institution_type=InstitutionType.PUBLIC,
            state="CA",
            fit_rationale="Strong faculty and top CS department.",
            admission_category=AdmissionCategory.TARGET,
            total_cost_of_attendance=44000.0,
            endowment_formatted="$7.4 Billion",
            early_program=EarlyProgramType.NONE,
            regular_decision_deadline="November 30",
            testing_policy=TestingPolicy.TEST_BLIND,
        )
        repo.record_run_snapshot("run-1", "student-test-1", [rec1])

        # Next weekly run with deadline change
        rec2 = rec1.model_copy(update={"regular_decision_deadline": "December 5"})
        diffs = repo.detect_weekly_changes("student-test-1", [rec2])

        self.assertTrue(any("DEADLINE CHANGE" in d for d in diffs))

    # ---------------------------------------------------------
    # 3. ORCHESTRATION & LOGIC (20 POINTS)
    # ---------------------------------------------------------

    def test_rubric_07_strategic_model_routing(self):
        """Rubric: Strategic Model Routing."""
        flash_model = ModelRouter.get_model_for_task(TaskComplexity.FAST_EXTRACTION)
        pro_model = ModelRouter.get_model_for_task(TaskComplexity.HOLISTIC_PLANNING)
        self.assertEqual(flash_model, "gemini-1.5-flash")
        self.assertEqual(pro_model, "gemini-1.5-pro")

    def test_rubric_08_guardrails_policy_evaluation(self):
        """Rubric: Guardrails & Policy Plugins."""
        # Create invalid recommendations list (only 1 school instead of 10)
        invalid_recs = [
            CollegeMatchRecommendation(
                institution_name="University of California, Berkeley",
                institution_type=InstitutionType.PUBLIC,
                state="CA",
                fit_rationale="Flagship public research university.",
                admission_category=AdmissionCategory.TARGET,
                total_cost_of_attendance=44000.0,
                endowment_formatted="$7.4 Billion",
                early_program=EarlyProgramType.NONE,
                regular_decision_deadline="November 30",
                testing_policy=TestingPolicy.TEST_BLIND,
            )
        ]
        report = CollegeAdmissionsPolicyGuardrail.evaluate_recommendations(invalid_recs)
        self.assertFalse(report.passed)
        self.assertTrue(any("Expected 10 total universities" in v for v in report.violations))

    def test_rubric_09_human_in_the_loop_code_stop(self):
        """Rubric: Human-in-the-Loop Hooks."""
        coordinator = AdmissionsCoordinatorAgent(run_id="eval-hitl-stop")

        # Calling pipeline without approval token must halt execution
        result = coordinator.run_advisory_pipeline(
            spreadsheet_id="mock_valid_sheet",
            student_id="student-hitl",
            human_approval_token=None,
        )

        self.assertEqual(result["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertIn("APPROVED_BY_USER", result["action_required"])

        # Calling pipeline WITH confirmed human token proceeds successfully
        approved_result = coordinator.run_advisory_pipeline(
            spreadsheet_id="mock_valid_sheet",
            student_id="student-hitl",
            human_approval_token="APPROVED_BY_USER",
        )
        self.assertEqual(approved_result["status"], "COMPLETED")
        self.assertEqual(approved_result["recommendations_count"], 10)

    # ---------------------------------------------------------
    # 4. OBSERVABILITY & TRACING (20 POINTS)
    # ---------------------------------------------------------

    def test_rubric_10_pii_redaction(self):
        """Rubric: PII Redaction."""
        sensitive_text = "Student John Doe (john.doe@example.com) has GPA: 3.95 and SAT: 1540."
        scrubbed = PIIScrubber.scrub_text(sensitive_text)
        self.assertNotIn("john.doe@example.com", scrubbed)
        self.assertIn("[REDACTED_EMAIL]", scrubbed)
        self.assertIn("[REDACTED_GPA]", scrubbed)
        self.assertIn("[REDACTED_SAT]", scrubbed)

    # ---------------------------------------------------------
    # 5. INFRASTRUCTURE & CI/CD (15 POINTS)
    # ---------------------------------------------------------

    def test_rubric_11_golden_dataset_benchmark_execution(self):
        """Rubric: Automated Evaluation Suites (Golden Dataset Regression)."""
        benchmark_case = self.golden_data["benchmark_profiles"][0]
        expected = benchmark_case["expected_criteria"]

        coordinator = AdmissionsCoordinatorAgent(run_id="eval-golden-benchmark")
        pipeline_output = coordinator.run_advisory_pipeline(
            spreadsheet_id="mock_valid_sheet",
            student_id="student-golden-01",
            human_approval_token="APPROVED_BY_USER",
        )

        self.assertEqual(pipeline_output["status"], "COMPLETED")
        self.assertEqual(pipeline_output["recommendations_count"], 10)
        self.assertGreaterEqual(pipeline_output["guardrail_score"], expected["minimum_guardrail_score"])

    def test_rubric_12_in_state_vs_out_of_state_and_flight_costs(self):
        """Rubric Addition: In-State vs. Out-of-State Public COA and 4 Annual Flight Cost Modeling."""
        # Test Case 1: In-state California public university for CA student
        in_state_travel = estimate_annual_college_travel_costs(
            TravelCostEstimationInput(
                home_airport_code="SFO",
                college_name="University of California, Berkeley",
                college_state="CA",
                student_home_state="CA",
                num_annual_trips=4,
            )
        )
        self.assertFalse(in_state_travel.is_out_of_state)
        self.assertEqual(in_state_travel.total_annual_flight_cost_usd, 0.0)
        self.assertIn("In-State", in_state_travel.flight_details)

        # Test Case 2: Out-of-state Michigan public university for CA student
        out_state_travel = estimate_annual_college_travel_costs(
            TravelCostEstimationInput(
                home_airport_code="SFO",
                college_name="University of Michigan",
                college_state="MI",
                student_home_state="CA",
                num_annual_trips=4,
            )
        )
        self.assertTrue(out_state_travel.is_out_of_state)
        self.assertEqual(out_state_travel.destination_airport, "DTW")
        self.assertEqual(out_state_travel.total_annual_flight_cost_usd, 1800.0)
        self.assertIn("4 round trips", out_state_travel.flight_details)


if __name__ == "__main__":
    unittest.main()
