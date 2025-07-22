resource "google_cloud_scheduler_job" "daily_rss_job" {
  name      = "daily-rss-summary-job"
  region    = var.region
  schedule  = "0 6 * * *"
  time_zone = "Europe/Rome"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.rss_audio_generator.name}:run"
    
    oauth_token {
      service_account_email = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"
    }
  }
}
