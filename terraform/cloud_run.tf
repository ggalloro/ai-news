# --- Artifact Registry ---

resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "app-images"
  format        = "DOCKER"

depends_on = [
    google_project_service.artifactregistry
  ]

}

# --- Cloud Build and Deploy ---

# Build the Job container image
resource "null_resource" "build_job_image" {
  triggers = {
    # This will re-build the image if any file in the directory changes
    source_hash = filesha256("../job/main.py")
  }

  provisioner "local-exec" {
    command = "gcloud builds submit ../job --tag ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/rss-audio-generator-job:latest --project=${var.project_id}"
  }

  depends_on = [time_sleep.iam_wait]
}

# Build the Webapp container image
resource "null_resource" "build_webapp_image" {
  triggers = {
    source_hash = filesha256("../webapp/main.py")
  }

  provisioner "local-exec" {
    command = "gcloud builds submit ../webapp --tag ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/rss-summaries-webapp:latest --project=${var.project_id}"
  }

  depends_on = [time_sleep.iam_wait]
}

# --- Cloud Run Job (Audio Generator) ---

resource "google_cloud_run_v2_job" "rss_audio_generator" {
  name     = "rss-audio-generator-job"
  location = var.region
  depends_on = [null_resource.build_job_image]

  template {
    task_count = 1
    template {
      service_account = google_service_account.job_runner_sa.email
      max_retries     = 1
      timeout         = "3600s" # 1 hour

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/rss-audio-generator-job:latest"
        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "GCS_BUCKET_NAME"
          value = var.gcs_bucket_name
        }
        env {
          name = "PYTHONUNBUFFERED"
          value = "1"
        }
      }
    }
  }
}

# --- Cloud Run Service (Web App) ---

resource "google_cloud_run_v2_service" "rss_summaries_webapp" {
  name       = "rss-summaries-webapp"
  location   = var.region
  depends_on = [null_resource.build_webapp_image]

  template {
    service_account = google_service_account.webapp_sa.email
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/rss-summaries-webapp:latest"
      ports {
        container_port = 8080
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = var.gcs_bucket_name
      }
      env {
        name  = "SERVICE_ACCOUNT_EMAIL"
        value = google_service_account.webapp_sa.email
      }
    }
  }
}

# Access control - either public or IAP-protected
resource "google_cloud_run_v2_service_iam_member" "webapp_public_access" {
  count    = length(var.iap_allowed_emails) == 0 ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.rss_summaries_webapp.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Note: When IAP is enabled on Cloud Run directly, no additional IAM bindings are needed
# IAP handles authentication and authorization automatically