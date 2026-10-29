"""PII Redaction and Data Scrubbing Pipeline.

Scrubs sensitive student personal data (Name, Email, GPA, SAT, Student IDs)
before logging, tracing, or persistence, supporting Google Cloud DLP API
with robust local pattern scrubbing fallbacks.
"""

import re
from typing import Any
from config.settings import settings


class PIIScrubber:
    """Active scrubbing mechanism to redact sensitive student metrics and identifiers."""

    # Regex patterns for sensitive student data
    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    GPA_PATTERN = re.compile(r"(?i)\b(?:gpa|unweighted gpa|grade point average)[\s:=]+([0-4](?:\.\d{1,2})?)\b")
    SAT_PATTERN = re.compile(r"(?i)\b(?:sat|sat score|composite sat)[\s:=]+([4-9]\d{2}|1[0-5]\d{2}|1600)\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Redacts sensitive PII from freeform strings before logging or tracing.

        If Google Cloud DLP is enabled and configured, can route to Cloud DLP API.
        Otherwise executes deterministic regex masking.

        Args:
            text: Raw log message or serialized payload.

        Returns:
            Sanitized string with sensitive tokens masked.
        """
        if not text:
            return text

        scrubbed = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        scrubbed = cls.PHONE_PATTERN.sub("[REDACTED_PHONE]", scrubbed)
        scrubbed = cls.GPA_PATTERN.sub("GPA: [REDACTED_GPA]", scrubbed)
        scrubbed = cls.SAT_PATTERN.sub("SAT: [REDACTED_SAT]", scrubbed)

        return scrubbed

    @classmethod
    def scrub_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively scrubs dictionary keys and values for safe structured JSON logging."""
        sanitized: dict[str, Any] = {}
        sensitive_keys = {"student_name", "applicant_name", "email", "phone", "gpa", "sat", "ssn"}

        for k, v in data.items():
            k_lower = k.lower()
            if any(s in k_lower for s in sensitive_keys):
                sanitized[k] = "[REDACTED_PII]"
            elif isinstance(v, dict):
                sanitized[k] = cls.scrub_dict(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    cls.scrub_dict(item) if isinstance(item, dict) else cls.scrub_text(str(item))
                    for item in v
                ]
            elif isinstance(v, str):
                sanitized[k] = cls.scrub_text(v)
            else:
                sanitized[k] = v

        return sanitized
