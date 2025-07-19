# AI News Audio Briefing

This project is a fully automated, cloud-native application that fetches the latest articles from multiple AI-focused RSS feeds, generates a conversational audio podcast, and serves it through a simple web interface.

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
              |                                                            |
              |  1. Fetches RSS from multiple sources                      |
              |  2. Calls Gemini API for summarization                     |
              |  3. Calls Text-to-Speech API for audio generation          |
              |  4. Stitches audio and uploads to GCS                      |
              +-----------------------------+------------------------------+
                                            |
                       +--------------------+--------------------+
                       | (Calls API)        | (Calls API)        |
                       v                    v                    v
+------------------+  +------------------+  +------------------+  +------------------+
|  Secret Manager  |  |    Gemini API    |  | Text-to-Speech   |  |  Cloud Storage   |
+------------------+  +------------------+  +------------------+  +------------------+
                                                                         |
                                                                         | (Serves files to)
                                                                         v
                                                              +---------------------+
                                                              | Cloud Run Service   |
                                                              | (webapp)            |
                                                              +---------------------+
```

## Features

- **Robust and Scalable Backend**: The core logic runs as a **Cloud Run Job**, designed for long-running, reliable batch processing. It's configured with a powerful 2-CPU instance, 2GiB of memory, and a 1-hour timeout, ensuring it can process a large volume of articles without failing.

- **Diverse and Balanced Content Sourcing**: The application fetches the latest articles from a curated list of top-tier AI blogs (DeepMind, OpenAI, Anthropic, etc.). The logic ensures a balanced selection from each source, guaranteeing a varied and interesting daily briefing rather than a monologue from a single publisher.

- **Stateful Processing**: The job is stateful, keeping track of the last article processed from each feed in a `last_processed_entries.json` file in the GCS bucket. This prevents reprocessing of old content and ensures that each daily run only includes what's new.

- **Intelligent, High-Quality Summarization**: Each article is summarized using the **Gemini 2.5 Pro** model. The prompt is carefully engineered to instruct the AI to act as a professional podcast host, producing summaries that are conversational, engaging, and free of technical artifacts like markdown.

- **Professional Audio Production**: The system generates a separate audio segment for each summary using Google's high-fidelity Text-to-Speech API. It then programmatically stitches these segments together with a professionally scripted intro and outro, creating a polished, podcast-style audio file.

- **Secure by Default Architecture**:
  - **Private Storage**: All generated audio files are stored in a **private** Google Cloud Storage bucket, inaccessible from the public internet.
  - **Secure Access**: The web application does not expose public URLs. While the current Terraform setup uses a public bucket for simplicity, the application is architected to be easily switched to a secure model using Signed URLs.
  - **Dedicated Identities**: The backend job and frontend service run with dedicated, least-privilege IAM service accounts, following modern security best practices.

- **Lightweight Web Frontend**: A simple and efficient Flask web application, running as a **Cloud Run Service**, provides a clean user interface for listing and playing the daily audio briefings.

- **Fully Automated and Scheduled**: A **Cloud Scheduler** job automatically triggers the backend process every morning, making the entire pipeline a "set it and forget it" solution.

- **Infrastructure as Code**: The entire cloud infrastructure—from service accounts and APIs to the Cloud Run services themselves—is defined in **Terraform**. This allows for reliable, repeatable, and auditable deployments in any Google Cloud project.

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

## Deploying Application Updates

If you only need to update the application code for the backend job or the frontend web app, you do not need to re-run `terraform apply`. You can deploy updates directly using the `gcloud` CLI.

### Updating the Backend Job (`rss-audio-generator-job`)

After making changes to the code in the `function/` directory:

```bash
gcloud run jobs deploy rss-audio-generator-job \
    --source=./function \
    --project=<YOUR_PROJECT_ID> \
    --region=europe-west1 
```

### Updating the Frontend Web App (`rss-summaries-webapp`)

After making changes to the code in the `webapp/` directory:

```bash
gcloud run deploy rss-summaries-webapp \
    --source=./webapp \
    --project=<YOUR_PROJECT_ID> \
    --region=europe-west1
```

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
