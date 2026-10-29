terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# 1. IAM & Service Accounts
# -----------------------------------------------------------------------------

resource "google_service_account" "agent_runner" {
  account_id   = "college-admissions-agent-sa"
  display_name = "College Admissions Agent Runner Service Account"
}

# -----------------------------------------------------------------------------
# 2. Secret Manager (Secure Secret Management - Rubric 5.3)
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "scorecard_api_key" {
  secret_id = "college-scorecard-api-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "agent_secret_access" {
  secret_id = google_secret_manager_secret.scorecard_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_runner.email}"
}

# -----------------------------------------------------------------------------
# 3. Cloud Run Service (Agent Runner)
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "admissions_agent_service" {
  name     = "college-admissions-agent"
  location = var.region

  template {
    service_account = google_service_account.agent_runner.email

    containers {
      image = var.app_image

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_SHEETS_SPREADSHEET_ID"
        value = var.spreadsheet_id
      }

      env {
        name  = "ENABLE_OPENTELEMETRY"
        value = "true"
      }

      env {
        name  = "ENABLE_CLOUD_DLP"
        value = "true"
      }

      env {
        name = "COLLEGE_SCORECARD_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.scorecard_api_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "2000m"
          memory = "2Gi"
        }
      }
    }
  }
}

# -----------------------------------------------------------------------------
# 4. Cloud Scheduler Job (Weekly Tuesday Execution Trigger)
# -----------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "weekly_tuesday_agent_trigger" {
  name             = "weekly-tuesday-college-agent-run"
  description      = "Triggers weekly review of college application deadlines and rankings every Tuesday."
  schedule         = var.scheduler_cron_tuesdays
  time_zone        = "Etc/UTC"
  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.admissions_agent_service.uri}/run-weekly-review"

    oidc_token {
      service_account_email = google_service_account.agent_runner.email
    }

    body = base64encode(jsonencode({
      action                  = "EXECUTE_WEEKLY_REVIEW"
      is_weekly_scheduled_run = true
    }))
  }
}
