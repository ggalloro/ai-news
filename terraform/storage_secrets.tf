# --- Google Cloud Storage ---

resource "google_storage_bucket" "audio_summaries" {
  project       = var.project_id
  name          = var.gcs_bucket_name
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
  
  # Ensure bucket is private (not publicly accessible)
  public_access_prevention = "enforced"

  depends_on = [google_project_service.storage]
}

# --- Google Secret Manager ---

resource "google_secret_manager_secret" "gemini_api_key_secret" {
  project   = var.project_id
  secret_id = "gemini-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "gemini_api_key_version" {
  secret      = google_secret_manager_secret.gemini_api_key_secret.id
  secret_data = var.gemini_api_key
}
