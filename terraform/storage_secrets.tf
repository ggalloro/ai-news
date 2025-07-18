# --- Google Cloud Storage ---

resource "google_storage_bucket" "audio_summaries" {
  name          = var.gcs_bucket_name
  location      = var.region
  force_destroy = true # Set to false in a real production environment

  uniform_bucket_level_access = true
}

# This makes the bucket public, which is required for the reverted, simpler webapp.
# In a production scenario, you would remove this and implement Signed URLs.
resource "google_storage_bucket_iam_member" "public_viewer" {
  bucket = google_storage_bucket.audio_summaries.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}


# --- Google Secret Manager ---

resource "google_secret_manager_secret" "gemini_api_key_secret" {
  secret_id = "gemini-api-key"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key_version" {
  secret      = google_secret_manager_secret.gemini_api_key_secret.id
  secret_data = var.gemini_api_key
}
