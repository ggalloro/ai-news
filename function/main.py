import os
import json
import feedparser
import subprocess
from time import mktime
from datetime import datetime, timezone

from google.cloud import texttospeech, storage, secretmanager
from pydub import AudioSegment
import google.generativeai as genai

# --- Configuration ---
# These values are fetched from environment variables, which are set during deployment.
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
PROJECT_ID = os.environ.get("PROJECT_ID")
GEMINI_SECRET_NAME = "gemini-api-key"

RSS_FEEDS = [
    "https://ai.googleblog.com/atom.xml",
    "https://openai.com/blog/rss.xml"
]

LAST_PROCESSED_FILE = "last_processed_entries.json"

def get_gemini_key():
    """Fetches the Gemini API key from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{GEMINI_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def get_new_rss_entries(feed_urls, last_times):
    """Fetches new entries from a list of RSS feeds."""
    new_entries = []
    latest_times = last_times.copy()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    for url in feed_urls:
        print(f"Fetching feed: {url}")
        temp_file = "/tmp/temp_feed.xml"
        
        try:
            subprocess.run(
                ["curl", "-A", user_agent, "-L", "-o", temp_file, url],
                check=True, capture_output=True
            )
            feed = feedparser.parse(temp_file)
            os.remove(temp_file)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  Error fetching or parsing feed with curl: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            continue

        if not feed.entries:
            print(f"  No entries found in feed: {url}")
            continue

        last_processed_dt = datetime.fromtimestamp(last_times.get(url, 0), tz=timezone.utc)
        for entry in feed.entries:
            entry_dt = datetime.fromtimestamp(mktime(entry.published_parsed)).replace(tzinfo=timezone.utc)
            if entry_dt > last_processed_dt:
                new_entries.append(entry)
                if entry_dt.timestamp() > latest_times.get(url, 0):
                    latest_times[url] = entry_dt.timestamp()

    new_entries.sort(key=lambda e: e.published_parsed)
    return new_entries, latest_times

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

def generate_italian_narrative(summaries, api_key):
    """Takes a list of summaries and generates a single, conversational script in Italian."""
    if not summaries:
        return "Nessuna notizia da riportare oggi."
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-pro')
    summaries_text = ""
    for item in summaries:
        summaries_text += f"Titolo: {item['title']}\nRiepilogo: {item['summary']}\n\n"
    prompt = f"""
    Combina i seguenti riassunti in un unico testo fluido e colloquiale in italiano.
    Inizia con un saluto, come "Buongiorno e benvenuti al vostro briefing sull'intelligenza artificiale."
    Introduci ogni argomento in modo naturale, creando una narrazione coesa.
    Termina con una frase di chiusura.
    IMPORTANTE: Genera solo le parole che devono essere pronunciate. Non includere alcuna formattazione, asterischi, o descrizioni come '[musica]' o 'fine della trasmissione'.

    Ecco i riassunti da combinare:
    {summaries_text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    Error generating narrative script: {e}")
        return "Non è stato possibile generare il copione narrativo."

def generate_and_upload_audio_summary(summary_text, bucket_name):
    """Generates audio and uploads it to GCS using the runtime service account."""
    try:
        # Instantiates clients. The libraries automatically use the function's
        # service account for authentication when running on Google Cloud.
        tts_client = texttospeech.TextToSpeechClient()
        storage_client = storage.Client()

        voice = texttospeech.VoiceSelectionParams(language_code="it-IT", name="it-IT-Wavenet-A")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        
        char_limit = 4800
        text_chunks = [summary_text[i:i + char_limit] for i in range(0, len(summary_text), char_limit)]
        
        audio_segments = []
        temp_dir = "/tmp/temp_audio"
        os.makedirs(temp_dir, exist_ok=True)

        for i, chunk in enumerate(text_chunks):
            if not chunk.strip():
                continue
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            temp_audio_path = os.path.join(temp_dir, f"chunk_{i}.mp3")
            with open(temp_audio_path, "wb") as out:
                out.write(response.audio_content)
            audio_segments.append(AudioSegment.from_mp3(temp_audio_path))
        
        final_audio = sum(audio_segments)
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_name = f"summary-{today_str}.mp3"
        local_path = os.path.join(temp_dir, file_name)
        final_audio.export(local_path, format="mp3")

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.upload_from_filename(local_path)
        
        # Clean up temporary files
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)
        
        return blob.public_url
    except Exception as e:
        print(f"Error generating or uploading audio: {e}")
        return None

def process_rss_feeds(request):
    """Cloud Function entry point."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(LAST_PROCESSED_FILE)
    last_processed_times = {}
    if blob.exists():
        try:
            last_processed_times = json.loads(blob.download_as_string())
        except Exception as e:
            print(f"Could not parse last processed times file, starting fresh. Error: {e}")
    else:
        print("last_processed_entries.json not found, starting fresh.")

    new_entries, latest_times = get_new_rss_entries(RSS_FEEDS, last_processed_times)

    if new_entries:
        gemini_api_key = get_gemini_key()
        individual_summaries = summarize_entries(new_entries, gemini_api_key)
        narrative_script = generate_italian_narrative(individual_summaries, gemini_api_key)
        public_url = generate_and_upload_audio_summary(narrative_script, GCS_BUCKET_NAME)
        if public_url:
            print(f"Audio uploaded to: {public_url}")
        blob.upload_from_string(json.dumps(latest_times, indent=4))
        return "Function executed successfully, new articles found."
    else:
        print("No new entries found.")
        return "Function executed successfully, no new articles."