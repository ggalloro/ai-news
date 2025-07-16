# How I Built an AI News Podcast Generator with Google Cloud and Gemini

Every day, there’s a flood of news from the world of Artificial Intelligence. Keeping up can be a challenge. I wanted a simple, automated way to get the latest updates, so I decided to build a personal AI news podcast generator.

This project automatically fetches the latest blog posts from sources like Google and OpenAI, uses the Gemini API to create a summary, converts it into a natural-sounding Italian audio file, and hosts it on a simple webpage.

In this post, I’ll walk you through how I built it. You can find the complete source code on my GitHub repository: [https://github.com/ggalloro/ai-news](https://github.com/ggalloro/ai-news).

## The Architecture: A Tale of Two Services

The application is split into two main parts, which is a common pattern for scalable web services:

1.  **The Backend: A Serverless Cloud Function**
    This is the workhorse. It’s a Python function deployed on Google Cloud Functions that runs on a schedule. Its only job is to find new articles, process them, and save the resulting audio file. Using a serverless function is perfect here because I only pay for the few seconds it runs each day.

2.  **The Frontend: A Containerized Web App**
    This is the user interface. It’s a simple Python web application using the Flask framework. It’s deployed as a container on Google Cloud Run. Its job is to list the audio files created by the backend so I can easily play them.

This separation means the user-facing website is always fast and available, completely independent of the data-processing backend.

## Part 1: The Backend Cloud Function

The backend function does all the heavy lifting in a few distinct steps.

### Step 1: Fetching New RSS Feeds

First, the function checks several RSS feeds for new articles. It keeps track of the last article it processed to avoid creating duplicate summaries. I used the `feedparser` library for this, but had to use `curl` via a subprocess to bypass bot-blocking measures from some sites.

### Step 2: Summarizing with the Gemini API

Once new articles are found, the core logic begins. I use the Gemini API to generate a concise summary for each article in Italian.

Here’s the snippet from `function/main.py` that handles this:

```python
import google.generativeai as genai

def summarize_entries(entries, api_key):
    """Summarizes each RSS entry individually in Italian."""
    if not entries:
        return []
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-pro')
    individual_summaries = []
    for entry in entries:
        content = entry.get('content', [{}])[0].get('value', entry.get('summary', ''))
        prompt = f"Per favore, fornisci un riassunto conciso del seguente articolo in italiano:\n\nTitolo: {entry.title}\n\nContenuto: {content}"
        try:
            response = model.generate_content(prompt)
            individual_summaries.append({'title': entry.title, 'summary': response.text.strip()})
        except Exception as e:
            print(f"    Error summarizing article {entry.title}: {e}")
            individual_summaries.append({'title': entry.title, 'summary': 'Riassunto non disponibile.'})
    return individual_summaries
```

### Step 3: Generating a Cohesive Narrative

A list of separate summaries isn't very engaging. To create a more podcast-like feel, I send all the individual summaries back to the Gemini API with a new prompt, asking it to weave them into a single, conversational script.

### Step 4: Text-to-Speech and Storage

With the final script ready, the function uses Google Cloud's Text-to-Speech service to generate a high-quality MP3 audio file. The `pydub` library is used to stitch together audio chunks if the text is very long.

The final audio file is saved to a Google Cloud Storage bucket, which is a simple and scalable place to store files.

## Part 2: The Frontend Web App

The frontend is a much simpler Flask application. Its only purpose is to display the audio files stored in the Cloud Storage bucket.

### The Flask Backend

The Python code for the web app is minimal. It has a single route (`/`) that uses the `google-cloud-storage` library to list all the `.mp3` files in the bucket. It then passes this list of files to an HTML template.

Here is the core of `webapp/main.py`:

```python
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
```

### The HTML Template

The `index.html` template uses Jinja2 syntax (which is standard for Flask) to loop through the list of files and create an HTML `<audio>` player for each one.

Here’s the relevant part of `webapp/templates/index.html`:

```html
<div class="container">
    <h1>Riepiloghi Audio AI</h1>
    {% if files %}
        {% for file in files %}
            <div class="summary-item">
                <h2>{{ file.name }}</h2>
                <audio controls>
                    <source src="{{ file.url }}" type="audio/mpeg">
                    Il tuo browser non supporta l'elemento audio.
                </audio>
            </div>
        {% endfor %}
    {% else %}
        <p>Nessun riepilogo audio trovato.</p>
    {% endif %}
</div>
```

## Deployment

To make deployment simple and repeatable, I used a `Dockerfile` for the web application. This file defines all the steps needed to create a container image with the Python environment and application code, which can then be easily deployed to Google Cloud Run.

## Conclusion

This was a fun project that combined several powerful cloud services to solve a real problem for me. By leveraging serverless functions, generative AI, and containerization, I was able to build a fully automated pipeline that turns the latest AI news into my own personal podcast.

Feel free to check out the [code on GitHub](https://github.com/ggalloro/ai-news), and let me know if you have any questions
