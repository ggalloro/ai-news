# --- Service Accounts ---

resource "google_service_account" "job_runner_sa" {
  account_id   = "job-runner-sa"
  display_name = "Audio Generation Job Runner SA"
}

resource "google_service_account" "webapp_sa" {
  account_id   = "webapp-service-sa"
  display_name = "Web App Service SA"
}

# --- IAM Bindings ---

# Permissions for the Job Runner Service Account
resource "google_project_iam_member" "job_runner_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = google_service_account.job_runner_sa.member
}

resource "google_storage_bucket_iam_member" "job_runner_storage_admin" {
  bucket = google_storage_bucket.audio_summaries.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.job_runner_sa.member
}

# Permissions for the Web App Service Account
resource "google_storage_bucket_iam_member" "webapp_storage_viewer" {
  bucket = google_storage_bucket.audio_summaries.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.webapp_sa.member
}

# *** THIS IS THE CRITICAL FIX ***
# Allow the webapp service account to create signed URLs by giving it permission
# to create tokens for itself.
resource "google_service_account_iam_member" "webapp_sa_token_creator" {
  service_account_id = google_service_account.webapp_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = google_service_account.webapp_sa.member
}


# Permissions for the Cloud Scheduler to invoke the Cloud Run Job
data "google_project" "project" {
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.rss_audio_generator.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute] # Wait for the SA to exist
}

# Grant the service account running `terraform apply` (the default compute SA in this case)
# the necessary permissions to upload source code for Cloud Build.
resource "google_project_iam_member" "terraform_gcloud_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin" # Broad role to ensure it can write to the _cloudbuild bucket
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute] # Wait for the SA to exist
}

# Grant the service account running `terraform apply` the ability to write to Artifact Registry.
resource "google_project_iam_member" "terraform_gcloud_sa_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_project_service.compute] # Wait for the SA to exist
}


# --- IAM Propagation Delay ---
# This resource creates a 2-minute delay to ensure that the IAM permissions
# granted above have propagated throughout Google Cloud before the Cloud Build
# resources try to use them.
resource "time_sleep" "iam_wait" {
  create_duration = "120s"

  depends_on = [
    google_project_iam_member.terraform_gcloud_sa_storage_admin,
    google_project_iam_member.terraform_gcloud_sa_artifact_writer,
  ]
}