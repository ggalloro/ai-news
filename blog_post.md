# Make an automatic podcast generator with Gemini and Cloud Run

Imagine waking up to a fresh, personalized podcast summarizing the latest AI news, generated automatically while you sleep. It sounds complex, but by combining the power of Google's Gemini model with the scalability of Cloud Run, you can build this exact application with surprising speed.

In this article, I'll walk you through the architecture and key code snippets of a fully automated AI news podcast generator. We'll see how a serverless backend on Cloud Run can handle the heavy lifting of fetching, summarizing, and generating audio, and how a simple web app can serve the final product.

You can find the complete code for this project on GitHub: [https://github.com/ggalloro/ai-news](https://github.com/ggalloro/ai-news)

## The Architecture: A Serverless Pipeline

The application is split into two main serverless components, creating a clean and scalable pipeline from content to listener.

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

1.  **Cloud Scheduler:** A simple cron job that kicks off the entire process every morning.
2.  **Cloud Run Job:** The heart of the application. This containerized Python script runs on a powerful instance to perform the main processing tasks.
3.  **Gemini API:** The core AI service for generating high-quality, conversational summaries.
4.  **Text-to-Speech API:** The service used to convert the generated text summaries into natural-sounding audio.
5.  **Cloud Run Service:** A lightweight, continuously running Flask web application that serves a simple HTML page where you can listen to the generated audio files.
6.  **Cloud Storage & Secret Manager:** Used for securely storing the generated MP3s and the Gemini API key, respectively.

## How the Backend Works

The backend is a Python script designed to run as a Cloud Run Job. It performs a sequence of tasks to create the daily podcast.

### Step 1: Fetching and Balancing the News

The first step is to gather the source material. The script fetches articles from a predefined list of RSS feeds. To ensure the podcast only contains new content, it first checks a `last_processed_entries.json` file in the Cloud Storage bucket. This file stores the timestamp of the last article processed for each feed. Only articles published after that timestamp will be considered.

To ensure the podcast is varied and doesn't just feature the most frequent publisher, the logic then intelligently selects the three most recent *new* articles from *each* feed and sorts the combined list chronologically. After processing, the job updates the timestamp file, ensuring no article is ever processed twice.

```python
def get_new_rss_entries(feed_urls, last_times):
    """
    Fetches new entries from a list of RSS feeds, ensuring a balanced selection.
    """
    all_new_entries = []
    latest_times = last_times.copy()
    # ... (headers and other setup)
    
    for url in feed_urls:
        # ... (fetches and parses the feed)
        
        # Sort entries for this feed by date and take the most recent 3
        feed_entries.sort(key=lambda e: e.published_parsed, reverse=True)
        all_new_entries.extend(feed_entries[:3])

    # Sort all collected entries by date to ensure a chronological podcast
    all_new_entries.sort(key=lambda e: e.published_parsed)
    return all_new_entries, latest_times
```

### Step 2: Intelligent Summarization with Gemini

With the articles collected, the next step is to create the podcast script. For each article, we call the Gemini 2.5 Pro model. The key to getting a high-quality, listenable summary is the prompt. We instruct the model to act as a professional radio journalist, which guides it to produce text that is conversational, engaging, and free of any formatting artifacts that would sound robotic when converted to speech.

```python
def summarize_entries(entries, api_key):
    """Summarizes each RSS entry individually in English."""
    client = genai.Client(api_key=api_key)
    individual_summaries = []
    
    for entry in entries:
        content = entry.get('content', [{}])[0].get('value', entry.get('summary', ''))
        prompt = f"""
        Your role is a professional podcast host writing a script for an English-language audio briefing on Artificial Intelligence.
        Your task is to summarize the following article.
        
        Guidelines for the summary:
        - Write in a natural, conversational, and engaging podcast style.
        - The output must be a clean paragraph of plain text.
        - It must be suitable for direct text-to-speech conversion.

        **CRITICAL INSTRUCTIONS:**
        - **DO NOT** use any Markdown formatting.
        - **DO NOT** begin with conversational filler like "Of course, here is a summary...".
        - **DO NOT** announce what you are doing. Just provide the summary directly.
        
        Article to summarize:
        Title: {entry.title}
        Content: {content}
        """
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt
        )
        individual_summaries.append({'title': entry.title, 'summary': response.text.strip()})
            
    return individual_summaries
```

### Step 3: Generating and Stitching the Audio

The final step is to turn the script into a polished audio file. The application iterates through the generated summaries, calling Google's Text-to-Speech API to create an audio segment for each one. It then uses the `pydub` library to stitch these segments together with a pre-recorded intro and outro, creating a single, professional-sounding MP3 file that is uploaded to Cloud Storage.

```python
def generate_and_upload_stitched_audio(summaries, bucket_name):
    """
    Generates audio for each summary, stitches them together, and uploads to GCS.
    """
    try:
        tts_client = texttospeech.TextToSpeechClient()
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Studio-O")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        
        all_audio_segments = []
        
        # Generate and add the intro
        intro_text = "Good morning, and welcome to your AI briefing. Here is the latest news."
        intro_segment = text_to_audio_segment(intro_text, tts_client, ...)
        if intro_segment:
            all_audio_segments.append(intro_segment)

        # Loop through summaries, creating audio for the title and content
        for summary in summaries:
            title_text = f"The next story is titled: {summary['title']}."
            title_segment = text_to_audio_segment(title_text, tts_client, ...)
            if title_segment:
                all_audio_segments.append(title_segment)
            
            summary_segment = text_to_audio_segment(summary['summary'], tts_client, ...)
            if summary_segment:
                all_audio_segments.append(summary_segment)

        # Generate and add the outro
        outro_text = "And that's all for your briefing today. Thanks for listening."
        outro_segment = text_to_audio_segment(outro_text, tts_client, ...)
        if outro_segment:
            all_audio_segments.append(outro_segment)

        # Stitch everything together using pydub and upload
        final_audio = sum(all_audio_segments)
        
        # ... export and upload to GCS ...
        
        return blob.public_url
    except Exception as e:
        # ... error handling ...
        return None
```

## The Frontend: A Simple Interface

The frontend is a standard Flask application, also containerized and deployed as a Cloud Run Service. Its only job is to list the available MP3 files from the Cloud Storage bucket and present them to the user with a simple HTML5 audio player.

## Conclusion

This project is a powerful example of how modern serverless tools and AI can be combined to create sophisticated, automated content pipelines. By using a Cloud Run Job, we have a robust and scalable backend that can handle intensive processing without timing out, and by leveraging the Gemini model with careful prompting, we can generate high-quality, listenable content.

The result is a fully automated podcast generator that delivers fresh, relevant content every day. I encourage you to explore the code on the official GitHub repository and deploy it yourself using the provided Terraform configuration.

**GitHub Repo:** [https://github.com/ggalloro/ai-news](https://github.com/ggalloro/ai-news)