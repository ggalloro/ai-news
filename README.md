# AI News Audio Briefing

This project is a fully automated, cloud-native application that fetches the latest articles from multiple AI-focused RSS feeds, generates a conversational audio podcast in Italian, and serves it through a simple web interface.

The entire pipeline is serverless, using a powerful **Cloud Run Job** for the backend batch processing and a **Cloud Run Service** for the web frontend. This architecture is designed for performance, scalability, and reliability.

## Architecture Diagram

```
                               +-------------------------+
                               |   Cloud Scheduler       |
                               | (daily-rss-summary-job) |
                               +------------+------------+
                                            | (Triggers daily)
                                            |
              +-----------------------------v------------------------------+
              |  Cloud Run Job (rss-audio-generator-job)                   |
              |  (2 CPU, 2GiB Memory, 1-hour timeout)                      |
              |                                                            |
              |  1. Fetches RSS from multiple sources (OpenAI, etc.)       |
              |  2. Checks GCS for last processed articles                 |
              |  3. Calls Gemini API for high-quality summarization        |
              |  4. Calls Text-to-Speech API to generate audio segments    |
              |  5. Stitches audio into a single MP3 file                  |
              |  6. Uploads final MP3 to GCS Bucket                        |
              |  7. Updates `last_processed_entries.json` state file       |
              +-----------------------------+------------------------------+
                                            |
                                            | (Writes to)
                                            v
+-------------------------+      +-------------------------+      +----------------------------+
|   Secret Manager        |      |   Cloud Storage         |      |   Cloud Run Service        |
| (Stores Gemini API Key) | <----+ (Private GCS Bucket)    +------> | (rss-summaries-webapp)     |
+-------------------------+      +-------------------------+      | (Serves audio files)       |
                                                                  +----------------------------+
```

## Features

- **Robust Batch Processing**: Uses a **Cloud Run Job** with a high-performance 2-CPU instance and a 1-hour timeout, ensuring reliable and fast processing of a large number of articles.
- **Diverse Content**: Fetches and processes a balanced selection of the latest articles from multiple RSS feeds (OpenAI, Anthropic, etc.) to ensure variety.
- **High-Quality Summarization**: Uses the **Gemini 2.5 Pro** model via the modern `google-genai` SDK to generate clean, conversational summaries in Italian.
- **Professional Audio Generation**: Creates a separate audio segment for each summary and stitches them together with a proper intro and outro, resulting in a polished podcast.
- **Secure by Default**: All audio files are stored in a **private** Google Cloud Storage bucket. The web application serves them securely to users and does not require public access.
- **Efficient Web Interface**: A lightweight Flask web application, hosted on Cloud Run, that provides a simple interface to listen to the audio briefings.
- **Fully Automated**: A Cloud Scheduler job triggers the entire process daily, making it a "set it and forget it" pipeline.
- **Infrastructure as Code**: The entire stack can be deployed reliably using the provided Terraform configuration.

## Project Structure

```
/
├── function/
│   ├── main.py         # The backend Cloud Run Job logic
│   ├── Dockerfile      # Container definition for the job
│   └── requirements.txt  # Python dependencies for the job
│
├── webapp/
│   ├── main.py         # The frontend Cloud Run Service logic
│   ├── Dockerfile      # Container definition for the service
│   └── requirements.txt  # Python dependencies for the service
│
├── terraform/
│   ├── main.tf         # Terraform configuration for the entire stack
│   └── ...             # Other Terraform files
│
└── README.md           # This file
```

---

## Cloud Deployment Guide

The recommended way to deploy this application is by using the provided Terraform configuration.

### Prerequisites

1.  [Terraform CLI](https://learn.hashicorp.com/tutorials/terraform/install-cli) installed.
2.  [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth application-default login`).
3.  A Google Cloud project with billing enabled.
4.  Permissions to enable APIs and create all the resources defined in the Terraform configuration (e.g., `Owner` or `Editor` roles).

### Deployment Steps

1.  **Navigate to the Terraform Directory:**
    ```bash
    cd terraform
    ```

2.  **Create a `terraform.tfvars` file:**
    This is the most secure way to provide your project-specific variables. Create the file and add the following content, replacing the placeholder values:
    ```hcl
    project_id      = "your-gcp-project-id"
    gcs_bucket_name = "your-globally-unique-bucket-name"
    gemini_api_key  = "your-gemini-api-key"
    ```

3.  **Initialize Terraform:**
    This command downloads the necessary provider plugins.
    ```bash
    terraform init
    ```

4.  **Plan the Deployment:**
    This command shows you what resources will be created. It's a dry run and is safe to run.
    ```bash
    terraform plan
    ```

5.  **Apply the Configuration:**
    This command will build the container images and deploy all the cloud resources.
    ```bash
    terraform apply
    ```
    Terraform will ask for confirmation. Type `yes` to proceed. The deployment will take several minutes.

6.  **Access Your Application:**
    Once the `apply` command is complete, Terraform will output the URL of your web application.

---

## Local Testing

### Testing the Web App

The web application can be tested locally, but it requires you to have a GCS bucket with audio files already in it.

1.  **Navigate to the webapp directory:**
    ```bash
    cd webapp
    ```
2.  **Activate a virtual environment:**
    ```bash
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Authenticate to Google Cloud:**
    ```bash
    gcloud auth application-default login
    ```
4.  **Set Environment Variables:**
    ```bash
    export GCS_BUCKET_NAME="<YOUR_GCS_BUCKET_NAME>"
    ```
5.  **Run the Flask App:**
    ```bash
    flask --app main run
    ```
    You can now access the web app at `http://127.0.0.1:5000`.

### Testing the Backend Job

The backend job is designed to run in the cloud and relies on the Cloud Run environment's service account and metadata server. Therefore, **local testing of the job is not recommended**. The most reliable way to test it is to trigger it in the cloud after deployment.
