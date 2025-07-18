variable "project_id" {
  description = "The Google Cloud project ID to deploy the resources in."
  type        = string
}

variable "region" {
  description = "The primary Google Cloud region for the resources."
  type        = string
  default     = "europe-west1"
}

variable "scheduler_location" {
  description = "The location for the Cloud Scheduler job (e.g., a region like europe-west2)."
  type        = string
  default     = "europe-west2"
}

variable "gcs_bucket_name" {
  description = "A globally unique name for the GCS bucket that will store the audio files."
  type        = string
}

variable "gemini_api_key" {
  description = "Your Gemini API key. This will be stored in Secret Manager."
  type        = string
  sensitive   = true
}
