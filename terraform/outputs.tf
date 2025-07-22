output "webapp_url" {
  description = "The URL of the deployed web application."
  value       = google_cloud_run_v2_service.rss_summaries_webapp.uri
}

output "iap_configuration" {
  description = "IAP configuration status"
  value = {
    enabled         = length(var.iap_allowed_emails) > 0
    allowed_emails  = var.iap_allowed_emails
    oauth_client_id = length(var.iap_allowed_emails) > 0 && length(google_iap_client.webapp_client) > 0 ? google_iap_client.webapp_client[0].client_id : null
    message         = length(var.iap_allowed_emails) > 0 ? "IAP enabled" : "IAP not configured - webapp is publicly accessible"
  }
}
