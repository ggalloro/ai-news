# This resource configures Cloud Build to build and push a container image.
# It acts as a data source, meaning the image is only built when `terraform apply` is run.
data "google_cloud_build_trigger" "job_builder" {
  provider = google-beta
  project    = var.project_id
  trigger_id = "placeholder" # This is not used, but required by the provider
  filename   = "cloudbuild.yaml" # Assumes a cloudbuild.yaml, we will create an inline one instead
  
  # We define the build steps inline here
  build {
    step {
      name = "gcr.io/cloud-builders/docker"
      args = [
        "build",
        "-t",
        "${var.region}-docker.pkg.dev/${var.project_id}/cloud-run-source-deploy/rss-audio-generator-job",
        "../function", # Path to the directory with the Dockerfile
      ]
    }
    step {
      name = "gcr.io/cloud-builders/docker"
      args = [
        "push",
        "${var.region}-docker.pkg.dev/${var.project_id}/cloud-run-source-deploy/rss-audio-generator-job",
      ]
    }
  }
}

resource "google_cloud_run_v2_job" "rss_audio_generator" {
  name     = "rss-audio-generator-job"
  location = var.region
  
  template {
    task_count = 1
    template {
      service_account = google_service_account.job_runner_sa.email
      max_retries     = 1
      timeout         = "3600s" # 1 hour

      containers {
        image = data.google_cloud_build_trigger.job_builder.build.images[0]
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

data "google_cloud_build_trigger" "webapp_builder" {
  provider = google-beta
  project    = var.project_id
  trigger_id = "placeholder"
  filename   = "cloudbuild.yaml"

  build {
    step {
      name = "gcr.io/cloud-builders/docker"
      args = [
        "build",
        "-t",
        "${var.region}-docker.pkg.dev/${var.project_id}/cloud-run-source-deploy/rss-summaries-webapp",
        "../webapp",
      ]
    }
    step {
      name = "gcr.io/cloud-builders/docker"
      args = [
        "push",
        "${var.region}-docker.pkg.dev/${var.project_id}/cloud-run-source-deploy/rss-summaries-webapp",
      ]
    }
  }
}

resource "google_cloud_run_v2_service" "rss_summaries_webapp" {
  name     = "rss-summaries-webapp"
  location = var.region

  template {
    service_account = google_service_account.webapp_sa.email
    containers {
      image = data.google_cloud_build_trigger.webapp_builder.build.images[0]
      ports {
        container_port = 8080
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = var.gcs_bucket_name
      }
    }
  }
}

# Make the web app publicly accessible
resource "google_cloud_run_v2_service_iam_member" "webapp_public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.rss_summaries_webapp.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
