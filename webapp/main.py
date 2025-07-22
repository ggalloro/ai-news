from flask import Flask, render_template
from google.cloud import storage
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.auth import impersonated_credentials, default
import requests
import os
import base64
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote

app = Flask(__name__)

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
SERVICE_ACCOUNT_EMAIL = os.environ.get("SERVICE_ACCOUNT_EMAIL")

def get_access_token():
    """Get an access token from the metadata server."""
    metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    headers = {"Metadata-Flavor": "Google"}
    response = requests.get(metadata_url, headers=headers)
    return response.json()["access_token"]

def generate_signed_url(bucket_name, object_name, expiration_minutes=1440):
    """Generate a signed URL using impersonated credentials."""
    try:
        # Get default credentials 
        source_credentials, project = default()
        
        # Create impersonated credentials for the target service account
        target_credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=SERVICE_ACCOUNT_EMAIL,
            target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
        )
        
        # Create storage client with impersonated credentials
        storage_client = storage.Client(credentials=target_credentials)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        # Generate signed URL using the blob's method (24 hours = 1440 minutes)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        
        return signed_url
        
    except Exception as e:
        print(f"Error generating signed URL: {e}")
        # Fallback to public URL if signing fails  
        return f"https://storage.googleapis.com/{bucket_name}/{object_name}"

@app.route('/')
def list_summaries():
    """Lists audio summary files from GCS and generates signed URLs for secure access."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blobs = bucket.list_blobs()

        files = []
        for blob in blobs:
            if blob.name.endswith('.mp3'):
                # Generate signed URL for secure access
                signed_url = generate_signed_url(GCS_BUCKET_NAME, blob.name)
                files.append({'name': blob.name, 'url': signed_url})
        
        files.sort(key=lambda x: x['name'], reverse=True)
        return render_template('index.html', files=files)
        
    except Exception as e:
        import traceback
        print(f"An error occurred: {e}")
        traceback.print_exc()
        return "Error: Could not retrieve audio files. Please check application logs.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))