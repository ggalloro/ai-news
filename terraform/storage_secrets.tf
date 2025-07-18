# --- Google Cloud Storage ---

resource "google_storage_bucket" "audio_summaries" {
  project       = var.project_id
  name          = var.gcs_bucket_name
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  depends_on = [google_project_service.storage]
}

# Make the bucket public for the simple webapp
resource "google_storage_bucket_iam_member" "public_viewer" {
  bucket = google_storage_bucket.audio_summaries.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
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
