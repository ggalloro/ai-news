# AI News Audio Briefing

This project is a fully automated, cloud-native application that fetches the latest articles from AI-focused RSS feeds, generates a conversational audio summary in Italian, and serves it through a simple web interface.

The entire pipeline is serverless, using Google Cloud Functions for backend processing and Cloud Run for the web frontend.

## Features

- **Automated Content Fetching**: Periodically fetches new articles from configured RSS feeds (OpenAI Blog, Google AI Blog).
- **AI-Powered Summarization**: Uses the Gemini 2.5 Pro model to generate a concise summary for each new article in Italian.
- **Narrative Generation**: Takes the individual summaries and uses Gemini 2.5 Pro again to create a single, cohesive, podcast-style script.
- **High-Quality Audio**: Converts the final narrative script into a natural-sounding Italian voice using Google's WaveNet Text-to-Speech API.
- **Cloud Storage**: Securely stores the generated MP3 audio files in a Google Cloud Storage bucket.
- **Web Interface**: A simple Flask web application, hosted on Cloud Run, that lists and streams all historical audio summaries.
- **Scheduled Execution**: A Cloud Scheduler job automatically triggers the entire process daily, ensuring you always have the latest briefing.

## Project Structure

The project is divided into two main components, following a standard microservices architecture:

```
/
├── function/
│   ├── main.py         # The backend Cloud Function logic
│   └── requirements.txt  # Python dependencies for the function
│
├── webapp/
│   ├── main.py         # The frontend Flask web app logic
│   ├── requirements.txt  # Python dependencies for the web app
│   ├── Dockerfile      # Container definition for Cloud Run
│   └── templates/
│       └── index.html  # HTML template for the web page
│
└── README.md           # This file
```

---

## Cloud Deployment Guide

This guide will walk you through deploying the entire application to Google Cloud.

### Prerequisites

1.  **Google Cloud Project**: You must have a Google Cloud project with billing enabled.
2.  **gcloud CLI**: The [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) must be installed and authenticated (`gcloud auth login`).
3.  **Project ID**: Know your Google Cloud Project ID.
4.  **GCS Bucket Name**: Choose a **globally unique** name for your Cloud Storage bucket (e.g., `your-name-audio-summaries`).
5.  **Gemini API Key**: Have your [Gemini API Key](https://aistudio.google.com/app/apikey) ready.

### Step 1: Initial Google Cloud Setup

Run the following commands in your terminal to configure your cloud environment.

**1. Enable Required APIs**
```bash
gcloud services enable \
    run.googleapis.com \
    cloudfunctions.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    storage.googleapis.com \
    texttospeech.googleapis.com
```

**2. Create the GCS Bucket**
Replace `<YOUR_UNIQUE_BUCKET_NAME>` with the name you chose.
```bash
gcloud storage buckets create gs://<YOUR_UNIQUE_BUCKET_NAME> --location=europe-west1
```

**3. Create a Service Account**
This account will be the identity for your services.
```bash
gcloud iam service-accounts create rss-summarizer-sa --display-name="RSS Summarizer Service Account"
```

**4. Grant Permissions to the Service Account**
Replace `<YOUR_PROJECT_ID>` and `<YOUR_SERVICE_ACCOUNT_EMAIL>` (e.g., `rss-summarizer-sa@<YOUR_PROJECT_ID>.iam.gserviceaccount.com`).
```bash
# Grant access to the specific bucket
gcloud storage buckets add-iam-policy-binding gs://<YOUR_UNIQUE_BUCKET_NAME> \
    --member="serviceAccount:<YOUR_SERVICE_ACCOUNT_EMAIL>" \
    --role="roles/storage.objectAdmin"

# Grant access to Text-to-Speech and Secret Manager at the project level
gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
    --member="serviceAccount:<YOUR_SERVICE_ACCOUNT_EMAIL>" \
    --role="roles/texttospeech.client"

gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
    --member="serviceAccount:<YOUR_SERVICE_ACCOUNT_EMAIL>" \
    --role="roles/secretmanager.secretAccessor"
```

**5. Store Your Gemini API Key in Secret Manager**
Replace `<YOUR_GEMINI_API_KEY>` with your actual key.
```bash
gcloud secrets create gemini-api-key --replication-policy="automatic"
echo -n "<YOUR_GEMINI_API_KEY>" | gcloud secrets versions add gemini-api-key --data-file=-
```

### Step 2: Deploy the Services

**1. Deploy the Backend Cloud Function**
This command deploys the code in the `function/` directory.
```bash
gcloud functions deploy rss-summarizer-function \
    --gen2 \
    --runtime=python311 \
    --region=europe-west1 \
    --source=./function \
    --entry-point=process_rss_feeds \
    --trigger-http \
    --allow-unauthenticated \
    --service-account=<YOUR_SERVICE_ACCOUNT_EMAIL> \
    --set-env-vars=PROJECT_ID=<YOUR_PROJECT_ID>,GCS_BUCKET_NAME=<YOUR_UNIQUE_BUCKET_NAME>
```

**2. Deploy the Frontend Web App**
This command deploys the code in the `webapp/` directory.
```bash
gcloud run deploy rss-summaries-webapp \
    --source=./webapp \
    --platform=managed \
    --region=europe-west1 \
    --allow-unauthenticated \
    --service-account=<YOUR_SERVICE_ACCOUNT_EMAIL> \
    --set-env-vars=GCS_BUCKET_NAME=<YOUR_UNIQUE_BUCKET_NAME>
```

### Step 3: Schedule the Function

This final command creates a job to run your function every morning at 8:00 AM Eastern Time.

First, get your function's URL:
```bash
FUNCTION_URL=$(gcloud functions describe rss-summarizer-function --region=europe-west1 --gen2 --format="value(serviceConfig.uri)")
```

Now, create the scheduler job:
```bash
gcloud scheduler jobs create http daily-rss-summary-job \
    --schedule="0 8 * * *" \
    --uri=$FUNCTION_URL \
    --http-method=POST \
    --time-zone="Europe/Rome"
```

Your application is now fully deployed and automated!

---

## Local Testing

While the backend function is best tested by invoking it in the cloud, the frontend web app can be tested locally.

### Prerequisites

-   Python 3.11+
-   A virtual environment

### Steps to Test the Web App Locally

1.  **Navigate to the webapp directory:**
    ```bash
    cd webapp
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Authenticate to Google Cloud:**
    Your local application needs to authenticate to access the GCS bucket. The easiest way is to use Application Default Credentials.
    ```bash
    gcloud auth application-default login
    ```

5.  **Set Environment Variables:**
    The app needs to know which bucket to read from.
    ```bash
    export GCS_BUCKET_NAME=<YOUR_UNIQUE_BUCKET_NAME>
    ```

6.  **Run the Flask App:**
    ```bash
    flask run
    ```

You can now open your browser to `http://127.0.0.1:5000` to see the web interface.
