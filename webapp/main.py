from flask import Flask, render_template
from google.cloud import storage
import os

app = Flask(__name__)

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

@app.route('/')
def list_summaries():
    """Lists the audio summary files from the GCS bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blobs = bucket.list_blobs()
        
        files = [
            {'name': blob.name, 'url': blob.public_url}
            for blob in blobs
            if blob.name.endswith('.mp3')
        ]
        
        files.sort(key=lambda x: x['name'], reverse=True)
        return render_template('index.html', files=files)
        
    except Exception as e:
        return f"Error listing files from bucket: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
