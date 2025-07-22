# --- Identity Aware Proxy (IAP) Configuration for Cloud Run ---

# OAuth consent screen - create automatically via Terraform
resource "google_iap_brand" "project_brand" {
  count             = length(var.iap_allowed_emails) > 0 ? 1 : 0
  support_email     = var.iap_allowed_emails[0]
  application_title = "AI News Audio Briefing"
  project           = var.project_id

  depends_on = [google_project_service.iap]
}

# IAP OAuth client for Cloud Run
resource "google_iap_client" "webapp_client" {
  count        = length(var.iap_allowed_emails) > 0 ? 1 : 0
  display_name = "AI News Webapp IAP Client"
  brand        = google_iap_brand.project_brand[0].name

  depends_on = [google_iap_brand.project_brand]
}

# Configure IAP access for Cloud Run using gcloud command
resource "null_resource" "configure_cloud_run_iap" {
  count = length(var.iap_allowed_emails) > 0 ? 1 : 0

  provisioner "local-exec" {
    command = <<-EOT
      # Enable IAP on the Cloud Run service using beta
      gcloud beta run services update ${google_cloud_run_v2_service.rss_summaries_webapp.name} \
        --platform=managed \
        --region=${var.region} \
        --project=${var.project_id} \
        --iap
      
      # Wait for IAP service account to be created
      sleep 30
      
      # Set IAP access policy (only after IAP is enabled)
      gcloud run services add-iam-policy-binding ${google_cloud_run_v2_service.rss_summaries_webapp.name} \
        --platform=managed \
        --region=${var.region} \
        --project=${var.project_id} \
        --member=serviceAccount:service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com \
        --role=roles/run.invoker
    EOT
  }

  depends_on = [
    google_cloud_run_v2_service.rss_summaries_webapp,
    google_iap_client.webapp_client
  ]

  triggers = {
    service_name = google_cloud_run_v2_service.rss_summaries_webapp.name
    emails       = join(",", var.iap_allowed_emails)
  }
}

# Grant IAP access to users
resource "google_project_iam_member" "iap_users" {
  count   = length(var.iap_allowed_emails) > 0 ? length(var.iap_allowed_emails) : 0
  project = var.project_id
  role    = "roles/iap.httpsResourceAccessor"
  member  = "user:${var.iap_allowed_emails[count.index]}"

  depends_on = [google_iap_client.webapp_client]
}