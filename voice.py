import os
import subprocess
import whisper
import tempfile
import streamlit as st
import speech_recognition as sr
import asyncio
import emoji

# Load model only once to save time during reload
@st.cache_resource
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

def speak(text, voice="en-US-AriaNeural"):
    """
    Uses edge-tts to generate speech and plays it using afplay.
    Runs in a subprocess so it doesn't block.
    """
    if not text:
        return
        
    # Remove emojis to prevent TTS from reading them (e.g. "waving hand")
    clean_text = emoji.replace_emoji(text, replace='')
    
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
        subprocess.Popen(full_cmd, shell=True)
    except Exception as e:
        print(f"Error speaking: {e}")

def transcribe(audio_bytes):
    """
    Takes raw audio bytes from Streamlit and returns text.
    """
    if audio_bytes is None:
        return None

    try:
        # Whisper needs a file path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_bytes.read())
            temp_path = temp_audio.name

        # Transcribe
        result = model.transcribe(temp_path)
        text = result["text"].strip()
        
        # Cleanup
        os.remove(temp_path)
        return text
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

def listen_for_wake_word(wake_word="voiceos"):
    """
    Listens to the microphone for the wake word.
    Returns the command (text after wake word) if detected, else None.
    """
    r = sr.Recognizer()
    r.energy_threshold = 300  # Adjust for background noise
    r.dynamic_energy_threshold = True
    
    with sr.Microphone() as source:
        print("Listening for wake word...")
        try:
            # Listen with a timeout to avoid hanging forever if no speech
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            
            # Save to temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio.write(audio.get_wav_data())
                temp_path = temp_audio.name
            
            # Transcribe
            result = model.transcribe(temp_path)
            text = result["text"].strip()
            os.remove(temp_path)
            
            print(f"Heard: {text}")
            
            # Check for wake word
            if text.lower().startswith(wake_word.lower()):
                # Return the part after the wake word
                command = text[len(wake_word):].strip()
                # Remove punctuation from start
                command = command.lstrip(",.!? ")
                return command
            
        except sr.WaitTimeoutError:
            pass # No speech detected
        except Exception as e:
            print(f"Listening error: {e}")
            
    return None
