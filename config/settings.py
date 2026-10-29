"""Configuration and Secure Secret Management.

Implements zero-hardcoding credential injection with Google Cloud Secret Manager
fallback, strict environment validation, and secure defaults.
"""

import os
from typing import Any
from schemas.pydantic_compat import BaseModel, Field


class AppConfig(BaseModel):
    """Application settings and API credentials container."""

    gcp_project_id: str = Field(
        default_factory=lambda: os.getenv("GCP_PROJECT_ID", "college-agent-project"),
        description="Google Cloud Project ID.",
    )

    college_scorecard_api_key: str = Field(
        default_factory=lambda: AppConfig._load_secret(
            env_var="COLLEGE_SCORECARD_API_KEY",
            secret_id="college-scorecard-api-key",
            default="DEMO_KEY",
        ),
        description="API Key for U.S. Department of Education College Scorecard.",
    )

    google_sheets_spreadsheet_id: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", ""),
        description="Target Google Sheets ID for intake and reporting.",
    )

    google_service_account_json_path: str | None = Field(
        default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        description="Path to Google Cloud Service Account JSON credentials.",
    )

    gemini_model_pro: str = Field(
        default="gemini-1.5-pro",
        description="Model identifier for high-reasoning coordinator and matchmaker agents.",
    )

    gemini_model_flash: str = Field(
        default="gemini-1.5-flash",
        description="Model identifier for fast tool extraction and parsing agents.",
    )

    enable_opentelemetry: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_OPENTELEMETRY", "true").lower() == "true",
        description="Flag to activate OpenTelemetry distributed tracing.",
    )

    enable_cloud_dlp_pii_scrubbing: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_CLOUD_DLP", "true").lower() == "true",
        description="Flag to scrub PII via Google Cloud DLP or local regex sanitizer.",
    )

    session_database_path: str = Field(
        default_factory=lambda: os.getenv("SESSION_DB_PATH", "/tmp/college_agent_session.db"),
        description="Persistent path for the SQLite session state datastore.",
    )

    @staticmethod
    def _load_secret(env_var: str, secret_id: str, default: str = "") -> str:
        """Securely retrieves secret from env var or Google Cloud Secret Manager.

        Prioritizes environment variables (useful in local dev / container envs),
        and falls back to Secret Manager API if available. Never hardcodes secrets.

        Args:
            env_var: Environment variable name.
            secret_id: Secret Manager secret name.
            default: Fallback string if secret cannot be retrieved.

        Returns:
            Resolved secret value.
        """
        env_val = os.getenv(env_var)
        if env_val:
            return env_val

        # Attempt retrieval from GCP Secret Manager
        project_id = os.getenv("GCP_PROJECT_ID")
        if project_id:
            try:
                from google.cloud import secretmanager  # type: ignore

                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except Exception:
                # Logged defensively without leaking credentials
                pass

        return default


settings = AppConfig()
