resource "google_cloud_scheduler_job" "daily_rss_job" {
  name             = "daily-rss-summary-job"
  location         = var.scheduler_location
  schedule         = "0 6 * * *"
  time_zone        = "Europe/Rome"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.rss_audio_generator.name}:run"
    
    oauth_token {
      service_account_email = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
    }
  }
}
