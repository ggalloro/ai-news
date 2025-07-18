output "webapp_url" {
  description = "The URL of the deployed web application."
  value       = google_cloud_run_v2_service.rss_summaries_webapp.uri
}
