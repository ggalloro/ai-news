import os
import json
import feedparser
import requests
from time import mktime
from datetime import datetime, timezone
import sys
import traceback

from google.cloud import texttospeech, storage, secretmanager
from pydub import AudioSegment
from google import genai

# --- Configuration ---
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
PROJECT_ID = os.environ.get("PROJECT_ID")
GEMINI_SECRET_NAME = "gemini-api-key"

RSS_FEEDS = [
    "https://deepmind.google/blog/rss.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "https://openai.com/blog/rss.xml",
    "https://simonwillison.net/atom/everything/"
]

LAST_PROCESSED_FILE = "last_processed_entries.json"

def get_gemini_key():
    """Fetches the Gemini API key from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{GEMINI_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def get_new_rss_entries(feed_urls, last_times):
    """
    Fetches new entries from a list of RSS feeds, ensuring a balanced selection.
    """
    all_new_entries = []
    latest_times = last_times.copy()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    headers = {'User-Agent': user_agent}
    
    for url in feed_urls:
        print(f"Fetching feed: {url}")
        feed_entries = []
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching feed with requests: {e}")
            continue
        except Exception as e:
            print(f"  Error parsing feed: {e}")
            continue

        if not feed.entries:
            print(f"  No entries found in feed: {url}")
            continue

        last_processed_dt = datetime.fromtimestamp(last_times.get(url, 0), tz=timezone.utc)
        for entry in feed.entries:
            if 'published_parsed' not in entry or not entry.published_parsed:
                continue
            entry_dt = datetime.fromtimestamp(mktime(entry.published_parsed)).replace(tzinfo=timezone.utc)
            if entry_dt > last_processed_dt:
                feed_entries.append(entry)
                if entry_dt.timestamp() > latest_times.get(url, 0):
                    latest_times[url] = entry_dt.timestamp()
        
        # Sort entries for this feed by date and take the most recent 3
        feed_entries.sort(key=lambda e: e.published_parsed, reverse=True)
        all_new_entries.extend(feed_entries[:3])

    # Sort all collected entries by date to ensure a chronological podcast
    all_new_entries.sort(key=lambda e: e.published_parsed)
    return all_new_entries, latest_times

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
        - **DO NOT** use any Markdown formatting (e.g., no asterisks, no hashes, no lists).
        - **DO NOT** begin with conversational filler like "Of course, here is a summary..." or "Here is a summary...".
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

def text_to_audio_segment(text, tts_client, temp_dir, voice, audio_config):
    """Converts a single text string to a pydub AudioSegment."""
    if not text.strip():
        return None
    synthesis_input = texttospeech.SynthesisInput(text=text)
    response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    temp_audio_path = os.path.join(temp_dir, f"segment_{hash(text)}.mp3")
    with open(temp_audio_path, "wb") as out:
        out.write(response.audio_content)
    return AudioSegment.from_mp3(temp_audio_path)

def generate_and_upload_stitched_audio(summaries, bucket_name):
    if not summaries:
        print("No summaries to generate audio for.")
        return None
    try:
        tts_client = texttospeech.TextToSpeechClient()
        storage_client = storage.Client()
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Studio-O")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        temp_dir = "/tmp/temp_audio"
        os.makedirs(temp_dir, exist_ok=True)
        all_audio_segments = []
        intro_text = "Good morning, and welcome to your AI briefing. Here is the latest news."
        intro_segment = text_to_audio_segment(intro_text, tts_client, temp_dir, voice, audio_config)
        if intro_segment:
            all_audio_segments.append(intro_segment)
        for summary in summaries:
            title_text = f"The next story is titled: {summary['title']}."
            summary_text = summary['summary']
            title_segment = text_to_audio_segment(title_text, tts_client, temp_dir, voice, audio_config)
            if title_segment:
                all_audio_segments.append(title_segment)
            char_limit = 4800
            text_chunks = [summary_text[i:i + char_limit] for i in range(0, len(summary_text), char_limit)]
            for chunk in text_chunks:
                summary_segment = text_to_audio_segment(chunk, tts_client, temp_dir, voice, audio_config)
                if summary_segment:
                    all_audio_segments.append(summary_segment)
        outro_text = "And that's all for your briefing today. Thanks for listening."
        outro_segment = text_to_audio_segment(outro_text, tts_client, temp_dir, voice, audio_config)
        if outro_segment:
            all_audio_segments.append(outro_segment)
        if not all_audio_segments:
            print("No audio segments were generated.")
            return None
        final_audio = sum(all_audio_segments)
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_name = f"summary-{today_str}.mp3"
        local_path = os.path.join(temp_dir, file_name)
        final_audio.export(local_path, format="mp3")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.upload_from_filename(local_path)
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)
        return blob.public_url
    except Exception as e:
        print(f"An error occurred during audio generation and upload: {e}")
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        return None

def main():
    """Main execution logic for the Cloud Run Job."""
    print("Starting RSS audio generation job...")
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(LAST_PROCESSED_FILE)
        last_processed_times = {}
        
        if blob.exists():
            try:
                last_processed_times = json.loads(blob.download_as_string())
            except Exception as e:
                print(f"Could not parse last processed times file, starting fresh. Error: {e}")
        
        new_entries, latest_times = get_new_rss_entries(RSS_FEEDS, last_processed_times)

        if new_entries:
            gemini_api_key = get_gemini_key()
            individual_summaries = summarize_entries(new_entries, gemini_api_key)
            public_url = generate_and_upload_stitched_audio(individual_summaries, GCS_BUCKET_NAME)
            
            if public_url:
                print(f"Successfully generated and uploaded audio: {public_url}")
                blob.upload_from_string(json.dumps(latest_times, indent=4))
                print("Job finished successfully.")
                sys.exit(0)
            else:
                print("Job failed during audio generation.")
                sys.exit(1)
        else:
            print("No new entries found. Job finished successfully.")
            sys.exit(0)
            
    except Exception as e:
        print(f"A critical error occurred: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()