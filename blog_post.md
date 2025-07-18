# Make an automatic podcast generator with Gemini and Cloud Run

Imagine waking up to a fresh, personalized podcast summarizing the latest AI news, generated automatically while you sleep. It sounds complex, but by combining the power of Google's Gemini model with the scalability of Cloud Run, you can build this exact application with surprising speed.

In this article, I'll walk you through the architecture and key code snippets of a fully automated AI news podcast generator. We'll see how a serverless backend on Cloud Run can handle the heavy lifting of fetching, summarizing, and generating audio, and how a simple web app can serve the final product. Most interestingly, I'll show you how I used the Gemini CLI as a development partner to write the core logic, turning high-level prompts into functional Python code.

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
              |  (2 CPU, 2GiB Memory, 1-hour timeout)                      |
              |                                                            |
              |  1. Fetches RSS from multiple sources (OpenAI, etc.)       |
              |  2. Calls Gemini API for high-quality summarization        |
              |  3. Calls Text-to-Speech API to generate audio segments    |
              |  4. Stitches audio into a single MP3 file                  |
              |  5. Uploads final MP3 to a private GCS Bucket              |
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

1.  **Cloud Scheduler:** A simple cron job that kicks off the entire process every morning.
2.  **Cloud Run Job:** The heart of the application. This is a containerized Python script that runs on a powerful instance, fetches the content, generates the podcast, and saves it. We use a Cloud Run Job because it's perfect for long-running, batch tasks that need to run to completion.
3.  **Cloud Run Service:** A lightweight, continuously running Flask web application that serves a simple HTML page where you can listen to the generated audio files.
4.  **Cloud Storage & Secret Manager:** Used for securely storing the generated MP3s and the Gemini API key, respectively.

## Building the Backend with Gemini CLI

I used the Gemini CLI to act as a pair programmer, generating the core Python functions based on a few high-level prompts. This approach significantly sped up the development process.

### Prompt 1: Fetching and Balancing the News

My first prompt was to create the core of our application: a Python script that could fetch articles from a list of RSS feeds and ensure a balanced selection of news from each source.

> **Prompt:** "Create a Python function that takes a list of RSS feed URLs, fetches them, and returns a balanced list of the 3 most recent articles from each feed, sorted chronologically."

This resulted in a clean function that uses the `requests` and `feedparser` libraries to do exactly that.

```python
def get_new_rss_entries(feed_urls, last_times):
    """
    Fetches new entries from a list of RSS feeds, ensuring a balanced selection.
    """
    all_new_entries = []
    latest_times = last_times.copy()
    # ... (headers and other setup)
    
    for url in feed_urls:
        print(f"Fetching feed: {url}")
        feed_entries = []
        try:
            # ... (fetches and parses the feed)
        except Exception as e:
            print(f"  Error fetching feed: {e}")
            continue

        # ... (logic to check for last processed time)
        
        # Sort entries for this feed by date and take the most recent 3
        feed_entries.sort(key=lambda e: e.published_parsed, reverse=True)
        all_new_entries.extend(feed_entries[:3])

    # Sort all collected entries by date to ensure a chronological podcast
    all_new_entries.sort(key=lambda e: e.published_parsed)
    return all_new_entries, latest_times
```

### Prompt 2: Intelligent Summarization with Gemini

Next, I needed to summarize the content. The key here was not just to get a summary, but to get one that sounded natural and conversational, as if written for a podcast. This is where prompt engineering becomes crucial.

> **Prompt:** "Write a Python function that takes a list of articles and uses the Gemini 2.5 Pro model to summarize each one. The prompt to the model should instruct it to act as a professional podcast host, writing a clean, conversational paragraph in English suitable for text-to-speech, with no markdown or filler phrases."

The resulting function initializes the modern `google-genai` client and iterates through the articles, using a carefully crafted prompt to get the perfect output.

```python
def summarize_entries(entries, api_key):
    """Summarizes each RSS entry individually in English."""
    if not entries:
        return []
    
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
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt
            )
            individual_summaries.append({'title': entry.title, 'summary': response.text.strip()})
        except Exception as e:
            print(f"    Error summarizing article {entry.title}: {e}")
            individual_summaries.append({'title': entry.title, 'summary': 'Summary not available.'})
            
    return individual_summaries
```

### Prompt 3: Generating and Stitching the Audio

Finally, I needed to turn the text script into a polished audio file.

> **Prompt:** "Create a Python function that takes the list of summaries, generates audio for each using Google's Text-to-Speech API, and stitches them together with an intro and outro using the `pydub` library."

This generated the logic for creating a professional-sounding podcast, complete with an introduction, transitions between articles, and a conclusion.

```python
def generate_and_upload_stitched_audio(summaries, bucket_name):
    if not summaries:
        return None
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
            # ... generate and append title_segment ...
            
            summary_text = summary['summary']
            # ... generate and append summary_segment ...

        # Generate and add the outro
        outro_text = "And that's all for your briefing today. Thanks for listening."
        outro_segment = text_to_audio_segment(outro_text, tts_client, ...)
        if outro_segment:
            all_audio_segments.append(outro_segment)

        # Stitch everything together and upload
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

This project is a powerful example of how modern serverless tools and AI can be combined to create sophisticated, automated content pipelines. By using a Cloud Run Job, we have a robust and scalable backend that can handle intensive processing without timing out. By leveraging the Gemini CLI, we were able to generate the core, high-quality Python code with just a few well-crafted prompts.

The result is a fully automated podcast generator that delivers fresh, relevant content every day. I encourage you to explore the code on the official GitHub repository, deploy it yourself using the provided Terraform configuration, and see what other automated content pipelines you can build.

**GitHub Repo:** [https://github.com/ggalloro/ai-news](https://github.com/ggalloro/ai-news)
