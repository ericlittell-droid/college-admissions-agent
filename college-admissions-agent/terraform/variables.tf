variable "project_id" {
  description = "The Google Cloud Project ID where resources will be provisioned."
  type        = string
  default     = "college-admissions-agent-prod"
}

variable "region" {
  description = "Google Cloud region for Cloud Run and Cloud Scheduler deployment."
  type        = string
  default     = "us-central1"
}

variable "app_image" {
  description = "Container image URL hosted on Artifact Registry."
  type        = string
  default     = "gcr.io/college-admissions-agent-prod/agent:latest"
}

variable "scheduler_cron_tuesdays" {
  description = "Cron schedule expression for running the agent weekly on Tuesdays at 09:00 AM UTC."
  type        = string
  default     = "0 9 * * 2"
}

variable "spreadsheet_id" {
  description = "Target Google Sheets ID for intake and reporting."
  type        = string
  default     = "1G-vcEp97d_ukUkXsBRNl1up_vT5SLgm7V-uSIzIEdPs"
}
