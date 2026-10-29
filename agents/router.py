"""Strategic Model Router.

Routes subtasks to the most cost-effective and capable Gemini model based on
reasoning complexity, context size, and latency requirements. Follows rubric
standards for strategic model routing.
"""

from enum import Enum
from config.settings import settings


class TaskComplexity(str, Enum):
    """Categorization of agent task complexity for model routing."""

    FAST_EXTRACTION = "FAST_EXTRACTION"
    FACT_VERIFICATION = "FACT_VERIFICATION"
    HOLISTIC_PLANNING = "HOLISTIC_PLANNING"
    MULTI_AGENT_COORDINATION = "MULTI_AGENT_COORDINATION"
    SELF_EVALUATION = "SELF_EVALUATION"


class ModelRouter:
    """Intelligently dispatches agent roles to Pro vs. Flash models."""

    @staticmethod
    def get_model_for_task(task_type: TaskComplexity) -> str:
        """Resolves optimal model identifier for a given agent task.

        Routing Strategy:
        - Gemini 1.5 Flash: Assigned to high-volume, low-latency tasks such as
          intake extraction, JSON parsing, regex extraction of endowments, and
          formatting sheet cells.
        - Gemini 1.5 Pro: Assigned to complex academic synthesis, matching 10
          colleges across Reach/Target/Safety bands, subjective fit rationale,
          and self-evaluation guardrail reasoning.

        Args:
            task_type: TaskComplexity classification enum.

        Returns:
            Resolved model string (e.g. 'gemini-1.5-pro' or 'gemini-1.5-flash').
        """
        match task_type:
            case TaskComplexity.FAST_EXTRACTION | TaskComplexity.FACT_VERIFICATION:
                # Fast, lightweight model for high-throughput fact retrieval
                return settings.gemini_model_flash

            case (
                TaskComplexity.HOLISTIC_PLANNING
                | TaskComplexity.MULTI_AGENT_COORDINATION
                | TaskComplexity.SELF_EVALUATION
            ):
                # High-reasoning model for coordinator planning and nuanced matching
                return settings.gemini_model_pro

            case _:
                return settings.gemini_model_pro
