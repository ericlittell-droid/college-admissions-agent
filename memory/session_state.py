"""Persistent Session State and Weekly Run Snapshot Repository.

Manages conversational state, student profile history, and cross-run university
snapshots across weekly Tuesday executions using a persistent SQLite database.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Any
from config.settings import settings
from schemas.student import StudentProfileSchema
from schemas.college import CollegeMatchRecommendation


class SessionStateRepository:
    """Persistent storage engine for agent state and weekly diff tracking."""

    def __init__(self, db_path: str | None = None):
        """Initializes database connection and ensures tables exist."""
        self.db_path = db_path or settings.session_database_path
        self._init_db()

    def _init_db(self) -> None:
        """Creates tables for sessions, student profiles, and historical recommendations."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Student Profile Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id TEXT PRIMARY KEY,
                    home_state TEXT NOT NULL,
                    unweighted_gpa REAL NOT NULL,
                    sat_score INTEGER,
                    intended_major TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Weekly Execution Snapshots Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS weekly_run_snapshots (
                    run_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    execution_timestamp TEXT NOT NULL,
                    recommendations_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(student_id) REFERENCES student_profiles(student_id)
                )
                """
            )
            conn.commit()

    def save_student_profile(self, student_id: str, profile: StudentProfileSchema) -> None:
        """Upserts a student profile into the persistent store."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO student_profiles (student_id, home_state, unweighted_gpa, sat_score, intended_major, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    home_state=excluded.home_state,
                    unweighted_gpa=excluded.unweighted_gpa,
                    sat_score=excluded.sat_score,
                    intended_major=excluded.intended_major,
                    updated_at=excluded.updated_at
                """,
                (
                    student_id,
                    profile.home_state,
                    profile.unweighted_gpa,
                    profile.sat_score,
                    profile.intended_major_field,
                    now,
                ),
            )
            conn.commit()

    def record_run_snapshot(
        self,
        run_id: str,
        student_id: str,
        recommendations: list[CollegeMatchRecommendation],
        status: str = "COMPLETED",
    ) -> None:
        """Saves a completed recommendation snapshot for this week's run."""
        now = datetime.now(timezone.utc).isoformat()
        serialized_recs = json.dumps([r.model_dump() for r in recommendations])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO weekly_run_snapshots (run_id, student_id, execution_timestamp, recommendations_json, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, student_id, now, serialized_recs, status),
            )
            conn.commit()

    def get_latest_previous_run(
        self, student_id: str
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """Retrieves the most recent prior execution snapshot for diff comparison."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, recommendations_json FROM weekly_run_snapshots
                WHERE student_id = ? AND status = 'COMPLETED'
                ORDER BY execution_timestamp DESC LIMIT 1
                """,
                (student_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            run_id, raw_json = row
            return run_id, json.loads(raw_json)

    def detect_weekly_changes(
        self, student_id: str, current_recommendations: list[CollegeMatchRecommendation]
    ) -> list[str]:
        """Compares current recommendations with the previous week's snapshot.

        Detects changes in:
        1. Newly added or dropped universities.
        2. Deadline shifts (e.g. Regular Decision moved).
        3. Cost changes (tuition increase).
        4. Testing policy modifications.

        Returns:
            List of human-readable diff change notices.
        """
        prior_run = self.get_latest_previous_run(student_id)
        if not prior_run:
            return ["Initial baseline execution. No prior weekly snapshot found."]

        _, prior_recs = prior_run
        prior_by_name = {r["institution_name"].lower(): r for r in prior_recs}
        diff_notices: list[str] = []

        for curr in current_recommendations:
            name_key = curr.institution_name.lower()
            if name_key not in prior_by_name:
                diff_notices.append(f"NEW ADDITION: '{curr.institution_name}' added to match list.")
                continue

            old = prior_by_name[name_key]

            # Check regular decision deadline
            if curr.regular_decision_deadline != old.get("regular_decision_deadline"):
                diff_notices.append(
                    f"DEADLINE CHANGE: '{curr.institution_name}' regular deadline updated from "
                    f"'{old.get('regular_decision_deadline')}' to '{curr.regular_decision_deadline}'."
                )

            # Check testing policy
            curr_policy_val = curr.testing_policy.value if hasattr(curr.testing_policy, "value") else str(curr.testing_policy)
            old_policy_val = old.get("testing_policy")
            if curr_policy_val != old_policy_val:
                diff_notices.append(
                    f"TESTING POLICY CHANGE: '{curr.institution_name}' shifted policy from "
                    f"'{old_policy_val}' to '{curr_policy_val}'."
                )

            # Check significant cost shifts (> $1000)
            old_cost = old.get("total_cost_of_attendance") or 0.0
            if abs(curr.total_cost_of_attendance - old_cost) > 1000:
                diff_notices.append(
                    f"COST OF ATTENDANCE CHANGE: '{curr.institution_name}' updated from "
                    f"${old_cost:,.0f} to ${curr.total_cost_of_attendance:,.0f}."
                )

        return diff_notices if diff_notices else ["No changes detected since prior weekly run."]
