# This file enables all the necessary Google Cloud APIs for the application to run.

resource "google_project_service" "run" {
  service = "run.googleapis.com"
}

resource "google_project_service" "cloudbuild" {
  service = "cloudbuild.googleapis.com"
}

resource "google_project_service" "secretmanager" {
  service = "secretmanager.googleapis.com"
}

resource "google_project_service" "cloudscheduler" {
  service = "cloudscheduler.googleapis.com"
}

resource "google_project_service" "storage" {
  service = "storage.googleapis.com"
}

resource "google_project_service" "texttospeech" {
  service = "texttospeech.googleapis.com"
}

resource "google_project_service" "iamcredentials" {
  service = "iamcredentials.googleapis.com"
}

resource "google_project_service" "iam" {
  service = "iam.googleapis.com"
}

resource "google_project_service" "artifactregistry" {
  service = "artifactregistry.googleapis.com"
}

# This is the key addition. Enabling this API triggers the creation of the default compute SA.
resource "google_project_service" "compute" {
  service = "compute.googleapis.com"
}

resource "google_project_service" "iap" {
  service = "iap.googleapis.com"
}