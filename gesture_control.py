import cv2
import mediapipe as mp
import time
import threading
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import voice
from loop import agent_loop, APIProvider, PROVIDER_TO_DEFAULT_MODEL_NAME

# Load env
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PROVIDER = os.getenv("API_PROVIDER", "anthropic") or APIProvider.ANTHROPIC
MODEL = PROVIDER_TO_DEFAULT_MODEL_NAME[APIProvider(PROVIDER)]
SYSTEM_PROMPT_SUFFIX = "User is using a gesture-controlled voice assistant. Be EXTREMELY concise. Max 1 sentence."

class GestureController:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self.is_listening = False
        self.stop_event = None
        self.listen_thread = None
        
        self.last_activation_time = 0
        self.cooldown = 2.0 # Seconds between state changes
        
    def is_open_palm(self, hand_landmarks):
        """
        Detects if the hand is an open palm (Start Gesture).
        Criteria: All 4 fingers are extended.
        """
        # Finger tip IDs: 8, 12, 16, 20
        # Finger PIP IDs: 6, 10, 14, 18
        
        extended_fingers = 0
        if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y: extended_fingers += 1
        if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y: extended_fingers += 1
        if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y: extended_fingers += 1
        if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y: extended_fingers += 1
            
        return extended_fingers >= 4

    def is_closed_fist(self, hand_landmarks):
        """
        Detects if the hand is a closed fist (Stop Gesture).
        Criteria: All 4 fingers are curled (Tip below PIP).
        """
        curled_fingers = 0
        if hand_landmarks.landmark[8].y > hand_landmarks.landmark[6].y: curled_fingers += 1
        if hand_landmarks.landmark[12].y > hand_landmarks.landmark[10].y: curled_fingers += 1
        if hand_landmarks.landmark[16].y > hand_landmarks.landmark[14].y: curled_fingers += 1
        if hand_landmarks.landmark[20].y > hand_landmarks.landmark[18].y: curled_fingers += 1
        
        return curled_fingers >= 4

    def start_listening(self):
        print("Starting recording...")
        voice.speak("Listening")
        time.sleep(0.5) # Wait for TTS
        
        self.is_listening = True
        self.stop_event = threading.Event()
        
        def listen_worker():
            text = voice.record_until_stopped(self.stop_event)
            if text:
                print(f"Heard: {text}")
                self.process_command(text)
            else:
                print("No speech detected.")
                self.is_listening = False

        self.listen_thread = threading.Thread(target=listen_worker, daemon=True)
        self.listen_thread.start()

    def stop_listening(self):
        print("Stopping recording...")
        if self.stop_event:
            self.stop_event.set()
        self.is_listening = False
        # The thread will finish and call process_command

    def process_command(self, text):
        if not text:
            return

        print(f"Processing command: {text}")
        voice.speak("Processing")
        
        # Fast path
        from tools.local_actions import handle_local_action
        system_note = handle_local_action(text)
        
        user_content = [{"type": "text", "text": text}]
        if system_note:
            print("Done (Fast Path)")
            voice.speak("Done") # Commentary for fast path
            user_content.append({"type": "text", "text": f"\n\n({system_note})"})
        
        async def run_agent():
            messages = [{"role": "user", "content": user_content}]
            
            def status_cb(block):
                if block.type == "text":
                    print(f"Agent: {block.text}")
                    voice.speak(block.text)
            
            def tool_cb(output, id):
                print(f"Tool output: {id}")
                # Commentary for tools (optional, but requested)
                # voice.speak("Working") 

            try:
                await agent_loop(
                    model=MODEL,
                    provider=PROVIDER,
                    system_prompt_suffix=SYSTEM_PROMPT_SUFFIX,
                    messages=messages,
                    output_callback=status_cb,
                    tool_output_callback=tool_cb,
                    api_response_callback=lambda *args: None,
                    api_key=API_KEY,
                    only_n_most_recent_images=3
                )
            except Exception as e:
                print(f"Agent error: {e}")
                voice.speak("Sorry, something went wrong.")

        asyncio.run(run_agent())

    def start(self):
        print("Starting Gesture Control... (Press Ctrl+C to stop)")
        print("Gestures: Open Palm = Start Listening | Closed Fist = Stop Listening")
        
        cap = cv2.VideoCapture(0)
        
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("Ignoring empty camera frame.")
                continue

            image = cv2.flip(image, 1)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.hands.process(image_rgb)
            
            current_time = time.time()
            
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    
                    # State Machine Logic
                    if not self.is_listening:
                        # Waiting for Start Gesture (Open Palm)
                        if self.is_open_palm(hand_landmarks):
                            if current_time - self.last_activation_time > self.cooldown:
                                print("Gesture: Open Palm -> Start Listening")
                                self.start_listening()
                                self.last_activation_time = current_time
                    else:
                        # Listening... Waiting for Stop Gesture (Closed Fist)
                        if self.is_closed_fist(hand_landmarks):
                            if current_time - self.last_activation_time > self.cooldown:
                                print("Gesture: Closed Fist -> Stop Listening")
                                self.stop_listening()
                                self.last_activation_time = current_time
            
            if cv2.waitKey(5) & 0xFF == 27:
                break
                
        cap.release()
        if self.stop_event:
            self.stop_event.set()

if __name__ == "__main__":
    controller = GestureController()
    controller.start()
