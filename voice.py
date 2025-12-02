import os
import subprocess
import whisper
import tempfile

import asyncio
import emoji
from functools import lru_cache

# Load model only once to save time during reload
@lru_cache(maxsize=1)
def load_whisper_model():
    print("Loading Whisper model...")
    return whisper.load_model("base") # "base" is a good balance of speed/accuracy for Mac

model = load_whisper_model()

def get_available_voices():
    """
    Returns a list of high-quality Edge-TTS voices.
    """
    return [
        "en-US-AriaNeural",
        "en-US-GuyNeural",
        "en-US-JennyNeural",
        "en-GB-SoniaNeural",
        "en-GB-RyanNeural",
        "en-AU-NatashaNeural",
        "en-AU-WilliamNeural",
        "en-CA-ClaraNeural",
        "en-CA-LiamNeural"
    ]

import re

# Global variable to track the current speech process
current_process = None

def stop_speaking():
    """
    Stops the current speech process if it's running.
    """
    global current_process
    
    # Aggressively kill all afplay instances to ensure silence
    try:
        subprocess.run(["killall", "afplay"], stderr=subprocess.DEVNULL)
    except Exception:
        pass

    if current_process:
        try:
            current_process.terminate()
            current_process.wait(timeout=0.5)
        except Exception:
            pass
        finally:
            current_process = None

def speak(text, voice="en-US-AriaNeural"):
    """
    Uses edge-tts to generate speech and plays it using afplay.
    Runs in a subprocess so it doesn't block.
    """
    global current_process
    
    # Stop any previous speech
    stop_speaking()
    
    if not text:
        return
        
    # Remove emojis
    clean_text = emoji.replace_emoji(text, replace='')
    
    # Remove markdown links [text](url) -> text
    clean_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_text)
    
    # Remove code blocks
    clean_text = re.sub(r'```[\s\S]*?```', '', clean_text)
    
    # Remove special characters but keep basic punctuation
    # This removes backslashes, underscores, etc.
    clean_text = re.sub(r'[^a-zA-Z0-9\s.,!?-]', ' ', clean_text)
    
    # Collapse multiple spaces
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Create a temporary file for the audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        output_file = fp.name
    
    # Escape quotes for the command line
    safe_text = clean_text.replace('"', '\\"').replace("'", "\\'")
    
    # Command to generate audio
    # edge-tts --voice en-US-AriaNeural --text "Hello" --write-media output.mp3
    gen_cmd = f'edge-tts --voice "{voice}" --text "{safe_text}" --write-media "{output_file}"'
    
    # Command to play audio (afplay is native macOS audio player)
    play_cmd = f'afplay "{output_file}" && rm "{output_file}"'
    
    # Chain them together
    full_cmd = f'{gen_cmd} && {play_cmd}'
    
    try:
        # Store the process so we can kill it later
        current_process = subprocess.Popen(full_cmd, shell=True)
    except Exception as e:
        print(f"Error speaking: {e}")

def transcribe(audio_bytes):
    """
    Takes raw audio bytes from Streamlit and returns text.
    """
    if audio_bytes is None:
        return None

    # Stop speaking when user provides input
    stop_speaking()

    try:
        # Whisper needs a file path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_bytes.read())
            temp_path = temp_audio.name

        # Transcribe
        result = model.transcribe(temp_path, fp16=False)
        text = result["text"].strip()
        
        # Cleanup
        os.remove(temp_path)
        return text
    except Exception as e:
        print(f"Transcription error: {e}")
        return None


import pyaudio
import wave

def record_until_stopped(stop_event):
    """
    Records audio until the stop_event is set.
    Returns the transcribed text.
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    p = pyaudio.PyAudio()
    
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    print("* Recording started...")
    frames = []
    
    while not stop_event.is_set():
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        
    print("* Recording stopped")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
        filename = fp.name
        
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    # Transcribe
    try:
        result = model.transcribe(filename, fp16=False)
        text = result["text"].strip()
        os.remove(filename)
        return text
    except Exception as e:
        print(f"Transcription error: {e}")
        return None


