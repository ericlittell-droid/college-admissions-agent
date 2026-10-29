"""Structured JSON Logging with Intent vs. Outcome Capture.

Implements structured logging capturing execution timestamps, agent identifiers,
correlation run IDs, explicit Intent vs. Outcome pairs, and automated PII redaction.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any
from observability.pii_scrubber import PIIScrubber


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that renders records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "structured_data"):
            log_payload.update(record.structured_data)

        # Active PII scrubbing on all structured log outputs
        scrubbed_payload = PIIScrubber.scrub_dict(log_payload)
        return json.dumps(scrubbed_payload)


# Configure root JSON logger
logger = logging.getLogger("CollegeAdmissionsAgent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)


class StructuredAgentLogger:
    """Specialized agent logger recording Intent before execution and Outcome after."""

    def __init__(self, agent_name: str, run_id: str | None = None):
        """Initializes logger for a specific agent role and run correlation ID."""
        self.agent_name = agent_name
        self.run_id = run_id or "run-default"

    def log_intent(
        self,
        action_name: str,
        intent_description: str,
        parameters: dict[str, Any] | None = None,
    ) -> float:
        """Records the agent's intended action before invoking an external tool or LLM step.

        Args:
            action_name: Functional action identifier (e.g. 'query_college_scorecard_api').
            intent_description: Human-readable rationale of what the agent aims to achieve.
            parameters: Action parameters (will be scrubbed for PII).

        Returns:
            Timestamp float to calculate execution latency upon completion.
        """
        start_time = time.time()
        extra_data = {
            "structured_data": {
                "event_type": "AGENT_INTENT",
                "run_id": self.run_id,
                "agent_name": self.agent_name,
                "action_name": action_name,
                "intent": intent_description,
                "parameters": parameters or {},
            }
        }
        logger.info(f"[{self.agent_name}] Intent: {intent_description}", extra=extra_data)
        return start_time

    def log_outcome(
        self,
        action_name: str,
        start_time: float,
        status: str,
        outcome_summary: str,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        """Records the actual outcome, status, and latency after an action completes.

        Args:
            action_name: Matching functional action identifier.
            start_time: Start timestamp float returned by log_intent().
            status: 'SUCCESS', 'FAILED', 'BLOCKED_BY_GUARDRAIL', or 'RECOVERED'.
            outcome_summary: Summary of results achieved.
            result_payload: Structured result payload (scrubbed for PII).
        """
        latency_ms = round((time.time() - start_time) * 1000, 2)
        extra_data = {
            "structured_data": {
                "event_type": "AGENT_OUTCOME",
                "run_id": self.run_id,
                "agent_name": self.agent_name,
                "action_name": action_name,
                "status": status,
                "outcome": outcome_summary,
                "latency_ms": latency_ms,
                "result": result_payload or {},
            }
        }
        log_method = logger.error if status == "FAILED" else logger.info
        log_method(f"[{self.agent_name}] Outcome ({status}): {outcome_summary} [{latency_ms}ms]", extra=extra_data)
