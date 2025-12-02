import os
import subprocess
import whisper
import tempfile
import speech_recognition as sr
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

def listen_for_wake_word(wake_words=["voiceos", "voice os", "computer", "jarvis"]):
    """
    Listens to the microphone for any of the wake words.
    Returns the command (text after wake word) if detected, else None.
    """
    r = sr.Recognizer()
    r.energy_threshold = 300  # Adjust for background noise
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.5   # Reduce silence needed to end phrase (default 0.8)
    r.non_speaking_duration = 0.3 # Reduce non-speaking duration (default 0.5)
    
    with sr.Microphone() as source:
        print(f"Listening for wake words: {wake_words}...")
        try:
            # Listen with a shorter timeout to fail fast and retry
            audio = r.listen(source, timeout=2, phrase_time_limit=5)
            
            # Save to temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(audio.get_wav_data())
                temp_path = temp_audio.name
            
            # Transcribe
            result = model.transcribe(temp_path, fp16=False)
            text = result["text"].strip()
            os.remove(temp_path)
            
            # Check for wake word (case-insensitive)
            text_lower = text.lower().strip()
            
            # Remove punctuation for check
            text_clean = re.sub(r'[^\w\s]', '', text_lower)
            
            # Check if it STARTS with any wake word
            detected_wake_word = None
            for ww in wake_words:
                if text_clean.startswith(ww):
                    detected_wake_word = ww
                    break
            
            if detected_wake_word:
                print(f"Wake word '{detected_wake_word}' detected! ({text})")
                
                # Extract command
                # We split by the detected wake word
                # Note: This simple split might fail if wake word appears multiple times, 
                # but usually it's at the start.
                # We use the length of the wake word to slice.
                
                # Find the index of the wake word in the clean text? 
                # No, we need to preserve the original text's casing/punctuation for the command if possible,
                # but we are working with lower case for matching.
                
                # Let's just find where the wake word ends in the lower string
                # This is a bit tricky with "voice os" vs "voiceos".
                
                # Simple approach: Replace the wake word with empty string at the start
                # We need to handle "voice os" carefully.
                
                if "voice os" in text_lower and detected_wake_word in ["voiceos", "voice os"]:
                     command = text_lower.split("voice os", 1)[1].strip()
                elif detected_wake_word in text_lower:
                     command = text_lower.split(detected_wake_word, 1)[1].strip()
                else:
                     # Fallback if exact string match fails (unlikely if startswith passed)
                     command = text_lower
                
                # Remove leading punctuation from command
                command = command.lstrip(".,!?- ")
                
                return command
            else:
                print(f"Ignored: {text} (No wake word at start)")
                return None
            
        except sr.WaitTimeoutError:
            pass # No speech detected
        except Exception as e:
            print(f"Listening error: {e}")
            
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

def listen_one_shot(timeout=5, phrase_time_limit=15):
    """
    Listens for a single command immediately and returns the transcribed text.
    """
    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.8
    
    with sr.Microphone() as source:
        print("Listening for command...")
        # Play a sound to indicate listening? 
        # We can do that in the caller.
        
        try:
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            
            # Save to temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(audio.get_wav_data())
                temp_path = temp_audio.name
            
            # Transcribe
            result = model.transcribe(temp_path, fp16=False)
            text = result["text"].strip()
            os.remove(temp_path)
            
            return text
            
        except sr.WaitTimeoutError:
            print("Timeout: No speech detected")
            return None
        except Exception as e:
            print(f"Listening error: {e}")
            return None
